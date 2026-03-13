from dotenv import load_dotenv
import os
import json
import re
import io
import fitz                 # PyMuPDF
import pdfplumber
import numpy as np
import easyocr
from pathlib import Path
from PIL import Image
from groq import Groq
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL   = "llama-3.3-70b-versatile"

PARAMETERS = [
    "name", "pan", "age",
    "gross_salary", "basic_salary", "hra_received", "rent_paid",
    "other_allowances", "standard_deduction",
    "capital_gains", "house_property_income", "business_income", "other_income",
    "deduction_80C", "deduction_80D", "deduction_80G", "interest_on_home_loan",
    "tds_salary", "tds_bank", "advance_tax", "self_assessment_tax",
    "regime",
    "deduction_80CCD1B",
    "deduction_80TTA",
    "employer_pf"
]

print("Loading EasyOCR... (downloads ~100 MB model on first run)")
ocr_reader = easyocr.Reader(
    ["en"],
    gpu=False,
    verbose=False
)
print("EasyOCR ready ✅")

def is_scanned_pdf(pdf_path: str, threshold: int = 50) -> bool:
    """
    Opens first 3 pages with PyMuPDF and tries to pull text.
    < threshold chars → scanned image PDF → use EasyOCR.
    >= threshold chars → native digital PDF → use pdfplumber.
    """
    doc = fitz.open(pdf_path)
    chars = sum(len(p.get_text("text").strip()) for p in doc[:3])
    doc.close()

    if chars < threshold:
        print(f"  → SCANNED PDF ({chars} chars) — routing to EasyOCR")
        return True
    print(f"  → DIGITAL PDF ({chars} chars) — routing to pdfplumber")
    return False

def extract_text_digital(pdf_path: str) -> str:
    """
    pdfplumber extracts both tables and plain text.
    Tables are flattened to tab-separated rows so the LLM
    can still read label-value pairs like Form 16 has.
    """
    full_text = ""

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):

            # Tables first (Form 16 is table-heavy)
            table_text = ""
            for table in page.extract_tables():
                for row in table:
                    clean = [cell.strip() if cell else "" for cell in row]
                    table_text += "\t".join(clean) + "\n"

            plain = page.extract_text() or ""

            full_text += f"\n\n--- PAGE {i+1} ---\n"
            if table_text:
                full_text += f"[TABLES]\n{table_text}\n"
            full_text += f"[TEXT]\n{plain}"

    return full_text.strip()

def extract_text_scanned(pdf_path: str, dpi: int = 250) -> str:
    """
    Renders each page to an image at dpi=250, then runs EasyOCR.
    Lines are sorted top-to-bottom to preserve reading order.
    Only keeps results with confidence > 0.5 to filter OCR noise.
    """
    doc = fitz.open(pdf_path)
    full_text = ""

    for page_num in range(len(doc)):
        page = doc[page_num]
        mat  = fitz.Matrix(dpi / 72, dpi / 72)

        # render page to image, but MuPDF sometimes chokes on malformed
        # JPEG streams ("Not a JPEG file" errors). In that case fall back to
        # pdfplumber rendering which is generally more forgiving.
        try:
            pix  = page.get_pixmap(matrix=mat)
            img  = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        except Exception as exc:  # broad because fitz raises RuntimeError
            print(f"  ⚠️  Rendering page {page_num+1} via MuPDF failed: {exc}")
            print("      Attempting fallback rendering with pdfplumber")
            with pdfplumber.open(pdf_path) as pdf2:
                page2 = pdf2.pages[page_num]
                # pdfplumber's to_image uses pillow internally
                pil_img = page2.to_image(resolution=dpi).original
                img = pil_img.convert("RGB")

        # EasyOCR returns: [ [bbox, text, confidence], ... ]
        results = ocr_reader.readtext(np.array(img))

        # Sort by vertical centre of bounding box (top → bottom)
        results.sort(key=lambda r: (r[0][0][1] + r[0][2][1]) / 2)

        lines = [text for (_, text, conf) in results if conf > 0.5]
        page_text = "\n".join(lines)

        full_text += f"\n\n--- PAGE {page_num+1} ---\n{page_text}"
        print(f"  Page {page_num+1}: {len(lines)} lines extracted via EasyOCR")

    doc.close()
    return full_text.strip()

def extract_raw_text(file_path: str) -> str:
    """
    Auto-detects file type and routes to the right extractor.
    Supports PDF (digital + scanned) and image files.
    """
    print(f"\n📄 Processing: {Path(file_path).name}")
    ext = Path(file_path).suffix.lower()

    if ext in (".jpg", ".jpeg", ".png", ".webp"):
        print("  → Image file — using EasyOCR directly")
        img = np.array(Image.open(file_path).convert("RGB"))
        results = ocr_reader.readtext(img)
        results.sort(key=lambda r: (r[0][0][1] + r[0][2][1]) / 2)
        return "\n".join(t for (_, t, c) in results if c > 0.5)

    if ext == ".pdf":
        if is_scanned_pdf(file_path):
            return extract_text_scanned(file_path)
        else:
            return extract_text_digital(file_path)

    raise ValueError(f"Unsupported file type: {ext}")


SYSTEM_PROMPT = """You are an expert Indian income tax document parser.
Extract specific financial parameters from raw text taken from documents
like Form 16, bank statements, salary slips, and Form 26AS.

The text may contain OCR noise, inconsistent spacing, or merged columns.
Reason carefully through ambiguous values.

Respond with ONLY a valid JSON object. No markdown, no explanation."""


def build_prompt(raw_text: str) -> str:
    return f"""Extract the following 25 parameters from the document text.

PARAMETERS:
- name                  : Full taxpayer/employee name (string)
- pan                   : PAN — 10 chars uppercase e.g. ABCDE1234F (string)
- age                   : Age as integer. Compute from DOB if needed (integer)
- gross_salary          : Gross salary u/s 17(1) in INR (integer)
- basic_salary          : Basic salary component in INR (integer)
- hra_received          : House Rent Allowance received in INR (integer)
- rent_paid             : Actual rent paid in INR (integer)
- other_allowances      : Other allowances (LTA, special etc.) in INR (integer)
- standard_deduction    : Standard deduction u/s 16 — usually 50000 or 75000 (integer)
- capital_gains         : Total capital gains in INR (integer)
- house_property_income : Net house property income — can be negative (integer)
- business_income       : Business/profession income in INR (integer)
- other_income          : Other sources income (interest, dividends) in INR (integer)
- deduction_80C         : Section 80C deductions, max 150000 (integer)
- deduction_80D         : Section 80D health insurance deduction (integer)
- deduction_80G         : Section 80G donation deduction (integer)
- interest_on_home_loan : Home loan interest u/s 24(b) in INR (integer)
- tds_salary            : TDS on salary in INR (integer)
- tds_bank              : TDS on bank interest in INR (integer)
- advance_tax           : Advance tax paid in INR (integer)
- self_assessment_tax   : Self-assessment tax paid in INR (integer)
- regime                : Exactly "old" or "new". Use "new" if doc mentions
                          New Tax Regime or 115BAC. Default "old" if unclear.
- deduction_80CCD1B      : Additional NPS deduction u/s 80CCD(1B), max 50000 (integer)
- deduction_80TTA        : Savings account interest deduction u/s 80TTA, max 10000 (integer)
- employer_pf            : Employer contribution to provident fund in INR (integer)

RULES:
1. Return ONLY a JSON object with exactly these 22 keys.
2. Use null for fields not found — never guess or hallucinate.
3. Monetary values as plain integers — strip commas and ₹ symbol.
   Example: 1,20,000 → 120000
4. If a field appears multiple times, use the final/summary figure.

DOCUMENT TEXT:
\"\"\"
{raw_text}
\"\"\"

JSON:"""


def query_groq(raw_text: str) -> dict:
    """
    Sends extracted text to Groq and parses the JSON response.
    Truncates text if it exceeds safe context window size.
    """
    client = Groq(api_key=GROQ_API_KEY)

    # Stay well within 128k context — 48k chars ≈ ~12k tokens
    MAX_CHARS = 48_000
    if len(raw_text) > MAX_CHARS:
        print(f"  ⚠️  Text truncated {len(raw_text):,} → {MAX_CHARS:,} chars")
        raw_text = raw_text[:MAX_CHARS]

    print(f"\n🤖 Sending {len(raw_text):,} chars to Groq ({GROQ_MODEL})...")

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.0,     # deterministic — facts only, no creativity
        max_tokens=1024,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": build_prompt(raw_text)},
        ]
    )

    raw_out = response.choices[0].message.content.strip()

    # Strip markdown fences just in case
    raw_out = re.sub(r"^```[a-z]*\n?", "", raw_out)
    raw_out = re.sub(r"\n?```$",        "", raw_out)

    try:
        result = json.loads(raw_out)
        found  = sum(1 for v in result.values() if v is not None)
        print(f"  ✅  {found}/22 fields extracted by Groq")
        return result
    except json.JSONDecodeError:
        print("  ❌  JSON parse failed. Groq raw output:")
        print(raw_out[:600])
        return {p: None for p in PARAMETERS}

SUMMABLE = {
    "tds_salary", "tds_bank", "advance_tax", "self_assessment_tax",
    "deduction_80C", "deduction_80D", "deduction_80G",
    "deduction_80CCD1B", "deduction_80TTA",
    "capital_gains"
}

def merge_results(results: list) -> dict:
    merged = {p: None for p in PARAMETERS}
    for res in results:
        for key in PARAMETERS:
            val = res.get(key)
            if val is None:
                continue
            if merged[key] is None:
                merged[key] = val
            elif key in SUMMABLE:
                try:
                    merged[key] = int(merged[key]) + int(val)
                except (TypeError, ValueError):
                    pass
    return merged

def extract_itr_parameters(file_paths: list) -> dict:
    """
    Full pipeline: file(s) → raw text → Groq → merged JSON dict.

    Pass multiple files (Form 16 + bank statement etc.) for
    better coverage across all 22 parameters.
    """
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set. Check your .env file.")

    all_results = []

    for fp in file_paths:
        raw_text = extract_raw_text(fp)

        if not raw_text.strip():
            print(f"  ⚠️  No text extracted from {fp} — skipping")
            continue

        extracted = query_groq(raw_text)
        all_results.append(extracted)

    if not all_results:
        raise RuntimeError("No text could be extracted from any provided file.")

    final = merge_results(all_results) if len(all_results) > 1 else all_results[0]

    # Guarantee all 22 keys exist
    for p in PARAMETERS:
        final.setdefault(p, None)

    return final

def display_results(result: dict):
    SECTIONS = {
        "👤 Personal":      ["name", "pan", "age"],
        "💼 Salary": [
    "gross_salary", "basic_salary", "hra_received",
    "rent_paid", "other_allowances",
    "employer_pf",
    "standard_deduction"
],
        "💰 Other Income":  ["capital_gains", "house_property_income",
                              "business_income", "other_income"],
        "🏷️  Deductions": [
    "deduction_80C",
    "deduction_80D",
    "deduction_80G",
    "deduction_80CCD1B",
    "deduction_80TTA",
    "interest_on_home_loan"
],
        "🏦 Tax Paid":      ["tds_salary", "tds_bank", "advance_tax",
                              "self_assessment_tax"],
        "📋 Filing":        ["regime"],
    }

    print("\n" + "═"*52)
    print("    📊  EXTRACTED ITR PARAMETERS")
    print("═"*52)

    for section, keys in SECTIONS.items():
        print(f"\n{section}")
        print("─"*45)
        for key in keys:
            val = result.get(key)
            if val is None:
                disp = "—  (not found)"
            elif isinstance(val, int) and val > 999:
                disp = f"₹ {val:,}"
            else:
                disp = str(val)
            print(f"  {key:<30} {disp}")

    found = sum(1 for v in result.values() if v is not None)
    print(f"\n{'═'*52}")
    print(f"  ✅  {found}/22 parameters extracted")
    print("═"*52)

def save_results(result: dict, path: str = "output/itr_extracted.json"):
    os.makedirs("output", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n💾  Saved → {path}")