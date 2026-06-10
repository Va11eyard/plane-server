# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os
from io import BytesIO

from fpdf import FPDF

FONT_PATHS = [
    "/usr/share/fonts/ttf-dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]


def _resolve_font() -> str | None:
    for path in FONT_PATHS:
        if os.path.isfile(path):
            return path
    return None


class ReportPDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Стр. {self.page_no()}", align="C")


def render_report_pdf(title: str, content: str, period_from: str = "", period_to: str = "") -> bytes:
    pdf = ReportPDF()
    font_path = _resolve_font()
    bold_path = font_path.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf") if font_path else None
    if font_path:
        pdf.add_font("DejaVu", "", font_path)
        if bold_path and os.path.isfile(bold_path):
            pdf.add_font("DejaVu", "B", bold_path)
    else:
        pdf.set_font("Helvetica", "", 12)

    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    if font_path:
        pdf.set_font("DejaVu", "B", 16)
    else:
        pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, title or "Отчёт")
    pdf.ln(4)

    if period_from and period_to:
        if font_path:
            pdf.set_font("DejaVu", "", 10)
        else:
            pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 8, f"Период: {period_from} — {period_to}", ln=True)
        pdf.ln(4)
        pdf.set_text_color(0, 0, 0)

    if font_path:
        pdf.set_font("DejaVu", "", 11)
    else:
        pdf.set_font("Helvetica", "", 11)

    for line in (content or "").split("\n"):
        pdf.multi_cell(0, 6, line)
        pdf.ln(1)

    return bytes(pdf.output())
