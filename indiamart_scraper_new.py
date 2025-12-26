import argparse
import os
import time
import csv
import random
import logging
from datetime import datetime
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent
from fuzzywuzzy import fuzz # For calculating relevancy score

# --- UTILITY FUNCTIONS ---

def setup_logger():
    """Set up and configure the logger."""
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"scraper_{timestamp}.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger()

def retry(max_attempts=3, delay=2):
    """Decorator to retry a function if it fails due to transient errors."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    logging.warning(f"Attempt {attempts}/{max_attempts} failed for '{func.__name__}' with error: {e}. Retrying in {delay} seconds...")
                    time.sleep(delay)
                    if attempts == max_attempts:
                        logging.error(f"Function '{func.__name__}' failed after {max_attempts} attempts.")
                        raise # Re-raise the last exception if all attempts fail
        return wrapper
    return decorator

def sanitize_data(data):
    """Clean and sanitize data for CSV export."""
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = value.strip()
                data[key] = data[key].replace('\n', ' ').replace('\t', ' ')
                while '  ' in data[key]:
                    data[key] = data[key].replace('  ', ' ')
    return data

def validate_phone(phone):
    """Validate and format phone numbers (specifically for Indian numbers)."""
    if not phone:
        return ""
    digits = ''.join(filter(str.isdigit, phone))
    if len(digits) == 10:
        return digits
    elif len(digits) in [11, 12] and digits.startswith(('91', '0')):
        return digits[-10:]
    return phone # Return original if not a clear 10-digit or Indian format

def validate_email(email):
    """Validate email addresses."""
    if not email:
        return ""
    # Basic validation: check for '@' and '.' after '@'
    if '@' in email and '.' in email.split('@')[1]:
        return email.strip().lower()
    return ""

# --- INDIA MART SCRAPER CLASS ---

class IndiaMartScraper:
    def __init__(self, headless=False):
        """
        Initializes the IndiaMartScraper with headless mode option.
        :param headless: If True, run Chrome in headless mode (no UI).
        """
        self.base_url = "https://www.indiamart.com/" # Base URL is still useful for general reference
        self.driver = None
        self.leads = []
        self.logger = setup_logger()
        self.headless = headless
        self._setup_driver() # Internal method for driver setup

    def _setup_driver(self):
        """Sets up the Selenium WebDriver with appropriate options."""
        self.logger.info("Setting up the browser...")
        try:
            ua = UserAgent()
            user_agent = ua.random

            chrome_options = Options()
            if self.headless:
                self.logger.info("Running in headless mode")
                chrome_options.add_argument("--headless=new")
                chrome_options.add_argument("--window-size=1920,1080")

            # Essential arguments for robust scraping
            chrome_options.add_argument(f"user-agent={user_agent}")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-popup-blocking")
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-gpu")
            
            # Dynamically assign a random port for remote debugging
            random_port = random.randint(9000, 10000)
            chrome_options.add_argument(f"--remote-debugging-port={random_port}") 
            self.logger.info(f"Using remote debugging port: {random_port}")

            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(30) # Set a page load timeout
            self.logger.info("Browser setup complete")
        except Exception as e:
            self.logger.error(f"Failed to set up browser: {e}")
            print("\nERROR: Could not initialize the browser. Please check your Chrome installation.")
            print("Possible solutions:")
            print("1. Make sure Chrome is installed and up to date")
            print("2. Try running the script with administrator privileges")
            print("3. Check if your antivirus is blocking Chrome automation")
            raise # Re-raise to stop execution if driver fails to set up

    @retry(max_attempts=3, delay=2)
    def login(self):
        """Navigates to IndiaMART buyer page and handles OTP-based login."""
        self.logger.info("Navigating to IndiaMART buyer login page...")
        try:
            # Navigate directly to the buyer login page
            self.driver.get("https://buyer.indiamart.com/")
            # Wait for the URL to contain the buyer domain, indicating page load
            WebDriverWait(self.driver, 15).until(EC.url_contains("buyer.indiamart.com"))
            self.logger.info(f"Navigated to buyer login page. Current URL: {self.driver.current_url}")
            time.sleep(3) # Time break: once the page loads

            # Default mobile number
            default_mobile = "<Mobile  Number Here>" # Replace with your mobile number for OTP login
            mobile_number = validate_phone(default_mobile)
            
            if not mobile_number or len(mobile_number) != 10:
                self.logger.error(f"Invalid default mobile number: {default_mobile}. Please check configuration.")
                print(f"Invalid default mobile number: {default_mobile}. Please correct it in the script.")
                return False

            # Find and fill mobile input field
            # Using id="mobilemy" from provided HTML
            mobile_input = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "mobilemy")) 
            )
            mobile_input.send_keys(mobile_number)
            self.logger.info(f"Entered mobile number: {mobile_number}")
            time.sleep(3) # Time break: after phone number is entered, before submitting

            # Find and click "Send OTP" button
            # Using id="signInSubmitButton" and value="Send OTP" from provided HTML
            send_otp_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@id='signInSubmitButton' and @value='Send OTP']"))
            )
            send_otp_button.click()
            self.logger.info("Clicked 'Send OTP' button.")
            time.sleep(3) # Give time for OTP input field to appear

            # Prompt for OTP
            otp = input("Enter the OTP received: ")

            # Find and fill OTP input field
            # Using type, placeholder, and maxlength from provided HTML as it has no ID
            otp_input = WebDriverWait(self.driver, 15).until(
                EC.visibility_of_element_located((By.XPATH, "//input[@type='text' and @placeholder='----' and @maxlength='4']"))
            )
            otp_input.send_keys(otp)
            self.logger.info("Entered OTP.")

            # Find and click "Verify OTP" button
            # Using id="signInSubmitButton" and value="Verify OTP" from provided HTML
            verify_otp_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@id='signInSubmitButton' and @value='Verify OTP']"))
            )
            verify_otp_button.click()
            self.logger.info("Clicked 'Verify OTP' button.")

            # Wait for successful login indicators on the buyer page (e.g., URL change, presence of dashboard elements)
            WebDriverWait(self.driver, 15).until(
                EC.any_of(
                    EC.url_contains("buyer.indiamart.com/"), # URL changes from the login form to dashboard
                    EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'My Account') or contains(text(), 'Dashboard') or contains(text(), 'My Orders') or contains(text(), 'Post Your Requirement')]"))
                )
            )
            self.logger.info("Login process successful!")
            return True

        except TimeoutException:
            self.logger.error("Login process timed out. Elements not found or page did not load.")
            self.driver.save_screenshot("login_timeout_error.png")
            return False
        except NoSuchElementException:
            self.logger.error("Login elements not found on the page.")
            self.driver.save_screenshot("login_elements_missing.png")
            return False
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during login: {e}")
            self.driver.save_screenshot("login_unexpected_error.png")
            return False

    @retry(max_attempts=3, delay=2)
    def search_product(self, keyword):
        """
        Searches for a product using the given keyword.
        :param keyword: The product keyword to search for.
        :return: True if search initiated successfully, False otherwise.
        """
        self.logger.info(f"Initiating search for: {keyword}")
        main_window_handle = self.driver.current_window_handle # Store original window handle
        try:
            # 1. Wait for the input box to be load then try to input the keyword
            time.sleep(3) # Wait for 3 seconds as requested after login for the page to fully settle.
            search_input_box = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.ID, "search_string")) # Targeting id="search_string"
            )
            search_input_box.clear()
            search_input_box.send_keys(keyword)
            self.logger.info(f"Entered keyword '{keyword}' into the search input box (id='search_string').")
            
            # 2. Click the first search button (magnifying glass icon/text "Search")
            first_search_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".rvmp_srch_button")) # Targeting class "rvmp_srch_button"
            )
            first_search_button.click()
            self.logger.info("Clicked the first search button (rvmp_srch_button).")
            
            time.sleep(2) # Wait for 2 seconds as requested after clicking the first search button

            # 3. Click the second search button (class="adv-btn search-button")
            second_search_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".adv-btn.search-button")) # Targeting classes "adv-btn" and "search-button"
            )
            second_search_button.click()
            self.logger.info("Clicked the second search button (adv-btn search-button).")
            
            # --- START: New tab handling logic ---
            # Wait for a new window/tab to open (expecting 2 windows now)
            # Increased timeout to 20 seconds for robustness
            WebDriverWait(self.driver, 20).until(EC.number_of_windows_to_be(2))
            
            # Switch to the new window/tab
            new_window_handle = [window_handle for window_handle in self.driver.window_handles if window_handle != main_window_handle][0]
            self.driver.switch_to.window(new_window_handle)
            self.logger.info(f"Switched to new window/tab: {self.driver.current_url}")
            # --- END: New tab handling logic ---

            # Wait for search results URL on the new tab
            WebDriverWait(self.driver, 20).until(EC.url_contains("/isearch.php")) # Increased timeout for URL to load
            self.logger.info("Search completed. Now scraping results...")
            return True
        except TimeoutException:
            self.logger.error("Search page or elements timed out.")
            self.driver.save_screenshot("search_timeout_error.png")
            return False
        except Exception as e:
            self.logger.error(f"Error during search for '{keyword}': {e}")
            self.driver.save_screenshot("search_error.png")
            return False
        finally:
            # Ensure we switch back to the original window if something goes wrong
            # This is important for the overall flow if subsequent actions are on the main window
            # Check if there's more than one window and we are not on the main window
            if len(self.driver.window_handles) > 1 and self.driver.current_window_handle != main_window_handle:
                self.driver.close() # Close the new tab if it's still open and we're on it
            # Always switch back to the original window handle
            self.driver.switch_to.window(main_window_handle) 
            self.logger.info("Returned to main window after search.")


    def _extract_seller_info_from_listing(self, seller_element):
        """
        Extracts basic information from a seller listing element on the search results page.
        :param seller_element: The WebDriver element representing a single seller listing.
        :return: A dictionary of extracted seller information.
        """
        seller_info = {
            "Company Name": "",
            "Company Profile URL": "",
            "Price": "Not Listed",
            "Address": "",
            "Phone Number": "",
            "Email": "", # New field
            "Product Title/Description": ""
        }

        try:
            # Extract Product Name
            try:
                product_name_element = seller_element.find_element(By.CSS_SELECTOR, ".producttitle .cardlinks")
                seller_info["Product Title/Description"] = product_name_element.text.strip()
                # Also get the product URL from this link
                seller_info["Company Profile URL"] = product_name_element.get_attribute("href")
            except NoSuchElementException:
                self.logger.debug("Product title/description or its link not found.")

            # Extract Price
            try:
                price_element = seller_element.find_element(By.CSS_SELECTOR, "p.price")
                seller_info["Price"] = price_element.text.strip()
            except NoSuchElementException:
                self.logger.debug("Price not found.")

            # Extract Company Name
            try:
                company_name_element = seller_element.find_element(By.CSS_SELECTOR, ".companyname .cardlinks")
                seller_info["Company Name"] = company_name_element.text.strip()
                # If Company Profile URL wasn't set by product link, try to get it from company name link
                if not seller_info["Company Profile URL"]:
                    seller_info["Company Profile URL"] = company_name_element.get_attribute("href")
            except NoSuchElementException:
                self.logger.debug("Company name or its link not found.")

            # Extract Location (short version from highlight span)
            try:
                short_location_element = seller_element.find_element(By.CSS_SELECTOR, ".newLocationUi .highlight")
                seller_info["Address"] = short_location_element.text.strip()
            except NoSuchElementException:
                self.logger.debug("Short location not found.")

            # Extract full Address (if available)
            try:
                full_address_element = seller_element.find_element(By.CSS_SELECTOR, "#citytt1 p")
                # Overwrite short location if full address is more descriptive
                if full_address_element.text.strip():
                    seller_info["Address"] = full_address_element.text.strip()
            except NoSuchElementException:
                self.logger.debug("Full address (citytt1 p) not found.")
            
            # --- Handle "View Mobile Number" and direct phone extraction ---
            initial_phone_found = False
            try:
                # Check if the direct phone number is already visible (not display:none)
                direct_phone_element = seller_element.find_element(By.CSS_SELECTOR, ".contactnumber .pns_h")
                if direct_phone_element.is_displayed():
                    seller_info["Phone Number"] = validate_phone(direct_phone_element.text.strip())
                    self.logger.debug(f"Direct phone number found: {seller_info['Phone Number']}")
                    initial_phone_found = True
            except NoSuchElementException:
                self.logger.debug("Direct phone number element not found initially.")

            if not initial_phone_found:
                try:
                    # Try to find and click the "View Mobile Number" button
                    view_mobile_button = seller_element.find_element(By.CSS_SELECTOR, ".mo.viewn.vmn")
                    if view_mobile_button.is_displayed() and view_mobile_button.is_enabled():
                        view_mobile_button.click()
                        self.logger.debug("Clicked 'View Mobile Number' button.")
                        time.sleep(1) # Small pause for the number to appear

                        # Now try to find the revealed phone number
                        revealed_phone_element = WebDriverWait(seller_element, 5).until(
                            EC.visibility_of_element_located((By.CSS_SELECTOR, ".contactnumber .pns_h"))
                        )
                        seller_info["Phone Number"] = validate_phone(revealed_phone_element.text.strip())
                        self.logger.debug(f"Revealed phone number extracted: {seller_info['Phone Number']}")
                        initial_phone_found = True
                except (NoSuchElementException, TimeoutException):
                    self.logger.debug("View Mobile Number button or revealed phone not found/interactable.")
                except Exception as e:
                    self.logger.warning(f"Error clicking/extracting 'View Mobile Number': {e}")
            # --- End of "View Mobile Number" handling ---

        except Exception as e:
            self.logger.warning(f"Error extracting seller info from listing: {e}")
        return seller_info

    @retry(max_attempts=2, delay=1)
    def _extract_detailed_info_from_profile(self, seller_info):
        """
        Visits the company's profile page to extract more detailed information (phone, email, full address).
        This method is now a fallback if phone/email aren't found on the listing card.
        :param seller_info: The dictionary containing existing seller information (must have 'Company Profile URL').
        """
        # Only visit profile if we still need phone or email, and a profile URL exists
        if (not seller_info.get("Phone Number") or not seller_info.get("Email")) and seller_info.get("Company Profile URL"):
            main_window = self.driver.current_window_handle
            try:
                # Open in a new tab to avoid losing current search results page
                self.driver.execute_script(f"window.open('{seller_info['Company Profile URL']}', '_blank');")
                WebDriverWait(self.driver, 10).until(EC.number_of_windows_to_be(2))
                self.driver.switch_to.window(self.driver.window_handles[-1])

                WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(random.uniform(2, 4)) # Allow content to load

                # Extract Phone Number (if not already found)
                if not seller_info["Phone Number"]:
                    try:
                        phone_elements = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'phone') or contains(@class, 'mobile') or contains(@class, 'contact-num') or contains(text(), '+91') or contains(text(), 'Call')]")
                        for el in phone_elements:
                            text = el.text.strip()
                            extracted_phone = validate_phone(text)
                            if extracted_phone and len(extracted_phone) >= 10:
                                seller_info["Phone Number"] = extracted_phone
                                self.logger.info(f"Extracted phone from profile: {seller_info['Phone Number']}")
                                break
                    except Exception as e:
                        self.logger.debug(f"Could not extract phone number from profile: {e}")
                
                # Extract Email (if not already found)
                if not seller_info["Email"]:
                    try:
                        email_elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'mailto:')] | //*[contains(text(), '@') and contains(text(), '.com')]")
                        for el in email_elements:
                            email_text = el.text.strip()
                            if not email_text and el.tag_name == 'a':
                                email_text = el.get_attribute('href').replace('mailto:', '').strip()
                            extracted_email = validate_email(email_text)
                            if extracted_email:
                                seller_info["Email"] = extracted_email
                                self.logger.info(f"Extracted email from profile: {seller_info['Email']}")
                                break
                    except Exception as e:
                        self.logger.debug(f"Could not extract email from profile: {e}")

                # Extract full Address (if not already sufficiently detailed)
                if not seller_info["Address"] or len(seller_info["Address"]) < 10: 
                    try:
                        address_selectors = [
                            "//div[contains(@class, 'address') or contains(@class, 'location-details') or contains(@class, 'company-address')]//text()",
                            "//span[contains(text(), 'Address:')]/following-sibling::span",
                            "//div[contains(text(), 'Address:')]/following-sibling::div"
                        ]
                        full_address_parts = []
                        for selector in address_selectors:
                            elements = self.driver.find_elements(By.XPATH, selector)
                            for el in elements:
                                text = el.text.strip() if hasattr(el, 'text') else str(el).strip()
                                if text and "Address:" not in text and "Location:" not in text and len(text) > 5:
                                    full_address_parts.append(text)
                            if full_address_parts:
                                break # Stop if we found parts from a selector
                        if full_address_parts:
                            seller_info["Address"] = " ".join(full_address_parts).replace("  ", " ").strip()
                            self.logger.info(f"Extracted detailed address from profile: {seller_info['Address']}")
                    except Exception as e:
                        self.logger.debug(f"Could not extract detailed address from profile: {e}")

            except Exception as e:
                self.logger.error(f"Error during detailed info extraction from profile {seller_info.get('Company Profile URL')}: {e}")
            finally:
                # Always close the tab and switch back to the main window
                self.driver.close()
                self.driver.switch_to.window(main_window)
                self.logger.info("Closed profile tab and switched back to main window.")
        else:
            self.logger.debug("Skipping detailed profile extraction (no URL or info already found).")


    def _calculate_relevancy_score(self, seller_info, keyword):
        """
        Calculates a relevancy score based on how well the seller info matches the keyword.
        :param seller_info: Dictionary containing seller data.
        :param keyword: The original search keyword.
        :return: An integer score (0-100).
        """
        score = 0
        keyword_lower = keyword.lower()

        product_desc_lower = seller_info["Product Title/Description"].lower()
        if keyword_lower in product_desc_lower:
            score += 60
            score += min(10, product_desc_lower.count(keyword_lower) * 2)
        else:
            ratio = fuzz.partial_ratio(keyword_lower, product_desc_lower)
            score += int(ratio * 0.6)

        company_name_lower = seller_info["Company Name"].lower()
        if keyword_lower in company_name_lower:
            score += 30
        else:
            ratio = fuzz.partial_ratio(keyword_lower, company_name_lower)
            score += int(ratio * 0.3)

        if seller_info["Phone Number"]:
            score += 3
        if seller_info["Email"]: # Bonus for email
            score += 2
        if seller_info["Address"]:
            score += 5

        return min(100, score)

    def scrape_search_results(self, keyword, min_leads=100):
        """
        Scrapes search results to collect leads until min_leads are collected or no more pages.
        :param keyword: The keyword used for the search.
        :param min_leads: Minimum number of leads to collect.
        :return: A list of collected leads.
        """
        page_num = 1
        leads_count = 0
        self.leads = [] # Reset leads list for a new scrape

        while leads_count < min_leads:
            self.logger.info(f"Scraping page {page_num}...")
            print(f"Scraping page {page_num}...")

            try:
                # Wait for the main container of listing cards to be present
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "listingCardContainer"))
                )
                self.logger.info("Found listingCardContainer.")
                time.sleep(random.uniform(2, 4)) # Additional wait for dynamic content within the container

                # Find all individual product cards within the container
                # Targeting div with class "card" within the "listingCardContainer"
                seller_elements = self.driver.find_elements(By.CSS_SELECTOR, ".listingCardContainer .card")
                
                if not seller_elements:
                    self.logger.warning(f"No product 'card' listings found on page {page_num}. Taking screenshot for debugging...")
                    self.driver.save_screenshot(f"search_results_page_{page_num}_no_listings.png")
                    print("No more results found or listings structure changed.")
                    break # Exit if no elements found on current page

                self.logger.info(f"Processing {len(seller_elements)} listings on page {page_num}")
                print(f"Found {len(seller_elements)} listings on this page.")

                for seller_element in seller_elements:
                    if leads_count >= min_leads:
                        break # Stop if minimum leads reached

                    time.sleep(random.uniform(0.5, 1.5)) # Shorter delay for individual element processing

                    # Extract seller information from the listing card
                    seller_info = self._extract_seller_info_from_listing(seller_element)

                    # If phone/email were NOT found on the listing card, try to get them from the profile page
                    if (not seller_info.get("Phone Number") or not seller_info.get("Email")):
                        self._extract_detailed_info_from_profile(seller_info)

                    # Calculate relevancy score
                    seller_info["Relevancy Score (%)"] = self._calculate_relevancy_score(seller_info, keyword)

                    # Add to leads list if we have at least company name or product description
                    if seller_info["Company Name"] or seller_info["Product Title/Description"]:
                        self.leads.append(sanitize_data(seller_info)) # Sanitize before adding
                        leads_count += 1
                        print(f"Collected lead {leads_count}: {seller_info['Company Name'] or seller_info['Product Title/Description']} (Score: {seller_info['Relevancy Score (%)']}%)")

                # Pagination: Try to find and click the "Next" button
                if leads_count < min_leads:
                    try:
                        next_button = WebDriverWait(self.driver, 7).until(
                            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Next') or @class='next' or @class='pagination__next'] | //span[text()='Next'] | //*[contains(@class, 'pg-next')]"))
                        )
                        next_button.click()
                        page_num += 1
                        time.sleep(random.uniform(3, 5)) # Wait for the next page to fully load
                    except (TimeoutException, NoSuchElementException):
                        self.logger.info("No more 'Next' page buttons found.")
                        print("No more pages available.")
                        break # Exit loop if no next button

            except TimeoutException:
                self.logger.error(f"Timed out waiting for elements on page {page_num}.")
                self.driver.save_screenshot(f"page_{page_num}_timeout.png")
                break
            except Exception as e:
                self.logger.error(f"Error scraping search results on page {page_num}: {e}")
                self.driver.save_screenshot(f"page_{page_num}_error.png")
                break

        self.logger.info(f"Total leads collected: {len(self.leads)}")
        print(f"Total leads collected: {len(self.leads)}")
        return self.leads

    def export_to_csv(self, filename="leads.csv"):
        """
        Exports the collected leads to a CSV file.
        :param filename: Name of the output CSV file.
        :return: True if export was successful, False otherwise.
        """
        if not self.leads:
            self.logger.warning("No leads to export.")
            print("No leads to export.")
            return False

        try:
            # Define all possible fields, ensuring 'Email' is included
            fields = [
                "Company Name", "Product Title/Description", "Price",
                "Address", "Phone Number", "Email", "Company Profile URL",
                "Relevancy Score (%)"
            ]

            # Sort leads by relevancy score (highest first)
            sorted_leads = sorted(self.leads, key=lambda x: x.get("Relevancy Score (%)", 0), reverse=True)

            df = pd.DataFrame(sorted_leads)
            # Reindex to ensure desired column order and handle missing columns if any lead doesn't have a field
            df = df.reindex(columns=fields, fill_value="")

            df.to_csv(filename, index=False, encoding='utf-8-sig')
            self.logger.info(f"Successfully exported {len(sorted_leads)} leads to {filename}")
            return True
        except Exception as e:
            self.logger.error(f"Error exporting to CSV: {e}")
            print(f"Failed to export leads to CSV: {e}")
            return False

    def close(self):
        """Closes the browser and cleans up WebDriver resources."""
        if self.driver:
            self.driver.quit()
            self.logger.info("Browser closed.")
            print("Browser closed.")

    def run(self):
        """Main entry point for the CLI, orchestrating the scraping process."""
        parser = argparse.ArgumentParser(description="IndiaMART Lead Scraper - Extract leads based on keywords")
        # Set default keyword to "Cricket Ball"
        parser.add_argument("--keyword", "-k", type=str, default="Cricket Ball", help="Product keyword to search for (default: 'Cricket Ball')")
        parser.add_argument("--output", "-o", type=str, default="leads.csv", help="Output CSV file name (default: leads.csv)")
        parser.add_argument("--min-leads", "-m", type=int, default=100, help="Minimum number of leads to collect (default: 100)")
        parser.add_argument("--headless", "-H", action="store_true", help="Run in headless mode (no browser UI)")
        args = parser.parse_args()

        # Update scraper's headless setting based on CLI arg
        self.headless = args.headless
        # Re-setup driver if headless mode changes or it wasn't set up initially
        if not self.driver or (self.headless and "--headless=new" not in self.driver.service.service_args):
             self.close() # Close existing driver if any
             self._setup_driver()


        self.logger.info("Starting IndiaMART Lead Scraper")
        print("Initializing browser...")

        try:
            print("Browser initialized successfully.")

            print("\nNavigating to IndiaMART for login...")
            login_success = self.login()

            if login_success:
                print("\nLogin successful!")
                # Keyword will now default to "Cricket Ball" if not provided via CLI
                keyword = args.keyword 
                # Removed the input prompt for keyword, as it's now defaulted or taken from CLI

                self.logger.info(f"Using keyword: {keyword}")
                print(f"\nSearching for '{keyword}'...")

                search_success = self.search_product(keyword)

                if search_success:
                    print("\nSearch successful! Starting to collect leads...")
                    leads = self.scrape_search_results(keyword, min_leads=args.min_leads)

                    if leads:
                        export_success = self.export_to_csv(filename=args.output)
                        if export_success:
                            print(f"\nScraping completed! {len(leads)} leads have been exported to {args.output}")
                        else:
                            print("\nFailed to export leads to CSV. Check logs for details.")
                    else:
                        print("\nNo leads were collected. Try a different keyword or check if the website structure has changed.")
                        self.logger.warning("No leads were collected.")
                else:
                    print("\nSearch failed. Please try again with a different keyword.")
                    self.logger.error("Search failed.")
            else:
                print("\nLogin failed. Please check your credentials and try again.")
                self.logger.error("Login failed.")

        except KeyboardInterrupt:
            self.logger.info("Operation cancelled by user.")
            print("\nOperation cancelled by user.")
        except Exception as e:
            self.logger.critical(f"A critical error occurred: {e}", exc_info=True)
            print(f"\nAn error occurred: {e}")
            print("Check the 'logs' directory for more details.")
        finally:
            self.close()

if __name__ == "__main__":
    scraper_app = IndiaMartScraper(headless=False) 
    scraper_app.run()
