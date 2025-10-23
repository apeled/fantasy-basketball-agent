import requests
import pandas as pd
import json
from typing import List, Dict, Optional
import os
from dotenv import load_dotenv

class ESPNFantasyClient:
    """
    ESPN Fantasy Basketball API Client
    Updated with correct base URL and authentication methods (April 2024+)
    """
    
    # CRITICAL: Use the new base URL (changed April 2024)
    BASE_URL = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba"
    
    def __init__(self, league_id: int, year: int = 2025, espn_s2: str = None, swid: str = None):
        """
        Initialize ESPN Fantasy Basketball client
        
        Args:
            league_id: Your ESPN Fantasy league ID
            year: Season year (2025 for 2024-25 season - use ending year)
            espn_s2: ESPN authentication cookie (for private leagues)
            swid: ESPN SWID cookie with curly braces (for private leagues)
        """
        self.league_id = league_id
        self.year = year
        
        # Build endpoint with /segments/0/ structure (required for v3 API)
        self.endpoint = f"{self.BASE_URL}/seasons/{year}/segments/0/leagues/{league_id}"
        
        # Load credentials
        load_dotenv()
        self.espn_s2 = espn_s2 or os.getenv('ESPN_S2')
        self.swid = swid or os.getenv('SWID')
        
        # Set up cookies
        self.cookies = None
        if self.espn_s2 and self.swid:
            self.cookies = {
                'espn_s2': self.espn_s2,
                'SWID': self.swid
            }
            print("✓ Authentication cookies loaded (private league access)")
        else:
            print("ℹ No authentication cookies provided (public league only)")
    
    def _make_request(self, params: Dict = None, headers: Dict = None) -> Dict:
        """
        Make authenticated API request with proper headers
        
        Args:
            params: Query parameters (e.g., {'view': 'mRoster'})
            headers: Additional headers (e.g., X-Fantasy-Filter)
        
        Returns:
            JSON response as dictionary
        """
        # Default headers - CRITICAL for getting JSON instead of HTML
        default_headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Merge with custom headers
        if headers:
            default_headers.update(headers)
        
        try:
            response = requests.get(
                self.endpoint,
                params=params,
                headers=default_headers,
                cookies=self.cookies,
                timeout=30
            )
            
            # Check if we got HTML instead of JSON
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' not in content_type:
                print(f"ERROR: Received HTML instead of JSON!")
                print(f"Status: {response.status_code}")
                print(f"Content-Type: {content_type}")
                print(f"URL: {response.url}")
                raise Exception(f"API returned HTML instead of JSON. Check base URL and view parameters.")
            
            # Handle HTTP errors
            if response.status_code == 401:
                raise Exception("Authentication failed. Check your espn_s2 and SWID cookies.")
            elif response.status_code == 404:
                raise Exception(f"League {self.league_id} not found for year {self.year}.")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}")
            print(f"Response text: {response.text[:500]}")
            raise Exception(f"Invalid JSON response. Received HTML or malformed data.")
        except Exception as e:
            raise Exception(f"Error making request: {e}")
    
    def get_league_info(self) -> Dict:
        """
        Get league settings and information
        
        Returns:
            Dictionary with league info including name, size, scoring type
        """
        params = {'view': 'mSettings'}
        data = self._make_request(params=params)
        
        settings = data.get('settings', {})
        scoring = settings.get('scoringSettings', {})
        
        league_info = {
            'name': settings.get('name'),
            'size': settings.get('size'),
            'scoring_type': 'H2H Category' if scoring.get('scoringType') == 'H2H_CATEGORY' else 'Points',
            'roster_slots': settings.get('rosterSettings', {}).get('lineupSlotCounts', {}),
            'acquisition_limit': settings.get('acquisitionSettings', {}).get('acquisitionLimit', -1),
        }
        
        # Get scoring categories for H2H Category leagues
        if league_info['scoring_type'] == 'H2H Category':
            scoring_items = scoring.get('scoringItems', [])
            categories = []
            for item in scoring_items:
                stat_id = item.get('statId')
                is_negative = item.get('isReverseItem', False)
                categories.append({
                    'stat_id': stat_id,
                    'is_negative': is_negative
                })
            league_info['scoring_categories'] = categories
        
        print(f"\nLeague: {league_info['name']}")
        print(f"Size: {league_info['size']} teams")
        print(f"Type: {league_info['scoring_type']}")
        
        return league_info
    
    def get_teams(self) -> List[Dict]:
        """
        Get all teams in the league
        
        Returns:
            List of team dictionaries
        """
        params = {'view': 'mTeam'}
        data = self._make_request(params=params)
        
        teams = []
        for team in data.get('teams', []):
            teams.append({
                'id': team.get('id'),
                'name': f"{team.get('location', '')} {team.get('nickname', '')}".strip(),
                'owner': team.get('primaryOwner'),
                'wins': team.get('record', {}).get('overall', {}).get('wins', 0),
                'losses': team.get('record', {}).get('overall', {}).get('losses', 0)
            })
        
        print(f"\nFound {len(teams)} teams")
        return teams
    
    def get_my_team(self, team_id: int = None) -> Dict:
        """
        Get your team's roster
        
        Args:
            team_id: Your team ID (optional - will use first team if not provided)
        
        Returns:
            Dictionary with team info and roster
        """
        params = {'view': 'mRoster'}
        data = self._make_request(params=params)
        
        teams = data.get('teams', [])
        
        if not teams:
            raise Exception("No teams found in league")
        
        # Use provided team_id or first team
        if team_id is None:
            team_id = teams[0]['id']
            print(f"ℹ Using team ID: {team_id}")
        
        # Find the specified team
        my_team = None
        for team in teams:
            if team['id'] == team_id:
                my_team = team
                break
        
        if not my_team:
            raise Exception(f"Team ID {team_id} not found")
        
        # Extract roster
        roster = []
        for entry in my_team.get('roster', {}).get('entries', []):
            player = entry.get('playerPoolEntry', {}).get('player', {})
            roster.append({
                'player_id': player.get('id'),
                'name': player.get('fullName'),
                'pro_team_id': player.get('proTeamId'),
                'position': player.get('defaultPositionId'),
                'injury_status': player.get('injuryStatus'),
                'lineup_slot': entry.get('lineupSlotId')
            })
        
        team_info = {
            'team_id': team_id,
            'team_name': f"{my_team.get('location', '')} {my_team.get('nickname', '')}".strip(),
            'owner': my_team.get('primaryOwner'),
            'roster': roster,
            'roster_size': len(roster)
        }
        
        print(f"\nTeam: {team_info['team_name']}")
        print(f"Roster size: {team_info['roster_size']}")
        
        return team_info
    
    def get_free_agents(self, size: int = 50, position: str = None) -> pd.DataFrame:
        """
        Get available free agents with X-Fantasy-Filter header
        
        Args:
            size: Number of players to return (max ~2000)
            position: Filter by position (PG, SG, SF, PF, C, G, F)
        
        Returns:
            DataFrame with available free agents
        """
        # Position mapping for basketball
        position_map = {
            'PG': 0, 'SG': 1, 'SF': 2, 'PF': 3, 'C': 4,
            'G': 5, 'F': 6, 'UTIL': 12
        }
        
        # Build filter - CRITICAL for basketball API
        filters = {
            "players": {
                "filterStatus": {
                    "value": ["FREEAGENT", "WAIVERS"]
                },
                "limit": size,
                "sortPercOwned": {
                    "sortPriority": 1,
                    "sortAsc": False
                }
            }
        }
        
        # Add position filter if specified
        if position and position.upper() in position_map:
            filters["players"]["filterSlotIds"] = {
                "value": [position_map[position.upper()]]
            }
        
        # X-Fantasy-Filter header is REQUIRED for basketball
        headers = {
            'x-fantasy-filter': json.dumps(filters)
        }
        
        params = {'view': 'kona_player_info'}
        
        data = self._make_request(params=params, headers=headers)
        
        # Parse player data
        players = []
        for player_entry in data.get('players', []):
            player = player_entry.get('player', {})
            
            players.append({
                'player_id': player.get('id'),
                'name': player.get('fullName'),
                'pro_team_id': player.get('proTeamId'),
                'position': player.get('defaultPositionId'),
                'percent_owned': player.get('ownership', {}).get('percentOwned', 0),
                'percent_started': player.get('ownership', {}).get('percentStarted', 0),
            })
        
        df = pd.DataFrame(players)
        print(f"\nFound {len(df)} available free agents")
        
        return df
    
    def get_current_matchup(self, team_id: int = None, week: int = None) -> Dict:
        """
        Get current or specific week matchup details
        
        Args:
            team_id: Your team ID (optional)
            week: Specific week/scoring period (optional - uses current if not provided)
        
        Returns:
            Dictionary with matchup information
        """
        params = {
            'view': ['mMatchup', 'mMatchupScore']
        }
        
        if week:
            params['scoringPeriodId'] = week
        
        data = self._make_request(params=params)
        
        current_period = data.get('scoringPeriodId', week)
        schedule = data.get('schedule', [])
        
        matchups = []
        for matchup in schedule:
            if week is None or matchup.get('matchupPeriodId') == current_period:
                home = matchup.get('home', {})
                away = matchup.get('away', {})
                
                matchups.append({
                    'period': matchup.get('matchupPeriodId'),
                    'home_team_id': home.get('teamId'),
                    'away_team_id': away.get('teamId'),
                    'home_score': home.get('totalPoints', 0),
                    'away_score': away.get('totalPoints', 0),
                })
        
        print(f"\nFound {len(matchups)} matchup(s) for week {current_period}")
        return {'period': current_period, 'matchups': matchups}
    
    def map_espn_team_to_abbr(self, espn_team_id: int) -> str:
        """
        Map ESPN's numeric team ID to standard abbreviation
        
        Args:
            espn_team_id: ESPN's team ID number
        
        Returns:
            Team abbreviation (e.g., 'ATL', 'BOS')
        """
        team_map = {
            1: 'ATL', 2: 'BOS', 3: 'NO', 4: 'CHI', 5: 'CLE',
            6: 'DAL', 7: 'DEN', 8: 'DET', 9: 'GSW', 10: 'HOU',
            11: 'IND', 12: 'LAC', 13: 'LAL', 14: 'MIA', 15: 'MIL',
            16: 'MIN', 17: 'BKN', 18: 'NYK', 19: 'ORL', 20: 'PHI',
            21: 'PHX', 22: 'POR', 23: 'SAC', 24: 'SAS', 25: 'OKC',
            26: 'TOR', 27: 'UTAH', 28: 'WAS', 29: 'CHA', 30: 'MEM'
        }
        return team_map.get(espn_team_id, 'UNK')


def main():
    """
    Example usage and testing
    """
    # Load from environment or use hardcoded values
    load_dotenv()
    league_id = os.getenv('LEAGUE_ID')
    team_id = os.getenv('TEAM_ID')
    espn_s2 = os.getenv('ESPN_S2')
    swid = os.getenv('SWID')
    
    # Fallback to hardcoded for testing
    if not league_id:
        print("\n⚠ .env file not loading properly, using hardcoded values for testing")
        league_id = 265333986
        team_id = 1
        espn_s2 = "AEADlMWQdX0mnz5rlcGU5%2F4s3eNu5iRd%2B%2Fichh0HhsE1nNpi%2FnU8ox1WXRNF3e9oShSg1DA0P%2F7yOeVompDwTu84jwYFC%2ByBGGPA%2Bcig6fLThfBKNejD2uaKmO4Tsyn1NOAQf%2B1FABVODNuNV33Nv9GNLDu%2Bp8Rq2iJVnFdO56eKPopxnfg1Er1eNj9c2odg4uVy%2BzMrFMs27AGmsXZhHF%2BA0I2XF57VYyaRwukb0KrTJe%2FDbTk2GYsNVbMMoVjaKXjpYBC8UjOp0hTiE911REuX"
        swid = "{6508CFF5-D7D1-45A6-88CF-F5D7D1F5A67C}"
    
    print("=" * 60)
    print("ESPN FANTASY BASKETBALL API CLIENT (FIXED)")
    print("=" * 60)
    
    try:
        # Initialize client with UPDATED base URL
        client = ESPNFantasyClient(
            league_id=int(league_id),
            year=2026,  # 2024-25 season
            espn_s2=espn_s2,
            swid=swid
        )
        
        print("\n" + "=" * 60)
        print("TESTING API CONNECTION")
        print("=" * 60)
        
        # Test 1: Get league info
        print("\n[1] Getting league information...")
        league_info = client.get_league_info()
        
        # Test 2: Get all teams
        print("\n[2] Getting all teams...")
        teams = client.get_teams()
        for team in teams[:3]:  # Show first 3
            print(f"  {team['name']}: {team['wins']}-{team['losses']}")
        
        # Test 3: Get your roster
        print("\n[3] Getting your roster...")
        if team_id:
            my_team = client.get_my_team(team_id=int(team_id))
        else:
            my_team = client.get_my_team()
        
        print(f"\nYour roster ({len(my_team['roster'])} players):")
        for player in my_team['roster'][:5]:  # Show first 5
            print(f"  - {player['name']} ({client.map_espn_team_to_abbr(player['pro_team_id'])})")
        
        # Test 4: Get free agents
        print("\n[4] Getting top 10 free agents...")
        free_agents = client.get_free_agents(size=10)
        print(f"\nTop available players:")
        print(free_agents[['name', 'percent_owned']].to_string(index=False))
        
        # Test 5: Current matchup
        print("\n[5] Getting current matchup...")
        matchup = client.get_current_matchup()
        
        print("\n" + "=" * 60)
        print("✓ ESPN FANTASY API CLIENT WORKING!")
        print("=" * 60)
        print("\nAll tests passed. API is returning JSON correctly.")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nTroubleshooting:")
        print("- Verify your League ID is correct")
        print("- Ensure cookies are fresh (re-fetch from browser)")
        print("- Check that league exists for year 2025")
        print("- Confirm you have access to the league")


if __name__ == "__main__":
    main()