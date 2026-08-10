"""
Extract Durham County 2020 Census PL 94-171 population totals — county-level
and voting-district (VTD/precinct) level — from the NC redistricting PDF
reports and save clean CSVs for the analysis.

Source (public): NC General Assembly / Census Bureau 2020 PL 94-171
redistricting data reports, downloaded as:
  - PL94_171_2020_CountyPop.pdf
  - PL94_171_2020_VtdPop.pdf

Usage:
    python 01_extract_census_population.py --downloads "C:/Users/jeffr/Downloads"
"""
import argparse
import csv
import re
from pathlib import Path

from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent / "data"

COUNTY_LINE = re.compile(r"^(?P<geoid>\d{5})\s+(?P<county>[A-Za-z]+)\s+(?P<pop>[\d,]+)\s*$")
VTD_LINE = re.compile(r"^(?P<geoid>\S+)\s+Durham\s+(?P<vtd>\S+)\s+(?P<name>.+?)\s+(?P<pop>[\d,]+)\s*$")


def extract_county_population(pdf_path: Path) -> int:
    reader = PdfReader(str(pdf_path))
    for page in reader.pages:
        for line in page.extract_text().splitlines():
            m = COUNTY_LINE.match(line.strip())
            if m and m.group("county") == "Durham":
                return int(m.group("pop").replace(",", ""))
    raise ValueError("Durham County row not found in CountyPop PDF")


def extract_vtd_population(pdf_path: Path) -> list[dict]:
    reader = PdfReader(str(pdf_path))
    rows = []
    for page in reader.pages:
        text = page.extract_text()
        if "Durham" not in text:
            continue
        for line in text.splitlines():
            m = VTD_LINE.match(line.strip())
            if m:
                rows.append({
                    "geoid": m.group("geoid"),
                    "precinct_code": m.group("vtd"),
                    "precinct_name": m.group("name").strip(),
                    "total_population_2020": int(m.group("pop").replace(",", "")),
                })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--downloads", default=str(Path.home() / "Downloads"))
    args = parser.parse_args()
    downloads = Path(args.downloads)

    county_pop = extract_county_population(downloads / "PL94_171_2020_CountyPop.pdf")
    vtd_rows = extract_vtd_population(downloads / "PL94_171_2020_VtdPop.pdf")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / "durham_vtd_population_2020.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["geoid", "precinct_code", "precinct_name", "total_population_2020"])
        writer.writeheader()
        writer.writerows(vtd_rows)

    vtd_sum = sum(r["total_population_2020"] for r in vtd_rows)
    print(f"Durham County total population (2020 Census): {county_pop:,}")
    print(f"Sum of {len(vtd_rows)} VTD/precinct populations: {vtd_sum:,}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
