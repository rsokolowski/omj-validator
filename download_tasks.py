#!/usr/bin/env python3
"""
Script to download OMJ/OMG competition tasks from https://omj.edu.pl/zadania
Downloads all three stages (etap1, etap2, etap3/finals) and organizes them by year.

Directory structure: <year>/<etap>/<file>.pdf
Example: 2024/etap2/20omj-2etap.pdf

Usage:
    python download_tasks.py              # Download etap2 only (default)
    python download_tasks.py --etap 3     # Download etap3 only
    python download_tasks.py --all-etaps  # Download all etaps
"""

import argparse
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


def get_etap3_filenames(edition: Edition) -> list[str]:
    """
    Generate possible filenames for etap 3 (finals) files based on edition.
    Returns list of potential filenames to try.
    """
    filenames = []
    num = edition.number
    # Year when etap 3 takes place (second half of school year)
    etap3_year = edition.year_start + 1
    etap3_year_suffix = str(etap3_year)[-2:]

    if edition.is_omj:
        prefix = f"{num}omj"

        if num >= 18:
            # Modern OMJ naming (editions XVIII-XXI, 2022+)
            filenames.extend([
                f"{prefix}-3etap.pdf",
                f"{prefix}-3etap-zad.pdf",
            ])
            filenames.extend([
                f"{prefix}-3r.pdf",
                f"{prefix}-3etap-r.pdf",
                f"{prefix}-3etap-rr.pdf",
            ])
            filenames.extend([
                f"{prefix}-3etap-st.pdf",
                f"{prefix}-3st.pdf",
            ])
        else:
            # Earlier OMJ naming (editions XII-XVII, 2016-2021)
            filenames.extend([
                f"3etap{etap3_year_suffix}.pdf",
            ])
            filenames.extend([
                f"3etap{etap3_year_suffix}r.pdf",
                f"3etap{etap3_year_suffix}-r.pdf",
            ])
            filenames.extend([
                f"3etap{etap3_year_suffix}st.pdf",
                f"3etap{etap3_year_suffix}-st.pdf",
            ])
    else:
        # OMG naming conventions (editions I-XI, 2005-2015)
        edition_num_padded = f"{num:02d}"

        # Different patterns used across OMG editions
        filenames.extend([
            f"3etap{etap3_year_suffix}.pdf",       # e.g., 3etap16.pdf
            f"omg{edition_num_padded}_3.pdf",       # e.g., omg02_3.pdf
        ])

        # Solutions
        filenames.extend([
            f"3etap{etap3_year_suffix}r.pdf",
            f"3etap{etap3_year_suffix}-r.pdf",
            f"omg{edition_num_padded}_3r.pdf",
        ])

        # Statistics (various naming across years)
        filenames.extend([
            f"3etap{etap3_year_suffix}st.pdf",
            f"3etap{etap3_year_suffix}-st.pdf",
            f"final_{etap3_year}_staty.pdf",
            f"final_{etap3_year - 1}-3.pdf",
            f"staty_3etap.pdf",
            f"staty_3etap_viii.pdf",
        ])

    return filenames


def get_etap1_filenames(edition: Edition) -> list[str]:
    """
    Generate possible filenames for etap 1 files based on edition.
    Returns list of potential filenames to try.
    """
    filenames = []
    num = edition.number
    # Year when etap 1 takes place (first half of school year)
    etap1_year = edition.year_start
    etap1_year_suffix = str(etap1_year)[-2:]

    if edition.is_omj:
        prefix = f"{num}omj"

        if num >= 18:
            # Modern OMJ naming
            filenames.extend([
                f"{prefix}-1etap.pdf",
                f"{prefix}-1etap-zad.pdf",
            ])
            filenames.extend([
                f"{prefix}-1r.pdf",
                f"{prefix}-1etap-r.pdf",
            ])
            filenames.extend([
                f"{prefix}-1etap-st.pdf",
                f"{prefix}-1st.pdf",
            ])
        else:
            # Earlier OMJ naming
            filenames.extend([
                f"1etap{etap1_year_suffix}.pdf",
            ])
            filenames.extend([
                f"1etap{etap1_year_suffix}r.pdf",
                f"1etap{etap1_year_suffix}-r.pdf",
            ])
            filenames.extend([
                f"1etap{etap1_year_suffix}st.pdf",
                f"1etap{etap1_year_suffix}-st.pdf",
            ])
    else:
        # OMG naming
        edition_num_padded = f"{num:02d}"

        filenames.extend([
            f"1etap{etap1_year_suffix}.pdf",
            f"omg{edition_num_padded}_1.pdf",
        ])
        filenames.extend([
            f"1etap{etap1_year_suffix}r.pdf",
            f"1etap{etap1_year_suffix}-r.pdf",
            f"omg{edition_num_padded}_1r.pdf",
        ])
        filenames.extend([
            f"1etap{etap1_year_suffix}st.pdf",
            f"1etap{etap1_year_suffix}-st.pdf",
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


def download_etap_for_edition(edition: Edition, output_dir: Path, etap: int) -> list[str]:
    """
    Download all files for a given edition and etap.
    Returns list of successfully downloaded files.
    """
    year_dir = output_dir / str(edition.year_start) / f"etap{etap}"
    downloaded = []

    if etap == 1:
        filenames = get_etap1_filenames(edition)
    elif etap == 2:
        filenames = get_etap2_filenames(edition)
    elif etap == 3:
        filenames = get_etap3_filenames(edition)
    else:
        return []

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


def download_etap2_for_edition(edition: Edition, output_dir: Path) -> list[str]:
    """
    Download all etap 2 files for a given edition.
    Returns list of successfully downloaded files.
    """
    return download_etap_for_edition(edition, output_dir, 2)


def main():
    """Main function to download OMJ/OMG tasks."""
    parser = argparse.ArgumentParser(description="Download OMJ/OMG competition tasks")
    parser.add_argument("--etap", type=int, choices=[1, 2, 3],
                        help="Download specific etap (1, 2, or 3)")
    parser.add_argument("--all-etaps", action="store_true",
                        help="Download all etaps (1, 2, and 3)")
    parser.add_argument("--year", type=int,
                        help="Download only specific year")
    args = parser.parse_args()

    # Default to etap 2 if no option specified
    if args.all_etaps:
        etaps = [1, 2, 3]
    elif args.etap:
        etaps = [args.etap]
    else:
        etaps = [2]

    etap_names = ", ".join([f"Etap {e}" for e in etaps])
    print(f"OMJ/OMG Task Downloader - {etap_names}")
    print("=" * 40)

    output_dir = OUTPUT_DIR
    output_dir.mkdir(exist_ok=True)

    total_downloaded = 0

    # Filter editions by year if specified
    editions_to_process = EDITIONS
    if args.year:
        editions_to_process = [e for e in EDITIONS if e.year_start == args.year]
        if not editions_to_process:
            print(f"No edition found for year {args.year}")
            return

    for edition in editions_to_process:
        comp_type = "OMJ" if edition.is_omj else "OMG"
        print(f"\n{comp_type} Edition {edition.number} ({edition.year_start}/{edition.year_start + 1 - 2000}):")

        for etap in etaps:
            print(f"  Etap {etap}:")
            downloaded = download_etap_for_edition(edition, output_dir, etap)
            total_downloaded += len(downloaded)

            if not downloaded:
                print(f"    No files found")

    print(f"\n{'=' * 40}")
    print(f"Total files downloaded: {total_downloaded}")
    print(f"Files saved to: {output_dir.absolute()}")


if __name__ == "__main__":
    main()
