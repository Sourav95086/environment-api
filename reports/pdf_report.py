from pathlib import Path
from xml.sax.saxutils import escape
import re
import math
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether
)
from schemas.report_schema import EnvironmentalReportData

SECTIONS = [
    ("Energy", "energy_metrics"),
    ("Water", "water_metrics"),
    ("Emissions and air pollution", "emissions_metrics"),
    ("Waste management", "waste_metrics"),
    ("Environmental clearances and assessments", "clearances_assessments"),
    ("Environmental compliance", "compliance_metrics"),
]

NAVY = "#17365D"
GREEN = "#2F855A"
PALE = "#EAF2F8"
MUTED = "#526579"
AMBER = "#B7791F"
RED = "#9C0006"

def _plain(value):
    return str(value if value is not None else "Not provided")

def _para(value, style):
    return Paragraph(escape(_plain(value)), style)

def _number(value):
    """Return a number only when the whole metric value is numeric."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    if not re.fullmatch(r"[-+]?\d+(?:\.\d+)?", s):
        return None
    try:
        n = float(s)
        return n if math.isfinite(n) else None
    except ValueError:
        return None

def _find(metrics, terms):
    for metric in metrics or []:
        name = metric.name.lower()
        if any(term in name for term in terms):
            n = _number(metric.value)
            if n is not None:
                return metric, n
    return None, None

def _metric_rows(metrics, styles):
    rows = [[_para(h, styles["SmallHead"]) for h in
             ["Metric", "Value", "Unit", "Status", "Source / notes"]]]
    for m in metrics:
        source_notes = "; ".join(x for x in [m.source_document, m.notes] if x)
        rows.append([
            _para(m.name, styles["SmallCell"]),
            _para(m.value, styles["SmallCell"]),
            _para(m.unit, styles["SmallCell"]),
            _para(m.status, styles["SmallCell"]),
            _para(source_notes, styles["SmallCell"]),
        ])
    table = Table(rows, colWidths=[34*mm, 22*mm, 18*mm, 23*mm, 75*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor(NAVY)),
        ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#C7D2DE")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F3F6F9")]),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    return table

def _save_bar_chart(path, title, labels, values, ylabel):
    fig, ax = plt.subplots(figsize=(8.4, 3.2))
    bars = ax.bar(labels, values, color=[GREEN if i == 0 else "#4A78A8" for i in range(len(values))])
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=NAVY, pad=12)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#D7E0E8")
    ax.spines["bottom"].set_color("#D7E0E8")
    ax.grid(axis="y", linestyle="--", alpha=.25)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelrotation=18, labelsize=8)
    ax.tick_params(axis="y", labelsize=8)
    for bar, value in zip(bars, values):
        ax.annotate(f"{value:,.1f}" if abs(value) < 10000 else f"{value:,.0f}",
                    (bar.get_x() + bar.get_width()/2, bar.get_height()),
                    textcoords="offset points", xytext=(0, 3), ha="center", fontsize=8, color=NAVY)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)

def _save_status_chart(path, report):
    all_metrics = []
    for _, attr in SECTIONS:
        all_metrics.extend(getattr(report, attr) or [])
    statuses = ["reported", "calculated", "partial", "unavailable", "not_verified", "unknown", "not_applicable"]
    counts = {s: sum(1 for m in all_metrics if str(m.status).lower() == s) for s in statuses}
    counts = {k:v for k,v in counts.items() if v}
    if not counts:
        return False
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    palette = [GREEN, "#4A78A8", "#E0A33A", "#B8C2CC", "#8C7BB8", "#D46A6A", "#5A9E9A"]
    ax.pie(list(counts.values()), labels=[f"{k.replace('_',' ')} ({v})" for k,v in counts.items()],
           startangle=90, counterclock=False, colors=palette[:len(counts)],
           wedgeprops={"width": .42, "edgecolor": "white"}, textprops={"fontsize": 8})
    ax.set_title("Metric status distribution", loc="left", fontsize=12, fontweight="bold", color=NAVY)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return True

def _chart_specs(report, tempdir):
    charts = []
    # Energy: compare unlike units only after labelling them as activity data; do not combine into a false total.
    metrics = report.energy_metrics or []
    selected = []
    for terms, label in [
        (["grid electricity consumed"], "Grid electricity (kWh)"),
        (["renewable electricity"], "Renewable electricity (kWh)"),
        (["diesel consumed"], "Diesel (L)"),
        (["petrol consumed"], "Petrol (L)"),
        (["lpg consumed"], "LPG (kg)"),
    ]:
        m, n = _find(metrics, terms)
        if m and n is not None and n >= 0:
            selected.append((label, n))
    if selected:
        p = Path(tempdir) / "energy_activity.png"
        _save_bar_chart(p, "Energy activity data by source", [x[0] for x in selected],
                        [x[1] for x in selected], "Reported activity (source units vary)")
        charts.append(("Energy activity data", str(p),
                       "Sources use different units. This chart compares activity values only; it is not a common-unit energy total."))

    # Water source profile
    selected = []
    for terms, label in [
        (["municipal", "third-party water received"], "Municipal / third-party"),
        (["groundwater withdrawal"], "Groundwater"),
        (["surface water withdrawal"], "Surface water"),
        (["rainwater harvested"], "Rainwater harvested"),
    ]:
        m, n = _find(metrics, terms)
        if m and n is not None and n >= 0:
            selected.append((label, n))
    if selected:
        p = Path(tempdir) / "water_sources.png"
        _save_bar_chart(p, "Water received / withdrawn by source", [x[0] for x in selected],
                        [x[1] for x in selected], "m³")
        charts.append(("Water profile", str(p), "Values are extracted from source records. Confirm boundaries and whether harvested rainwater is included in the applicable withdrawal total."))

    # Emissions: only compare numeric values in tCO2e
    selected = []
    for terms, label in [
        (["total scope 1 ghg", "total scope 1 emissions"], "Scope 1 total"),
        (["scope 2 – purchased", "scope 2 purchased", "scope 2 grid"], "Scope 2 purchased electricity"),
        (["total scope 1 + scope 2", "total scope 1 and scope 2"], "Scope 1 + 2 total"),
    ]:
        m, n = _find(report.emissions_metrics or [], terms)
        if m and n is not None and ("tco" in (m.unit or "").lower() or "co2" in (m.unit or "").lower()):
            selected.append((label, n))
    if selected:
        p = Path(tempdir) / "emissions.png"
        _save_bar_chart(p, "Reported / calculated greenhouse-gas values", [x[0] for x in selected],
                        [x[1] for x in selected], "tCO₂e")
        charts.append(("GHG emissions", str(p), "Check that component totals are not plotted alongside totals as if they were independent emissions. Values remain provisional where factors or evidence are unverified."))

    # Waste generated streams only
    selected = []
    for m in report.waste_metrics or []:
        name = m.name.lower()
        if "generated" in name and not name.startswith("total") and "total recorded waste" not in name:
            n = _number(m.value)
            if n is not None and n >= 0 and ("tonne" in (m.unit or "").lower() or "kg" in (m.unit or "").lower()):
                selected.append((m.name.replace(" – generated", "").replace(" - generated", "")[:30], n))
    if selected:
        p = Path(tempdir) / "waste_generated.png"
        _save_bar_chart(p, "Waste generated by stream", [x[0] for x in selected],
                        [x[1] for x in selected], "tonnes")
        charts.append(("Waste generation", str(p), "Only numeric metrics explicitly labelled as generated are included. Verify generated = recovered + disposed for each waste stream."))

    return charts

def _footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setStrokeColor(colors.HexColor("#D7E0E8"))
    canvas.line(12*mm, 10*mm, w-12*mm, 10*mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor(MUTED))
    canvas.drawString(12*mm, 6*mm, "ENVIRONMENTAL ESG / BRSR • AUTOMATED DRAFT")
    canvas.drawRightString(w-12*mm, 6*mm, f"Page {doc.page}")
    canvas.restoreState()

def create_pdf_report(data: EnvironmentalReportData, output_path: Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitleX", parent=styles["Title"], fontSize=25, leading=30,
        alignment=TA_CENTER, textColor=colors.HexColor(NAVY), spaceAfter=7))
    styles.add(ParagraphStyle(name="SubtitleX", parent=styles["Normal"], fontSize=13, leading=18,
        alignment=TA_CENTER, textColor=colors.HexColor(GREEN), spaceAfter=4))
    styles.add(ParagraphStyle(name="SmallCell", parent=styles["BodyText"], fontSize=7.2, leading=9))
    styles.add(ParagraphStyle(name="SmallHead", parent=styles["BodyText"], fontName="Helvetica-Bold",
        fontSize=7.2, leading=9, textColor=colors.white))
    styles.add(ParagraphStyle(name="SectionX", parent=styles["Heading1"], fontSize=17, leading=21,
        textColor=colors.HexColor(NAVY), spaceBefore=4, spaceAfter=4))
    styles.add(ParagraphStyle(name="NoteX", parent=styles["BodyText"], fontSize=8, leading=11,
        textColor=colors.HexColor(MUTED), spaceAfter=4))
    styles.add(ParagraphStyle(name="CalloutX", parent=styles["BodyText"], fontSize=9, leading=13,
        textColor=colors.HexColor(RED), backColor=colors.HexColor("#FCE8E6"),
        borderPadding=8, spaceBefore=4, spaceAfter=4))

    story = []
    with tempfile.TemporaryDirectory(prefix="esg_charts_") as tempdir:
        # Cover
        story += [
            Spacer(1, 12*mm),
            Paragraph("ENVIRONMENTAL<br/>ESG / BRSR REPORT", styles["ReportTitleX"]),
            Paragraph("PROJECT ENVIRONMENTAL PERFORMANCE", styles["SubtitleX"]),
            Spacer(1, 4*mm),
        ]
        cover = [
            [_para("PROJECT", styles["SmallHead"]), _para("REPORTING PERIOD", styles["SmallHead"])],
            [_para(data.project_name, styles["BodyText"]), _para(data.reporting_period, styles["BodyText"])],
            [_para(f"Project ID: {data.project_id}", styles["BodyText"]), _para("Automated draft • Version 1.0", styles["BodyText"])],
        ]
        ct = Table(cover, colWidths=[82*mm, 82*mm])
        ct.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor(NAVY)),
            ("BACKGROUND",(0,1),(-1,-1),colors.HexColor(PALE)),
            ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#D0DCE6")),
            ("VALIGN",(0,0),(-1,-1),"TOP"),
            ("LEFTPADDING",(0,0),(-1,-1),9),("RIGHTPADDING",(0,0),(-1,-1),9),
            ("TOPPADDING",(0,0),(-1,-1),9),("BOTTOMPADDING",(0,0),(-1,-1),9),
        ]))
        story.append(ct)
        if data.synthetic_data:
            story.append(Spacer(1, 2.5*mm))
            story.append(Paragraph(
                "<b>SYNTHETIC TEST DATA — NOT ACTUAL MEIL DATA.</b><br/>"
                "For demonstration and software testing only. Not suitable for statutory filing.",
                styles["CalloutX"]))
        story += [Spacer(1, 8*mm),
                  Paragraph("Prepared from project documents provided to the automated reporting workflow.",
                            ParagraphStyle("CoverText", parent=styles["BodyText"], alignment=TA_CENTER,
                                           textColor=colors.HexColor(MUTED), fontSize=10, leading=15)),
                  Spacer(1, 12*mm),
                  Paragraph("CONFIDENTIAL • FOR REVIEW", ParagraphStyle("Conf", parent=styles["Normal"],
                            alignment=TA_CENTER, textColor=colors.HexColor(GREEN), fontName="Helvetica-Bold")),
                  PageBreak()]

        # Executive summary dashboard
        story.append(Paragraph("Executive dashboard", styles["SectionX"]))
        story.append(Paragraph(escape(data.project_overview or "Project overview was not extracted."),
                               styles["BodyText"]))
        story.append(Spacer(1, 2.5*mm))

        kpis = []
        for title, metrics, terms, unit in [
            ("Total energy", data.energy_metrics, ["total energy consumption"], "GJ"),
            ("Water withdrawal", data.water_metrics, ["total water withdrawal"], "m³"),
            ("Scope 1 + 2 GHG", data.emissions_metrics, ["total scope 1 + scope 2", "total scope 1 and scope 2"], "tCO₂e"),
            ("Waste generated", data.waste_metrics, ["total recorded waste", "total waste generated"], "tonnes"),
        ]:
            m, n = _find(metrics or [], terms)
            if m:
                value = f"{n:,.1f}" if n is not None else _plain(m.value)
                if n is not None and abs(n) >= 1000:
                    value = f"{n:,.0f}"
                subtitle = unit
            else:
                value, subtitle = "Not available", "Requires review"
            kpis.append((title, value, subtitle))
        cards = []
        for title, value, unit in kpis:
            cards.append([
                Paragraph(escape(title.upper()), ParagraphStyle("KTitle"+str(len(cards)), parent=styles["Normal"],
                          fontSize=7.5, textColor=colors.HexColor(MUTED), alignment=TA_CENTER)),
                Paragraph(escape(value), ParagraphStyle("KValue"+str(len(cards)), parent=styles["Normal"],
                          fontSize=16, leading=20, textColor=colors.HexColor(NAVY), alignment=TA_CENTER,
                          fontName="Helvetica-Bold")),
                Paragraph(escape(unit), ParagraphStyle("KUnit"+str(len(cards)), parent=styles["Normal"],
                          fontSize=8, textColor=colors.HexColor(GREEN), alignment=TA_CENTER)),
            ])
        # Each card is a nested table; 4 cards across.
        card_tables = []
        for card in cards:
            t = Table([[card[0]],[card[1]],[card[2]]], colWidths=[39*mm], rowHeights=[8*mm,13*mm,7*mm])
            t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor(PALE)),
                                   ("BOX",(0,0),(-1,-1),0.6,colors.HexColor("#D0DCE6")),
                                   ("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),
                                   ("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
            card_tables.append(t)
        kt = Table([card_tables], colWidths=[41*mm]*4)
        kt.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),1),
                                ("RIGHTPADDING",(0,0),(-1,-1),1)]))
        story += [kt, Spacer(1, 2.5*mm)]

        all_metrics = [m for _, attr in SECTIONS for m in (getattr(data, attr) or [])]
        status_counts = {}
        for m in all_metrics:
            status_counts[str(m.status)] = status_counts.get(str(m.status), 0) + 1
        story.append(Paragraph("Data quality at a glance", styles["Heading2"]))
        if status_counts:
            status_line = "   •   ".join(f"{k.replace('_',' ').title()}: {v}" for k,v in sorted(status_counts.items()))
            story.append(Paragraph(escape(status_line), styles["BodyText"]))
        else:
            story.append(Paragraph("No structured metrics were extracted.", styles["BodyText"]))
        story.append(Spacer(1, 0.8*mm))
        status_path = Path(tempdir) / "status.png"
        if _save_status_chart(status_path, data):
            story.append(Image(str(status_path), width=120*mm, height=69*mm))
        story.append(Paragraph("Key interpretation: KPI cards are populated only where a matching numeric metric exists. Values marked provisional, synthetic, partial, or unverified must be reviewed before external reporting.",
                               styles["NoteX"]))
        story.append(Spacer(1, 3*mm))

        # Chart gallery with charts dynamically generated from numeric metrics.
        story.append(Paragraph("Environmental performance charts", styles["SectionX"]))
        charts = _chart_specs(data, tempdir)
        if charts:
            for title, path, note in charts:
                block = [Paragraph(escape(title), styles["Heading2"]),
                         Image(path, width=160*mm, height=48*mm),
                         Paragraph(escape(note), styles["NoteX"]),
                         Spacer(1, 0.8*mm)]
                story.append(KeepTogether(block))
        else:
            story.append(Paragraph("No chartable numeric metrics were found. Review the extraction output and metric units.",
                                   styles["BodyText"]))
        story.append(Paragraph("Charting rule: metrics with incompatible units are not combined into a single total. Component values and aggregate totals should not be interpreted as independent categories.",
                               styles["NoteX"]))
        story.append(PageBreak())

        # Detail tables
        for title, attr in SECTIONS:
            story.append(Paragraph(escape(title), styles["SectionX"]))
            metrics = getattr(data, attr) or []
            if not metrics:
                story.append(Paragraph("No structured metrics extracted. Manual review required.", styles["BodyText"]))
            else:
                story.append(_metric_rows(metrics, styles))
            story.append(Spacer(1, 2.5*mm))

        for title, values in [("Data gaps", data.data_gaps), ("Validation warnings", data.validation_warnings)]:
            story.append(Paragraph(title, styles["SectionX"]))
            if values:
                for value in values:
                    story.append(Paragraph("• " + escape(str(value)), styles["BodyText"]))
                    story.append(Spacer(1, 0.8*mm))
            else:
                story.append(Paragraph("None recorded by automated checks. This does not constitute independent assurance.",
                                       styles["BodyText"]))
            story.append(Spacer(1, 0.8*mm))

        story.append(Paragraph("Source documents", styles["SectionX"]))
        if data.source_documents:
            for name in data.source_documents:
                story.append(Paragraph("• " + escape(name), styles["BodyText"]))
        else:
            story.append(Paragraph("No source documents recorded.", styles["BodyText"]))
        story.append(Spacer(1, 2.5*mm))
        story.append(Paragraph(
            "Review note: This document is an automated draft. Validate source records, calculations, reporting "
            "boundary, applicability, units, emission factors, and current SEBI BRSR disclosure requirements before use.",
            styles["NoteX"]))

        doc = SimpleDocTemplate(str(output_path), pagesize=A4,
            rightMargin=12*mm, leftMargin=12*mm, topMargin=10*mm, bottomMargin=14*mm,
            title="Environmental ESG / BRSR Report Draft", author="Environmental Reporting Agent")
        doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output_path
