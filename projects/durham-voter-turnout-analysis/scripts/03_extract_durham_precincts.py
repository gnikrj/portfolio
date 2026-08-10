"""
Filter the statewide NC precinct boundary shapefile (public download from
ncsbe.gov) down to Durham County precincts only, and save as GeoJSON —
small enough to commit, used for choropleth maps in the analysis.

Usage:
    python 03_extract_durham_precincts.py --downloads "C:/Users/jeffr/Downloads"
"""
import argparse
import io
import json
import zipfile
from pathlib import Path

import shapefile  # pyshp

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent / "data"

ZIP_NAME = "SBE_PRECINCTS_20251212.zip"
SHP_BASE = "SBE_PRECINCTS_20251212"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--downloads", default=str(Path.home() / "Downloads"))
    parser.add_argument("--county", default="DURHAM")
    args = parser.parse_args()
    downloads = Path(args.downloads)

    with zipfile.ZipFile(downloads / ZIP_NAME) as zf:
        shp = io.BytesIO(zf.read(f"{SHP_BASE}.shp"))
        dbf = io.BytesIO(zf.read(f"{SHP_BASE}.dbf"))
        shx = io.BytesIO(zf.read(f"{SHP_BASE}.shx"))
        reader = shapefile.Reader(shp=shp, dbf=dbf, shx=shx)

        features = []
        for sr in reader.iterShapeRecords():
            rec = sr.record.as_dict()
            if rec.get("county_nam", "").strip().upper() != args.county:
                continue
            features.append({
                "type": "Feature",
                "properties": {
                    "precinct_code": rec.get("prec_id", "").strip(),
                    "precinct_name": rec.get("enr_desc", "").strip(),
                    "county": rec.get("county_nam", "").strip(),
                },
                "geometry": sr.shape.__geo_interface__,
            })

    geojson = {"type": "FeatureCollection", "features": features}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / "durham_precincts.geojson"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(geojson, f)

    print(f"Wrote {len(features)} Durham precinct features to {out_path}")


if __name__ == "__main__":
    main()
