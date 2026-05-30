#!/usr/bin/env python3
"""
Generate Pandoc reference.docx with diploma formatting from FORMAT.md.
Run: python make_reference.py
Output: diploma/reference.docx
"""

import subprocess
import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING

PANDOC = r"C:\Users\XVII\AppData\Local\Pandoc\pandoc.exe"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(SCRIPT_DIR, "reference.docx")
TEMP = os.path.join(SCRIPT_DIR, "_temp_default_ref.docx")


def extract_default_reference():
    result = subprocess.run(
        [PANDOC, "--print-default-data-file", "reference.docx"],
        capture_output=True, check=True
    )
    with open(TEMP, "wb") as f:
        f.write(result.stdout)


def force_tnr_all(doc):
    """Force Times New Roman, no italic, black color on every style."""
    for style in doc.styles:
        try:
            f = style.font
            if f is not None:
                f.name = "Times New Roman"
                f.italic = False
                f.color.rgb = RGBColor(0, 0, 0)
        except Exception:
            pass


def normal_style(style):
    """Body text: TNR 14pt, justified, 1.25cm indent, 1.5 line spacing."""
    f = style.font
    f.name = "Times New Roman"
    f.size = Pt(14)
    f.bold = False
    f.italic = False
    f.color.rgb = RGBColor(0, 0, 0)

    pf = style.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf.first_line_indent = Cm(1.25)
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = 1.5
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.widow_control = True


def heading_style(style, size, centered=False, page_break=False,
                  indent=Cm(1.25), space_before=Pt(12), space_after=Pt(12)):
    """Heading: TNR bold, justified or centered, no italic."""
    f = style.font
    f.name = "Times New Roman"
    f.size = Pt(size)
    f.bold = True
    f.italic = False
    f.color.rgb = RGBColor(0, 0, 0)
    f.underline = False

    pf = style.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER if centered else WD_ALIGN_PARAGRAPH.JUSTIFY
    pf.first_line_indent = Cm(0) if centered else indent
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = 1.5
    pf.space_before = space_before
    pf.space_after = space_after
    pf.page_break_before = page_break
    pf.widow_control = True
    pf.keep_with_next = True


def caption_style(style):
    """Figure/table caption: TNR 14pt, centered, 12pt around, NO italic, NO bold."""
    f = style.font
    f.name = "Times New Roman"
    f.size = Pt(14)
    f.bold = False
    f.italic = False
    f.color.rgb = RGBColor(0, 0, 0)

    pf = style.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf.first_line_indent = Cm(0)
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = 1.5
    pf.space_before = Pt(12)
    pf.space_after = Pt(12)


def main():
    print("Extracting Pandoc default reference.docx ...")
    extract_default_reference()

    doc = Document(TEMP)

    # --- Step 1: Force TNR + no-italic on ALL styles as baseline ---
    force_tnr_all(doc)
    print("  Force TNR applied to all styles")

    # --- Page margins ---
    for section in doc.sections:
        section.left_margin = Cm(3.0)
        section.right_margin = Cm(1.0)
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)

    # --- Normal (body text) ---
    normal_style(doc.styles["Normal"])

    # --- Heading 1: chapter title, centered, no auto page break ---
    heading_style(
        doc.styles["Heading 1"],
        size=16, centered=True, page_break=False,
        space_before=Pt(0), space_after=Pt(12)
    )

    # --- Heading 2: section, 1.25cm indent, no auto page break ---
    heading_style(
        doc.styles["Heading 2"],
        size=16, centered=False, page_break=False,
        space_before=Pt(0), space_after=Pt(12)
    )

    # --- Heading 3: subsection, no page break ---
    heading_style(
        doc.styles["Heading 3"],
        size=14, centered=False, page_break=False,
        space_before=Pt(12), space_after=Pt(12)
    )

    # --- Heading 4+ ---
    for h in ("Heading 4", "Heading 5"):
        try:
            heading_style(
                doc.styles[h],
                size=14, centered=False, page_break=False,
                space_before=Pt(12), space_after=Pt(12)
            )
        except KeyError:
            pass

    # --- Caption: figure/table captions, explicit no-italic ---
    all_style_names = [s.name for s in doc.styles]
    caption_applied = False
    for name in ("Caption", "Image Caption", "Figure Caption", "Table Caption"):
        if name in all_style_names:
            caption_style(doc.styles[name])
            caption_applied = True
            print(f"  Caption style applied: '{name}'")
            break
    if not caption_applied:
        print("  WARNING: no caption style found")

    # --- Code/Verbatim styles: TNR 12pt, no italic, no bold ---
    for name in ("Verbatim Char", "Source Code", "Verbatim", "Code", "Compact",
                 "Verbatim Char", "Code Block"):
        if name in all_style_names:
            s = doc.styles[name]
            s.font.name = "Times New Roman"
            s.font.size = Pt(12)
            s.font.italic = False
            s.font.bold = False
            print(f"  Code style fixed: '{name}'")

    # --- Table body cells: TNR 12pt, left-aligned, no indent ---
    for name in ("Table Contents", "Table Paragraph"):
        if name in all_style_names:
            s = doc.styles[name]
            s.font.name = "Times New Roman"
            s.font.size = Pt(12)
            s.font.italic = False
            s.font.bold = False
            s.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
            s.paragraph_format.first_line_indent = Cm(0)
            print(f"  Table style fixed: '{name}'")

    doc.save(OUTPUT)
    os.remove(TEMP)
    print(f"OK: reference.docx -> {OUTPUT}")


if __name__ == "__main__":
    main()
