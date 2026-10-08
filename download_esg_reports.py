"""Download the public sustainability reports used for the ESG test.

The PDFs are the companies' copyrighted material, so they are not stored in this
repository (esg_reports/ is git-ignored). Run this script to fetch them from
the companies' own websites.
"""

from pathlib import Path

import requests

OUT = Path(__file__).parent / "esg_reports"

REPORTS = {
    "kerry_annual_report_2025.pdf": "https://www.kerry.com/annual-report/assets/pdfs/KGAR25_FullReport.pdf",
    "ryanair_sustainability_statement_fy26.pdf": "https://corporate.ryanair.com/wp-content/uploads/2026/07/Ryanair-FY26-Sustainability-Statement.pdf",
    "bank_of_ireland_sustainability_report_2024.pdf": "https://investorrelations.bankofireland.com/app/uploads/BOI-Sustainability-Report-Final.pdf",
}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, url in REPORTS.items():
        path = OUT / name
        if path.exists():
            print(f"already have {name}")
            continue
        response = requests.get(url, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        if not response.content.startswith(b"%PDF"):
            raise ValueError(f"{url} did not return a PDF")
        path.write_bytes(response.content)
        print(f"downloaded {name} ({len(response.content) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
