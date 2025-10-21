import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from typing import List, Dict, Optional
import json

class ESPNMultiStatsScraper:
    """
    Enhanced scraper for multiple ESPN NBA player stat categories
    """
    def __init__(self):
        self.base_url = "https://www.espn.com/nba/stats/player"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        # Define available stat categories
        self.stat_categories = {
            'general': '',  # Default view
            'offense': '/_/view/offense',
            'defense': '/_/view/defense', 
            'shooting': '/_/view/shooting',
            'rebounds': '/_/view/rebounds',
            'scoring': '/_/view/scoring'
        }
    
    def test_stat_category(self, category: str) -> bool:
        """
        Test if a stat category URL exists and returns data
        
        Args:
            category: Category name from self.stat_categories
            
        Returns:
            True if category exists and has data
        """
        if category not in self.stat_categories:
            print(f"Unknown category: {category}")
            return False
        
        url = f"{self.base_url}{self.stat_categories[category]}"
        
        try:
            print(f"\nTesting category '{category}': {url}")
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            tables = soup.find_all('table', class_='Table')
            
            if len(tables) >= 2:
                # Get column names from stats table
                stats_table = tables[1]
                headers = [th.get_text(strip=True) for th in stats_table.find_all('th') if th.get_text(strip=True)]
                print(f"  ✓ Found {len(headers)} stat columns: {headers}")
                return True
            else:
                print(f"  ✗ No data found")
                return False
                
        except Exception as e:
            print(f"  ✗ Error: {e}")
            return False
    
    def discover_stat_categories(self) -> Dict[str, bool]:
        """
        Test all stat categories to see which ones are available
        
        Returns:
            Dictionary of category names and whether they're available
        """
        print("=" * 60)
        print("DISCOVERING AVAILABLE STAT CATEGORIES")
        print("=" * 60)
        
        results = {}
        for category in self.stat_categories.keys():
            results[category] = self.test_stat_category(category)
            time.sleep(0.5)  # Be polite
        
        print(f"\n{'=' * 60}")
        print("SUMMARY:")
        available = [cat for cat, status in results.items() if status]
        unavailable = [cat for cat, status in results.items() if not status]
        
        print(f"✓ Available ({len(available)}): {', '.join(available)}")
        if unavailable:
            print(f"✗ Unavailable ({len(unavailable)}): {', '.join(unavailable)}")
        print("=" * 60)
        
        return results
    
    def scrape_category(self, category: str, max_pages: int = 20) -> Optional[pd.DataFrame]:
        """
        Scrape all pages for a specific stat category
        
        Args:
            category: Category name from self.stat_categories
            max_pages: Maximum number of pages to scrape
            
        Returns:
            DataFrame with all players' stats for that category
        """
        if category not in self.stat_categories:
            print(f"Unknown category: {category}")
            return None
        
        print(f"\n{'=' * 60}")
        print(f"SCRAPING CATEGORY: {category.upper()}")
        print("=" * 60)
        
        all_data = []
        category_url = self.stat_categories[category]
        
        for page in range(1, max_pages + 1):
            print(f"\nPage {page}/{max_pages}...")
            
            # Construct URL
            if page == 1:
                url = f"{self.base_url}{category_url}"
            else:
                url = f"{self.base_url}{category_url}/_/page/{page}"
            
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                tables = soup.find_all('table', class_='Table')
                
                if len(tables) < 2:
                    print(f"  No more data at page {page}")
                    break
                
                # Parse player names (Table 1)
                name_table = tables[0]
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
                
                # Parse stats (Table 2)
                stats_table = tables[1]
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
                
                # Combine data
                if players_data and stats_data:
                    name_df = pd.DataFrame(players_data, columns=['RK', 'Name', 'Team', 'PlayerID'])
                    stats_df = pd.DataFrame(stats_data, columns=stats_headers)
                    page_df = pd.concat([name_df, stats_df], axis=1)
                    all_data.append(page_df)
                    print(f"  ✓ Scraped {len(page_df)} players")
                else:
                    break
                
                time.sleep(1)
                
            except Exception as e:
                print(f"  Error on page {page}: {e}")
                break
        
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            print(f"\n✓ Total: {len(combined_df)} players, {len(combined_df.columns)} columns")
            return combined_df
        else:
            return None
    
    def scrape_all_categories(self, categories: List[str], max_pages: int = 20, season: str = "2025") -> Dict[str, pd.DataFrame]:
        """
        Scrape multiple stat categories
        
        Args:
            categories: List of category names to scrape
            max_pages: Max pages per category
            season: Season identifier
            
        Returns:
            Dictionary mapping category names to DataFrames
        """
        print("=" * 60)
        print(f"SCRAPING MULTIPLE CATEGORIES - {season} SEASON")
        print("=" * 60)
        
        results = {}
        
        for category in categories:
            if category not in self.stat_categories:
                print(f"\n⚠ Skipping unknown category: {category}")
                continue
            
            df = self.scrape_category(category, max_pages)
            if df is not None:
                results[category] = df
                # Save individual category
                filename = f"player_stats_{season}_{category}.csv"
                df.to_csv(f"data/{filename}", index=False)
                print(f"  ✓ Saved: data/{filename}")
            
            time.sleep(2)  # Be extra polite between categories
        
        return results
    
    def merge_categories(self, dataframes: Dict[str, pd.DataFrame], season: str = "2025") -> pd.DataFrame:
        """
        Merge multiple stat category DataFrames into one master dataset
        
        Args:
            dataframes: Dict of category name -> DataFrame
            season: Season identifier
            
        Returns:
            Merged DataFrame
        """
        print(f"\n{'=' * 60}")
        print("MERGING STAT CATEGORIES")
        print("=" * 60)
        
        if not dataframes:
            print("No dataframes to merge")
            return None
        
        # Start with first dataframe as base
        base_category = list(dataframes.keys())[0]
        merged = dataframes[base_category].copy()
        print(f"\nBase: {base_category} ({len(merged.columns)} columns)")
        
        # Merge additional categories
        for category, df in list(dataframes.items())[1:]:
            # Merge on player identifiers
            print(f"Adding: {category} ({len(df.columns)} columns)")
            
            # Keep only new columns (avoid duplicates)
            merge_cols = ['Name', 'Team', 'PlayerID']
            new_cols = [col for col in df.columns if col not in merged.columns or col in merge_cols]
            df_subset = df[new_cols]
            
            merged = merged.merge(df_subset, on=merge_cols, how='left', suffixes=('', f'_{category}'))
            print(f"  ✓ Merged (total columns now: {len(merged.columns)})")
        
        print(f"\n✓ Final merged dataset: {len(merged)} players, {len(merged.columns)} columns")
        
        # Save merged dataset
        filename = f"player_stats_{season}_merged.csv"
        merged.to_csv(f"data/{filename}", index=False)
        print(f"✓ Saved: data/{filename}")
        
        return merged


def main():
    scraper = ESPNMultiStatsScraper()
    season = "2025"
    
    print("=" * 60)
    print("ESPN MULTI-CATEGORY STATS SCRAPER")
    print("=" * 60)
    
    # Step 1: Discover available categories
    print("\n[Step 1] Discovering available stat categories...")
    available = scraper.discover_stat_categories()
    
    # Step 2: Choose what to scrape
    print("\n" + "=" * 60)
    print("SCRAPING OPTIONS:")
    print("=" * 60)
    print("1. Scrape single category")
    print("2. Scrape all available categories")
    print("3. Scrape custom selection")
    
    choice = input("\nChoose option (1-3): ")
    
    if choice == "1":
        category = input(f"Enter category ({', '.join(available.keys())}): ")
        df = scraper.scrape_category(category, max_pages=20)
        if df is not None:
            scraper.save_stats(df, season=season, category=category)
    
    elif choice == "2":
        valid_categories = [cat for cat, status in available.items() if status]
        print(f"\nScraping categories: {', '.join(valid_categories)}")
        results = scraper.scrape_all_categories(valid_categories, max_pages=20, season=season)
        
        if len(results) > 1:
            print("\nMerge all categories into one master file? (y/n): ", end='')
            if input().lower() == 'y':
                merged = scraper.merge_categories(results, season=season)
    
    elif choice == "3":
        print(f"\nAvailable: {', '.join([cat for cat, status in available.items() if status])}")
        cats = input("Enter categories separated by commas: ").split(',')
        cats = [c.strip() for c in cats]
        results = scraper.scrape_all_categories(cats, max_pages=20, season=season)
        
        if len(results) > 1:
            print("\nMerge selected categories? (y/n): ", end='')
            if input().lower() == 'y':
                merged = scraper.merge_categories(results, season=season)
    
    print("\n" + "=" * 60)
    print("✓ SCRAPING COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    main()