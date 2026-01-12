import argparse
import re
from playwright.sync_api import sync_playwright
from openpyxl import Workbook


URL = "https://kansspelautoriteit.nl/veilig-spelen/kansspelwijzer/"


def scrape_kansspelwijzer(attach=False):
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not attach,
            slow_mo=50 if attach else 0
        )
        context = browser.new_context()
        page = context.new_page()

        print("Loading page...")
        page.goto(URL, timeout=60000, wait_until="domcontentloaded")

        page.wait_for_selector(".grid-element", timeout=60000)

        cards = page.locator(".grid-element")
        total = cards.count()
        print(f"Found {total} companies")

        for i in range(total):
            card = cards.nth(i)

            name_el = card.locator(".grid-title a.siteLink")
            if name_el.count() == 0:
                continue

            company_name = name_el.first.text_content().strip()

            product_items = card.locator("ul.products a").all_text_contents()

            valid_domains = []

            for item in product_items:
                item = item.strip().lower()

                # STRICT real .nl domain check
                if re.fullmatch(r"[a-z0-9.-]+\.nl", item):
                    valid_domains.append(item)

            if valid_domains:
                for domain in valid_domains:
                    rows.append((company_name, domain))
            else:
                # IMPORTANT: keep company even if no .nl sites
                rows.append((company_name, ""))

        browser.close()

    return rows


def export_xlsx(rows, filename):
    wb = Workbook()
    ws = wb.active
    ws.title = "Kansspelwijzer"

    ws.append(["Company", "Website"])

    for company, site in rows:
        ws.append([company, site])

    wb.save(filename)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attach", action="store_true", help="Run with visible browser")
    args = parser.parse_args()

    rows = scrape_kansspelwijzer(attach=args.attach)

    if not rows:
        raise RuntimeError("Scrape finished but returned 0 rows")

    export_xlsx(rows, "KSA_Kansspelwijzer_NL_Websites.xlsx")
    print(f"Exported {len(rows)} rows → KSA_Kansspelwijzer_NL_Websites.xlsx")


if __name__ == "__main__":
    main()
