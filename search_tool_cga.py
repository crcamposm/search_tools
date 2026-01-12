import argparse
import time
import random
import urllib.parse
import re
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

def random_sleep(min_seconds=0.3, max_seconds=0.8):
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
        # Use fake-useragent for a dynamic identity
        try:
            ua = UserAgent()
            # Try to use a very common desktop User Agent
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            options.add_argument(f'--user-agent={user_agent}')
        except:
            pass

        # options.add_argument("--headless=new") 
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
    
    # Check for captcha BEFORE starting
    check_for_captcha(driver)
    
    collected_results = []  # Will store dicts: {'url': ..., 'website': ...}
    
    try:
        # Check if we are on Google, otherwise go there
        if "google.com" not in driver.current_url:
            driver.get("https://www.google.com")
            check_for_captcha(driver)
        
        # Handle Consent if present (Before doing anything)
        
        # Handle Consent if present (Before doing anything)
        try:
            consent_button = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accept all') or contains(., 'I agree')]"))
            )
            random_sleep(0.3, 0.6)
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
            random_sleep(0.3, 0.8)
            search_box.send_keys(Keys.RETURN)
            
            # Check for captcha AFTER search submission
            random_sleep(0.5, 1.0)
            check_for_captcha(driver)
        except Exception as e:
            print(f"Error finding search box: {e}")
            return

        pages_checked = 0

        while len(collected_results) < num_results and pages_checked < max_pages:
            pages_checked += 1
            # print(f"Scanning page {pages_checked}...")
            
            # Wait for results to load
            random_sleep(0.3, 0.8) # Simulate reading/waiting
            
            # Random scroll
            try:
                scroll_amount = random.randint(300, 700)
                driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            except:
                pass

            wait_retries = 0
            while wait_retries < 2:
                try:
                    # Try generic result container '#rso' or 'div.g'
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "#rso, .g, #search"))
                    )
                    break # Success
                except:
                    # Check for CAPTCHA/Unusual traffic using our helper
                    if check_for_captcha(driver):
                        wait_retries += 1
                        print(f"Retrying result detection after CAPTCHA (attempt {wait_retries})...")
                        continue
                    else:
                        print(f"Timeout waiting for results on page {pages_checked}. Current Title: {driver.title}")
                        break
            
            if wait_retries >= 2:
                # If we still can't find results after solving captcha, something is wrong
                break

            # Parse current page
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Strategy: Find all links that match the prefix, then look around them for the description.
            # This is more robust than relying on div.g structure which might vary.
            
            # Find all 'a' tags first
            all_links = soup.find_all('a', href=True)
            
            found_count_on_page = 0
            
            for link in all_links:
                href = link.get('href')
                
                # Basic validation
                if not href.startswith('http'):
                    continue
                if 'google.com' in href or 'google.co' in href:
                    continue
                
                # STRICT FILTER MATCHING
                if required_prefix and not href.startswith(required_prefix):
                    # print(f"DEBUG: Skipped {href}")
                    continue
                
                # Check if URL already collected
                if any(r['url'] == href for r in collected_results):
                    continue
                    
                found_count_on_page += 1
                
                # Now try to find the description snippet.
                # Strategy: Look for the parent container (usually div.g), then find snippet elements within it
                extracted_site = None
                
                # Traverse up to find the result container (div.g or similar)
                container = None
                current = link
                for _ in range(6):
                    if current.parent:
                        current = current.parent
                        # Check if this looks like a result container
                        if current.name == 'div' and (current.get('class') and 'g' in current.get('class', [])):
                            container = current
                            break
                        # Also accept if it has enough text (fallback)
                        if len(current.get_text(" ", strip=True)) > 200:
                            container = current
                    else:
                        break
                
                # If we found a container, look for snippet text within it
                if container:
                    # Common Google snippet classes
                    snippet_selectors = ['.VwiC3b', '.yXK7lf', '.s', '.st', 'span', 'div']
                    snippet_text = ""
                    
                    for selector in snippet_selectors:
                        snippet_elem = container.select_one(selector)
                        if snippet_elem:
                            snippet_text = snippet_elem.get_text(" ", strip=True)
                            if len(snippet_text) > 50:
                                break
                    
                    # If no specific snippet found, use all container text
                    if len(snippet_text) < 50:
                        snippet_text = container.get_text(" ", strip=True)
                    
                    # Try regex match
                    match = re.search(r"This is to certify that\s+(.*?)\s+is operated by", snippet_text, re.IGNORECASE)
                    if match:
                        extracted_site = match.group(1).strip()
                
                # Store result ONLY if we found the certification pattern
                if extracted_site:
                    collected_results.append({
                        'url': href,
                        'website': extracted_site
                    })

                if len(collected_results) >= num_results:
                    break
            
            # if found_count_on_page == 0:
            #     print("DEBUG: found 0 matching links on this page.")
            
            if len(collected_results) >= num_results:
                break
            
            if len(collected_results) >= num_results:
                break
                
            # Next page
            try:
                next_button = driver.find_element(By.ID, "pnnext")
                next_button.click()
                random_sleep(0.7, 1.5) # Wait for load with random delay
            except:
                # Check for "omitted results" link (English and Spanish)
                try:
                    # Using XPath to support multiple languages
                    omitted_link = driver.find_element(By.XPATH, "//a[contains(., 'omitted results') or contains(., 'resultados omitidos')]")
                    print("Found 'omitted results' link. Clicking to show all results...")
                    omitted_link.click()
                    random_sleep(1.0, 2.5)
                    continue # Continue the outer loop to scrape the new results
                except:
                    print("No next page button or omitted results link found.")
                    break

        # Print all results together
        print("\n" + "="*60)
        print(f"Found {len(collected_results)} result(s):")
        print("="*60)
        
        if collected_results:
            for i, result in enumerate(collected_results, 1):
                print(f"\n{i}. URL: {result['url']}")
                if result['website']:
                    print(f"   {result['website']}")
                else:
                    print(f"   (No certified website pattern found)")
        else:
            print("\nNo matching results found.")
            if required_prefix:
                print("Tip: Try checking your spelling or the filter prefix.")
        
        return collected_results

    except Exception as e:
        print(f"An error occurred during search: {e}")
        return []

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search for Company Certificates on cert.gcb.cw.")
    parser.add_argument("company", nargs='*', help="The Company Name to search for (or use --file)")
    parser.add_argument("-n", "--num", type=int, default=30, help="Number of results to fetch per company (default: 30)")
    parser.add_argument("--filter", type=str, default="https://cert.gcb.cw/certificate", help="Only return URLs starting with this prefix")
    parser.add_argument("--file", type=str, help="Path to file containing company names (one per line)")
    parser.add_argument("--output-dir", type=str, default=".", help="Directory to save output files (default: current directory)")
    parser.add_argument("--attach", action="store_true", help="Attach to an already running Chrome on localhost:9222")
    parser.add_argument("--user-data-dir", type=str, help="Path to your Chrome user data directory for persistent sessions")
    parser.add_argument("--profile", type=str, default="Default", help="Chrome profile directory name (default: Default)")
    
    args = parser.parse_args()
    
    # Determine company list
    companies = []
    start_time = time.time() # Record start time
    
    if args.file:
        # Read from file
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                companies = [line.strip() for line in f if line.strip()]
            print(f"Loaded {len(companies)} companies from {args.file}")
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found.")
            exit(1)
    elif args.company:
        # Single company from command line
        companies = [" ".join(args.company)]
    else:
        print("Error: Please provide a company name or use --file to specify an input file.")
        parser.print_help()
        exit(1)
    
    # Batch processing
    all_results = {}  # {company_name: [{'url': ..., 'website': ...}, ...]}
    
    driver = None
    try:
        if args.attach:
            print("Connecting to existing Chrome on localhost:9222...")
            driver = init_driver(debugger_address="127.0.0.1:9222")
        else:
            driver = init_driver(user_data_dir=args.user_data_dir, profile_directory=args.profile)
        
        for idx, company_name in enumerate(companies, 1):
            print(f"\n[{idx}/{len(companies)}] Processing: {company_name}")
            print("=" * 60)
            
            # Construct specific query: site:cert.gcb.cw "Company Name"
            full_query = f'site:cert.gcb.cw "{company_name}"'
            
            # Run search
            results = search_web(driver, full_query, num_results=args.num, required_prefix=args.filter)
            all_results[company_name] = results if results else []
            
            print(f"Found {len(all_results[company_name])} result(s) for {company_name}")
            
            # PERIODIC PAUSE: Every 5 companies, take a longer breather to evade detection
            if idx % 5 == 0 and idx < len(companies):
                pause_time = random.uniform(5.0, 8.0)
                print(f"\n[STEALTH] Periodic breather: Sleeping for {pause_time:.1f}s...")
                time.sleep(pause_time)
            
            # Small random pause between companies if more than one
            if idx < len(companies):
                random_sleep(0.3, 0.8)
    finally:
        if driver and not args.attach:
            print("Closing Chrome...")
            driver.quit()
        elif driver:
            print("Leaving Chrome open (attached mode).")
    
    # Export to files
    import os
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    
    excel_file = os.path.join(output_dir, "certificates.xlsx")
    
    # Create Excel workbook
    from openpyxl import Workbook
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Certificates"
    
    # Set up headers
    headers = ["CGA - Licencia", "Company", "", "Website", "Certificate URL"]
    ws.append(headers)
    
    # Add data rows
    for company_name, results in all_results.items():
        if not results:
            # Add an empty row if no results found for this company
            ws.append(["CGA - Licencia", company_name, "", "", ""])
        else:
            for result in results:
                website = result['website'] if result['website'] else ""
                url = result['url']
                ws.append(["CGA - Licencia", company_name, "", website, url])
    
    # Adjust column widths
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 30
    ws.column_dimensions['C'].width = 5  # Empty column
    ws.column_dimensions['D'].width = 25
    ws.column_dimensions['E'].width = 15
    
    # Save workbook
    wb.save(excel_file)
    
    print("\n" + "=" * 60)
    print("EXPORT COMPLETE")
    print("=" * 60)
    print(f"Excel file saved to: {excel_file}")
    print(f"Total companies processed: {len(companies)}")
    
    # Calculate and print total duration
    end_time = time.time()
    duration = end_time - start_time
    minutes = int(duration // 60)
    seconds = int(duration % 60)
    print(f"Total execution time: {minutes}m {seconds}s")
    print("=" * 60)
