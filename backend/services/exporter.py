"""
Stage 7: Exports.

Writes output/leads.json, output/leads.csv, output/leads.xlsx and
output/summary.json. Excel gets readable headers, a frozen header row and
column filters.
"""
from pathlib import Path
from typing import List

import pandas as pd
from openpyxl.utils import get_column_letter

from backend.config import OUTPUT_DIR
from backend.utils.helpers import safe_write_json

EXPORT_COLUMNS = [
    ("name", "Business"),
    ("category", "Category"),
    ("phone", "Phone"),
    ("email", "Email"),
    ("email_confidence", "Email Confidence"),
    ("website", "Website"),
    ("facebook", "Facebook"),
    ("instagram", "Instagram"),
    ("linkedin", "LinkedIn"),
    ("twitter", "Twitter/X"),
    ("youtube", "YouTube"),
    ("directories", "Directories"),
    ("rating", "Rating"),
    ("review_count", "Review Count"),
    ("full_address", "Full Address"),
    ("city", "City"),
    ("pincode", "Pincode"),
    ("hours", "Hours"),
    ("is_sponsored", "Sponsored"),
    ("website_status", "Website Enrichment Status"),
    ("lead_score", "Lead Score"),
    ("lead_grade", "Lead Grade"),
    ("maps_url", "Maps URL"),
]


def _to_dataframe(leads: List[dict]) -> pd.DataFrame:
    rows = []
    for lead in leads:
        row = {}
        for key, header in EXPORT_COLUMNS:
            value = lead.get(key, "")
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            row[header] = value
        rows.append(row)
    return pd.DataFrame(rows, columns=[h for _, h in EXPORT_COLUMNS])


def export_json(leads: List[dict], path: Path = None) -> Path:
    path = path or (OUTPUT_DIR / "leads.json")
    safe_write_json(path, leads)
    return path


def export_csv(leads: List[dict], path: Path = None) -> Path:
    path = path or (OUTPUT_DIR / "leads.csv")
    df = _to_dataframe(leads)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def export_excel(leads: List[dict], path: Path = None) -> Path:
    path = path or (OUTPUT_DIR / "leads.xlsx")
    df = _to_dataframe(leads)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Leads")
        worksheet = writer.sheets["Leads"]

        worksheet.freeze_panes = "A2"
        if len(df) > 0:
            worksheet.auto_filter.ref = worksheet.dimensions

        for i, column in enumerate(df.columns, start=1):
            max_len = max([len(str(column))] + [len(str(v)) for v in df[column].astype(str).tolist()])
            worksheet.column_dimensions[get_column_letter(i)].width = min(max_len + 3, 45)

    return path


def export_summary(summary: dict, path: Path = None) -> Path:
    path = path or (OUTPUT_DIR / "summary.json")
    safe_write_json(path, summary)
    return path


def export_all(leads: List[dict], summary: dict) -> dict:
    return {
        "json": str(export_json(leads)),
        "csv": str(export_csv(leads)),
        "excel": str(export_excel(leads)),
        "summary": str(export_summary(summary)),
    }