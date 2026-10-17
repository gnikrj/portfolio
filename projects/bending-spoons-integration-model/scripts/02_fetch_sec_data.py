"""
Fetch SEC EDGAR XBRL company facts for Bending Spoons and the acquired
companies that were US-listed before the deal (Vimeo, Eventbrite,
Brightcove), and cache the raw JSON in raw/ (gitignored).

Same fair-access User-Agent pattern as sec-o2c-profiler.
"""
from pathlib import Path
import json
import time
import urllib.request

RAW_DIR = Path(__file__).resolve().parent.parent / "raw"
USER_AGENT = "bending-spoons-integration-portfolio-project contact@example.com"


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    tickers_path = RAW_DIR / "company_tickers.json"
    if not tickers_path.exists():
        tickers_path.write_text(json.dumps(get("https://www.sec.gov/files/company_tickers.json")), encoding="utf-8")
    listing = json.loads(tickers_path.read_text(encoding="utf-8")).values()

    # Delisted targets drop out of company_tickers.json, so pin known CIKs.
    ciks = {"VMEO": "0001837686", "EB": "0001475115", "BCOV": "0001313275"}
    for row in listing:
        if row["ticker"] == "BSP":
            ciks["BSP"] = str(row["cik_str"]).zfill(10)
    print("CIKs:", ciks)

    for ticker, cik in ciks.items():
        out = RAW_DIR / f"{ticker}_companyfacts.json"
        if out.exists():
            print(f"{ticker}: cached")
            continue
        try:
            out.write_text(json.dumps(get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")), encoding="utf-8")
            print(f"{ticker}: fetched")
        except Exception as e:  # BSP is a foreign private issuer; XBRL may not exist yet
            print(f"{ticker}: no company facts ({e})")
        time.sleep(0.3)


if __name__ == "__main__":
    main()
