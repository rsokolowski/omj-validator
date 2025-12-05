#!/usr/bin/env python3
"""
Script to download OMJ/OMG competition tasks from https://omj.edu.pl/zadania
Focuses on etap 2 (second stage) tasks and organizes them by year.

Directory structure: <year>/<etap>/<file>.pdf
Example: 2024/etap2/20omj-2etap.pdf
"""

import json
import requests
from pathlib import Path
from typing import NamedTuple

BASE_URL = "https://omj.edu.pl/uploads/attachments"
OUTPUT_DIR = Path("tasks")


class Edition(NamedTuple):
    """Represents an OMJ/OMG edition."""
    number: int          # Roman numeral as integer (e.g., 20 for XX)
    year_start: int      # Starting year of the edition (e.g., 2024 for 2024/25)
    is_omj: bool         # True for OMJ (XII+), False for OMG (I-XI)


# Edition mappings: edition number -> (start_year, is_omj)
# OMJ editions (XII-XXI): 2016/17 - 2025/26
# OMG editions (I-XI): 2005/06 - 2015/16
EDITIONS = [
    Edition(21, 2025, True),
    Edition(20, 2024, True),
    Edition(19, 2023, True),
    Edition(18, 2022, True),
    Edition(17, 2021, True),
    Edition(16, 2020, True),
    Edition(15, 2019, True),
    Edition(14, 2018, True),
    Edition(13, 2017, True),
    Edition(12, 2016, True),
    Edition(11, 2015, False),
    Edition(10, 2014, False),
    Edition(9, 2013, False),
    Edition(8, 2012, False),
    Edition(7, 2011, False),
    Edition(6, 2010, False),
    Edition(5, 2009, False),
    Edition(4, 2008, False),
    Edition(3, 2007, False),
    Edition(2, 2006, False),
    Edition(1, 2005, False),
]


def get_etap2_filenames(edition: Edition) -> list[str]:
    """
    Generate possible filenames for etap 2 files based on edition.
    Returns list of potential filenames to try.
    """
    filenames = []
    num = edition.number
    # Year when etap 2 takes place (second half of school year)
    etap2_year = edition.year_start + 1
    etap2_year_suffix = str(etap2_year)[-2:]

    if edition.is_omj:
        prefix = f"{num}omj"

        if num >= 18:
            # Modern OMJ naming (editions XVIII-XXI, 2022+)
            # Uses edition number prefix: 18omj-2etap.pdf, 19omj-2etap.pdf, etc.
            filenames.extend([
                f"{prefix}-2etap.pdf",
                f"{prefix}-2etap-zad.pdf",
            ])
            filenames.extend([
                f"{prefix}-2r.pdf",
                f"{prefix}-2etap-r.pdf",
                f"{prefix}-2etap-rr.pdf",
            ])
            filenames.extend([
                f"{prefix}-2etap-st.pdf",
                f"{prefix}-2st.pdf",
            ])
        else:
            # Earlier OMJ naming (editions XII-XVII, 2016-2021)
            # Uses calendar year of etap 2: 2etap17.pdf, 2etap18.pdf, etc.
            filenames.extend([
                f"2etap{etap2_year_suffix}.pdf",
            ])
            filenames.extend([
                f"2etap{etap2_year_suffix}r.pdf",
                f"2etap{etap2_year_suffix}-r.pdf",
            ])
            filenames.extend([
                f"2etap{etap2_year_suffix}st.pdf",
                f"2etap{etap2_year_suffix}-st.pdf",
            ])
    else:
        # OMG naming conventions (editions I-XI, 2005-2015)
        # Edition number with leading zero (e.g., 01, 02, ... 11)
        edition_num_padded = f"{num:02d}"

        # Different patterns used across OMG editions:
        # - Early editions (I-V): omgXX_2.pdf where XX is edition number
        # - Later editions (VI-XI): 2etapYY.pdf where YY is calendar year of etap 2
        filenames.extend([
            f"2etap{etap2_year_suffix}.pdf",       # e.g., 2etap15.pdf (for 2014/15 edition)
            f"omg{edition_num_padded}_2.pdf",       # e.g., omg02_2.pdf (edition II)
        ])

        # Solutions
        filenames.extend([
            f"2etap{etap2_year_suffix}r.pdf",
            f"2etap{etap2_year_suffix}-r.pdf",
            f"omg{edition_num_padded}_2r.pdf",       # e.g., omg02_2r.pdf
        ])

        # Statistics
        filenames.extend([
            f"2etap{etap2_year_suffix}st.pdf",
            f"2etap{etap2_year_suffix}-st.pdf",
        ])

    return filenames


def download_file(url: str, output_path: Path) -> bool:
    """
    Download a file from URL to the specified path.
    Returns True if successful, False otherwise.
    """
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            # Verify it's actually a PDF
            if response.content[:4] == b'%PDF':
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(response.content)
                return True
        return False
    except requests.RequestException as e:
        print(f"  Error downloading {url}: {e}")
        return False


def classify_file(filename: str) -> str:
    """Classify a file as tasks, solutions, or statistics based on filename."""
    lower = filename.lower()
    if lower.endswith("st.pdf") or "-st." in lower:
        return "statistics"
    if "r.pdf" in lower or "-r." in lower or "rr.pdf" in lower:
        return "solutions"
    return "tasks"


def download_etap2_for_edition(edition: Edition, output_dir: Path) -> list[str]:
    """
    Download all etap 2 files for a given edition.
    Returns list of successfully downloaded files.
    """
    year_dir = output_dir / str(edition.year_start) / "etap2"
    downloaded = []

    filenames = get_etap2_filenames(edition)

    for filename in filenames:
        url = f"{BASE_URL}/{filename}"
        output_path = year_dir / filename

        # Skip if already downloaded
        if output_path.exists():
            print(f"  Already exists: {filename}")
            downloaded.append(str(output_path))
            continue

        if download_file(url, output_path):
            print(f"  Downloaded: {filename}")
            downloaded.append(str(output_path))

    return downloaded


def generate_index(output_dir: Path) -> dict:
    """Generate index mapping years to their PDF files."""
    index = {}

    for year_dir in sorted(output_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        year = year_dir.name

        for etap_dir in sorted(year_dir.iterdir()):
            if not etap_dir.is_dir():
                continue
            etap = etap_dir.name

            files = {"tasks": None, "solutions": None, "statistics": None}
            for pdf in sorted(etap_dir.glob("*.pdf")):
                file_type = classify_file(pdf.name)
                if files[file_type] is None:
                    files[file_type] = str(pdf)

            # Remove None values
            files = {k: v for k, v in files.items() if v is not None}

            if files:
                if year not in index:
                    index[year] = {}
                index[year][etap] = files

    return index


def main():
    """Main function to download all etap 2 tasks."""
    print("OMJ/OMG Task Downloader - Etap 2")
    print("=" * 40)

    output_dir = OUTPUT_DIR
    output_dir.mkdir(exist_ok=True)

    total_downloaded = 0

    for edition in EDITIONS:
        comp_type = "OMJ" if edition.is_omj else "OMG"
        print(f"\n{comp_type} Edition {edition.number} ({edition.year_start}/{edition.year_start + 1 - 2000}):")

        downloaded = download_etap2_for_edition(edition, output_dir)
        total_downloaded += len(downloaded)

        if not downloaded:
            print("  No files found for this edition")

    # Generate index JSON
    index = generate_index(output_dir)
    index_path = Path("tasks_index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 40}")
    print(f"Total files downloaded: {total_downloaded}")
    print(f"Files saved to: {output_dir.absolute()}")
    print(f"Index saved to: {index_path.absolute()}")


if __name__ == "__main__":
    main()
