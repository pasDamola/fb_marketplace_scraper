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

# --- Deduplication ---

def load_scraped_ids(filepath):
    """Loads previously scraped listing IDs from a file into a set."""
    try:
        with open(filepath, "r") as f:
            return set(line.strip() for line in f)
    except FileNotFoundError:
        return set()

def save_scraped_id(filepath, item_id):
    """Appends a new scraped ID to the deduplication file."""
    with open(filepath, "a") as f:
        f.write(f"{item_id}\n")


# --- Hide Subsequent Login Popup ---
def hide_login_popup(driver):
    """
    Finds the persistent "Log in to Facebook" popup and hides it using JavaScript.
    This is necessary because it has no close button and covers the listings.
    """
    try:
        # This JavaScript finds the form by its unique ID, then finds its parent
        # container (which is the actual visual popup) and sets its display to 'none'.
        js_script = """
        var loginPopup = document.querySelector('form#login_popup_cta_form');
        if (loginPopup && loginPopup.parentElement) {
            console.log(loginPopup.parentElement)
            loginPopup.parentElement.style.display = 'none';
            return true; // Indicate that the popup was found and hidden
        }
        return false; // Indicate popup was not found
        """
        popup_hidden = driver.execute_script(js_script)
        if popup_hidden:
            logging.info("Found and hid the persistent login popup overlay.")
            
    except Exception as e:
        logging.error(f"An error occurred while trying to hide the login popup: {e}")

# def close_overlays_and_popups(driver):
#     """
#     Intelligently tries to close overlays using user-like methods to avoid breaking the page state.
    
#     Updated Strategy:
#     1. Tries to find and click the specific 'Close' button of the dialog.
#     2. If that fails, sends the ESCAPE key to the page.
#     3. Targets and removes the specific "offline" overlay using its distinctive class.
#     4. As a last resort, falls back to hiding the dialog with JavaScript.
#     """
#     # Strategy 1: Find and click the 'Close' button
#     try:
#         close_button_selector = 'div[aria-label="Close"][role="button"]'
#         close_button = WebDriverWait(driver, 3).until(
#             EC.element_to_be_clickable((By.CSS_SELECTOR, close_button_selector))
#         )
#         logging.info("Attempting to close overlay by clicking the 'X' button.")
#         driver.execute_script("arguments[0].click();", close_button)
#         time.sleep(1)
#         return
#     except TimeoutException:
#         logging.warning("'X' button not found or not clickable in time.")

#     # Strategy 2: Send the ESCAPE key
#     try:
#         logging.info("Attempting to close overlay by sending the ESCAPE key.")
#         body = driver.find_element(By.TAG_NAME, 'body')
#         body.send_keys(Keys.ESCAPE)
#         time.sleep(1)
#         return
#     except Exception as e:
#         logging.error(f"Failed to send ESCAPE key: {e}")

#     # --- NEW STRATEGY: SPECIFICALLY TARGET OFFLINE OVERLAY ---
#     try:
#         # Use the distinctive class from the provided HTML
#         offline_overlay_selector = 'div.__fb-light-mode'
#         offline_overlay = driver.find_element(By.CSS_SELECTOR, offline_overlay_selector)
#         logging.info("Found 'offline' overlay. Removing it completely from DOM.")
#         driver.execute_script("arguments[0].remove();", offline_overlay)
#         time.sleep(0.5)
#         return
#     except NoSuchElementException:
#         logging.debug("No 'offline' overlay found.")
#     except Exception as e:
#         logging.error(f"Failed to remove offline overlay: {e}")

#     # Strategy 4: Last resort - hide any dialog
#     logging.warning("As a last resort, attempting to hide any dialog via JavaScript.")
#     try:
#         js_script = """
#         var dialog = document.querySelector('div[role="dialog"]');
#         if (dialog) {
#             dialog.style.display = 'none';
#         }
#         """
#         driver.execute_script(js_script)
#     except Exception as e:
#         logging.error(f"Failed to hide dialog with JS: {e}")

def close_overlays_and_popups(driver):
    """
    Intelligently tries to close overlays and popups, including the listing detail modal.
    """
    # Strategy 1: Find and click the 'Close' button (most common for modals)
    try:
        # This selector is specific to the close button inside a dialog/modal
        close_button_selector = 'div[role="dialog"] div[aria-label="Close"][role="button"]'
        close_button = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, close_button_selector))
        )
        logging.info("Attempting to close dialog by clicking its 'X' button.")
        driver.execute_script("arguments[0].click();", close_button)
        time.sleep(1)
        return
    except TimeoutException:
        logging.debug("Dialog-specific 'X' button not found, trying generic one.")
    
    # Strategy 2: Try the generic close button (for initial login popups)
    try:
        close_button_selector = 'div[aria-label="Close"][role="button"]'
        close_button = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, close_button_selector))
        )
        logging.info("Attempting to close overlay by clicking the generic 'X' button.")
        driver.execute_script("arguments[0].click();", close_button)
        time.sleep(1)
        return
    except TimeoutException:
        logging.warning("'X' button not found or not clickable in time.")

    try:
        # Use the distinctive class from the provided HTML
        offline_overlay_selector = 'div.__fb-light-mode'
        offline_overlay = driver.find_element(By.CSS_SELECTOR, offline_overlay_selector)
        logging.info("Found 'offline' overlay. Removing it completely from DOM.")
        driver.execute_script("arguments[0].remove();", offline_overlay)
        time.sleep(0.5)
        return
    except NoSuchElementException:
        logging.debug("No 'offline' overlay found.")
    except Exception as e:
        logging.error(f"Failed to remove offline overlay: {e}")

    # Strategy 3: Send the ESCAPE key as a fallback
    try:
        logging.info("Attempting to close overlay by sending the ESCAPE key.")
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
        time.sleep(1)
        return
    except Exception as e:
        logging.error(f"Failed to send ESCAPE key: {e}")

# --- Output & Notifications ---

def save_listing_to_file(filepath, listing_data):
    """Saves a listing dictionary to a JSON Lines file."""
    with open(filepath, 'a', encoding='utf-8') as f:
        json.dump(listing_data, f)
        f.write('\n')

def save_listing_to_csv(filepath, listing_data):
    """Saves a listing dictionary to a CSV file, creating a header if needed."""
    
    # Define the order of columns in the CSV file.
    fieldnames = [
        "id", "title", "price", "location", "post_time_str", 
        "scraped_at", "link", "image_url"  # Changed from image_urls
    ]
    
    # Check if the file already exists to decide if we need to write the header.
    file_exists = os.path.exists(filepath)
    
    # Open the file in 'append' mode. 
    # newline='' is crucial to prevent extra blank rows.
    with open(filepath, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        # If the file is new, write the header row first.
        if not file_exists:
            writer.writeheader()
            
        # Write the listing data as a new row.
        writer.writerow(listing_data)

def send_slack_notification(webhook_url, listing_data):
    """Sends a nicely formatted notification to a Slack channel."""
    try:
        message = (
            f"*{listing_data['title']}*\n"
            f"Price: *{listing_data['price']}*\n"
            f"Location: {listing_data['location']}\n"
            f"Posted: {listing_data['post_time_str']}\n"
            f"Link: {listing_data['link']}"
        )
        payload = {
            "text": message,
            "attachments": [{
                "image_url": listing_data['image_urls'][0] if listing_data['image_urls'] else "",
                "text": "Listing Image"
            }]
        }
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logging.info(f"Successfully sent Slack notification for: {listing_data['title']}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send Slack notification: {e}")

# --- Core Scraper Logic ---

def setup_driver():
    """
    Sets up the Selenium WebDriver with appropriate options, including a
    safeguard for known path and permission issues on macOS.
    """
    options = Options()
    #options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-notifications")
    
    logging.info("Setting up ChromeDriver...")
    try:
        # Step 1: Let webdriver-manager download the driver and return its path.
        driver_path = ChromeDriverManager().install()
        logging.info(f"WebDriver Manager initially found driver at: {driver_path}")

        # Step 2: Correct the known path issue on macOS (from previous fix).
        notice_filename = 'THIRD_PARTY_NOTICES.chromedriver'
        if notice_filename in driver_path:
            correct_driver_path = driver_path.replace(notice_filename, 'chromedriver')
            logging.warning(f"Incorrect driver path detected. Correcting path to: {correct_driver_path}")
            driver_path = correct_driver_path

        # --- NEW FIX IS HERE ---
        # Step 3: Set executable permissions for the driver. This is crucial for macOS/Linux.
        # The mode 0o755 gives read/write/execute permissions to the owner,
        # and read/execute permissions to group and others.
        logging.info(f"Setting executable permissions for: {driver_path}")
        os.chmod(driver_path, 0o755)
        # --- END OF NEW FIX ---

        # Step 4: Create the Service object with the verified and permissioned executable path.
        service = Service(executable_path=driver_path)

        # Step 5: Initialize the WebDriver.
        driver = webdriver.Chrome(service=service, options=options)
        logging.info("ChromeDriver and WebDriver initialized successfully.")

    except Exception as e:
        logging.critical(f"A critical error occurred during WebDriver setup: {e}", exc_info=True)
        logging.critical("Please ensure Google Chrome is installed and that your internet connection is stable.")
        raise

    return driver

def parse_post_time(time_str: str) -> timedelta:
    """
    Parses human-readable time strings like "a day ago" or "5 minutes ago" 
    into a timedelta object. Returns a large timedelta if parsing fails.
    """
    if not time_str:
        return timedelta(days=999) # Return a large delta if not found

    time_str = time_str.lower()
    
    # Handle the most immediate case first
    if "just now" in time_str:
        return timedelta(minutes=1)

    # NEW: Normalize strings like "a day ago" to "1 day ago" before regex.
    # This also handles "an hour ago" -> "1 hour ago", etc.
    time_str = time_str.replace("an ", "1 ")
    time_str = time_str.replace("a ", "1 ")

    match = re.search(r'(\d+)\s+(minute|hour|day|week)s?', time_str)
    if match:
        value = int(match.group(1))
        unit = match.group(2)
        if "minute" in unit:
            return timedelta(minutes=value)
        if "hour" in unit:
            return timedelta(hours=value)
        if "day" in unit:
            return timedelta(days=value)
        if "week" in unit:
            return timedelta(weeks=value)
            
    # Fallback for unparsed formats (e.g., "Over a month ago")
    return timedelta(days=999)

def parse_config_duration(duration_str: str) -> timedelta:
    """
    Parses a human-readable duration string from the config file (e.g., "1 day", "12 hours").
    """
    try:
        match = re.match(r'(\d+)\s+(minute|hour|day)s?', duration_str.lower())
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            if "minute" in unit:
                return timedelta(minutes=value)
            if "hour" in unit:
                return timedelta(hours=value)
            if "day" in unit:
                return timedelta(days=value)
    except (TypeError, AttributeError):
        pass

    logging.warning(f"Could not parse duration '{duration_str}'. Defaulting to 10 minutes.")
    return timedelta(minutes=10)

def scrape_marketplace(driver, search_terms, location, config):
    """Main function to orchestrate the scraping process."""
    base_url = "https://www.facebook.com/marketplace"
    
    max_age_str = config['Scraper']['max_listing_age']
    max_age_delta = parse_config_duration(max_age_str)
    logging.info(f"Scraping for listings newer than: {max_age_str}")
    anti_keywords = [kw.strip().lower() for kw in config['Scraper']['anti_keywords'].split(',')]
    timeout = int(config['Advanced']['timeout'])
    human_delay = int(config['Advanced']['human_delay_seconds'])
    output_file = config['Output']['output_file']
    dedup_file = config['Output']['deduplication_file']
    slack_enabled = config['Notifications'].getboolean('slack_enabled')
    slack_webhook_url = config['Notifications']['slack_webhook_url']

    scraped_ids = load_scraped_ids(dedup_file)
    new_listings_found = 0

    for term in search_terms:
        search_query = quote(term)
        url = f"{base_url}/{location}/search/?query={search_query}&sortBy=creation_time_descend&deliveryMethod=local_only"
        
        logging.info(f"Navigating to URL for search term '{term}' in '{location}': {url}")
        driver.get(url)
        time.sleep(random.uniform(human_delay, human_delay + 2))

        try:
            close_overlays_and_popups(driver)
        except Exception:
            logging.warning("Could not close initial popup, continuing anyway.")

        logging.info("Scrolling to load listings...")
        for _ in range(3): # Scroll a few times to load initial set
            hide_login_popup(driver)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
        hide_login_popup(driver)

        try:
            listings = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/marketplace/item/"]')
            logging.info(f"Found {len(listings)} potential listings for '{term}'. Starting processing...")

            for i in range(len(listings)):
                listing_element = None
                title = "N/A" # Default title for logging

                try:
                    # Re-find the element in each iteration to avoid StaleElementReferenceException
                    listings_on_page = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/marketplace/item/"]')
                    if i >= len(listings_on_page):
                        logging.warning("Listings have changed on page, ending processing for this term.")
                        break
                    listing_element = listings_on_page[i]

                    # --- PRE-CLICK FILTERING (FAST) ---
                    link = listing_element.get_attribute('href')
                    item_id_match = re.search(r'/item/(\d+)/', link)
                    if not item_id_match: continue
                    item_id = item_id_match.group(1)
                    if item_id in scraped_ids: continue

                    if listing_element.find_elements(By.CSS_SELECTOR, 'i[data-visualcompletion="css-img"]'):
                        save_scraped_id(dedup_file, item_id)
                        scraped_ids.add(item_id)
                        continue

                    try:
                        title = listing_element.find_element(By.TAG_NAME, 'img').get_attribute('alt')
                    except NoSuchElementException:
                        continue

                    if any(kw in title.lower() for kw in anti_keywords):
                        save_scraped_id(dedup_file, item_id)
                        scraped_ids.add(item_id)
                        continue
                    
                    # --- SINGLE-TAB WORKFLOW ---
                    logging.info(f"Clicking on listing '{title}' to open detail view.")
                    listing_element.click()

                    detail_modal_selector = 'div[role="dialog"]'
                    WebDriverWait(driver, timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, detail_modal_selector))
                    )
                    time.sleep(1)
                    
                    # --- TIME & FINAL DATA EXTRACTION ---
                    post_time_str = ""
                    post_age = timedelta(days=999)
                    
                    time_element = WebDriverWait(driver, timeout).until(
                        EC.presence_of_element_located((By.XPATH, '//abbr[@aria-label]'))
                    )
                    post_time_str = time_element.get_attribute('aria-label')
                    print("POST TIME", post_time_str)
                    post_age = parse_post_time(post_time_str)
                    print("POST AGE", post_age)

                    # *** IMPORTANT: Changed 'break' to 'continue' as requested ***
                    if post_age > max_age_delta:
                        logging.info(f"Skipping listing older than {max_age_minutes} mins: '{title}' ({post_time_str})")
                        continue

                    # --- SUCCESS! LISTING PASSED ALL FILTERS ---
                    logging.info(f"✅ Found valid new listing: '{title}'")
                    price = driver.find_element(By.XPATH, '//div[@aria-hidden="false"]//span[starts-with(text(), "$")]').text
                    location_text = driver.find_element(By.XPATH, '//a[contains(@href, "/marketplace/") and .//span]').text
                    image_url = driver.find_element(By.XPATH, '//img[starts-with(@alt, "Product photo of")]').get_attribute('src')
                    
                    listing_data = {
                        "id": item_id, "title": title, "price": price, "location": location_text,
                        "post_time_str": post_time_str, "scraped_at": datetime.now().isoformat(),
                        "link": link, "image_url": [image_url]
                    }

                    save_listing_to_csv(output_file, listing_data)
                    save_scraped_id(dedup_file, item_id)
                    scraped_ids.add(item_id)
                    new_listings_found += 1

                    if slack_enabled and slack_webhook_url and 'YOUR' not in slack_webhook_url:
                        send_slack_notification(slack_webhook_url, listing_data)

                # except:
                #     logging.warning("Stale element encountered. The page likely refreshed. Moving to next listing.")
                #     continue
                except (TimeoutException, NoSuchElementException) as e:
                    logging.warning(f"Could not process listing '{title}'. A required element was not found in time. Skipping. Error: {e}")
                except Exception as e:
                    logging.error(f"Error processing listing '{title}': {e}", exc_info=True)
                finally:
                    # This robustly closes the modal to get back to the search results
                    try:
                        close_overlays_and_popups(driver)
                        WebDriverWait(driver, 5).until(
                           EC.invisibility_of_element_located((By.CSS_SELECTOR, 'div[role="dialog"]'))
                        )
                    except (TimeoutException, NoSuchElementException):
                        pass # Dialog is already closed, which is fine.
                    time.sleep(random.uniform(1, 2)) # Pause before next listing

        except Exception as e:
            logging.error(f"An unexpected error occurred during scraping for '{term}': {e}", exc_info=True)

    logging.info(f"Scraping run finished. Found {new_listings_found} new listings.")


# def scrape_marketplace(driver, search_terms, location, config):
#     """Main function to orchestrate the scraping process."""
#     base_url = "https://www.facebook.com/marketplace"
    
#     # Load config values
#     max_age_minutes = int(config['Scraper']['max_listing_age_minutes'])
#     anti_keywords = [kw.strip().lower() for kw in config['Scraper']['anti_keywords'].split(',')]
#     timeout = int(config['Advanced']['timeout'])
#     human_delay = int(config['Advanced']['human_delay_seconds'])
#     output_file = config['Output']['output_file']
#     dedup_file = config['Output']['deduplication_file']
#     slack_enabled = config['Notifications'].getboolean('slack_enabled')
#     slack_webhook_url = config['Notifications']['slack_webhook_url']

#     scraped_ids = load_scraped_ids(dedup_file)
#     new_listings_found = 0

#     for term in search_terms:
#         # Construct the URL for newest, local-only listings
#         search_query = quote(term)
#         url = f"{base_url}/{location}/search/?query={search_query}&sortBy=creation_time_descend&deliveryMethod=local_only"
        
#         logging.info(f"Navigating to URL for search term '{term}' in '{location}': {url}")
#         driver.get(url)
#         time.sleep(random.uniform(human_delay, human_delay + 3)) # Human-like pause

#         # Locate the button for the login pop-up with aria-label="Close"
#         try:
#             close_button = driver.find_element(By.XPATH, '//div[@aria-label="Close" and @role="button"]')
#             close_button.click()
#             logging.info(f"Navigating to URL for search term '{term}': {url}")
            
#         except:
#             logging.error(f"Could not find close button")
#             pass


#         logging.info("Starting to scroll to load all listings...")
#         scroll_attempts = 0
#         max_scroll_attempts = 5 # Prevents infinite loops

#         while scroll_attempts < max_scroll_attempts:
#             # HIDE THE POPUP before we do anything else.
#             hide_login_popup(driver)
            
#             last_height = driver.execute_script("return document.body.scrollHeight")
            
#             # Scroll down
#             driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
#             time.sleep(4) # Wait for new content to load

#             # HIDE THE POPUP AGAIN, as scrolling may have triggered it.
#             hide_login_popup(driver)
            
#             new_height = driver.execute_script("return document.body.scrollHeight")

#             if new_height == last_height:
#                 logging.info("Reached the bottom of the page or no new content loaded.")
#                 break
            
#             scroll_attempts += 1
#             logging.info(f"Scrolled down. Attempt {scroll_attempts}/{max_scroll_attempts}")

       

#         try:
#             # This is our main, stable selector for each listing card's link
#             listings = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/marketplace/item/"]')
#             print(listings)
#             logging.info(f"Found {len(listings)} potential listings for '{term}'. Starting filtering...")
#             # input(f"PAUSED for {term}. Press Enter in this terminal to continue scraping...")

#             if not listings:
#                 logging.warning(f"No listing elements found on page for '{term}'. The page structure might have changed.")
#                 continue

#             # for listing_element in listings:
#             #     main_window = driver.current_window_handle
                
#             #     # --- PRE-CLICK FILTERING (FAST) ---
#             #     try:
#             #         # 1. DEDUPLICATION CHECK
#             #         link = listing_element.get_attribute('href')
#             #         item_id_match = re.search(r'/item/(\d+)/', link)
#             #         if not item_id_match: continue
#             #         item_id = item_id_match.group(1)
#             #         if item_id in scraped_ids: continue

#             #         # 2. SHIPPING ENABLED CHECK
#             #         # We check for the presence of the small truck/shipping icon.
#             #         # This is far more efficient than clicking.
#             #         shipping_icon = listing_element.find_elements(By.CSS_SELECTOR, 'i[data-visualcompletion="css-img"]')
#             #         if shipping_icon:
#             #             logging.info(f"Skipping listing (ID: {item_id}) - Shipping is enabled.")
#             #             save_scraped_id(dedup_file, item_id) # Save to avoid re-checking
#             #             scraped_ids.add(item_id)
#             #             continue
                    
#             #         # 3. ANTI-KEYWORD CHECK
#             #         # Using a more robust selector for the title based on its visual style.
#             #         # Fallback to the image alt text which is also very reliable.
#             #         title = ""
#             #         try:
#             #             title_element = listing_element.find_element(By.CSS_SELECTOR, "span[style*='-webkit-line-clamp:2']")
#             #             title = title_element.text
#             #         except NoSuchElementException:
#             #             img_element = listing_element.find_element(By.TAG_NAME, 'img')
#             #             title = img_element.get_attribute('alt')

#             #         if not title:
#             #             logging.warning(f"Could not extract title for listing {link}. Skipping.")
#             #             continue

#             #         if any(kw in title.lower() for kw in anti_keywords):
#             #             logging.info(f"Skipping '{title}' due to anti-keyword.")
#             #             save_scraped_id(dedup_file, item_id) # Save to avoid re-checking
#             #             scraped_ids.add(item_id)
#             #             continue
                    
#             #         # --- If we get here, the listing passed the fast filters. Now we do the slow time check. ---

#             #         # 4. POST TIME CHECK (EXPENSIVE)
#             #         logging.info(f"Performing JS click on listing: '{title}'")
#             #         driver.execute_script("arguments[0].click();", listing_element)
#             #         # Wait for the new tab to open and switch to it
#             #         WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
#             #         new_window = [window for window in driver.window_handles if window != main_window][0]
#             #         driver.switch_to.window(new_window)

#             #         post_time_str = ""
#             #         post_age = timedelta(days=999) # Default to a very old age
                    
#             #         try:
#             #             # Wait for the "Posted..." text to appear in the new tab
#             #             time_element = WebDriverWait(driver, 10).until(
#             #                 EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Posted ')]"))
#             #             )
#             #             post_time_str = time_element.text
#             #             post_age = parse_post_time(post_time_str)
#             #         except TimeoutException:
#             #             logging.warning(f"Could not find post time for '{title}' after clicking. Skipping.")
                    
#             #         # This check is crucial for efficiency.
#             #         if post_age > timedelta(minutes=max_age_minutes):
#             #             logging.info(f"Stopping search for '{term}'. Found listing older than {max_age_minutes} mins: '{title}' (Posted: {post_time_str}).")
#             #             driver.close() # Close the tab
#             #             driver.switch_to.window(main_window) # Switch back
#             #             break # EXIT THE LOOP for this search term

#             #         # --- SUCCESS! LISTING PASSED ALL FILTERS ---
#             #         logging.info(f"✅ Found valid new listing: '{title}'")

#             #         # Extract remaining data from the now-open page
#             #         price = driver.find_element(By.XPATH, "//h1/..//span").text
#             #         location_text = driver.find_element(By.XPATH, "//*[contains(@href, '/marketplace/category/')]//span").text
#             #         image_url = driver.find_element(By.CSS_SELECTOR, "img[data-visualcompletion='media-vc-image']").get_attribute('src')
                    
#             #         listing_data = {
#             #             "id": item_id, "title": title, "price": price, "location": location_text,
#             #             "post_time_str": post_time_str, "scraped_at": datetime.now().isoformat(),
#             #             "link": link, "image_urls": [image_url]
#             #         }

#             #         save_listing_to_file(output_file, listing_data)
#             #         save_scraped_id(dedup_file, item_id)
#             #         scraped_ids.add(item_id)
#             #         new_listings_found += 1

#             #         if slack_enabled and slack_webhook_url and 'YOUR' not in slack_webhook_url:
#             #             send_slack_notification(slack_webhook_url, listing_data)

#             #     except Exception as e:
#             #         logging.error(f"Error processing a listing card: {e}", exc_info=True)
#             #     finally:
#             #         # Ensure we always switch back to the main window
#             #         if len(driver.window_handles) > 1:
#             #             driver.close()
#             #         driver.switch_to.window(main_window)

#             for listing_element in listings:
#                 main_window = driver.current_window_handle
    
#                 # --- PRE-NAVIGATION FILTERING (FAST) ---
#                 try:
#                     # 1. DEDUPLICATION CHECK
#                     link = listing_element.get_attribute('href')
#                     item_id_match = re.search(r'/item/(\d+)/', link)
#                     if not item_id_match: continue
#                     item_id = item_id_match.group(1)
#                     if item_id in scraped_ids: continue

#                     # 2. SHIPPING ENABLED CHECK
#                     shipping_icon = listing_element.find_elements(By.CSS_SELECTOR, 'i[data-visualcompletion="css-img"]')
#                     if shipping_icon:
#                         logging.info(f"Skipping listing (ID: {item_id}) - Shipping enabled on grid view.")
#                         save_scraped_id(dedup_file, item_id)
#                         scraped_ids.add(item_id)
#                         continue
                    
#                     # 3. ANTI-KEYWORD CHECK
#                     title = ""
#                     try:
#                         title_element = listing_element.find_element(By.CSS_SELECTOR, "span[style*='-webkit-line-clamp:2']")
#                         title = title_element.text
#                     except NoSuchElementException:
#                         try:
#                             img_element = listing_element.find_element(By.TAG_NAME, 'img')
#                             title = img_element.get_attribute('alt')
#                         except NoSuchElementException:
#                             logging.warning(f"Could not extract title for listing {link}. Skipping.")
#                             continue

#                     if any(kw in title.lower() for kw in anti_keywords):
#                         logging.info(f"Skipping '{title}' due to anti-keyword.")
#                         save_scraped_id(dedup_file, item_id)
#                         scraped_ids.add(item_id)
#                         continue
                    
#                     # --- If we get here, the listing is promising. Let's visit its page. ---
                    
#                     # 4. NAVIGATE TO DETAIL PAGE FOR TIME CHECK
#                     logging.info(f"Visiting details for '{title}' to check post time.")
                    
#                     # Open a new tab and navigate directly to the URL
#                     driver.switch_to.new_window('tab')
#                     driver.get(link)
                    
#                     # IMPORTANT: Handle overlays on the new detail page
#                     time.sleep(2) # Give page a moment to load elements
#                     close_overlays_and_popups(driver) # Clear any new popups
#                     time.sleep(1) # Wait a tick for the overlay to disappear


#                     post_time_str = ""
#                     post_age = timedelta(days=999)
            
                    
#                     try:
#                         # --- NEW TWO-STAGE WAIT ---
#                         # Stage 1: Wait for a stable landmark element to appear. The main title (H1) is perfect for this.
#                         # This confirms the main content of the page has started to render.
#                         logging.info("Waiting for page content to load (H1 title)...")
#                         WebDriverWait(driver, 10).until(
#                             EC.presence_of_element_located((By.TAG_NAME, "h1"))
#                         )

#                         # Stage 2: NOW that the page is stable, wait for the specific post time element.
#                         # We also use a more robust XPath selector that ignores extra whitespace.
#                         logging.info("Page content loaded. Waiting for post time...")
#                         time_element = WebDriverWait(driver, 10).until(
#                             EC.presence_of_element_located((By.XPATH, "//*[contains(normalize-space(.), 'Posted') or contains(normalize-space(.), 'Listed')]"))
#                         )
                        
#                         post_time_str = time_element.text
#                         post_age = parse_post_time(post_time_str)

                        

#                     except TimeoutException:
#                         logging.warning(f"Could not find post time for '{title}' on detail page after waiting. Skipping.")
#                         # Take a screenshot for debugging, this is extremely helpful
#                         screenshot_file = f"debug_screenshot_{item_id}.png"
#                         driver.save_screenshot(screenshot_file)
#                         logging.warning(f"Saved a debug screenshot to {screenshot_file}")
#                         driver.close()
#                         driver.switch_to.window(main_window)
#                         continue

#                     if post_age > timedelta(minutes=max_age_minutes):
#                         logging.info(f"Stopping search for '{term}'. Found listing older than {max_age_minutes} mins: '{title}' (Posted: {post_time_str}).")
#                         driver.close()
#                         driver.switch_to.window(main_window)
#                         break

#                     # --- SUCCESS! LISTING PASSED ALL FILTERS ---
#                     logging.info(f"✅ Found valid new listing: '{title}'")

#                     # Extract remaining data
#                     # These selectors are for the detail page
#                     price = driver.find_element(By.XPATH, "//h1/..//span").text
#                     location_text = driver.find_element(By.XPATH, "//*[contains(@href, '/marketplace/location/')]").text
#                     image_url = driver.find_element(By.CSS_SELECTOR, "img[data-visualcompletion='media-vc-image']").get_attribute('src')
                    
#                     listing_data = {
#                         "id": item_id, "title": title, "price": price, "location": location_text,
#                         "post_time_str": post_time_str, "scraped_at": datetime.now().isoformat(),
#                         "link": link, "image_urls": [image_url]
#                     }

#                     save_listing_to_file(output_file, listing_data)
#                     save_scraped_id(dedup_file, item_id)
#                     scraped_ids.add(item_id)
#                     new_listings_found += 1

#                     if slack_enabled and slack_webhook_url and 'YOUR' not in slack_webhook_url:
#                         send_slack_notification(slack_webhook_url, listing_data)

#                 except Exception as e:
#                     logging.error(f"Error processing a listing: {e}", exc_info=True)
#                 finally:
#                     # This cleanup ensures we always return to the main search page
#                     # It closes any extra tabs that might have been opened
#                     while len(driver.window_handles) > 1:
#                         driver.switch_to.window(driver.window_handles[-1])
#                         driver.close()
#                     driver.switch_to.window(main_window)
             
#         except TimeoutException:
#             logging.error(f"Timeout waiting for listings page to load for term '{term}'.")
#         except Exception as e:
#             logging.error(f"An unexpected error occurred during scraping for '{term}': {e}", exc_info=True)

#     logging.info(f"Scraping run finished. Found {new_listings_found} new listings.")





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
        driver = setup_driver()
        
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
            scrape_marketplace(driver, search_terms, location, config)

    except Exception as e:
        logging.critical(f"A critical error occurred in the main script: {e}", exc_info=True)
    finally:
        if driver:
            driver.quit()
            logging.info("WebDriver closed.")

if __name__ == "__main__":
    main()