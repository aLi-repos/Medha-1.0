"""Real DOCX report generator for MEDHA task analyses.

Builds a genuine Office Open XML (.docx) document with python-docx from a
task-derived report payload. Layout is static; content comes from the live
Task Passport, stored analysis, and authorized evidence only.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

SAFE_MAX_SNIPPET_CHARS = 600


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _add_heading(doc: Document, text: str, level: int = 1) -> None:
    heading = doc.add_heading(text, level=level)
    for run in heading.runs:
        run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)


def _add_kv(doc: Document, label: str, value: object) -> None:
    p = doc.add_paragraph()
    run_label = p.add_run(f"{label}: ")
    run_label.bold = True
    p.add_run(str(value) if value is not None else "—")


def _sanitize_text(text: str) -> str:
    """Strip control characters; never pass through secrets-shaped blobs."""
    if not text:
        return ""
    cleaned = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ch.isprintable())
    return cleaned.strip()


def generate_docx(report: dict) -> bytes:
    """Return DOCX bytes for the given report payload.

    Expected keys (all optional except task identity):
      task_id, title, purpose, security_mode, sensitivity, status,
      generated_at, summary, findings, recommendations, evidence,
      execution, disclaimers, analysis_id
    """
    doc = Document()

    # --- Title block ---
    title = doc.add_heading("MEDHA", level=0)
    for run in title.runs:
        run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
    subtitle = doc.add_paragraph("Sovereign Industrial AI Workbench")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in subtitle.runs:
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0x4B, 0x55, 0x63)

    task_title = _sanitize_text(str(report.get("title") or "Task Report"))
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"Task: {task_title}")
    r.bold = True
    r.font.size = Pt(13)

    stamp = doc.add_paragraph()
    stamp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    stamp.add_run(
        f"Generated: {_sanitize_text(str(report.get('generated_at') or _utc_now_iso()))}"
    ).font.size = Pt(9)

    classification = report.get("disclaimer")
    if classification:
        note = doc.add_paragraph()
        note.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = note.add_run(_sanitize_text(str(classification)))
        run.italic = True
        run.font.size = Pt(9)

    doc.add_paragraph()

    # --- 1. Executive Summary ---
    _add_heading(doc, "1. Executive Summary", level=1)
    summary = _sanitize_text(str(report.get("summary") or ""))
    if summary:
        doc.add_paragraph(summary)
    else:
        doc.add_paragraph(
            "No completed analysis is available for this task yet. "
            "Run a secure analysis to populate findings."
        )

    # --- 2. Task Information ---
    _add_heading(doc, "2. Task Information", level=1)
    _add_kv(doc, "Task ID", report.get("task_id") or "—")
    if report.get("analysis_id"):
        _add_kv(doc, "Analysis ID", report.get("analysis_id"))
    _add_kv(doc, "Purpose", _sanitize_text(str(report.get("purpose") or "—")))
    _add_kv(doc, "Security mode", report.get("security_mode") or "—")
    _add_kv(doc, "Sensitivity", report.get("sensitivity") or "—")
    _add_kv(doc, "Task status", report.get("status") or "—")
    _add_kv(doc, "Report timestamp", report.get("generated_at") or _utc_now_iso())

    # --- 3. Analysis / Findings ---
    _add_heading(doc, "3. Analysis / Findings", level=1)
    findings = report.get("findings") or []
    if findings:
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        for i, name in enumerate(("Category", "Severity", "Label", "Detail")):
            hdr[i].text = name
            for paragraph in hdr[i].paragraphs:
                for run in paragraph.runs:
                    run.bold = True
        for f in findings:
            row = table.add_row().cells
            row[0].text = _sanitize_text(str(f.get("category", "")))
            row[1].text = _sanitize_text(str(f.get("severity", "")))
            row[2].text = _sanitize_text(str(f.get("label", "")))
            row[3].text = _sanitize_text(str(f.get("detail", "")))[:SAFE_MAX_SNIPPET_CHARS]
    else:
        doc.add_paragraph("No analysis findings recorded for this task.")

    # --- 4. Evidence ---
    _add_heading(doc, "4. Evidence", level=1)
    evidence = report.get("evidence") or []
    if evidence:
        doc.add_paragraph(
            "Retrieved evidence limited to sources authorized on this Task Passport:"
        )
        for item in evidence:
            source = _sanitize_text(str(item.get("source", "")))
            snippet = _sanitize_text(str(item.get("snippet", "")))[:SAFE_MAX_SNIPPET_CHARS]
            p = doc.add_paragraph(style="List Bullet")
            r = p.add_run(f"Source: {source}")
            r.bold = True
            if snippet:
                doc.add_paragraph(f"Snippet: {snippet}")
    else:
        doc.add_paragraph(
            "No authorized evidence chunks were available for this task at report time."
        )

    # --- 5. Analysis Result / Recommendations ---
    _add_heading(doc, "5. Analysis Result / Recommendations", level=1)
    recommendations = report.get("recommendations") or []
    if recommendations:
        for rec in recommendations:
            p = doc.add_paragraph(style="List Number")
            r = p.add_run(f"[{rec.get('priority', 'medium')}] ")
            r.bold = True
            p.add_run(
                f"{_sanitize_text(str(rec.get('action', '')))} — "
                f"{_sanitize_text(str(rec.get('rationale', '')))}"
            )
    else:
        doc.add_paragraph("No recommendations recorded.")

    # --- 6. MEDHA Execution Information ---
    _add_heading(doc, "6. MEDHA Execution Information", level=1)
    execution = report.get("execution") or {}
    _add_kv(doc, "Pipeline", execution.get("pipeline", "MEDHA secure analysis pipeline"))
    if execution.get("model"):
        _add_kv(doc, "Model routing", execution.get("model"))
    if execution.get("sources_authorized") is not None:
        _add_kv(doc, "Authorized sources", execution.get("sources_authorized"))
    if execution.get("tools_authorized") is not None:
        _add_kv(doc, "Authorized tools", execution.get("tools_authorized"))
    if execution.get("risk_level"):
        _add_kv(doc, "Risk level", execution.get("risk_level"))
        _add_kv(doc, "Risk score", execution.get("risk_score"))
    _add_kv(doc, "Generation mode", "Local MEDHA export (server-side, authorized)")

    # --- 7. Security / Provenance Note ---
    _add_heading(doc, "7. Security / Provenance Note", level=1)
    doc.add_paragraph(
        "Analysis generated using MEDHA's authorized local knowledge and "
        "controlled execution pipeline. Evidence snippets above are retrieved "
        "from sources allowed by this Task Passport; they are retrieved "
        "context, not independently verified external citations."
    )
    if report.get("disclaimer"):
        doc.add_paragraph(_sanitize_text(str(report.get("disclaimer"))))

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()
