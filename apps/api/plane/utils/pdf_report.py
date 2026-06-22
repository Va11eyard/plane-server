# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os
import re
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


def _strip_inline_markdown(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text.strip()


def _is_table_separator(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    return bool(re.match(r"^\|[\s\-:|]+\|$", stripped))


def _parse_table_row(line: str) -> list[str]:
    return [_strip_inline_markdown(cell) for cell in line.strip().strip("|").split("|")]


def _soft_wrap_long_tokens(text: str, max_len: int = 60) -> str:
    """Break very long unbreakable tokens so fpdf can lay out Cyrillic/Latin text."""
    parts: list[str] = []
    for token in re.split(r"(\s+)", text):
        if not token or token.isspace():
            parts.append(token)
            continue
        if len(token) <= max_len:
            parts.append(token)
            continue
        parts.append("\n".join(token[i : i + max_len] for i in range(0, len(token), max_len)))
    return "".join(parts)


class MarkdownPDFWriter:
    def __init__(self, pdf: ReportPDF, has_font: bool):
        self.pdf = pdf
        self.has_font = has_font
        self.body_size = 10
        self.line_height = 5.5

    def _content_width(self, left_indent: float = 0) -> float:
        width = self.pdf.w - self.pdf.l_margin - self.pdf.r_margin - left_indent
        return max(width, 20)

    def _reset_x(self, left_indent: float = 0) -> None:
        self.pdf.set_x(self.pdf.l_margin + left_indent)

    def _set_font(self, style: str = "", size: int | None = None):
        size = size or self.body_size
        if self.has_font:
            self.pdf.set_font("DejaVu", style, size)
        else:
            family = "Helvetica"
            if style == "B":
                family = "Helvetica"
            self.pdf.set_font(family, style, size)

    def _write_multiline(self, text: str, size: int | None = None, left_indent: float = 0):
        self._set_font("", size)
        self.pdf.set_text_color(0, 0, 0)
        self._reset_x(left_indent)
        safe_text = _soft_wrap_long_tokens(_strip_inline_markdown(text))
        self.pdf.multi_cell(self._content_width(left_indent), self.line_height, safe_text)

    def write_heading(self, text: str, level: int):
        sizes = {1: 16, 2: 13, 3: 11}
        self.pdf.ln(2 if level > 1 else 4)
        self._set_font("B", sizes.get(level, 11))
        self.pdf.set_text_color(0, 0, 0)
        self._reset_x()
        safe_text = _soft_wrap_long_tokens(_strip_inline_markdown(text))
        self.pdf.multi_cell(self._content_width(), self.line_height + 1, safe_text)
        self.pdf.ln(1)

    def write_paragraph(self, text: str):
        if not text.strip():
            self.pdf.ln(2)
            return
        self._write_multiline(text)

    def write_bullet(self, text: str, depth: int = 0):
        indent = 6 + depth * 4
        bullet_w = 4
        text_width = self._content_width(indent + bullet_w)
        self._set_font("", self.body_size)
        self.pdf.set_text_color(0, 0, 0)
        self._reset_x(indent)
        self.pdf.cell(bullet_w, self.line_height, "•")
        safe_text = _soft_wrap_long_tokens(_strip_inline_markdown(text))
        self.pdf.multi_cell(text_width, self.line_height, safe_text)
        self.pdf.ln(0.5)
        self._reset_x()

    def write_hr(self):
        self.pdf.ln(3)
        y = self.pdf.get_y()
        self.pdf.set_draw_color(200, 200, 200)
        self.pdf.line(self.pdf.l_margin, y, self.pdf.w - self.pdf.r_margin, y)
        self.pdf.ln(4)

    def write_table(self, rows: list[list[str]]):
        if not rows:
            return
        col_count = max(len(r) for r in rows)
        if col_count == 0:
            return

        page_width = self._content_width()
        col_width = max(page_width / col_count, 18)
        if col_width * col_count > page_width:
            col_width = page_width / col_count

        self.pdf.ln(2)
        self._reset_x()
        for row_idx, row in enumerate(rows):
            padded = [_soft_wrap_long_tokens(cell, max_len=40) for cell in row] + [""] * (col_count - len(row))
            is_header = row_idx == 0
            self._set_font("B" if is_header else "", 9)
            self.pdf.set_fill_color(245, 245, 245) if is_header else self.pdf.set_fill_color(255, 255, 255)
            self.pdf.set_text_color(0, 0, 0)

            x_start = self.pdf.l_margin
            y_start = self.pdf.get_y()
            max_h = self.line_height

            cell_lines: list[list[str]] = []
            for cell in padded:
                lines = self.pdf.multi_cell(col_width, self.line_height, cell, split_only=True)
                cell_lines.append(lines or [""])
                max_h = max(max_h, self.line_height * len(lines or [""]))

            if y_start + max_h > self.pdf.page_break_trigger:
                self.pdf.add_page()
                y_start = self.pdf.get_y()
                x_start = self.pdf.l_margin

            for col_idx, lines in enumerate(cell_lines):
                x = x_start + col_idx * col_width
                self.pdf.rect(x, y_start, col_width, max_h)
                self.pdf.set_xy(x, y_start)
                self.pdf.multi_cell(col_width, self.line_height, "\n".join(lines), fill=is_header)

            self.pdf.set_xy(self.pdf.l_margin, y_start + max_h)
        self.pdf.ln(3)
        self._reset_x()

    def render(self, content: str):
        lines = (content or "").split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if stripped.startswith("# "):
                self.write_heading(stripped[2:], 1)
            elif stripped.startswith("## "):
                self.write_heading(stripped[3:], 2)
            elif stripped.startswith("### "):
                self.write_heading(stripped[4:], 3)
            elif stripped.startswith("#### "):
                self.write_heading(stripped[5:], 3)
            elif stripped in ("---", "***", "___"):
                self.write_hr()
            elif stripped.startswith("|") and "|" in stripped[1:]:
                table_rows: list[list[str]] = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    if not _is_table_separator(lines[i]):
                        table_rows.append(_parse_table_row(lines[i]))
                    i += 1
                self.write_table(table_rows)
                continue
            elif re.match(r"^[-*]\s+", stripped):
                bullet_text = re.sub(r"^[-*]\s+", "", stripped)
                self.write_bullet(bullet_text)
            elif re.match(r"^\d+\.\s+", stripped):
                numbered = re.sub(r"^\d+\.\s+", "", stripped)
                self.write_bullet(numbered)
            elif stripped:
                self.write_paragraph(stripped)
            else:
                self.pdf.ln(2)

            i += 1


def render_report_pdf(
    title: str,
    content: str,
    period_from: str = "",
    period_to: str = "",
    author: str = "",
) -> bytes:
    pdf = ReportPDF()
    font_path = _resolve_font()
    bold_path = font_path.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf") if font_path else None
    has_font = bool(font_path)
    if font_path:
        pdf.add_font("DejaVu", "", font_path)
        if bold_path and os.path.isfile(bold_path):
            pdf.add_font("DejaVu", "B", bold_path)

    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    body = (content or "").strip()
    starts_with_heading = body.startswith("#")

    if not starts_with_heading:
        if has_font:
            pdf.set_font("DejaVu", "B", 16)
        else:
            pdf.set_font("Helvetica", "B", 16)
        content_width = pdf.w - pdf.l_margin - pdf.r_margin
        pdf.multi_cell(content_width, 10, title or "Отчёт")
        pdf.ln(3)

        meta_parts = []
        if period_from and period_to:
            meta_parts.append(f"Период: {period_from} — {period_to}")
        if author:
            meta_parts.append(author)
        if meta_parts:
            if has_font:
                pdf.set_font("DejaVu", "", 10)
            else:
                pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(100, 100, 100)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(content_width, 6, " · ".join(meta_parts))
            pdf.ln(4)
            pdf.set_text_color(0, 0, 0)

        body_to_render = body
    else:
        body_to_render = body

    MarkdownPDFWriter(pdf, has_font).render(body_to_render)

    return bytes(pdf.output())
