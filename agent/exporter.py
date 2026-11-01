import csv
import json
import os
from typing import Any, List
import pandas as pd
from agent.models import LeadRecord


def sanitize_csv_cell(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(("+", "-", "=", "@", "	", "")):
        return "'" + value
    return value


def export_leads(leads: List[LeadRecord], output_dir: str, run_summary: dict) -> None:
    os.makedirs(output_dir, exist_ok=True)

    sorted_leads = sorted(leads, key=lambda x: (-x.score, x.brand))

    json_path = os.path.join(output_dir, "leads.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([l.model_dump() for l in sorted_leads], f, indent=2, ensure_ascii=False)

    summary_path = os.path.join(output_dir, "run_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(run_summary, f, indent=2, ensure_ascii=False)

    csv_path = os.path.join(output_dir, "leads.csv")
    csv_rows = []
    for l in sorted_leads:
        csv_rows.append({
            "brand": sanitize_csv_cell(l.brand),
            "score": l.score,
            "grade": l.grade.value,
            "category": sanitize_csv_cell(l.category),
            "website": sanitize_csv_cell(l.website),
            "has_ecommerce_channel": l.has_ecommerce_channel,
            "amazon_url": sanitize_csv_cell(l.amazon_url),
            "price_tier": l.price_tier.value,
            "evidence_coverage": l.evidence_coverage,
            "research_status": l.research_status.value,
            "priority_note": sanitize_csv_cell(l.priority_note),
            "recommended_next_step": sanitize_csv_cell(l.recommended_next_step),
            "researched_at": l.researched_at
        })
    df_csv = pd.DataFrame(csv_rows)
    df_csv.to_csv(csv_path, index=False, encoding="utf-8-sig")

    excel_path = os.path.join(output_dir, "leads.xlsx")
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df_csv.to_excel(writer, sheet_name="Leads", index=False)

        evidence_rows = []
        for l in sorted_leads:
            for ev in l.evidence:
                evidence_rows.append({
                    "brand": l.brand,
                    "evidence_id": ev.id,
                    "source_url": ev.source_url,
                    "summary": ev.summary,
                    "timestamp": ev.timestamp
                })
        if evidence_rows:
            df_ev = pd.DataFrame(evidence_rows)
            df_ev.to_excel(writer, sheet_name="Evidence", index=False)
        else:
            pd.DataFrame({"notice": ["No evidence records available"]}).to_excel(writer, sheet_name="Evidence", index=False)

        summary_data = [
            {"metric": "Mode", "value": run_summary.get("mode")},
            {"metric": "Total Processed", "value": run_summary.get("total_processed")},
            {"metric": "Successful", "value": run_summary.get("successful")},
            {"metric": "Partial / Failed", "value": run_summary.get("failed")},
            {"metric": "Timestamp", "value": run_summary.get("timestamp")}
        ]
        df_sum = pd.DataFrame(summary_data)
        df_sum.to_excel(writer, sheet_name="Run Summary", index=False)
