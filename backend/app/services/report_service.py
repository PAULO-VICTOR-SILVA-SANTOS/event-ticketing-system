from __future__ import annotations

import datetime as dt
import io
from pathlib import Path

import httpx
from PIL import Image as PILImage
from reportlab.graphics.shapes import Drawing, Polygon, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.event import Event
from app.models.participant import Participant

# Optional real exported logo -- if this file exists it's used as-is
# instead of the drawn approximation below. Drop a PNG/SVG-exported-as-PNG
# here to make the PDF match the brand exactly.
LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "pv-logo.png"

ACCENT = colors.HexColor("#7b2fff")
TEXT_DARK = colors.HexColor("#1a1a2e")
TEXT_MUTED = colors.HexColor("#55556b")
ROW_ALT = colors.HexColor("#f5f5fa")
GRID_LINE = colors.HexColor("#cccccc")


def generate_paid_participants_report(
    event: Event, participants: list[Participant]
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        title=f"Participantes pagos - {event.name}",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "EventTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=TEXT_DARK,
        spaceAfter=2,
    )
    meta_style = ParagraphStyle(
        "EventMeta", parent=styles["Normal"], fontSize=10, textColor=TEXT_MUTED
    )
    section_style = ParagraphStyle(
        "Section", parent=styles["Normal"], fontSize=9, textColor=TEXT_MUTED
    )

    story = [
        _build_header(),
        Spacer(1, 10 * mm),
    ]

    banner_image = _fetch_banner_image(event.banner_url)
    if banner_image is not None:
        story.append(banner_image)
        story.append(Spacer(1, 8 * mm))

    story.append(Paragraph(event.name, title_style))
    story.append(Paragraph(_format_event_meta(event), meta_style))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("Participantes com pagamento confirmado", section_style))
    story.append(Spacer(1, 3 * mm))

    table_data = [["Nome completo", "Apelido", "Status", "Check"]]
    for participant in participants:
        table_data.append([participant.name, participant.nickname or "-", "Paga", ""])

    table = Table(
        table_data,
        colWidths=[75 * mm, 35 * mm, 25 * mm, 20 * mm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, GRID_LINE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 8 * mm))

    story.append(
        Paragraph(f"<b>Total de participantes pagos:</b> {len(participants)}", meta_style)
    )
    generated_at = dt.datetime.now(dt.timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    story.append(Paragraph(f"Relatorio gerado em {generated_at}", meta_style))

    doc.build(story)
    return buffer.getvalue()


def _format_event_meta(event: Event) -> str:
    date_str = event.date.strftime("%d/%m/%Y") if event.date else "-"
    time_str = event.time.strftime("%H:%M") if event.time else "-"
    return f"{date_str} as {time_str} - {event.location}"


def _fetch_banner_image(banner_url: str | None) -> Image | None:
    """Downloads the event banner for embedding in the PDF.

    Never raises -- a missing/unreachable/corrupt banner shouldn't block
    generating the rest of the report, it just gets skipped.
    """
    if not banner_url:
        return None
    try:
        response = httpx.get(banner_url, timeout=10.0)
        response.raise_for_status()
        data = response.content

        pil_image = PILImage.open(io.BytesIO(data))
        pil_image.load()

        target_width = 178 * mm
        aspect_ratio = pil_image.height / pil_image.width
        target_height = target_width * aspect_ratio
        max_height = 80 * mm
        if target_height > max_height:
            target_height = max_height
            target_width = target_height / aspect_ratio

        return Image(io.BytesIO(data), width=target_width, height=target_height)
    except Exception:
        return None


def _build_header() -> Table:
    if LOGO_PATH.exists():
        logo_flowable = Image(str(LOGO_PATH), width=22 * mm, height=22 * mm)
    else:
        logo_flowable = _draw_pv_mark()

    text_style = ParagraphStyle(
        "HeaderName", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=TEXT_DARK
    )
    sub_style = ParagraphStyle(
        "HeaderSub",
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        spaceBefore=2,
        textColor=TEXT_MUTED,
    )
    text_cell = [
        Paragraph("PV Technology", text_style),
        Paragraph("Sistema de ingressos", sub_style),
    ]

    header_table = Table([[logo_flowable, text_cell]], colWidths=[26 * mm, 148 * mm])
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return header_table


def _draw_pv_mark() -> Drawing:
    """Approximates the "PV" heptagon mark used across the site (see
    .pv-mini-icon's clip-path in frontend/assets/css/style.css) with plain
    ReportLab shapes, since that mark only exists as a live CSS clip-path,
    not an exported image file.
    """
    size = 22 * mm
    drawing = Drawing(size, size)
    # Same 7 points as the CSS clip-path polygon, with y flipped (CSS 0% is
    # the top of the box, ReportLab 0 is the bottom).
    points_pct = [
        (0.50, 1.00),
        (0.88, 0.82),
        (1.00, 0.42),
        (0.74, 0.06),
        (0.26, 0.06),
        (0.00, 0.42),
        (0.12, 0.82),
    ]
    coords: list[float] = []
    for x_pct, y_pct in points_pct:
        coords.extend([x_pct * size, y_pct * size])
    drawing.add(Polygon(coords, fillColor=ACCENT, strokeColor=None))
    drawing.add(
        String(
            size / 2,
            size / 2 - 4,
            "PV",
            fontName="Helvetica-Bold",
            fontSize=11,
            fillColor=colors.white,
            textAnchor="middle",
        )
    )
    return drawing
