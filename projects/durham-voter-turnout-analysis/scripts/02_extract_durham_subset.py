"""
Stream the statewide NC voter registration + voter history files (public
downloads from ncsbe.gov) directly out of their ZIPs, keep only Durham
County rows, and keep only the columns needed for aggregate precinct-level
analysis (no name/address/phone fields are retained, even locally).

Output goes to raw/ which is gitignored — these are still not committed,
even filtered to one county, because they remain individual-level records.
Only the aggregated outputs computed downstream get committed.

Usage:
    python 02_extract_durham_subset.py --downloads "C:/Users/jeffr/Downloads"
"""
import argparse
import csv
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE.parent / "raw"

VOTER_KEEP_COLS = [
    "county_desc", "ncid", "voter_reg_num", "status_cd", "voter_status_desc",
    "reason_cd", "voter_status_reason_desc", "race_code", "ethnic_code",
    "party_cd", "gender_code", "birth_year", "age_at_year_end", "registr_dt",
    "precinct_abbrv", "precinct_desc", "municipality_desc", "ward_desc",
    "cong_dist_abbrv", "nc_senate_abbrv", "nc_house_abbrv",
]

HISTORY_KEEP_COLS = [
    "county_desc", "ncid", "voter_reg_num", "election_lbl", "election_desc",
    "voting_method", "voted_party_cd", "pct_label", "pct_description",
    "voted_county_desc",
]


def stream_filter(zip_path: Path, member: str, keep_cols: list[str], county: str, out_path: Path):
    count_in = 0
    count_out = 0
    with zipfile.ZipFile(zip_path) as z, z.open(member) as raw:
        text = (line.decode("latin-1") for line in raw)
        reader = csv.DictReader(text, delimiter="\t", quotechar='"')
        with out_path.open("w", newline="", encoding="utf-8") as out_f:
            writer = csv.DictWriter(out_f, fieldnames=keep_cols)
            writer.writeheader()
            for row in reader:
                count_in += 1
                if row.get("county_desc", "").strip().upper() == county:
                    writer.writerow({k: row.get(k, "") for k in keep_cols})
                    count_out += 1
                if count_in % 1_000_000 == 0:
                    print(f"  ...scanned {count_in:,} rows, kept {count_out:,}")
    print(f"Done: {member} -> {out_path.name}  (scanned {count_in:,}, kept {count_out:,})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--downloads", default=str(Path.home() / "Downloads"))
    parser.add_argument("--county", default="DURHAM")
    args = parser.parse_args()
    downloads = Path(args.downloads)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("Filtering voter registration file...")
    stream_filter(
        downloads / "ncvoter_Statewide.zip", "ncvoter_Statewide.txt",
        VOTER_KEEP_COLS, args.county, RAW_DIR / "durham_voter_registration.csv",
    )

    print("Filtering voter history file...")
    stream_filter(
        downloads / "ncvhis_Statewide.zip", "ncvhis_Statewide.txt",
        HISTORY_KEEP_COLS, args.county, RAW_DIR / "durham_voter_history.csv",
    )


if __name__ == "__main__":
    main()
