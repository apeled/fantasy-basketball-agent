import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from typing import List, Dict, Optional
from datetime import datetime

class ESPNScheduleScraper:
    """
    Scraper for ESPN NBA team schedules
    """
    def __init__(self):
        self.base_url = "https://www.espn.com/nba/team/schedule/_/name"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        # All 30 NBA teams with their ESPN abbreviations
        self.nba_teams = {
            'ATL': 'Atlanta Hawks',
            'BOS': 'Boston Celtics',
            'BKN': 'Brooklyn Nets',
            'CHA': 'Charlotte Hornets',
            'CHI': 'Chicago Bulls',
            'CLE': 'Cleveland Cavaliers',
            'DAL': 'Dallas Mavericks',
            'DEN': 'Denver Nuggets',
            'DET': 'Detroit Pistons',
            'GSW': 'Golden State Warriors',
            'HOU': 'Houston Rockets',
            'IND': 'Indiana Pacers',
            'LAC': 'LA Clippers',
            'LAL': 'LA Lakers',
            'MEM': 'Memphis Grizzlies',
            'MIA': 'Miami Heat',
            'MIL': 'Milwaukee Bucks',
            'MIN': 'Minnesota Timberwolves',
            'NO': 'New Orleans Pelicans',
            'NYK': 'New York Knicks',
            'OKC': 'Oklahoma City Thunder',
            'ORL': 'Orlando Magic',
            'PHI': 'Philadelphia 76ers',
            'PHX': 'Phoenix Suns',
            'POR': 'Portland Trail Blazers',
            'SAC': 'Sacramento Kings',
            'SAS': 'San Antonio Spurs',
            'TOR': 'Toronto Raptors',
            'UTAH': 'Utah Jazz',
            'WAS': 'Washington Wizards'
        }
    
    def inspect_schedule_page(self, team_abbr: str = 'atl') -> None:
        """
        Inspect a team's schedule page to understand structure
        """
        url = f"{self.base_url}/{team_abbr.lower()}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            print("=" * 60)
            print(f"ESPN SCHEDULE PAGE STRUCTURE - {team_abbr.upper()}")
            print("=" * 60)
            
            # Find tables
            tables = soup.find_all('table', class_='Table')
            print(f"\nFound {len(tables)} table(s)")
            
            for table_idx, table in enumerate(tables):
                print(f"\n--- TABLE {table_idx + 1} ---")
                
                # Check for thead section
                thead = table.find('thead')
                if thead:
                    print("\nTHEAD found:")
                    headers = thead.find_all('th')
                    print(f"  Column Headers ({len(headers)}):")
                    for i, header in enumerate(headers):
                        print(f"    {i}: '{header.get_text(strip=True)}'")
                else:
                    print("\nNo THEAD found")
                
                # Check for all th tags
                all_th = table.find_all('th')
                print(f"\nAll TH tags ({len(all_th)}):")
                for i, th in enumerate(all_th):
                    print(f"  {i}: '{th.get_text(strip=True)}'")
                
                # Check tbody
                tbody = table.find('tbody')
                if tbody:
                    rows = tbody.find_all('tr')
                    print(f"\nTBODY found with {len(rows)} rows")
                else:
                    print("\nNo TBODY found")
                    rows = table.find_all('tr', class_='Table__TR')
                    print(f"Found {len(rows)} TR rows with Table__TR class")
                
                # Look at first few rows in detail
                all_rows = table.find_all('tr')
                print(f"\nTotal TR tags: {len(all_rows)}")
                print("\nFirst 5 rows:")
                for i, row in enumerate(all_rows[:5]):
                    cells = row.find_all(['td', 'th'])
                    print(f"\n  Row {i}:")
                    for j, cell in enumerate(cells):
                        text = cell.get_text(strip=True)
                        tag = cell.name
                        classes = ' '.join(cell.get('class', []))
                        print(f"    Cell {j} [{tag}] (class: {classes}): {text[:60]}")
            
            print("\n" + "=" * 60)
            
        except Exception as e:
            print(f"Error inspecting page: {e}")
            import traceback
            traceback.print_exc()
    
    def get_team_schedule(self, team_abbr: str, season: str = "2026") -> Optional[pd.DataFrame]:
        """
        Scrape schedule for a single team
        
        Args:
            team_abbr: Team abbreviation (e.g., 'ATL', 'BOS')
            season: Season identifier (e.g., "2026" for 2025-26 season)
        
        Returns:
            DataFrame with team's schedule including parsed dates and back-to-backs
        """
        url = f"{self.base_url}/{team_abbr.lower()}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find schedule table
            tables = soup.find_all('table', class_='Table')
            
            if not tables:
                print(f"No tables found for {team_abbr}")
                return None
            
            schedule_table = tables[0]
            tbody = schedule_table.find('tbody')
            
            if not tbody:
                print(f"No tbody found for {team_abbr}")
                return None
            
            # Find all rows
            all_rows = tbody.find_all('tr')
            
            # Find header row (has Table_Headers class)
            headers = []
            header_row_idx = None
            for idx, row in enumerate(all_rows):
                cells = row.find_all('td')
                if cells and 'Table_Headers' in cells[0].get('class', []):
                    headers = [cell.get_text(strip=True) for cell in cells]
                    header_row_idx = idx
                    break
            
            if not headers:
                print(f"Could not find headers for {team_abbr}")
                return None
            
            # Extract schedule data (skip section headers and header row)
            schedule_data = []
            for row in all_rows[header_row_idx + 1:]:
                cells = row.find_all('td')
                if not cells:
                    continue
                
                # Skip section divider rows (like "Regular Season", "Playoffs", etc.)
                if len(cells) == 1 or 'Table__Title' in cells[0].get('class', []):
                    continue
                
                row_data = []
                for cell in cells:
                    text = cell.get_text(strip=True)
                    row_data.append(text)
                
                if row_data and len(row_data) >= 3:  # At least DATE, OPPONENT, TIME
                    schedule_data.append(row_data)
            
            # Create DataFrame
            if schedule_data:
                # Use only the relevant columns (ignore 'tickets' column)
                df = pd.DataFrame(schedule_data, columns=headers[:len(schedule_data[0])])
                
                # Keep only relevant columns
                relevant_cols = ['DATE', 'OPPONENT', 'TIME', 'TV']
                df = df[[col for col in relevant_cols if col in df.columns]]
                
                # Add team column
                df.insert(0, 'Team', team_abbr.upper())
                
                # Parse and enhance the schedule
                df = self._enhance_schedule(df, team_abbr.upper())
                
                print(f"  ✓ Scraped {len(df)} games for {team_abbr.upper()}")
                return df
            else:
                print(f"  ✗ No schedule data found for {team_abbr.upper()}")
                return None
                
        except Exception as e:
            print(f"  ✗ Error scraping {team_abbr.upper()}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _enhance_schedule(self, df: pd.DataFrame, team_abbr: str) -> pd.DataFrame:
        """
        Enhance schedule with parsed dates, day of week, home/away, back-to-backs
        
        Args:
            df: Raw schedule DataFrame
            team_abbr: Team abbreviation
        
        Returns:
            Enhanced DataFrame with additional columns
        """
        # Parse dates from ESPN format "Wed, Oct 22"
        if 'DATE' in df.columns:
            try:
                # ESPN format: "Wed, Oct 22" or similar
                # We need to add the year (2025 for Oct-Dec, 2026 for Jan+)
                def parse_espn_date(date_str):
                    try:
                        # First try parsing with just the date part
                        # ESPN format is like "Wed, Oct 22" - day name, month, day
                        from datetime import datetime
                        
                        # Parse the date string
                        # Add current year first
                        temp_date = datetime.strptime(date_str + ', 2025', '%a, %b %d, %Y')
                        
                        # Adjust year based on month
                        # Oct, Nov, Dec = 2025; Jan-Sep = 2026
                        if temp_date.month < 10:
                            temp_date = temp_date.replace(year=2026)
                        
                        return pd.Timestamp(temp_date)
                    except Exception as e:
                        print(f"      Error parsing date '{date_str}': {e}")
                        return pd.NaT
                
                df['ParsedDate'] = df['DATE'].apply(parse_espn_date)
                
                # Debug: Show first few parsed dates
                print(f"    First 3 parsed dates: {df['ParsedDate'].head(3).tolist()}")
                
                # Extract day of week from parsed date
                df['DayOfWeek'] = df['ParsedDate'].dt.day_name()
                
                # Sort by date
                df = df.sort_values('ParsedDate').reset_index(drop=True)
                
                # Detect back-to-backs - mark BOTH games
                df['IsBackToBack'] = False
                df['BackToBackPosition'] = 'None'
                
                for i in range(1, len(df)):
                    if pd.notna(df.loc[i, 'ParsedDate']) and pd.notna(df.loc[i-1, 'ParsedDate']):
                        days_diff = (df.loc[i, 'ParsedDate'] - df.loc[i-1, 'ParsedDate']).days
                        if days_diff == 1:
                            # Mark BOTH games as back-to-backs
                            df.loc[i-1, 'IsBackToBack'] = True
                            df.loc[i-1, 'BackToBackPosition'] = 'First'
                            df.loc[i, 'IsBackToBack'] = True
                            df.loc[i, 'BackToBackPosition'] = 'Second'
                
                # Debug: Show back-to-backs
                b2b_count = df['IsBackToBack'].sum()
                print(f"    Detected {b2b_count} back-to-back games")
                
            except Exception as e:
                print(f"    Warning: Could not parse dates for {team_abbr}: {e}")
                import traceback
                traceback.print_exc()
        
        # Parse opponent and home/away
        if 'OPPONENT' in df.columns:
            # ESPN format: "vsToronto" (home) or "@Orlando" (away)
            df['HomeAway'] = df['OPPONENT'].apply(
                lambda x: 'Away' if str(x).startswith('@') else 'Home'
            )
            
            # Clean opponent name (remove 'vs' and '@' prefixes, handle spaces)
            def clean_opponent(opp):
                opp = str(opp)
                # Remove @ prefix
                if opp.startswith('@'):
                    opp = opp[1:]
                # Remove vs prefix (case insensitive)
                if opp.lower().startswith('vs'):
                    opp = opp[2:]
                return opp.strip()
            
            df['OpponentClean'] = df['OPPONENT'].apply(clean_opponent)
        
        return df
    
    def get_all_team_schedules(self, season: str = "2026") -> Optional[pd.DataFrame]:
        """
        Scrape schedules for all 30 NBA teams
        
        Args:
            season: Season identifier (e.g., "2026" for 2025-26 season)
        
        Returns:
            Combined DataFrame with all team schedules
        """
        all_schedules = []
        total_teams = len(self.nba_teams)
        
        print(f"\nScraping schedules for all {total_teams} NBA teams...")
        print("=" * 60)
        
        for idx, (abbr, name) in enumerate(self.nba_teams.items(), 1):
            print(f"[{idx}/{total_teams}] {name} ({abbr})...")
            
            df = self.get_team_schedule(abbr, season)
            if df is not None:
                all_schedules.append(df)
            
            # Be polite to ESPN's servers
            time.sleep(0.5)
        
        if all_schedules:
            combined_df = pd.concat(all_schedules, ignore_index=True)
            print(f"\n{'=' * 60}")
            print(f"✓ Successfully scraped {len(combined_df)} total games")
            print(f"  Teams: {combined_df['Team'].nunique()}")
            print(f"  Columns: {combined_df.columns.tolist()}")
            return combined_df
        else:
            print("\n✗ No schedule data collected")
            return None
    
    def save_schedules(self, df: pd.DataFrame, season: str = "2026") -> None:
        """
        Save schedules to CSV file
        
        Args:
            df: DataFrame with schedule data
            season: Season identifier
        """
        filename = f"team_schedules_{season}_season.csv"
        filepath = f"data/{filename}"
        df.to_csv(filepath, index=False)
        print(f"\n✓ Schedules saved to {filepath}")
        print(f"  Total records: {len(df)}")
    
    def analyze_weekly_games(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Analyze schedule to determine games per week for each team
        Useful for fantasy basketball streaming decisions
        
        Args:
            df: Schedule DataFrame with ParsedDate column
        
        Returns:
            DataFrame with weekly game counts per team
        """
        if 'ParsedDate' not in df.columns:
            print("Error: ParsedDate column not found. Cannot analyze weekly games.")
            return None
        
        # Filter to only future games (remove past games if any)
        df_future = df[df['ParsedDate'] >= pd.Timestamp.now()].copy()
        
        # Create week number (starting from Monday)
        df_future['WeekStart'] = df_future['ParsedDate'].dt.to_period('W-MON').dt.start_time
        df_future['WeekNum'] = (df_future['WeekStart'] - df_future['WeekStart'].min()).dt.days // 7 + 1
        
        # Group by team and week
        weekly_summary = df_future.groupby(['Team', 'WeekNum', 'WeekStart']).agg({
            'ParsedDate': 'count',
            'DayOfWeek': lambda x: ', '.join(x.unique())
        }).reset_index()
        
        weekly_summary.columns = ['Team', 'WeekNum', 'WeekStart', 'GamesInWeek', 'GameDays']
        
        return weekly_summary


def main():
    """
    Example usage
    """
    scraper = ESPNScheduleScraper()
    
    season = "2026"  # 2025-26 season
    
    print("=" * 60)
    print(f"NBA TEAM SCHEDULES - {season} SEASON (2025-26)")
    print("=" * 60)
    
    # Option 1: Inspect a single team's page
    print("\n[Option 1] Inspecting schedule structure (ATL)...")
    scraper.inspect_schedule_page('atl')
    
    # Option 2: Test with single team
    print("\n[Option 2] Testing with single team...")
    df_test = scraper.get_team_schedule('ATL', season)
    if df_test is not None:
        print("\nSample schedule:")
        print(df_test.head(10))
    
    # Option 3: Scrape all teams
    print("\n" + "=" * 60)
    user_input = input("\nScrape ALL 30 team schedules? This will take ~30 seconds (y/n): ")
    
    if user_input.lower() == 'y':
        df_all = scraper.get_all_team_schedules(season)
        
        if df_all is not None:
            print(f"\n{'=' * 60}")
            print("SCHEDULE SCRAPING COMPLETE!")
            print(f"{'=' * 60}")
            
            # Show sample data
            print("\nSample games:")
            print(df_all.head(20))
            
            # Save to file
            scraper.save_schedules(df_all, season)
            
            print("\n✓ Ready for schedule analysis!")
            print(f"  File: data/team_schedules_{season}_season.csv")
        else:
            print("Failed to scrape schedules")
    else:
        print("\nSkipping full scrape. Run again when ready!")


if __name__ == "__main__":
    main()