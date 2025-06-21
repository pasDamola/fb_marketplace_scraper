import argparse
import configparser
import json
import logging
import os
import random
import csv
import re
import time
from datetime import datetime, timedelta
from urllib.parse import quote, urlparse, urlunparse

import requests
from curl_cffi import requests
from bs4 import BeautifulSoup
from dateutil.parser import isoparse
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys

# --- Configuration & Logging Setup ---



def setup_logging():
    """Sets up a logger to output to both console and a file."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("scraper.log"),
            logging.StreamHandler()
        ]
    )

def load_config(filename="config.ini"):
    """Loads configuration from an INI file."""
    config = configparser.ConfigParser()
    config.read(filename)
    return config


cookies = {
    'sb': 'xJ5JZ1vDxbsv4w3eoPY_So3J',
    'ps_l': '1',
    'ps_n': '1',
    'datr': 'Irr6Z49lCkWq6Nzc7B3EVDyx',
    'ar_debug': '1',
    'locale': 'en_GB',
    'c_user': '100001769364027',
    'presence': 'C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1750500883790%2C%22v%22%3A1%7D',
    'fr': '1PQvyXZnUZjtwOr94.AWdUFjghhTInoDYQ_WkLO6V2NXRlNBjAdjp9WXbMzSYhVIjMrAk.BoVoYU..AAA.0.0.BoVoYU.AWd9OEesOSNHtWRhujKjyi7NTng',
    'xs': '30%3A2ptME4Avf_6FzA%3A2%3A1750084182%3A-1%3A-1%3A%3AAcV9FyybTI8ngWPFGe-0BT1SYmzJ8FpAGiyP5u7KdUA',
    'wd': '1473x406',
}

headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
    'cache-control': 'max-age=0',
    'dpr': '2',
    'priority': 'u=0, i',
    'sec-ch-prefers-color-scheme': 'light',
    'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
    'sec-ch-ua-full-version-list': '"Google Chrome";v="137.0.7151.120", "Chromium";v="137.0.7151.120", "Not/A)Brand";v="24.0.0.0"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-model': '""',
    'sec-ch-ua-platform': '"macOS"',
    'sec-ch-ua-platform-version': '"14.3.0"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
    'viewport-width': '1473',
    # 'cookie': 'sb=xJ5JZ1vDxbsv4w3eoPY_So3J; ps_l=1; ps_n=1; datr=Irr6Z49lCkWq6Nzc7B3EVDyx; ar_debug=1; locale=en_GB; c_user=100001769364027; presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1750500883790%2C%22v%22%3A1%7D; fr=1PQvyXZnUZjtwOr94.AWdUFjghhTInoDYQ_WkLO6V2NXRlNBjAdjp9WXbMzSYhVIjMrAk.BoVoYU..AAA.0.0.BoVoYU.AWd9OEesOSNHtWRhujKjyi7NTng; xs=30%3A2ptME4Avf_6FzA%3A2%3A1750084182%3A-1%3A-1%3A%3AAcV9FyybTI8ngWPFGe-0BT1SYmzJ8FpAGiyP5u7KdUA; wd=1473x406',
}

params = {
    'query': 'MacBook Pro M1',
    'sortBy': 'creation_time_descend',
    'deliveryMethod': 'local_only',
}

import requests

def scrape_marketplace(search_terms, location, config):
    url = f'https://www.facebook.com/marketplace/{location}/search/'
    response = requests.get(url, params=params, cookies=cookies, headers=headers)
    soup = BeautifulSoup(response.content, 'lxml')

    listings = soup.select('a[href*="/marketplace/item/"]')
    print(len(listings))
    for item in listings:
        href = item.get('href')
        text = item.get_text(strip=True)
        print(f"Link: {href} | Text: {text}")





def main():
    """Main execution block: parses args and runs the scraper."""
    setup_logging()
    
    parser = argparse.ArgumentParser(
        description="Facebook Marketplace Scraper for Newest Listings.",
        epilog="Example CLI usage:\n"
               "  python scraper.py all                          (uses all settings from config.ini)\n"
               "  python scraper.py miami \"iphone 13 pro\"        (searches for 'iphone 13 pro' in Miami)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "location", 
        help="The location slug (e.g., 'miami') or the special keyword 'all' to use settings from config.ini."
    )
    parser.add_argument(
        "search_term", 
        nargs='?', # Makes this argument optional
        help="The keyword(s) to search for. Required if location is not 'all'."
    )
    args = parser.parse_args()
    
    config = load_config()
    driver = None

    try:
        
        if args.location.lower() == 'all':
            logging.info("Running in 'all' mode, using settings from config.ini.")
            search_terms = [term.strip() for term in config['Scraper']['search_terms'].split(',')]
            location = config['Scraper']['location']
            if not search_terms or not location:
                logging.critical("Scraper[search_terms] and Scraper[location] must be set in config.ini for 'all' mode.")
                sys.exit(1)
            scrape_marketplace(driver, search_terms, location, config)

        else:
            if not args.search_term:
                parser.error("The 'search_term' argument is required when not using 'all' mode.")
            
            logging.info(f"Running in 'specific' mode for location '{args.location}' and term '{args.search_term}'.")
            # The search term is a single item, but the function expects a list.
            search_terms = [args.search_term]
            location = args.location
            scrape_marketplace(search_terms, location, config)

    except Exception as e:
        logging.critical(f"A critical error occurred in the main script: {e}", exc_info=True)
    finally:
        if driver:
            driver.quit()
            logging.info("WebDriver closed.")

if __name__ == "__main__":
    main()