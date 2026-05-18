#!/usr/bin/env python3
"""
Post-process Pandoc-generated diploma.docx:
- Tables: autofit layout, standard 0.5pt borders, no cell paragraph indent
- Captions: remove italic/bold from all runs
"""
import sys
import os
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Cm

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT = os.path.join(SCRIPT_DIR, "diploma.docx")


def _set_tbl_autofit(table):
    tbl = table._tbl
    tblPr = tbl.find(qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl.insert(0, tblPr)

    # Remove existing layout element and replace with autofit
    for old in tblPr.findall(qn("w:tblLayout")):
        tblPr.remove(old)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "autofit")
    tblPr.append(layout)

    # Remove fixed table-level width
    for tblW in tblPr.findall(qn("w:tblW")):
        tblW.set(qn("w:type"), "auto")
        tblW.set(qn("w:w"), "0")

    # Remove fixed column widths from tblGrid
    tblGrid = tbl.find(qn("w:tblGrid"))
    if tblGrid is not None:
        for col in tblGrid.findall(qn("w:gridCol")):
            col.attrib.pop(qn("w:w"), None)

    # Set table-level borders
    for old in tblPr.findall(qn("w:tblBorders")):
        tblPr.remove(old)
    tblBorders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")       # 0.5pt
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000")
        tblBorders.append(el)
    tblPr.append(tblBorders)


def _fix_cell(cell):
    tc = cell._tc

    # Remove fixed cell width (let autofit decide)
    tcPr = tc.find(qn("w:tcPr"))
    if tcPr is not None:
        for tcW in tcPr.findall(qn("w:tcW")):
            tcW.set(qn("w:type"), "auto")
            tcW.set(qn("w:w"), "0")

    # Remove first-line indent from each paragraph in cell
    for para in cell.paragraphs:
        pPr = para._p.find(qn("w:pPr"))
        if pPr is not None:
            for ind in pPr.findall(qn("w:ind")):
                ind.attrib.pop(qn("w:firstLine"), None)
                ind.attrib.pop(qn("w:firstLineChars"), None)
        para.paragraph_format.first_line_indent = Cm(0)


def process_tables(doc):
    count = 0
    for table in doc.tables:
        _set_tbl_autofit(table)
        for row in table.rows:
            for cell in row.cells:
                _fix_cell(cell)
        count += 1
    return count


def fix_captions(doc):
    count = 0
    for para in doc.paragraphs:
        if para.style.name == "Caption":
            para.paragraph_format.first_line_indent = Cm(0)
            for run in para.runs:
                run.font.italic = False
                run.font.bold = False
            count += 1
    return count


def main():
    if not os.path.exists(INPUT):
        print(f"FAIL: {INPUT} not found")
        sys.exit(1)

    doc = Document(INPUT)
    tables = process_tables(doc)
    captions = fix_captions(doc)
    doc.save(INPUT)
    print(f"OK: postprocessed {INPUT} ({tables} tables, {captions} captions)")


if __name__ == "__main__":
    main()
