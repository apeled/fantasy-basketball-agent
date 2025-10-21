import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from typing import List, Dict, Optional
import json

class ESPNStatsScraper:
    """
    Scraper for ESPN NBA player statistics
    """
    def __init__(self):
        self.base_url = "https://www.espn.com/nba/stats/player"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    
    def inspect_page_structure(self) -> None:
        """
        Inspect the page to understand its structure
        Useful for debugging and initial development
        """
        try:
            response = requests.get(self.base_url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            print("=" * 60)
            print("ESPN NBA STATS PAGE STRUCTURE")
            print("=" * 60)
            
            # Find all tables
            tables = soup.find_all('table', class_='Table')
            print(f"\nFound {len(tables)} table(s)")
            
            # Inspect each table
            for table_idx, table in enumerate(tables):
                print(f"\n--- TABLE {table_idx + 1} ---")
                headers = table.find_all('th')
                print(f"Column Headers ({len(headers)}):")
                for i, header in enumerate(headers):
                    print(f"  {i}: {header.get_text(strip=True)}")
                
                # Look at first data row
                rows = table.find_all('tr', class_='Table__TR')
                print(f"Found {len(rows)} rows")
                
                if rows:
                    print("\nFirst Row Structure:")
                    cells = rows[0].find_all('td')
                    for i, cell in enumerate(cells):
                        print(f"  Cell {i}: {cell.get_text(strip=True)[:50]}")
            
            print("\n" + "=" * 60)
            
        except requests.RequestException as e:
            print(f"Error fetching page: {e}")
    
    def get_player_stats(self, stat_type: str = "_/view/general") -> Optional[pd.DataFrame]:
        """
        Scrape player statistics from ESPN
        ESPN uses 2 tables: one for player names, one for stats
        
        Args:
            stat_type: Type of stats to fetch
                - "_/view/general" (default stats)
                - "_/view/offense" (offensive stats)
                - "_/view/defense" (defensive stats)
        
        Returns:
            DataFrame with player stats or None if error
        """
        url = f"{self.base_url}/{stat_type}" if stat_type != "_/view/general" else self.base_url
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find both tables
            tables = soup.find_all('table', class_='Table')
            
            if len(tables) < 2:
                print(f"Expected 2 tables but found {len(tables)}")
                return None
            
            # TABLE 1: Player names and info
            name_table = tables[0]
            name_headers = []
            for th in name_table.find_all('th'):
                name_headers.append(th.get_text(strip=True) or 'RK')
            
            players_data = []
            name_rows = name_table.find_all('tr', class_='Table__TR')
            
            for row in name_rows:
                cells = row.find_all('td')
                if not cells:
                    continue
                
                row_data = []
                for i, cell in enumerate(cells):
                    if i == 0:  # Rank column
                        row_data.append(cell.get_text(strip=True))
                    elif i == 1:  # Player name column
                        player_link = cell.find('a', class_='AnchorLink')
                        team_abbrev = cell.find('span', class_='athleteCell__teamAbbrev')
                        
                        player_name = player_link.get_text(strip=True) if player_link else ''
                        team = team_abbrev.get_text(strip=True) if team_abbrev else ''
                        
                        # Extract player ID
                        player_id = None
                        if player_link and player_link.get('href'):
                            href = player_link['href']
                            parts = href.split('/id/')
                            if len(parts) > 1:
                                player_id = parts[1].split('/')[0]
                        
                        row_data.extend([player_name, team, player_id])
                
                if row_data:
                    players_data.append(row_data)
            
            # TABLE 2: Stats
            stats_table = tables[1]
            stats_headers = []
            for th in stats_table.find_all('th'):
                header_text = th.get_text(strip=True)
                if header_text:  # Only add non-empty headers
                    stats_headers.append(header_text)
            
            stats_data = []
            stats_rows = stats_table.find_all('tr', class_='Table__TR')
            
            for row in stats_rows:
                cells = row.find_all('td')
                if not cells:
                    continue
                
                row_stats = [cell.get_text(strip=True) for cell in cells]
                if row_stats:
                    stats_data.append(row_stats)
            
            # Combine the data
            name_df = pd.DataFrame(players_data, columns=['RK', 'Name', 'Team', 'PlayerID'])
            stats_df = pd.DataFrame(stats_data, columns=stats_headers)
            
            # Merge by index (same row order)
            combined_df = pd.concat([name_df, stats_df], axis=1)
            
            print(f"Successfully scraped {len(combined_df)} players with {len(combined_df.columns)} columns")
            return combined_df
            
        except requests.RequestException as e:
            print(f"Error fetching data: {e}")
            return None
        except Exception as e:
            print(f"Error parsing data: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def save_stats(self, df: pd.DataFrame, season: str = "2025", filename: str = None) -> None:
        """
        Save stats to CSV file in data directory with season identifier
        
        Args:
            df: DataFrame to save
            season: Season identifier (e.g., "2025" for 2024-25 season)
            filename: Custom filename (optional)
        """
        if filename is None:
            filename = f"player_stats_{season}_season.csv"
        
        filepath = f"data/{filename}"
        df.to_csv(filepath, index=False)
        print(f"\n✓ Stats saved to {filepath}")
        print(f"  Total records: {len(df)}")
        print(f"  Columns: {len(df.columns)}")
    
    def clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and convert data types for the scraped DataFrame
        Converts numeric columns from strings to proper numeric types
        
        Args:
            df: Raw scraped DataFrame
            
        Returns:
            Cleaned DataFrame with proper data types
        """
        df_clean = df.copy()
        
        # Columns that should be integers
        int_columns = ['RK', 'GP', 'FGM', 'FGA', '3PM', '3PA', 'FTM', 'FTA', 'DD2', 'TD3']
        
        # Columns that should be floats
        float_columns = ['MIN', 'PTS', 'FG%', '3P%', 'FT%', 'REB', 'AST', 'STL', 'BLK', 'TO']
        
        # Print column info before conversion
        print("\nBefore conversion:")
        for col in int_columns + float_columns:
            if col in df_clean.columns:
                print(f"{col}: Sample values = {df_clean[col].head()} (dtype: {df_clean[col].dtype})")
        
        # Convert integers
        for col in int_columns:
            if col in df_clean.columns:
                try:
                    df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').astype('Int64')
                except Exception as e:
                    print(f"\nError converting {col}: {str(e)}")
                    print(f"Unique values in {col}: {df_clean[col].unique()}")
        
        # Convert floats
        for col in float_columns:
            if col in df_clean.columns:
                try:
                    df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
                except Exception as e:
                    print(f"\nError converting {col}: {str(e)}")
                    print(f"Unique values in {col}: {df_clean[col].unique()}")
        
        # Print column info after conversion
        print("\nAfter conversion:")
        for col in int_columns + float_columns:
            if col in df_clean.columns:
                print(f"{col}: Sample values = {df_clean[col].head()} (dtype: {df_clean[col].dtype})")
        
        return df_clean
    
    def get_all_players_paginated(self, max_pages: int = 20, season: str = "2025") -> Optional[pd.DataFrame]:
        """
        Get multiple pages of player stats
        ESPN typically shows 50 players per page, ~400 total players
        
        Args:
            max_pages: Maximum number of pages to scrape (default 20 should get all players)
            season: Season identifier for file naming (e.g., "2025" for 2024-25 season)
        
        Returns:
            Combined DataFrame of all pages
        """
        all_data = []
        
        for page in range(1, max_pages + 1):
            print(f"\nScraping page {page}/{max_pages}...")
            
            # Construct URL with page parameter
            url = f"{self.base_url}/_/page/{page}"
            
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                tables = soup.find_all('table', class_='Table')
                
                # Check if we got data (empty page means we've reached the end)
                if len(tables) < 2:
                    print(f"No more data found at page {page}")
                    break
                
                # Parse both tables (same logic as get_player_stats)
                name_table = tables[0]
                stats_table = tables[1]
                
                # Extract player names
                players_data = []
                name_rows = name_table.find_all('tr', class_='Table__TR')
                
                for row in name_rows:
                    cells = row.find_all('td')
                    if not cells:
                        continue
                    
                    row_data = []
                    for i, cell in enumerate(cells):
                        if i == 0:  # Rank
                            row_data.append(cell.get_text(strip=True))
                        elif i == 1:  # Player info
                            player_link = cell.find('a', class_='AnchorLink')
                            team_abbrev = cell.find('span', class_='athleteCell__teamAbbrev')
                            
                            player_name = player_link.get_text(strip=True) if player_link else ''
                            team = team_abbrev.get_text(strip=True) if team_abbrev else ''
                            
                            player_id = None
                            if player_link and player_link.get('href'):
                                href = player_link['href']
                                parts = href.split('/id/')
                                if len(parts) > 1:
                                    player_id = parts[1].split('/')[0]
                            
                            row_data.extend([player_name, team, player_id])
                    
                    if row_data:
                        players_data.append(row_data)
                
                # Extract stats
                stats_headers = [th.get_text(strip=True) for th in stats_table.find_all('th') if th.get_text(strip=True)]
                
                stats_data = []
                stats_rows = stats_table.find_all('tr', class_='Table__TR')
                
                for row in stats_rows:
                    cells = row.find_all('td')
                    if not cells:
                        continue
                    row_stats = [cell.get_text(strip=True) for cell in cells]
                    if row_stats:
                        stats_data.append(row_stats)
                
                # Combine data for this page
                if players_data and stats_data:
                    name_df = pd.DataFrame(players_data, columns=['RK', 'Name', 'Team', 'PlayerID'])
                    stats_df = pd.DataFrame(stats_data, columns=stats_headers)
                    page_df = pd.concat([name_df, stats_df], axis=1)
                    all_data.append(page_df)
                    print(f"  ✓ Scraped {len(page_df)} players from page {page}")
                else:
                    print(f"No valid data on page {page}, stopping")
                    break
                
                # Be polite to ESPN's servers
                time.sleep(1)
                
            except Exception as e:
                print(f"Error on page {page}: {e}")
                break
        
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            print(f"\n✓ Total players scraped: {len(combined_df)}")
            return combined_df
        else:
            return None


def main():
    """
    Example usage
    """
    scraper = ESPNStatsScraper()
    
    # Set season identifier
    # "2025" = 2024-25 season (last season before current starts)
    # "2026" = 2025-26 season (current season starting tomorrow)
    season = "2025"
    
    print("=" * 60)
    print(f"SCRAPING NBA STATS - {season} SEASON (2024-25)")
    print("=" * 60)
    
    # Option 1: Quick test - scrape first page only
    print("\n[Option 1] Testing with first page...")
    df_test = scraper.get_player_stats()
    if df_test is not None:
        print(f"\nFirst page preview:")
        print(df_test.head())
    
    # Option 2: Full scrape - all players
    print("\n" + "=" * 60)
    user_input = input("\nScrape ALL players? This will take ~1-2 minutes (y/n): ")
    
    if user_input.lower() == 'y':
        print("\n[Option 2] Scraping all players across all pages...")
        df_all = scraper.get_all_players_paginated(max_pages=20, season=season)
        
        if df_all is not None:
            # Clean the data types
            print("\nCleaning data types...")
            df_all = scraper.clean_dataframe(df_all)
            
            print(f"\n{'=' * 60}")
            print("SCRAPING COMPLETE!")
            print(f"{'=' * 60}")
            print(f"\nTotal players: {len(df_all)}")
            print(f"Columns: {df_all.columns.tolist()}")
            
            print("\nTop 10 scorers:")
            print(df_all.nlargest(10, 'PTS')[['Name', 'Team', 'GP', 'PTS', 'REB', 'AST']])
            
            # Save to file
            scraper.save_stats(df_all, season=season)
            
            print("\n✓ Ready for analysis!")
            print(f"  File: data/player_stats_{season}_season.csv")
        else:
            print("Failed to scrape all players")
    else:
        print("\nSkipping full scrape. Run again when ready!")


if __name__ == "__main__":
    main()