import pandas as pd
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Add parent directory to path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.espn_fantasy_client import ESPNFantasyClient
from analyzers.schedule_analyzer import ScheduleAnalyzer


class MatchupAnalyzer:
    """
    Analyzes current H2H category matchup with projections for rest of week
    """
    
    def __init__(self, league_id: int, team_id: int, year: int = 2025, 
                 espn_s2: str = None, swid: str = None):
        """
        Initialize matchup analyzer
        
        Args:
            league_id: ESPN Fantasy league ID
            team_id: Your team ID
            year: Season year
            espn_s2: ESPN authentication cookie
            swid: ESPN SWID cookie
        """
        # Initialize ESPN API client
        self.espn_client = ESPNFantasyClient(league_id, year, espn_s2, swid)
        self.team_id = team_id
        
        # Initialize schedule analyzer
        self.schedule_analyzer = ScheduleAnalyzer()
        
        # Load player stats
        stats_file = "data/player_stats_2025_season.csv"
        if not os.path.exists(stats_file):
            raise FileNotFoundError(f"Player stats file not found: {stats_file}")
        
        self.player_stats = pd.read_csv(stats_file)
        print(f"✓ Loaded {len(self.player_stats)} player stat records")
        
        # Get league info to determine scoring categories
        self.league_info = self.espn_client.get_league_info()
        raw_scoring_type = self.league_info.get('scoring_type')
        
        # Convert ESPN's format to our format
        if 'Category' in raw_scoring_type or 'CATEGORY' in raw_scoring_type:
            self.scoring_type = 'H2H Category'
        elif 'Points' in raw_scoring_type or 'POINTS' in raw_scoring_type:
            self.scoring_type = 'Points'
        else:
            self.scoring_type = raw_scoring_type
        
        # Check if scoring categories exist (definitive proof of H2H Category)
        if 'scoring_categories' in self.league_info and self.league_info['scoring_categories']:
            self.scoring_type = 'H2H Category'
            self.categories = self.league_info['scoring_categories']
            print(f"✓ Detected H2H Category league with {len(self.categories)} categories")
        else:
            print(f"ℹ️  League type: {self.scoring_type} (raw: {raw_scoring_type})")
    
    def _map_stat_id_to_column(self, stat_id: int) -> str:
        """
        Map ESPN's stat ID to our CSV column name
        
        Common stat IDs:
        0: PTS, 1: BLK, 2: STL, 3: AST, 6: REB, 
        11: TO, 13: FGM, 14: FGA, 15: FTM, 16: FTA,
        17: 3PM, 18: 3PA
        """
        stat_map = {
            0: 'PTS',
            1: 'BLK', 
            2: 'STL',
            3: 'AST',
            6: 'REB',
            11: 'TO',
            13: 'FGM',
            14: 'FGA',
            15: 'FTM',
            16: 'FTA',
            17: '3PM',
            18: '3PA',
            19: 'FG%',
            20: 'FT%'
        }
        return stat_map.get(stat_id, f'STAT_{stat_id}')
    
    def get_current_matchup_scores(self, week: int = None) -> Dict:
        """
        Get current scores for the matchup
        Works for both Points and H2H Category leagues
        
        Args:
            week: Specific week (optional - uses current if not provided)
            
        Returns:
            Dictionary with matchup details and scores
        """
        # Get matchup from ESPN API with detailed scoring view
        params = {
            'view': ['mMatchup', 'mMatchupScore']
        }
        
        if week:
            params['scoringPeriodId'] = week
        
        data = self.espn_client._make_request(params=params)
        
        current_period = data.get('scoringPeriodId', week)
        schedule = data.get('schedule', [])
        
        # DEBUG: Print raw response structure
        print(f"\n[DEBUG] Fetching matchup for period {current_period}")
        
        if not schedule:
            print("⚠️  No matchup data found")
            return None
        
        # Find your matchup for current period
        your_matchup = None
        for matchup in schedule:
            if matchup.get('matchupPeriodId') == current_period:
                home = matchup.get('home', {})
                away = matchup.get('away', {})
                
                if home.get('teamId') == self.team_id or away.get('teamId') == self.team_id:
                    your_matchup = matchup
                    break
        
        if not your_matchup:
            print(f"⚠️  Could not find matchup for team {self.team_id} in week {current_period}")
            return None
        
        # Parse matchup details
        home = your_matchup.get('home', {})
        away = your_matchup.get('away', {})
        
        is_home = home.get('teamId') == self.team_id
        
        # For H2H Category leagues, parse the category scores
        if self.scoring_type == 'H2H Category':
            # Get cumulative category stats for each team
            home_cumulative = home.get('cumulativeScore', {})
            away_cumulative = away.get('cumulativeScore', {})
            
            # Stats are in a nested structure: cumulativeScore.scoreByStat{statId: {score: value}}
            home_stats = home_cumulative.get('scoreByStat', {}) or home_cumulative.get('stats', {})
            away_stats = away_cumulative.get('scoreByStat', {}) or away_cumulative.get('stats', {})
            
            your_stats = home_stats if is_home else away_stats
            opp_stats = away_stats if is_home else home_stats
            
            # Also try totalPointsLive for current win count
            your_cats_won = home.get('totalPoints', 0) if is_home else away.get('totalPoints', 0)
            opp_cats_won = away.get('totalPoints', 0) if is_home else home.get('totalPoints', 0)
            
            # Calculate categories won/lost/tied from actual stat comparisons
            your_wins = 0
            opp_wins = 0
            ties = 0
            
            category_breakdown = []
            
            for cat in self.categories:
                stat_id = str(cat['stat_id'])
                is_negative = cat['is_negative']  # True for TO (lower is better)
                
                # Get the stat values - try multiple paths in the response
                your_stat_obj = your_stats.get(stat_id, {})
                opp_stat_obj = opp_stats.get(stat_id, {})
                
                your_value = your_stat_obj.get('score', 0) if isinstance(your_stat_obj, dict) else your_stat_obj
                opp_value = opp_stat_obj.get('score', 0) if isinstance(opp_stat_obj, dict) else opp_stat_obj
                
                # Convert to float
                your_value = float(your_value) if your_value else 0
                opp_value = float(opp_value) if opp_value else 0
                
                stat_name = self._map_stat_id_to_column(stat_id)
                
                # Determine winner (reverse logic for negative stats like TO)
                if is_negative:
                    if your_value < opp_value:
                        winner = 'YOU'
                        your_wins += 1
                    elif opp_value < your_value:
                        winner = 'OPP'
                        opp_wins += 1
                    else:
                        winner = 'TIE'
                        ties += 1
                else:
                    if your_value > opp_value:
                        winner = 'YOU'
                        your_wins += 1
                    elif opp_value > your_value:
                        winner = 'OPP'
                        opp_wins += 1
                    else:
                        winner = 'TIE'
                        ties += 1
                
                category_breakdown.append({
                    'category': stat_name,
                    'your_score': your_value,
                    'opp_score': opp_value,
                    'winner': winner,
                    'is_negative': is_negative
                })
            
            # Use calculated wins if totalPoints is 0
            if your_cats_won == 0 and opp_cats_won == 0:
                your_cats_won = your_wins
                opp_cats_won = opp_wins
            
            result = {
                'week': current_period,
                'scoring_type': 'H2H Category',
                'your_team_id': self.team_id,
                'opponent_team_id': away.get('teamId') if is_home else home.get('teamId'),
                'categories_won': your_cats_won,
                'categories_lost': opp_cats_won,
                'categories_tied': ties,
                'is_winning': your_cats_won > opp_cats_won,
                'category_breakdown': category_breakdown
            }
        else:
            # Points league (fallback)
            your_score = home.get('totalPoints', 0) if is_home else away.get('totalPoints', 0)
            opp_score = away.get('totalPoints', 0) if is_home else home.get('totalPoints', 0)
            
            result = {
                'week': current_period,
                'scoring_type': 'Points',
                'your_team_id': self.team_id,
                'opponent_team_id': away.get('teamId') if is_home else home.get('teamId'),
                'your_total_score': your_score,
                'opponent_total_score': opp_score,
                'is_winning': your_score > opp_score,
                'point_differential': your_score - opp_score
            }
        
        return result
    
    def get_player_projections(self, roster: List[Dict], start_date: str, end_date: str) -> pd.DataFrame:
        """
        Project stats for your roster for remaining games in date range
        
        Args:
            roster: List of player dictionaries from get_my_team()
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            DataFrame with projected stats per player
        """
        projections = []
        
        for player in roster:
            player_name = player['name']
            pro_team = self.espn_client.map_espn_team_to_abbr(player['pro_team_id'])
            
            # Find player in stats CSV - try exact team match first
            player_stats_row = self.player_stats[
                (self.player_stats['Name'].str.lower() == player_name.lower()) &
                (self.player_stats['Team'] == pro_team)
            ]
            
            # If not found, try just name match (player changed teams)
            if player_stats_row.empty:
                player_stats_row = self.player_stats[
                    self.player_stats['Name'].str.lower() == player_name.lower()
                ]
                
                if not player_stats_row.empty:
                    old_team = player_stats_row.iloc[0]['Team']
                    print(f"ℹ️  Found {player_name} - was on {old_team}, now on {pro_team}")
                else:
                    print(f"⚠️  Could not find stats for {player_name} (searched all teams)")
                    continue
            
            # Get per-game averages
            stats = player_stats_row.iloc[0]
            
            # Get remaining games for this player's team
            games = self.schedule_analyzer.get_games_in_date_range(
                pro_team, start_date, end_date
            )
            
            games_remaining = len(games)
            
            # Project stats = per-game avg * games remaining
            projection = {
                'Player': player_name,
                'Team': pro_team,
                'GamesRemaining': games_remaining,
                'PTS': stats.get('PTS', 0) * games_remaining,
                'REB': stats.get('REB', 0) * games_remaining,
                'AST': stats.get('AST', 0) * games_remaining,
                'STL': stats.get('STL', 0) * games_remaining,
                'BLK': stats.get('BLK', 0) * games_remaining,
                '3PM': stats.get('3PM', 0) * games_remaining,
                'FGM': stats.get('FGM', 0) * games_remaining,
                'FGA': stats.get('FGA', 0) * games_remaining,
                'FTM': stats.get('FTM', 0) * games_remaining,
                'FTA': stats.get('FTA', 0) * games_remaining,
                'TO': stats.get('TO', 0) * games_remaining,
                'FG%_Contribution': (stats.get('FGM', 0) * games_remaining, 
                                     stats.get('FGA', 0) * games_remaining),
                'FT%_Contribution': (stats.get('FTM', 0) * games_remaining,
                                     stats.get('FTA', 0) * games_remaining)
            }
            
            projections.append(projection)
        
        return pd.DataFrame(projections)
    
    def analyze_matchup(self, week: int = None) -> Dict:
        """
        Complete matchup analysis with current scores and projections
        
        Args:
            week: Specific week (optional)
            
        Returns:
            Dictionary with full matchup analysis
        """
        print("=" * 70)
        if self.scoring_type == 'Points':
            print("POINTS LEAGUE MATCHUP ANALYSIS")
        else:
            print("H2H CATEGORY MATCHUP ANALYSIS")
        print("=" * 70)
        
        # Get current matchup scores
        matchup = self.get_current_matchup_scores(week)
        if not matchup:
            return None
        
        print(f"\nWeek {matchup['week']}")
        print(f"Your Team ID: {matchup['your_team_id']}")
        print(f"Opponent Team ID: {matchup['opponent_team_id']}")
        
        if matchup['scoring_type'] == 'H2H Category':
            print(f"\nCurrent Score: YOU {matchup['categories_won']}-{matchup['categories_lost']}-{matchup['categories_tied']} OPP")
            print(f"Status: {'🟢 WINNING' if matchup['is_winning'] else '🔴 LOSING' if matchup['categories_won'] < matchup['categories_lost'] else '🟡 TIED'}")
            
            # Show category breakdown
            print(f"\n{'CATEGORY':<15} {'YOU':>12} {'OPP':>12} {'RESULT':>12}")
            print("-" * 55)
            for cat in matchup['category_breakdown']:
                result_symbol = "✓" if cat['winner'] == 'YOU' else "✗" if cat['winner'] == 'OPP' else "="
                print(f"{cat['category']:<15} {cat['your_score']:>12.4f} {cat['opp_score']:>12.4f} {result_symbol:>12}")
        else:
            print(f"\nCurrent Score: YOU {matchup['your_total_score']:.1f} - {matchup['opponent_total_score']:.1f} OPP")
            print(f"Differential: {matchup['point_differential']:+.1f}")
            print(f"Status: {'🟢 WINNING' if matchup['is_winning'] else '🔴 LOSING'}")
        
        # Get your roster
        my_team = self.espn_client.get_my_team(self.team_id)
        
        # Calculate date range for rest of week
        today = datetime.now()
        week_end = today + timedelta(days=(6 - today.weekday()))  # End on Sunday
        
        # Project remaining stats
        print(f"\n{'=' * 70}")
        print(f"PROJECTIONS FOR REST OF WEEK")
        print(f"Date Range: {today.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}")
        print(f"{'=' * 70}")
        
        projections_df = self.get_player_projections(
            my_team['roster'],
            today.strftime('%Y-%m-%d'),
            week_end.strftime('%Y-%m-%d')
        )
        
        if projections_df.empty:
            print("⚠️  No projections available")
            return matchup
        
        # Show detailed stats
        print("\nYOUR PROJECTED STATS (Rest of Week):")
        print(f"Total Games Remaining: {projections_df['GamesRemaining'].sum()}")
        print("\nCounting Stats:")
        print(f"  Points:    {projections_df['PTS'].sum():>6.1f}")
        print(f"  Rebounds:  {projections_df['REB'].sum():>6.1f}")
        print(f"  Assists:   {projections_df['AST'].sum():>6.1f}")
        print(f"  Steals:    {projections_df['STL'].sum():>6.1f}")
        print(f"  Blocks:    {projections_df['BLK'].sum():>6.1f}")
        print(f"  3-Pointers: {projections_df['3PM'].sum():>6.1f}")
        print(f"  Turnovers: {projections_df['TO'].sum():>6.1f}")
        
        # Calculate percentage stats
        total_fgm = projections_df['FGM'].sum()
        total_fga = projections_df['FGA'].sum()
        total_ftm = projections_df['FTM'].sum()
        total_fta = projections_df['FTA'].sum()
        
        fg_pct = (total_fgm / total_fga * 100) if total_fga > 0 else 0
        ft_pct = (total_ftm / total_fta * 100) if total_fta > 0 else 0
        
        print("\nPercentage Stats:")
        print(f"  FG%: {fg_pct:.1f}% ({total_fgm:.0f}/{total_fga:.0f})")
        print(f"  FT%: {ft_pct:.1f}% ({total_ftm:.0f}/{total_fta:.0f})")
        
        # For H2H Category leagues, show which categories you're projected to win/lose
        if matchup['scoring_type'] == 'H2H Category':
            print("\n" + "=" * 70)
            print("PROJECTED CATEGORY OUTCOMES")
            print("=" * 70)
            print("\nBased on current scores + rest of week projections:\n")
            
            proj_wins = 0
            proj_losses = 0
            proj_ties = 0
            
            for cat in matchup['category_breakdown']:
                cat_name = cat['category']
                current_yours = cat['your_score']
                current_opp = cat['opp_score']
                is_negative = cat['is_negative']
                
                # Map category name to projection column
                proj_col = cat_name
                if proj_col in projections_df.columns:
                    proj_value = projections_df[proj_col].sum()
                elif cat_name == 'FG%':
                    proj_value = fg_pct / 100
                    current_yours = current_yours  # Already a percentage
                    current_opp = current_opp
                elif cat_name == 'FT%':
                    proj_value = ft_pct / 100
                    current_yours = current_yours
                    current_opp = current_opp
                else:
                    continue
                
                # Project final scores (assuming opponent maintains pace)
                # This is simplified - ideally we'd project opponent too
                projected_yours = current_yours + proj_value
                
                # Determine projected outcome
                if is_negative:
                    if projected_yours < current_opp:
                        outcome = "✓ WINNING"
                        proj_wins += 1
                    else:
                        outcome = "✗ LOSING"
                        proj_losses += 1
                else:
                    if projected_yours > current_opp:
                        outcome = "✓ WINNING"
                        proj_wins += 1
                    else:
                        outcome = "✗ LOSING"
                        proj_losses += 1
                
                print(f"{cat_name:<15} Current: {current_yours:>8.2f} | Projected Final: {projected_yours:>8.2f} | {outcome}")
            
            print(f"\nProjected Final Record: {proj_wins}-{proj_losses}-0")
            print(f"Current Record: {matchup['categories_won']}-{matchup['categories_lost']}-{matchup['categories_tied']}")
        
        # Show top contributors
        print(f"\n{'=' * 70}")
        print("TOP PROJECTED PERFORMERS:")
        print("=" * 70)
        top_performers = projections_df.nlargest(5, 'PTS')[
            ['Player', 'Team', 'GamesRemaining', 'PTS', 'REB', 'AST', 'STL', 'BLK']
        ]
        print(top_performers.to_string(index=False))
        
        print("\n" + "=" * 70)
        
        # Add projections to result
        matchup['projections'] = {
            'total_games': int(projections_df['GamesRemaining'].sum()),
            'PTS': float(projections_df['PTS'].sum()),
            'REB': float(projections_df['REB'].sum()),
            'AST': float(projections_df['AST'].sum()),
            'STL': float(projections_df['STL'].sum()),
            'BLK': float(projections_df['BLK'].sum()),
            '3PM': float(projections_df['3PM'].sum()),
            'TO': float(projections_df['TO'].sum()),
            'FG%': float(fg_pct),
            'FT%': float(ft_pct),
            'top_performers': top_performers.to_dict('records')
        }
        
        return matchup
    
    def get_opponent_projections(self, opponent_team_id: int, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Get projections for opponent's roster
        
        Args:
            opponent_team_id: Opponent's team ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            DataFrame with opponent's projected stats
        """
        try:
            # Get opponent's roster
            opp_team = self.espn_client.get_my_team(opponent_team_id)
            
            # Project their stats using same method
            opp_projections = self.get_player_projections(
                opp_team['roster'],
                start_date,
                end_date
            )
            
            return opp_projections
            
        except Exception as e:
            print(f"⚠️  Could not get opponent projections: {e}")
            return pd.DataFrame()
    
    def compare_with_opponent(self, week: int = None) -> Dict:
        """
        Full matchup comparison including opponent projections
        
        Args:
            week: Specific week (optional)
            
        Returns:
            Dictionary with comparison data
        """
        print("=" * 70)
        print("FULL MATCHUP COMPARISON (YOU vs OPPONENT)")
        print("=" * 70)
        
        # Get matchup info
        matchup = self.get_current_matchup_scores(week)
        if not matchup:
            return None
        
        # Get date range
        today = datetime.now()
        week_end = today + timedelta(days=(6 - today.weekday()))
        
        # Get your projections
        my_team = self.espn_client.get_my_team(self.team_id)
        your_proj = self.get_player_projections(
            my_team['roster'],
            today.strftime('%Y-%m-%d'),
            week_end.strftime('%Y-%m-%d')
        )
        
        # Get opponent projections
        opp_proj = self.get_opponent_projections(
            matchup['opponent_team_id'],
            today.strftime('%Y-%m-%d'),
            week_end.strftime('%Y-%m-%d')
        )
        
        if your_proj.empty or opp_proj.empty:
            print("⚠️  Could not get complete projection data")
            return matchup
        
        # Calculate totals
        your_totals = {
            'games': your_proj['GamesRemaining'].sum(),
            'PTS': your_proj['PTS'].sum(),
            'REB': your_proj['REB'].sum(),
            'AST': your_proj['AST'].sum(),
            'STL': your_proj['STL'].sum(),
            'BLK': your_proj['BLK'].sum(),
            '3PM': your_proj['3PM'].sum(),
            'TO': your_proj['TO'].sum()
        }
        
        opp_totals = {
            'games': opp_proj['GamesRemaining'].sum(),
            'PTS': opp_proj['PTS'].sum(),
            'REB': opp_proj['REB'].sum(),
            'AST': opp_proj['AST'].sum(),
            'STL': opp_proj['STL'].sum(),
            'BLK': opp_proj['BLK'].sum(),
            '3PM': opp_proj['3PM'].sum(),
            'TO': opp_proj['TO'].sum()
        }
        
        # Calculate fantasy points if Points league
        if self.scoring_type == 'Points':
            your_proj_fpts = (
                your_proj['PTS'] * 1.0 +
                your_proj['REB'] * 1.2 +
                your_proj['AST'] * 1.5 +
                your_proj['STL'] * 3.0 +
                your_proj['BLK'] * 3.0 +
                your_proj['3PM'] * 0.5 +
                your_proj['TO'] * -1.0
            ).sum()
            
            opp_proj_fpts = (
                opp_proj['PTS'] * 1.0 +
                opp_proj['REB'] * 1.2 +
                opp_proj['AST'] * 1.5 +
                opp_proj['STL'] * 3.0 +
                opp_proj['BLK'] * 3.0 +
                opp_proj['3PM'] * 0.5 +
                opp_proj['TO'] * -1.0
            ).sum()
            
            your_final = matchup['your_total_score'] + your_proj_fpts
            opp_final = matchup['opponent_total_score'] + opp_proj_fpts
            
            print(f"\nWeek {matchup['week']} - POINTS LEAGUE")
            print(f"\n{'CURRENT SCORE':<25} {'YOU':>12} {'OPP':>12} {'DIFF':>12}")
            print("-" * 70)
            print(f"{'Fantasy Points':<25} {matchup['your_total_score']:>12.1f} {matchup['opponent_total_score']:>12.1f} {matchup['point_differential']:>+12.1f}")
            
            print(f"\n{'PROJECTED (Rest of Week)':<25} {'YOU':>12} {'OPP':>12} {'DIFF':>12}")
            print("-" * 70)
            print(f"{'Games Remaining':<25} {your_totals['games']:>12.0f} {opp_totals['games']:>12.0f} {your_totals['games']-opp_totals['games']:>+12.0f}")
            print(f"{'Fantasy Points':<25} {your_proj_fpts:>12.1f} {opp_proj_fpts:>12.1f} {your_proj_fpts-opp_proj_fpts:>+12.1f}")
            
            print(f"\n{'PROJECTED FINAL':<25} {'YOU':>12} {'OPP':>12} {'DIFF':>12}")
            print("-" * 70)
            print(f"{'Fantasy Points':<25} {your_final:>12.1f} {opp_final:>12.1f} {your_final-opp_final:>+12.1f}")
            
            win_probability = "🟢 LIKELY WIN" if your_final > opp_final else "🔴 LIKELY LOSS"
            print(f"\nProjected Outcome: {win_probability}")
            
            matchup['comparison'] = {
                'your_projected_fpts': your_proj_fpts,
                'opp_projected_fpts': opp_proj_fpts,
                'your_projected_final': your_final,
                'opp_projected_final': opp_final,
                'projected_differential': your_final - opp_final
            }
        
        # Show detailed stats comparison
        print(f"\n{'STAT COMPARISON':<15} {'YOU':>12} {'OPP':>12} {'ADVANTAGE':>15}")
        print("-" * 70)
        for stat in ['PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', 'TO']:
            diff = your_totals[stat] - opp_totals[stat]
            advantage = f"{'+' if diff > 0 else ''}{diff:.1f}"
            print(f"{stat:<15} {your_totals[stat]:>12.1f} {opp_totals[stat]:>12.1f} {advantage:>15}")
        
        print("\n" + "=" * 70)
        
        return matchup
        """
        Side-by-side comparison of you vs opponent in each category
        Includes current + projected final
        
        Args:
            week: Specific week (optional)
            
        Returns:
            DataFrame with category comparison
        """
        # This would require getting opponent's roster too
        # For now, just shows your projections
        # TODO: Add opponent analysis when ESPN API provides that data
        
        print("⚠️  Opponent projections require additional API calls")
        print("Currently showing only YOUR projections")
        
        matchup = self.analyze_matchup(week)
        return matchup


def main():
    """
    Example usage
    """
    load_dotenv()
    
    # Get credentials
    league_id = os.getenv('LEAGUE_ID') or 265333986
    team_id = os.getenv('TEAM_ID') or 1
    espn_s2 = os.getenv('ESPN_S2')
    swid = os.getenv('SWID')
    
    # Fallback if .env doesn't load
    if not espn_s2:
        print("⚠️  .env not loading, using hardcoded values")
        espn_s2 = "AEADlMWQdX0mnz5rlcGU5%2F4s3eNu5iRd%2B%2Fichh0HhsE1nNpi%2FnU8ox1WXRNF3e9oShSg1DA0P%2F7yOeVompDwTu84jwYFC%2ByBGGPA%2Bcig6fLThfBKNejD2uaKmO4Tsyn1NOAQf%2B1FABVODNuNV33Nv9GNLDu%2Bp8Rq2iJVnFdO56eKPopxnfg1Er1eNj9c2odg4uVy%2BzMrFMs27AGmsXZhHF%2BA0I2XF57VYyaRwukb0KrTJe%2FDbTk2GYsNVbMMoVjaKXjpYBC8UjOp0hTiE911REuX"
        swid = "{6508CFF5-D7D1-45A6-88CF-F5D7D1F5A67C}"
    
    try:
        # Initialize analyzer
        analyzer = MatchupAnalyzer(
            league_id=int(league_id),
            team_id=int(team_id),
            year=2026,  # 2025-26 season
            espn_s2=espn_s2,
            swid=swid
        )
        
        print("\n" + "=" * 70)
        print("MATCHUP ANALYZER - OPTIONS")
        print("=" * 70)
        print("\n1. Quick Analysis (your projections only)")
        print("2. Full Comparison (you vs opponent projections)")
        print("\nNote: Option 2 provides complete win/loss prediction")
        
        choice = input("\nSelect option (1 or 2): ").strip()
        
        if choice == "2":
            # Full comparison with opponent
            result = analyzer.compare_with_opponent()
        else:
            # Quick analysis (default)
            result = analyzer.analyze_matchup()
        
        if result:
            print("\n✓ Matchup analysis complete!")
            
            if result.get('comparison'):
                print("\n💡 INSIGHTS:")
                diff = result['comparison']['projected_differential']
                if diff > 50:
                    print("  - You're projected to win comfortably")
                    print("  - Consider holding your roster unless injuries occur")
                elif diff > 0:
                    print("  - Close matchup! Every game counts")
                    print("  - Look for streaming opportunities to secure the win")
                else:
                    print("  - You're projected to lose")
                    print("  - AGGRESSIVE STREAMING NEEDED to close the gap")
                    print(f"  - Need approximately {abs(diff):.0f} fantasy points")
            else:
                print("\nUse this data to identify streaming opportunities!")
        else:
            print("\n✗ Could not analyze matchup")
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()