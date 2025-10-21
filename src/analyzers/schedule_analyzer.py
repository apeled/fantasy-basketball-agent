import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import os

class ScheduleAnalyzer:
    """
    Analyzes NBA team schedules for fantasy basketball streaming strategies
    """
    
    def __init__(self, schedule_filepath: str = "data/team_schedules_2026_season.csv"):
        """
        Initialize analyzer with schedule data
        
        Args:
            schedule_filepath: Path to the schedule CSV file
        """
        if not os.path.exists(schedule_filepath):
            raise FileNotFoundError(f"Schedule file not found: {schedule_filepath}")
        
        self.schedule_df = pd.read_csv(schedule_filepath)
        
        # Convert ParsedDate to datetime
        self.schedule_df['ParsedDate'] = pd.to_datetime(self.schedule_df['ParsedDate'])
        
        print(f"Loaded schedule: {len(self.schedule_df)} games, {self.schedule_df['Team'].nunique()} teams")
        print(f"Date range: {self.schedule_df['ParsedDate'].min()} to {self.schedule_df['ParsedDate'].max()}")
    
    def get_teams_playing_on(self, date: str) -> List[str]:
        """
        Get list of teams playing on a specific date
        
        Args:
            date: Date string in format 'YYYY-MM-DD' or datetime object
        
        Returns:
            List of team abbreviations playing on that date
        
        Example:
            >>> analyzer.get_teams_playing_on('2025-10-22')
            ['ATL', 'BOS', 'LAL', ...]
        """
        target_date = pd.to_datetime(date).date()
        
        games = self.schedule_df[self.schedule_df['ParsedDate'].dt.date == target_date]
        teams = games['Team'].unique().tolist()
        
        return sorted(teams)
    
    def get_games_in_date_range(self, team: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Get games for a specific team in a date range
        
        Args:
            team: Team abbreviation (e.g., 'ATL', 'BOS')
            start_date: Start date 'YYYY-MM-DD'
            end_date: End date 'YYYY-MM-DD'
        
        Returns:
            DataFrame with team's games in date range
        
        Example:
            >>> analyzer.get_games_in_date_range('ATL', '2025-10-22', '2025-10-28')
        """
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        mask = (
            (self.schedule_df['Team'] == team.upper()) &
            (self.schedule_df['ParsedDate'] >= start) &
            (self.schedule_df['ParsedDate'] <= end)
        )
        
        return self.schedule_df[mask].sort_values('ParsedDate')
    
    def get_game_count_in_range(self, team: str, start_date: str, end_date: str) -> int:
        """
        Get number of games for a team in a date range
        
        Args:
            team: Team abbreviation
            start_date: Start date 'YYYY-MM-DD'
            end_date: End date 'YYYY-MM-DD'
        
        Returns:
            Number of games
        """
        games = self.get_games_in_date_range(team, start_date, end_date)
        return len(games)
    
    def find_back_to_back_opportunities(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Find all back-to-back games in a date range
        
        Args:
            start_date: Start date 'YYYY-MM-DD'
            end_date: End date 'YYYY-MM-DD'
        
        Returns:
            DataFrame with back-to-back games info
        
        Example:
            >>> analyzer.find_back_to_back_opportunities('2025-10-22', '2025-10-28')
        """
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        mask = (
            (self.schedule_df['ParsedDate'] >= start) &
            (self.schedule_df['ParsedDate'] <= end) &
            (self.schedule_df['IsBackToBack'] == True)
        )
        
        b2b_games = self.schedule_df[mask].sort_values(['Team', 'ParsedDate'])
        
        return b2b_games[['Team', 'ParsedDate', 'DATE', 'DayOfWeek', 'OpponentClean', 
                          'HomeAway', 'BackToBackPosition']]
    
    def calculate_weekly_game_counts(self, week_start_date: str) -> pd.DataFrame:
        """
        Calculate number of games each team plays in a week (Mon-Sun)
        
        Args:
            week_start_date: Monday of the week 'YYYY-MM-DD'
        
        Returns:
            DataFrame with teams and their game counts for the week, sorted by count
        
        Example:
            >>> analyzer.calculate_weekly_game_counts('2025-10-27')  # Monday Oct 27
        """
        week_start = pd.to_datetime(week_start_date)
        
        # Ensure it's a Monday
        if week_start.dayofweek != 0:
            print(f"Warning: {week_start_date} is not a Monday. Adjusting to nearest Monday.")
            days_to_monday = week_start.dayofweek
            week_start = week_start - timedelta(days=days_to_monday)
        
        week_end = week_start + timedelta(days=6)  # Sunday
        
        # Get all games in this week
        mask = (
            (self.schedule_df['ParsedDate'] >= week_start) &
            (self.schedule_df['ParsedDate'] <= week_end)
        )
        
        week_games = self.schedule_df[mask]
        
        # Count games per team
        game_counts = week_games.groupby('Team').agg({
            'ParsedDate': 'count',
            'DayOfWeek': lambda x: ', '.join(x.unique())
        }).reset_index()
        
        game_counts.columns = ['Team', 'GamesInWeek', 'GameDays']
        game_counts = game_counts.sort_values('GamesInWeek', ascending=False)
        
        print(f"\nWeek of {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}")
        print(f"Total games: {len(week_games)}")
        
        return game_counts
    
    def get_optimal_streaming_days(self, start_date: str, end_date: str) -> Dict[str, List[str]]:
        """
        Get which teams play on each day in a date range
        Useful for planning streaming pickups/drops
        
        Args:
            start_date: Start date 'YYYY-MM-DD'
            end_date: End date 'YYYY-MM-DD'
        
        Returns:
            Dictionary mapping dates to list of teams playing
        
        Example:
            >>> analyzer.get_optimal_streaming_days('2025-10-22', '2025-10-28')
            {
                '2025-10-22': ['ATL', 'BOS', 'LAL', ...],
                '2025-10-23': ['MIA', 'DEN', ...],
                ...
            }
        """
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        mask = (
            (self.schedule_df['ParsedDate'] >= start) &
            (self.schedule_df['ParsedDate'] <= end)
        )
        
        games_in_range = self.schedule_df[mask]
        
        # Group by date
        daily_teams = {}
        for date in games_in_range['ParsedDate'].dt.date.unique():
            date_str = str(date)
            teams = games_in_range[games_in_range['ParsedDate'].dt.date == date]['Team'].tolist()
            daily_teams[date_str] = sorted(teams)
        
        return dict(sorted(daily_teams.items()))
    
    def get_teams_with_most_games(self, start_date: str, end_date: str, top_n: int = 10) -> pd.DataFrame:
        """
        Get teams with most games in a date range
        Perfect for identifying streaming candidates
        
        Args:
            start_date: Start date 'YYYY-MM-DD'
            end_date: End date 'YYYY-MM-DD'
            top_n: Number of top teams to return
        
        Returns:
            DataFrame with top teams by game count
        """
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        mask = (
            (self.schedule_df['ParsedDate'] >= start) &
            (self.schedule_df['ParsedDate'] <= end)
        )
        
        games = self.schedule_df[mask]
        
        team_counts = games.groupby('Team').agg({
            'ParsedDate': 'count',
            'HomeAway': lambda x: f"{(x=='Home').sum()}H/{(x=='Away').sum()}A"
        }).reset_index()
        
        team_counts.columns = ['Team', 'TotalGames', 'HomeAway']
        team_counts = team_counts.sort_values('TotalGames', ascending=False).head(top_n)
        
        return team_counts
    
    def get_all_weekly_breakdowns(self) -> pd.DataFrame:
        """
        Get game counts for all teams across all weeks of the season
        Creates a matrix showing games per team per week
        
        Returns:
            DataFrame with weeks as rows, teams as columns showing game counts
            
        Example output:
            Week    ATL  BOS  BKN  ...
            Week1    4    3    4   ...
            Week2    3    4    2   ...
        """
        # Get date range
        min_date = self.schedule_df['ParsedDate'].min()
        max_date = self.schedule_df['ParsedDate'].max()
        
        # Find first Monday
        first_monday = min_date - timedelta(days=min_date.dayofweek)
        
        # Create list of all weeks
        weeks_data = []
        current_monday = first_monday
        week_num = 1
        
        while current_monday <= max_date:
            week_end = current_monday + timedelta(days=6)
            
            # Get games for this week
            mask = (
                (self.schedule_df['ParsedDate'] >= current_monday) &
                (self.schedule_df['ParsedDate'] <= week_end)
            )
            week_games = self.schedule_df[mask]
            
            # Count games per team
            team_counts = week_games.groupby('Team').size().to_dict()
            
            # Add week info
            week_info = {
                'Week': f'Week{week_num}',
                'WeekStart': current_monday.strftime('%Y-%m-%d'),
                'WeekEnd': week_end.strftime('%Y-%m-%d')
            }
            week_info.update(team_counts)
            weeks_data.append(week_info)
            
            current_monday += timedelta(days=7)
            week_num += 1
        
        df = pd.DataFrame(weeks_data)
        
        # Fill NaN with 0 (teams with no games that week)
        team_columns = [col for col in df.columns if col not in ['Week', 'WeekStart', 'WeekEnd']]
        df[team_columns] = df[team_columns].fillna(0).astype(int)
        
        print(f"\nGenerated weekly breakdown: {len(df)} weeks, {len(team_columns)} teams")
        return df
    
    def get_season_schedule_summary(self) -> pd.DataFrame:
        """
        Get a transposed view: each row is a team, columns are weeks
        Easier to see a team's full season schedule at a glance
        
        Returns:
            DataFrame with teams as rows, weeks as columns
            
        Example output:
            Team    Week1  Week2  Week3  ...  Avg
            ATL       4      3      4    ...  3.2
            BOS       3      4      2    ...  3.1
        """
        weekly_df = self.get_all_weekly_breakdowns()
        
        # Get just the week and team columns
        team_columns = [col for col in weekly_df.columns if col not in ['Week', 'WeekStart', 'WeekEnd']]
        
        # Pivot to get teams as rows
        summary = weekly_df[['Week'] + team_columns].set_index('Week').T
        summary.index.name = 'Team'
        
        # Add statistics
        summary['TotalGames'] = summary.sum(axis=1)
        summary['AvgGamesPerWeek'] = summary[summary.columns[:-1]].mean(axis=1).round(2)
        summary['MaxGamesInWeek'] = summary[summary.columns[:-2]].max(axis=1)
        summary['MinGamesInWeek'] = summary[summary.columns[:-3]].min(axis=1)
        
        return summary.sort_values('AvgGamesPerWeek', ascending=False)
    
    def find_best_streaming_weeks(self, top_n: int = 10) -> pd.DataFrame:
        """
        Find weeks with the most games scheduled (more streaming opportunities)
        
        Args:
            top_n: Number of top weeks to return
            
        Returns:
            DataFrame with weeks ranked by total games
        """
        weekly_df = self.get_all_weekly_breakdowns()
        
        team_columns = [col for col in weekly_df.columns if col not in ['Week', 'WeekStart', 'WeekEnd']]
        weekly_df['TotalGames'] = weekly_df[team_columns].sum(axis=1)
        
        # Count how many teams have 4+ games
        weekly_df['Teams4Plus'] = (weekly_df[team_columns] >= 4).sum(axis=1)
        weekly_df['Teams3Games'] = (weekly_df[team_columns] == 3).sum(axis=1)
        weekly_df['Teams2Games'] = (weekly_df[team_columns] == 2).sum(axis=1)
        
        result = weekly_df[['Week', 'WeekStart', 'WeekEnd', 'TotalGames', 
                           'Teams4Plus', 'Teams3Games', 'Teams2Games']].sort_values('TotalGames', ascending=False).head(top_n)
        
        return result
    
    def get_team_schedule_trends(self, team: str) -> pd.DataFrame:
        """
        Get week-by-week schedule for a specific team with context
        
        Args:
            team: Team abbreviation
            
        Returns:
            DataFrame showing team's weekly game counts and schedule details
        """
        weekly_df = self.get_all_weekly_breakdowns()
        
        if team.upper() not in weekly_df.columns:
            raise ValueError(f"Team {team} not found in schedule data")
        
        team_schedule = weekly_df[['Week', 'WeekStart', 'WeekEnd', team.upper()]].copy()
        team_schedule.columns = ['Week', 'WeekStart', 'WeekEnd', 'GamesInWeek']
        
        # Add context - get actual game details for each week
        details = []
        for _, row in team_schedule.iterrows():
            games = self.get_games_in_date_range(team, row['WeekStart'], row['WeekEnd'])
            
            if len(games) > 0:
                game_days = ', '.join(games['DayOfWeek'].tolist())
                has_b2b = games['IsBackToBack'].any()
                home_count = (games['HomeAway'] == 'Home').sum()
                away_count = (games['HomeAway'] == 'Away').sum()
            else:
                game_days = 'No games'
                has_b2b = False
                home_count = 0
                away_count = 0
            
            details.append({
                'GameDays': game_days,
                'HasBackToBack': has_b2b,
                'Home': home_count,
                'Away': away_count
            })
        
        details_df = pd.DataFrame(details)
        result = pd.concat([team_schedule, details_df], axis=1)
        
        return result
    
    def save_weekly_breakdown(self, filepath: str = "data/weekly_game_counts.csv"):
        """
        Save the full weekly breakdown to CSV for easy reference
        
        Args:
            filepath: Where to save the file
        """
        print("\nGenerating weekly breakdown files...")
        weekly_df = self.get_all_weekly_breakdowns()
        weekly_df.to_csv(filepath, index=False)
        print(f"✓ Weekly breakdown saved to {filepath}")
        
        # Also save the transposed version (teams as rows)
        summary_df = self.get_season_schedule_summary()
        summary_path = filepath.replace('.csv', '_by_team.csv')
        summary_df.to_csv(summary_path)
        print(f"✓ Team summary saved to {summary_path}")
        
        return filepath, summary_path
        """
        Compare schedules for multiple teams in a specific week
        Useful for deciding between streaming options
        
        Args:
            teams: List of team abbreviations
            week_start_date: Monday of the week 'YYYY-MM-DD'
        
        Returns:
            DataFrame comparing team schedules
        """
        week_start = pd.to_datetime(week_start_date)
        if week_start.dayofweek != 0:
            days_to_monday = week_start.dayofweek
            week_start = week_start - timedelta(days=days_to_monday)
        
        week_end = week_start + timedelta(days=6)
        
        comparison = []
        for team in teams:
            games = self.get_games_in_date_range(team, 
                                                   week_start.strftime('%Y-%m-%d'),
                                                   week_end.strftime('%Y-%m-%d'))
            
            comparison.append({
                'Team': team,
                'GamesInWeek': len(games),
                'GameDays': ', '.join(games['DayOfWeek'].tolist()),
                'HasBackToBack': games['IsBackToBack'].any(),
                'HomeGames': (games['HomeAway'] == 'Home').sum(),
                'AwayGames': (games['HomeAway'] == 'Away').sum()
            })
        
        return pd.DataFrame(comparison).sort_values('GamesInWeek', ascending=False)


def main():
    """
    Example usage and testing
    """
    # Initialize analyzer
    analyzer = ScheduleAnalyzer()
    
    print("\n" + "=" * 60)
    print("SCHEDULE ANALYZER - EXAMPLE QUERIES")
    print("=" * 60)
    
    # Example 1: Teams playing on opening night
    print("\n[1] Teams playing on Wednesday, Oct 22, 2025:")
    teams = analyzer.get_teams_playing_on('2025-10-22')
    print(f"   {len(teams)} teams: {', '.join(teams)}")
    
    # Example 2: ATL's games in first week
    print("\n[2] Atlanta Hawks schedule for first week (Oct 22-28):")
    atl_games = analyzer.get_games_in_date_range('ATL', '2025-10-22', '2025-10-28')
    print(atl_games[['DATE', 'DayOfWeek', 'OpponentClean', 'HomeAway', 'IsBackToBack']])
    
    # Example 3: Weekly game counts for all teams (first 3 weeks)
    print("\n[3] Weekly breakdown for entire season (showing first 3 weeks):")
    weekly_breakdown = analyzer.get_all_weekly_breakdowns()
    print(weekly_breakdown.head(3))
    
    # Example 4: Season schedule by team (top 10)
    print("\n[4] Teams ranked by average games per week:")
    season_summary = analyzer.get_season_schedule_summary()
    print(season_summary[['TotalGames', 'AvgGamesPerWeek', 'MaxGamesInWeek', 'MinGamesInWeek']].head(10))
    
    # Example 5: Best weeks for streaming
    print("\n[5] Best weeks for streaming (most games scheduled):")
    best_weeks = analyzer.find_best_streaming_weeks(top_n=5)
    print(best_weeks)
    
    # Example 6: Team-specific trends
    print("\n[6] Atlanta Hawks week-by-week schedule (first 5 weeks):")
    atl_trends = analyzer.get_team_schedule_trends('ATL')
    print(atl_trends.head(5))
    
    # Example 7: Save weekly breakdown
    print("\n[7] Saving weekly breakdown to CSV...")
    analyzer.save_weekly_breakdown()
    
    print("\n" + "=" * 60)
    print("✓ Schedule Analyzer Ready!")
    print("✓ Files created:")
    print("  - data/weekly_game_counts.csv (weeks as rows)")
    print("  - data/weekly_game_counts_by_team.csv (teams as rows)")
    print("=" * 60)


if __name__ == "__main__":
    main()