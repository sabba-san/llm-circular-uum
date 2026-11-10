#!/usr/bin/env python3
"""
Multi-Format Text Extractor & Semantic Chunker for UUM College Documents
Handles:
  - PDF: page-by-page via pdftotext, with tesseract OCR fallback for scanned pages
  - DOCX: XML parsing from word/document.xml with heading detection
  - DOC: legacy Word 97-2003 binary stream extraction (ASCII + UTF-16LE)
  - JPG/PNG: direct OCR extraction via tesseract
  - ZIP: redirected to pre-extracted chapter PDFs
"""

import os
import re
import tempfile
import zipfile
import subprocess
import xml.etree.ElementTree as ET

def extract_chunks_from_pdf(filepath, max_pages=150):
    """Extract page-level chunks from PDF using fast pdftotext; fallback to OCR only if PDF has no text."""
    chunks = []
    try:
        res = subprocess.run(["pdftotext", filepath, "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        full_text = res.stdout.decode("utf-8", errors="ignore")
    except Exception:
        full_text = ""

    # If the entire PDF has almost no text (< 100 chars), it is a scanned document -> use OCR
    if len(full_text.strip()) < 100:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                img_prefix = os.path.join(tmpdir, "page")
                # Render up to first 5 pages for scanned documents
                subprocess.run(
                    ["pdftoppm", "-png", "-r", "150", "-f", "1", "-l", "5", filepath, img_prefix],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=25
                )
                imgs = sorted([os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.endswith(".png")])
                for idx, img in enumerate(imgs, 1):
                    ocr_out = os.path.join(tmpdir, f"ocr_{idx}")
                    subprocess.run(
                        ["tesseract", img, ocr_out],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=20
                    )
                    txt_path = ocr_out + ".txt"
                    if os.path.exists(txt_path):
                        with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                            ocr_txt = f.read().strip()
                        if len(ocr_txt) > 30:
                            chunks.append({
                                "page": idx,
                                "heading": f"Scanned Page {idx}",
                                "text": ocr_txt[:1400]
                            })
        except Exception:
            pass
        return chunks

    pages = full_text.split("\x0c") if full_text else []
    limit_pages = min(len(pages), max_pages)

    for p_idx in range(limit_pages):
        p = p_idx + 1
        page_text = pages[p_idx].strip()
        if not page_text or len(page_text) < 30:
            continue

        # Split page text into semantic paragraphs
        raw_paras = [para.strip() for para in page_text.split("\n\n") if len(para.strip()) > 25]
        if not raw_paras:
            raw_paras = [page_text]

        curr_text = []
        curr_len = 0
        heading = f"Page {p}"

        for para in raw_paras:
            first_line = para.split("\n")[0].strip()
            if len(first_line) < 80 and (first_line.isupper() or re.match(r"^\d+[\.\)]", first_line) or "BAB" in first_line.upper() or "SECTION" in first_line.upper()):
                heading = first_line

            curr_text.append(para)
            curr_len += len(para)

            if curr_len >= 800:
                chunks.append({
                    "page": p,
                    "heading": heading[:100],
                    "text": "\n".join(curr_text)[:1400]
                })
                curr_text = []
                curr_len = 0

        if curr_text:
            chunks.append({
                "page": p,
                "heading": heading[:100],
                "text": "\n".join(curr_text)[:1400]
            })

    return chunks

def extract_chunks_from_docx(filepath):
    """Extract structured paragraphs and headings from modern DOCX files."""
    chunks = []
    try:
        with zipfile.ZipFile(filepath, "r") as z:
            xml_content = z.read("word/document.xml")
        tree = ET.fromstring(xml_content)

        current_heading = "General"
        current_paras = []
        current_len = 0

        for p in tree.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
            t = "".join(n.text for n in p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t") if n.text).strip()
            if not t:
                continue

            # Heading candidate: short uppercase or numbered line
            if len(t) < 70 and (t.isupper() or re.match(r"^\d+[\.\)]", t) or "BAHAGIAN" in t.upper() or "PART" in t.upper()):
                if current_paras:
                    chunks.append({
                        "page": 1,
                        "heading": current_heading[:100],
                        "text": "\n".join(current_paras)[:1400]
                    })
                    current_paras = []
                    current_len = 0
                current_heading = t
            else:
                current_paras.append(t)
                current_len += len(t)
                if current_len >= 800:
                    chunks.append({
                        "page": 1,
                        "heading": current_heading[:100],
                        "text": "\n".join(current_paras)[:1400]
                    })
                    current_paras = []
                    current_len = 0

        if current_paras:
            chunks.append({
                "page": 1,
                "heading": current_heading[:100],
                "text": "\n".join(current_paras)[:1400]
            })
    except Exception:
        pass
    return chunks

def extract_chunks_from_doc(filepath):
    """Extract text from legacy Word 97-2003 binary compound documents (.doc)."""
    chunks = []
    try:
        with open(filepath, "rb") as f:
            raw = f.read()

        # Try UTF-16LE strings (standard in Word 97-2003 OLE)
        utf16_words = re.findall(b"(?:[\x20-\x7E]\x00){4,}", raw)
        utf16_text = "\n".join(w.decode("utf-16le", errors="ignore").strip() for w in utf16_words if len(w.strip()) > 3)

        # Try ASCII strings
        ascii_words = re.findall(rb"[\x20-\x7E]{4,}", raw)
        ascii_text = "\n".join(w.decode("latin1", errors="ignore").strip() for w in ascii_words if len(w.strip()) > 3)

        chosen = utf16_text if len(utf16_text) > len(ascii_text) else ascii_text
        lines = [l.strip() for l in chosen.split("\n") if len(l.strip()) > 4]

        current_heading = "Form Content"
        curr_paras = []
        curr_len = 0

        for line in lines:
            if len(line) < 60 and (line.isupper() or re.match(r"^\d+[\.\)]", line)):
                if curr_paras:
                    chunks.append({
                        "page": 1,
                        "heading": current_heading[:100],
                        "text": "\n".join(curr_paras)[:1400]
                    })
                    curr_paras = []
                    curr_len = 0
                current_heading = line
            else:
                curr_paras.append(line)
                curr_len += len(line)
                if curr_len >= 800:
                    chunks.append({
                        "page": 1,
                        "heading": current_heading[:100],
                        "text": "\n".join(curr_paras)[:1400]
                    })
                    curr_paras = []
                    curr_len = 0

        if curr_paras:
            chunks.append({
                "page": 1,
                "heading": current_heading[:100],
                "text": "\n".join(curr_paras)[:1400]
            })
    except Exception:
        pass
    return chunks

def extract_chunks_from_image(filepath):
    """Extract text from image files (JPG, PNG) using Tesseract OCR."""
    chunks = []
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ocr_out = os.path.join(tmpdir, "ocr")
            res = subprocess.run(
                ["tesseract", filepath, ocr_out],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            txt_file = ocr_out + ".txt"
            if os.path.exists(txt_file):
                with open(txt_file, "r", encoding="utf-8", errors="ignore") as f:
                    txt = f.read().strip()
                if len(txt) > 20:
                    lines = [l.strip() for l in txt.split("\n") if l.strip()]
                    heading = lines[0][:80] if lines else "Infographic / Scanned Form"
                    chunks.append({
                        "page": 1,
                        "heading": heading,
                        "text": txt[:1400]
                    })
    except Exception:
        pass
    return chunks

def extract_document_chunks(filepath, max_pages=150):
    """Route document to appropriate extractor by extension and return list of chunks."""
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".pdf":
        return extract_chunks_from_pdf(filepath, max_pages=max_pages)
    elif ext == ".docx":
        return extract_chunks_from_docx(filepath)
    elif ext == ".doc":
        return extract_chunks_from_doc(filepath)
    elif ext in [".png", ".jpg", ".jpeg"]:
        return extract_chunks_from_image(filepath)
    elif ext == ".zip":
        # Check if pre-extracted directory exists
        extracted_dir = filepath[:-4] + "_extracted"
        if os.path.exists(extracted_dir):
            nested_chunks = []
            for root, _, files in os.walk(extracted_dir):
                for f in sorted(files):
                    if f.endswith(".pdf"):
                        fpath = os.path.join(root, f)
                        c_title = os.path.splitext(f)[0]
                        sub_chunks = extract_chunks_from_pdf(fpath, max_pages=50)
                        for sc in sub_chunks:
                            sc["heading"] = f"{c_title} - {sc['heading']}"[:100]
                            nested_chunks.append(sc)
            return nested_chunks
    return []

