import argparse
import time
import os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException

from webdriver_manager.chrome import ChromeDriverManager
from openpyxl import Workbook

URL = "https://www.gluecksspiel-behoerde.de/de/fuer-spielende/uebersicht-erlaubter-anbieter-whitelist"
BATCH_SIZE = 15


def init_driver(attach=False):
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")

    if attach:
        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        return webdriver.Chrome(options=options)

    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )


def safe_click(driver, element):
    try:
        element.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", element)


def export_excel(rows, output_dir, export_number):
    os.makedirs(output_dir, exist_ok=True)
    filename = f"ggl_whitelist_{export_number}.xlsx"
    path = os.path.join(output_dir, filename)

    wb = Workbook()
    ws = wb.active
    ws.title = "GGL Whitelist"
    ws.append(["Company", "Website"])

    for row in rows:
        ws.append(row)

    ws.column_dimensions["A"].width = 45
    ws.column_dimensions["B"].width = 35

    wb.save(path)
    print(f"✔ Exported → {path}")


def scrape_ggl(driver, output_dir):
    wait = WebDriverWait(driver, 20)
    driver.get(URL)

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul[uk-accordion] > li")))

    results = []
    export_count = 0
    companies_processed = 0

    items = driver.find_elements(By.CSS_SELECTOR, "ul[uk-accordion] > li")
    total = len(items)

    for i in range(total):
        items = driver.find_elements(By.CSS_SELECTOR, "ul[uk-accordion] > li")
        li = items[i]

        title = li.find_element(By.CSS_SELECTOR, "a.uk-accordion-title")
        company = title.text.strip()

        print(f"[{i+1}/{total}] {company}")

        # Open accordion safely
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", title
        )
        time.sleep(0.15)
        safe_click(driver, title)

        wait.until(lambda d: "uk-open" in li.get_attribute("class"))

        content = li.find_element(By.CSS_SELECTOR, "div.uk-accordion-content")

        # Extract ONLY real websites
        urls = set()
        spans = content.find_elements(
            By.CSS_SELECTOR,
            "div.el-title span.ggl-wl-check-to-highlight"
        )

        for span in spans:
            domain = span.text.strip().lower()
            if domain and "." in domain:
                urls.add(domain)

        if urls:
            for u in urls:
                results.append((company, u))
        else:
            results.append((company, ""))

        # Close accordion safely
        safe_click(driver, title)
        time.sleep(0.2)

        companies_processed += 1

        # Checkpoint export
        if companies_processed % BATCH_SIZE == 0:
            export_count += 1
            export_excel(results, output_dir, export_count)

    # Final fallback export
    if companies_processed % BATCH_SIZE != 0:
        export_count += 1
        export_excel(results, output_dir, export_count)


def main():
    parser = argparse.ArgumentParser(
        description="GGL Whitelist Scraper (checkpointed, UIkit-safe)"
    )
    parser.add_argument(
        "--output",
        default=".",
        help="Output folder (default: current directory)"
    )
    parser.add_argument(
        "--attach",
        action="store_true",
        help="Attach to Chrome on 127.0.0.1:9222"
    )

    args = parser.parse_args()

    driver = init_driver(attach=args.attach)
    try:
        scrape_ggl(driver, args.output)
        print("\n✔ Scraping completed successfully.")
    finally:
        if not args.attach:
            driver.quit()


if __name__ == "__main__":
    main()
