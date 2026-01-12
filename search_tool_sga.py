import argparse
import time
import os
import re

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from webdriver_manager.chrome import ChromeDriverManager
from openpyxl import Workbook

URL = "https://www.spillemyndigheden.dk/tilladelsesindehavere/print"
BATCH_SIZE = 15


def init_driver(attach=False):
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")

    if attach:
        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        return webdriver.Chrome(options=options)

    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )


def export_excel(rows, output_dir, export_number):
    os.makedirs(output_dir, exist_ok=True)
    filename = f"spillemyndigheden_whitelist_{export_number}.xlsx"
    path = os.path.join(output_dir, filename)

    wb = Workbook()
    ws = wb.active
    ws.title = "Spillemyndigheden"

    ws.append(["Company", "Website"])

    for row in rows:
        ws.append(row)

    ws.column_dimensions["A"].width = 45
    ws.column_dimensions["B"].width = 40

    wb.save(path)
    print(f"✔ Exported → {path}")


def extract_domains_from_text(text):
    """
    Extract domains from plain text (fallback).
    """
    if not text:
        return set()

    pattern = r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b"
    return set(m.group(0).lower() for m in re.finditer(pattern, text))


def scrape_spillemyndigheden(driver, output_dir):
    wait = WebDriverWait(driver, 20)
    driver.get(URL)

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table")))

    rows_data = []
    export_count = 0
    companies_processed = 0

    table_rows = driver.find_elements(By.CSS_SELECTOR, "table tr")

    # Skip header row
    for row in table_rows[1:]:
        cells = row.find_elements(By.TAG_NAME, "td")
        if not cells:
            continue

        company = cells[0].text.strip()
        websites_cell = cells[3]

        urls = set()

        # 1️⃣ Real links (if present)
        links = websites_cell.find_elements(By.CSS_SELECTOR, "a[href]")
        for a in links:
            href = a.get_attribute("href")
            if href:
                clean = (
                    href.replace("https://", "")
                        .replace("http://", "")
                        .replace("www.", "")
                        .rstrip("/")
                        .lower()
                )
                urls.add(clean)

        # 2️⃣ Plain text, comma-separated domains
        raw_text = websites_cell.text.strip()
        if raw_text:
            parts = [p.strip() for p in raw_text.split(",")]
            for part in parts:
                clean = (
                    part.replace("https://", "")
                        .replace("http://", "")
                        .replace("www.", "")
                        .rstrip("/")
                        .lower()
                )
                if "." in clean:
                    urls.add(clean)

        if urls:
            for u in urls:
                rows_data.append((company, u))
        else:
            rows_data.append((company, ""))

        companies_processed += 1
        print(f"[{companies_processed}] {company}")

        if companies_processed % BATCH_SIZE == 0:
            export_count += 1
            export_excel(rows_data, output_dir, export_count)

    # Final fallback export
    if companies_processed % BATCH_SIZE != 0:
        export_count += 1
        export_excel(rows_data, output_dir, export_count)


def main():
    parser = argparse.ArgumentParser(
        description="Spillemyndigheden Licence Holder Scraper"
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
        scrape_spillemyndigheden(driver, args.output)
        print("\n✔ Scraping completed successfully.")
    finally:
        if not args.attach:
            driver.quit()


if __name__ == "__main__":
    main()
