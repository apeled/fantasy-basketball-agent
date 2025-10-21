import requests
import pandas as pd
from typing import List, Dict, Optional
import os
from dotenv import load_dotenv

class ESPNFantasyClient:
    """
    Client for ESPN Fantasy Basketball API
    Handles authentication and data retrieval
    """
    
    def __init__(self, league_id: int, year: int = 2025, espn_s2: str = None, swid: str = None):
        """
        Initialize ESPN Fantasy client
        
        Args:
            league_id: Your ESPN Fantasy league ID (from URL)
            year: Season year (2025 for 2024-25 season, 2026 for 2025-26)
            espn_s2: ESPN authentication cookie (for private leagues)
            swid: ESPN SWID cookie (for private leagues)
        """
        self.league_id = league_id
        self.year = year
        self.base_url = f"https://fantasy.espn.com/apis/v3/games/fba/seasons/{year}/segments/0/leagues/{league_id}"
        
        # Load from .env file if not provided
        load_dotenv()
        self.espn_s2 = espn_s2 or os.getenv('ESPN_S2')
        self.swid = swid or os.getenv('SWID')
        
        # Set up cookies for private league access
        self.cookies = None
        if self.espn_s2 and self.swid:
            self.cookies = {
                'espn_s2': self.espn_s2,
                'SWID': self.swid
            }
            print("✓ Authentication cookies loaded (private league access)")
        else:
            print("ℹ No authentication cookies provided (public league only)")
    
    def _make_request(self, params: Dict = None) -> Dict:
        """
        Make authenticated request to ESPN API
        
        Args:
            params: Query parameters
        
        Returns:
            JSON response as dictionary
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        
        try:
            response = requests.get(
                self.base_url,
                params=params,
                cookies=self.cookies,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            # Debug: Print response details
            if response.status_code != 200:
                print(f"Debug: Status code: {response.status_code}")
                print(f"Debug: Response text: {response.text[:500]}")
            
            return response.json()
        except requests.exceptions.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}")
            print(f"Response status: {response.status_code}")
            print(f"Response text: {response.text[:500]}")
            raise Exception(f"Invalid JSON response from API. Status: {response.status_code}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise Exception("Authentication failed. Check your espn_s2 and SWID cookies.")
            else:
                raise Exception(f"API request failed: {e}")
        except Exception as e:
            raise Exception(f"Error making request: {e}")
    
    def get_league_info(self) -> Dict:
        """
        Get basic league information and settings
        
        Returns:
            Dictionary with league info
        """
        params = {'view': 'mSettings'}
        data = self._make_request(params)
        
        settings = data.get('settings', {})
        scoring = settings.get('scoringSettings', {})
        
        league_info = {
            'name': settings.get('name'),
            'size': settings.get('size'),
            'scoring_type': 'Category' if scoring.get('scoringType') == 'H2H_CATEGORY' else 'Points',
            'roster_slots': settings.get('rosterSettings', {}).get('lineupSlotCounts', {}),
            'acquisition_limit': settings.get('acquisitionSettings', {}).get('acquisitionLimit', -1),
            'trade_deadline': settings.get('tradeSettings', {}).get('deadlineDate'),
        }
        
        # Get scoring categories for H2H Category leagues
        if league_info['scoring_type'] == 'Category':
            scoring_items = scoring.get('scoringItems', [])
            categories = []
            for item in scoring_items:
                if item.get('isReverseItem', False):
                    # Negative categories like TO
                    categories.append(f"{item.get('statId')} (negative)")
                else:
                    categories.append(str(item.get('statId')))
            league_info['scoring_categories'] = categories
        
        print(f"\nLeague: {league_info['name']}")
        print(f"Size: {league_info['size']} teams")
        print(f"Type: {league_info['scoring_type']}")
        if league_info['acquisition_limit'] > 0:
            print(f"Weekly acquisition limit: {league_info['acquisition_limit']}")
        
        return league_info
    
    def get_my_team(self, team_id: int = None) -> Dict:
        """
        Get your team's roster
        
        Args:
            team_id: Your team ID (if None, gets first team - use for testing)
        
        Returns:
            Dictionary with roster information
        """
        params = {'view': 'mRoster'}
        data = self._make_request(params)
        
        teams = data.get('teams', [])
        
        if not teams:
            raise Exception("No teams found in league")
        
        # If no team_id provided, use first team (for testing)
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
                'team': player.get('proTeamId'),  # ESPN team ID
                'position': entry.get('lineupSlotId'),  # Position/slot
                'injury_status': player.get('injuryStatus')
            })
        
        team_info = {
            'team_id': team_id,
            'team_name': my_team.get('name'),
            'owner': my_team.get('primaryOwner'),
            'roster': roster,
            'roster_size': len(roster)
        }
        
        print(f"\nTeam: {team_info['team_name']}")
        print(f"Roster size: {team_info['roster_size']}")
        
        return team_info
    
    def get_free_agents(self, stat_category: str = None, limit: int = 100) -> pd.DataFrame:
        """
        Get available free agents
        
        Args:
            stat_category: Filter by stat (e.g., 'blocks', 'steals')
            limit: Number of players to return
        
        Returns:
            DataFrame with available free agents and their stats
        """
        params = {
            'view': 'kona_player_info',
            'scoringPeriodId': 0,  # Current period
        }
        
        # Add filters for free agents
        filters = {
            'players': {
                'filterStatus': {
                    'value': ['FREEAGENT', 'WAIVERS']
                },
                'limit': limit,
                'sortPercOwned': {
                    'sortPriority': 1,
                    'sortAsc': False
                }
            }
        }
        
        import json
        params['filters'] = json.dumps(filters)
        
        data = self._make_request(params)
        
        players = []
        for player_entry in data.get('players', []):
            player = player_entry.get('player', {})
            
            # Get stats
            stats = {}
            for stat_entry in player.get('stats', []):
                if stat_entry.get('scoringPeriodId') == 0:  # Season stats
                    stats = stat_entry.get('stats', {})
                    break
            
            players.append({
                'player_id': player.get('id'),
                'name': player.get('fullName'),
                'team': player.get('proTeamId'),
                'position': player.get('defaultPositionId'),
                'percent_owned': player.get('ownership', {}).get('percentOwned', 0),
                'percent_started': player.get('ownership', {}).get('percentStarted', 0),
                'stats': stats
            })
        
        df = pd.DataFrame(players)
        print(f"\nFound {len(df)} available free agents")
        
        return df
    
    def get_current_matchup(self, team_id: int = None) -> Dict:
        """
        Get your current weekly matchup details
        
        Args:
            team_id: Your team ID
        
        Returns:
            Dictionary with matchup information
        """
        params = {
            'view': ['mMatchup', 'mMatchupScore']
        }
        
        data = self._make_request(params)
        
        # Find current matchup period
        current_period = data.get('scoringPeriodId')
        
        # Get schedule/matchups
        schedule = data.get('schedule', [])
        
        current_matchup = None
        for matchup in schedule:
            if matchup.get('matchupPeriodId') == current_period:
                # Check if this matchup involves your team
                if team_id is None or matchup.get('home', {}).get('teamId') == team_id or matchup.get('away', {}).get('teamId') == team_id:
                    current_matchup = matchup
                    break
        
        if not current_matchup:
            print("No active matchup found")
            return None
        
        matchup_info = {
            'period': current_period,
            'home_team': current_matchup.get('home', {}).get('teamId'),
            'away_team': current_matchup.get('away', {}).get('teamId'),
            'home_score': current_matchup.get('home', {}).get('totalPoints', 0),
            'away_score': current_matchup.get('away', {}).get('totalPoints', 0),
        }
        
        print(f"\nCurrent Matchup (Period {matchup_info['period']}):")
        print(f"Team {matchup_info['home_team']} vs Team {matchup_info['away_team']}")
        
        return matchup_info
    
    def map_espn_team_to_abbr(self, espn_team_id: int) -> str:
        """
        Map ESPN's team ID to standard abbreviation
        
        Args:
            espn_team_id: ESPN's numeric team ID
        
        Returns:
            Team abbreviation (e.g., 'ATL', 'BOS')
        """
        # ESPN team ID mapping
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
    Example usage and setup
    """
    print("=" * 60)
    print("ESPN FANTASY BASKETBALL API CLIENT")
    print("=" * 60)
    
    # Setup instructions
    print("\nSETUP INSTRUCTIONS:")
    print("-" * 60)
    print("1. Find your League ID:")
    print("   - Go to your ESPN Fantasy Basketball league")
    print("   - Look at the URL: fantasy.espn.com/basketball/league?leagueId=XXXXXX")
    print("   - The XXXXXX is your League ID")
    print()
    print("2. For PRIVATE leagues, get authentication cookies:")
    print("   - Open ESPN Fantasy in your browser")
    print("   - Press F12 (Developer Tools)")
    print("   - Go to Application > Cookies > fantasy.espn.com")
    print("   - Copy the values for 'espn_s2' and 'SWID'")
    print()
    print("3. Create a .env file in your project root:")
    print("   ESPN_S2=your_espn_s2_value")
    print("   SWID=your_swid_value")
    print("   LEAGUE_ID=your_league_id")
    print("-" * 60)
    
    # Try to load from .env, otherwise use hardcoded values for testing
    load_dotenv()
    league_id = os.getenv('LEAGUE_ID')
    team_id = os.getenv('TEAM_ID')
    espn_s2 = os.getenv('ESPN_S2')
    swid = os.getenv('SWID')
    
    # Fallback to hardcoded for testing if .env doesn't work
    if not league_id:
        print("\n⚠ .env file not loading properly, using hardcoded values for testing")
        league_id = 265333986
        team_id = 1
        espn_s2 = "AEADlMWQdX0mnz5rlcGU5%2F4s3eNu5iRd%2B%2Fichh0HhsE1nNpi%2FnU8ox1WXRNF3e9oShSg1DA0P%2F7yOeVompDwTu84jwYFC%2ByBGGPA%2Bcig6fLThfBKNejD2uaKmO4Tsyn1NOAQf%2B1FABVODNuNV33Nv9GNLDu%2Bp8Rq2iJVnFdO56eKPopxnfg1Er1eNj9c2odg4uVy%2BzMrFMs27AGmsXZhHF%2BA0I2XF57VYyaRwukb0KrTJe%2FDbTk2GYsNVbMMoVjaKXjpYBC8UjOp0hTiE911REuX"
        swid = "{6508CFF5-D7D1-45A6-88CF-F5D7D1F5A67C}"
    
    # Initialize client
    try:
        client = ESPNFantasyClient(
            league_id=int(league_id),
            year=2025,
            espn_s2=espn_s2,
            swid=swid
        )
        
        print("\n" + "=" * 60)
        print("TESTING API CONNECTION")
        print("=" * 60)
        
        # Test 1: Get league info
        print("\n[1] Getting league information...")
        league_info = client.get_league_info()
        
        # Test 2: Get your team
        print("\n[2] Getting your roster...")
        team_info = client.get_my_team()
        
        # Test 3: Get free agents
        print("\n[3] Getting available free agents...")
        free_agents = client.get_free_agents(limit=20)
        print(f"\nTop 5 available players by ownership:")
        print(free_agents[['name', 'percent_owned']].head())
        
        # Test 4: Current matchup
        print("\n[4] Getting current matchup...")
        matchup = client.get_current_matchup(team_id=team_info['team_id'])
        
        print("\n" + "=" * 60)
        print("✓ ESPN Fantasy API Client Ready!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nTroubleshooting:")
        print("- Verify your League ID is correct")
        print("- For private leagues, check your espn_s2 and SWID cookies")
        print("- Make sure you have access to the league")


if __name__ == "__main__":
    main()