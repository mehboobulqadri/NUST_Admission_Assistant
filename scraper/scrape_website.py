# scraper/scrape_website.py
import cloudscraper
from bs4 import BeautifulSoup
import os
import yaml
import time
import re

class NUSTScraper:
    def __init__(self, output_dir="data/raw"):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one level to the main bot folder
        root_dir = os.path.dirname(script_dir)
        # Force the path to be root/data/raw
        self.output_dir = os.path.join(root_dir, "data", "raw")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # MAGIC FIX: Replace standard requests with cloudscraper
        # This bypasses Cloudflare and 403 Forbidden blocks
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )

    def clean_filename(self, name):
        """Removes illegal characters from file names"""
        return re.sub(r'[\\/*?:"<>|]', "", name).replace(" ", "_")
    
    def scrape_page(self, url, raw_name):
        name = self.clean_filename(raw_name)
        
        try:
            print(f"Fetching: {raw_name}...")
            # Use self.scraper instead of self.session
            response = self.scraper.get(url, timeout=30)
            
            # Check if it's STILL giving a 403
            if response.status_code == 403:
                print(f"❌ Failed: {name} - 403 Forbidden (Firewall still blocking)")
                return None
                
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove scripts, styles, nav, footer
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript']):
                tag.decompose()
            
            # Get main content
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            
            if not main_content:
                print(f"⚠️ Warning: Could not find main content for {name}")
                return None

            # 1. Save raw HTML
            raw_path = os.path.join(self.output_dir, f"{name}.html")
            with open(raw_path, 'w', encoding='utf-8') as f:
                f.write(str(main_content))
            
            # 2. Save extracted text
            text_path = os.path.join(self.output_dir, f"{name}.txt")
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(f"SOURCE_URL: {url}\n")
                f.write(f"SOURCE_TITLE: {raw_name}\n\n")
                f.write(main_content.get_text(separator='\n', strip=True))
            
            print(f"✅ Successfully Scraped: {name}\n")
            return True
            
        except Exception as e:
            print(f"❌ Failed: {name} - {e}\n")
            return None

    def scrape_all(self, sources_file="scraper/sources.yaml"):
        with open(sources_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        print(f"🚀 Starting scraper for {len(config['sources'])} sources...\n")

        for source in config['sources']:
            if source['type'] == 'web':
                self.scrape_page(source['url'], source['name'])
                time.sleep(3) # Increased sleep to 3 seconds to be extra safe

if __name__ == "__main__":
    bot = NUSTScraper(output_dir="data/raw")
    bot.scrape_all(sources_file="sources.yaml")
    print("🎉 Web scraping complete! Check your data/raw/ folder.")