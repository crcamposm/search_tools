import argparse
import time
import random
import urllib.parse
import re
import difflib
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth
from fake_useragent import UserAgent

def check_for_captcha(driver):
    """Checks for captcha or 'unusual traffic' and blocks until solved."""
    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text
        if "unusual traffic" in page_text or "recaptcha" in page_text.lower():
            print("\n!!! CAPTCHA DETECTED !!!")
            print("Please solve the CAPTCHA in the opened Chrome window.")
            input("Press Enter here in the console once you have solved it and results are visible...")
            return True
    except:
        pass
    return False

def random_sleep(min_seconds=0.5, max_seconds=1.5):
    time.sleep(random.uniform(min_seconds, max_seconds))

def human_type(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.001, 0.005)) # Ultra-fast typing

def init_driver(debugger_address=None, user_data_dir=None, profile_directory="Default"):
    options = Options()
    
    if debugger_address:
        # When attaching, we ONLY want the debugger address
        options.add_experimental_option("debuggerAddress", debugger_address)
    else:
        # Default to a local profile folder if not specified
        if not user_data_dir:
            import os
            # Build a default path in the current directory
            user_data_dir = os.path.join(os.getcwd(), "chrome_profile")
            
        # Set persistent user profile
        options.add_argument(f"--user-data-dir={user_data_dir}")
        options.add_argument(f"--profile-directory={profile_directory}")
        print(f"Using persistent browser profile in: {user_data_dir}")

        # Standard options for a new browser instance
        try:
            ua = UserAgent()
            # Try to use a very common desktop User Agent
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            options.add_argument(f'--user-agent={user_agent}')
        except:
            pass

        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("start-maximized")
        
        # KEY stealth options to mimic the Antigravity browser
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Add additional flags used by stealthy browsers
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # Only apply stealth if NOT attaching to an existing browser
    if not debugger_address:
        stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )
    return driver

def search_web(driver, query, num_results=30, required_prefix=None, max_pages=10):
    if required_prefix:
        print(f"Filtering for URLs starting with: {required_prefix}")
        print("-" * 40)
    
    # Check for captcha BEFORE starting
    check_for_captcha(driver)
    
    collected_results = []  # Will store dicts: {'url': ..., 'website': ...}
    
    try:
        # Check if we are on Google, otherwise go there
        if "google.com" not in driver.current_url:
            driver.get("https://www.google.com")
            check_for_captcha(driver)
        
        # Handle Consent if present (Before doing anything)
        try:
            consent_button = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accept all') or contains(., 'I agree')]"))
            )
            random_sleep(0.5, 1.0)
            consent_button.click()
        except:
            pass # No consent button found or timeout

        # Find search box
        try:
            search_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "q"))
            )
            search_box.clear() # Clear any existing text
            human_type(search_box, query)
            random_sleep(0.5, 1.5)
            search_box.send_keys(Keys.RETURN)
            
            # Check for captcha AFTER search submission
            random_sleep(1.0, 2.0)
            check_for_captcha(driver)
        except Exception as e:
            print(f"Error finding search box: {e}")
            return
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

    # Parse results
    pages_checked = 0
    while len(collected_results) < num_results and pages_checked < max_pages:
        pages_checked += 1
        # TURBO: Redacted "Waiting for results" sleep - we just wait for the element
        
        wait_retries = 0
        while wait_retries < 2:
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#rso, .g, #search"))
                )
                break
            except:
                if check_for_captcha(driver):
                    wait_retries += 1
                    continue
                else: break

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        all_links = soup.find_all('a', href=True)
        page_urls = []
        
        for link in all_links:
            href = link.get('href')
            if not href.startswith('http') or 'google.com' in href or 'google.co' in href:
                continue
            if required_prefix and not href.startswith(required_prefix):
                continue
            if any(r['url'] == href for r in collected_results) or href in page_urls:
                continue
            page_urls.append(href)
            break # First one only

        for url in page_urls:
            if len(collected_results) >= num_results: break
            print(f"Scraping detail page: {url}")
            try:
                search_results_url = driver.current_url
                driver.get(url)
                random_sleep(1.5, 2.5)
                
                # UKGC Detail Page Scrape
                # 0. Handle Cookie Banner
                try:
                    cookie_button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accept all cookies')]"))
                    )
                    cookie_button.click()
                    random_sleep(0.5, 1.0)
                except:
                    pass

                # 0.5 Ensure we are on the Licence summary page (Fallback if landed on Premises, etc.)
                try:
                    current_url = driver.current_url
                    # Extract ID: handles /detail/123 or /detail/premises/123
                    id_match = re.search(r'/detail/(?:[^/]+/)?(\d+)', current_url)
                    if id_match:
                        business_id = id_match.group(1)
                        # If the URL is longer than the base detail URL, it's a sub-page
                        base_detail_url = f"https://www.gamblingcommission.gov.uk/public-register/business/detail/{business_id}"
                        if current_url.rstrip('/') != base_detail_url:
                            print(f"Landed on sub-page, jumping to Licence summary: {base_detail_url}")
                            driver.get(base_detail_url)
                            random_sleep(1.0, 2.0)
                    else:
                        # Fallback click if regex fails
                        summary_tab = driver.find_elements(By.XPATH, "//a[contains(text(), 'Licence summary')]")
                        if summary_tab:
                            driver.execute_script("arguments[0].click();", summary_tab[0])
                            random_sleep(1.0, 2.0)
                except Exception as e:
                    print(f"Fallback navigation to summary failed: {e}")

                detail_soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # 1. Extract Statuses from Summary Table
                status_counts = {}
                summary_table = detail_soup.find('table', class_='govuk-table')
                if not summary_table:
                    summary_table = detail_soup.find('table') # Fallback
                
                if summary_table:
                    summary_rows = summary_table.select('tbody tr')
                    for row in summary_rows:
                        tds = row.find_all('td')
                        if len(tds) >= 2:
                            status_text = tds[1].get_text(strip=True)
                            if status_text:
                                status_counts[status_text] = status_counts.get(status_text, 0) + 1
                
                # Sort for consistent display
                sorted_statuses = sorted(status_counts.items(), key=lambda x: x[1], reverse=True)
                formatted_status = ", ".join([f"{count}x {status}" for status, count in sorted_statuses])
                if not formatted_status:
                    formatted_status = "No status found"
                print(f"Extracted formatted status: {formatted_status}")
                print("-" * 40)
                
                # 1.5 Extract Trading Names for Brand Mapping
                trading_names = []
                try:
                    current_url = driver.current_url
                    business_id = current_url.split('/')[-1]
                    if business_id.isdigit():
                        trading_url = f"https://www.gamblingcommission.gov.uk/public-register/business/detail/trading-names/{business_id}"
                        print(f"Turbo: Fetching trading names from: {trading_url}")
                        driver.get(trading_url)
                        random_sleep(0.8, 1.5)
                        
                        trading_soup = BeautifulSoup(driver.page_source, 'html.parser')
                        trading_table = trading_soup.find('table', class_='govuk-table')
                        if trading_table:
                            rows = trading_table.select('tbody tr')
                            for r in rows:
                                tds = r.find_all('td')
                                if tds:
                                    name = tds[0].get_text(strip=True)
                                    if name:
                                        trading_names.append(name.lower())
                        print(f"Found {len(trading_names)} total trading names (including inactive).")
                        print("-" * 40)
                        # Return to summary to get ID correctly if needed, or just stay on detail/trading-names
                        # The domain logic below also uses the ID
                except Exception as e:
                    print(f"Could not extract trading names: {e}")

                # 2. Extract Domains (TURBO: Direct URL Navigation)
                websites = []
                try:
                    # Extract business ID from current URL
                    # Format: .../detail/39372 or .../detail/domain-names/39372
                    current_url = driver.current_url
                    business_id = current_url.split('/')[-1]
                    
                    if business_id.isdigit():
                        domain_url = f"https://www.gamblingcommission.gov.uk/public-register/business/detail/domain-names/{business_id}"
                        print(f"Turbo: Jumping directly to domains: {domain_url}")
                        driver.get(domain_url)
                    else:
                        # Fallback to clicking if ID extraction fails
                        print("Clicking 'Domain names' tab (fallback)...")
                        domain_link_xpath = "//a[contains(@class, 'gc-vertical-nav__link') and contains(normalize-space(.), 'Domain names')]"
                        domain_button = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, domain_link_xpath))
                        )
                        driver.execute_script("arguments[0].click();", domain_button)
                    
                    random_sleep(1.0, 1.8) # Wait for page/tables load
                    
                    # 2.5 Parse domains (Handle cases with zero domains)
                    try:
                        # Check if "No domain names have been recorded" message exists
                        no_domains_text = "No domain names have been recorded for this business"
                        if no_domains_text in driver.page_source:
                            print("No domain names recorded for this business.")
                        else:
                            # Only wait for tables if the "No domain names" message is NOT present
                            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, "govuk-table")))
                            
                            domain_soup = BeautifulSoup(driver.page_source, 'html.parser')
                            all_domain_tables = domain_soup.find_all('table', class_='govuk-table')
                            if not all_domain_tables:
                                all_domain_tables = domain_soup.find_all('table') 
                                
                            for table in all_domain_tables:
                                domain_rows = table.select('tbody tr')
                                for row in domain_rows:
                                    tds = row.find_all('td')
                                    if len(tds) >= 2:
                                        domain_name = tds[0].get_text(strip=True)
                                        status_val = tds[1].get_text(strip=True)
                                        if domain_name and "." in domain_name:
                                            # Best Match Logic
                                            best_brand = ""
                                            clean_domain = domain_name.split('/')[0].lower()
                                            # Remove TLDs for matching
                                            match_domain = re.sub(r'\.(com|co\.uk|net|org|it|es|de|bet)$', '', clean_domain)
                                            match_domain = match_domain.replace('www.', '').replace('.', '')
                                            
                                            if trading_names:
                                                # 1. Substring match
                                                for brand in trading_names:
                                                    clean_brand = brand.replace(' ', '')
                                                    if clean_brand in match_domain or match_domain in clean_brand:
                                                        best_brand = brand.title()
                                                        break
                                                
                                                # 2. Fuzzy match if no substring match
                                                if not best_brand:
                                                    matches = difflib.get_close_matches(match_domain, trading_names, n=1, cutoff=0.6)
                                                    if matches:
                                                        best_brand = matches[0].title()
                                                    else:
                                                        best_brand = ""
                                            
                                            websites.append({
                                                'name': domain_name, 
                                                'status': status_val,
                                                'brand': best_brand
                                            })
                    except Exception as e:
                        # Only print the short error to keep the console clean
                        print(f"Note: Could not parse domains (usually means none listed).")
                    print(f"Found {len(websites)} domain names total.")
                    print("-" * 40)
                except Exception as e:
                    print(f"Could not extract domains: {e}")
                
                # website_str is now a list of dicts, but search_web expects a string or similar
                # Let's adjust how we return results to handle domain statuses
                collected_results.append({
                    'url': url,
                    'websites': websites, # List of {'name': ..., 'status': ...}
                    'status': formatted_status
                })
                
                driver.get(search_results_url)
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "q")))
            except Exception as e:
                print(f"Error: {e}")
        
        if len(collected_results) >= num_results: break
        
        # Next page (simplified for core logic)
        try:
            next_button = driver.find_element(By.ID, "pnnext")
            next_button.click()
        except: break

    return collected_results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search for Company Licences on the UK Gambling Commission register.")
    parser.add_argument("company", nargs='*', help="The Company Name to search for (or use --file)")
    parser.add_argument("-n", "--num", type=int, default=1, help="Number of results to fetch per company (default: 1)")
    parser.add_argument("--filter", type=str, default="https://www.gamblingcommission.gov.uk/public-register/business/detail", help="Only return URLs starting with this prefix")
    parser.add_argument("--file", type=str, help="Path to file containing company names (one per line)")
    parser.add_argument("--output-dir", type=str, default=".", help="Directory to save output files (default: current directory)")
    parser.add_argument("--attach", action="store_true", help="Attach to an already running Chrome on localhost:9222")
    parser.add_argument("--user-data-dir", type=str, help="Path to your Chrome user data directory")
    parser.add_argument("--profile", type=str, default="Default", help="Chrome profile directory name")
    
    args = parser.parse_args()
    companies = []
    start_time = time.time()
    
    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            companies = [line.strip() for line in f if line.strip()]
    elif args.company:
        companies = [" ".join(args.company)]
    else:
        parser.print_help()
        exit(1)
    
    all_results = {}
    driver = None
    try:
        if args.attach:
            driver = init_driver(debugger_address="127.0.0.1:9222")
        else:
            driver = init_driver(user_data_dir=args.user_data_dir, profile_directory=args.profile)
        
        for idx, company_name in enumerate(companies, 1):
            print(f"[{idx}/{len(companies)}] Processing: {company_name}")
            print("-" * 40)
            full_query = f'site:gamblingcommission.gov.uk/public-register/business/detail "{company_name}"'
            results = search_web(driver, full_query, num_results=args.num, required_prefix=args.filter)
            all_results[company_name] = results
    finally:
        if driver and not args.attach: driver.quit()

    import os
    from openpyxl import Workbook
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    excel_file = os.path.join(output_dir, "certificates.xlsx")
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Certificates"
    headers = ["UKGC - Licencia", "Company", "Brand", "Website", "URL Status", "Certificate URL", "Status"]
    ws.append(headers)
    
    for company_name, results in all_results.items():
        if not results:
            ws.append(["UKGC - Licencia", company_name, "", "", "", "", ""])
        else:
            for result in results:
                url = result['url']
                websites_list = result.get('websites', [])
                global_status = result.get('status', '')
                
                if websites_list:
                    for web_dict in websites_list:
                        ws.append([
                            "UKGC - Licencia", 
                            company_name, 
                            web_dict.get('brand', ''), 
                            web_dict['name'], 
                            web_dict['status'], 
                            url, 
                            global_status
                        ])
                else:
                    ws.append(["UKGC - Licencia", company_name, "", "", "", url, global_status])
    
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 30
    ws.column_dimensions['C'].width = 20
    ws.column_dimensions['D'].width = 25
    ws.column_dimensions['E'].width = 15 # URL Status
    ws.column_dimensions['F'].width = 15 # Certificate URL
    ws.column_dimensions['G'].width = 30 # Status
    wb.save(excel_file)
    print(f"Export complete: {excel_file}")
