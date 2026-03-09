# ITR AI — Backend

Intelligent ITR (Income Tax Return) filing assistant using Agentic AI.  
Automatically extracts, classifies, calculates, and validates tax parameters from financial documents.

---

## Current Status

| Agent | File | Status |
|-------|------|--------|
| 01 — Ingestion + Extraction | `core/extractor.py` | ✅ Done |
| 02 — Classification | `core/classifier.py` | 🔜 Next |
| 03 — Tax Engine | `core/tax_engine.py` | 🔮 Upcoming |
| 04 — RAG Knowledge | `rag/retriever.py` | 🔮 Upcoming |
| 05 — Validation | `core/validator.py` | 🔮 Upcoming |
| 06 — Optimization | `core/optimizer.py` | 🔮 Upcoming |
| 07 — Output Generator | `output/report_generator.py` | 🔮 Upcoming |

---

## Tech Stack

- **Python 3.10**
- **pdfplumber** — digital PDF text extraction
- **EasyOCR** — scanned PDF text extraction
- **PyMuPDF (fitz)** — PDF to image conversion + PDF type detection
- **Groq API** (llama-3.3-70b-versatile) — LLM parameter extraction
- **LangChain + FAISS** — RAG pipeline (upcoming)
- **FastAPI** — API server (upcoming)

---

## Folder Structure

```
backend/
│
├── core/
│   ├── extractor.py        ← OCR + Groq extraction pipeline (DONE)
│   ├── classifier.py       ← ITR form classifier (Agent 02)
│   ├── tax_engine.py       ← hardcoded tax calculations (Agent 03)
│   ├── validator.py        ← validation checks (Agent 05)
│   └── optimizer.py        ← regime optimiser (Agent 06)
│
├── rag/
│   ├── knowledge_base/     ← tax law text files go here
│   ├── embedder.py         ← converts docs to vectors
│   └── retriever.py        ← queries vector DB
│
├── agents/
│   └── orchestrator.py     ← runs all agents in sequence
│
├── documents/              ← put test PDFs here
│
├── output/
│   └── report_generator.py ← PDF + JSON output
│
├── testCases/              ← sample documents for testing
├── .devcontainer/
│   └── devcontainer.json   ← Codespaces auto-setup config
├── .env                    ← API keys (never commit this)
├── .gitignore
├── main.py                 ← entry point
├── requirements.txt
└── README.md
```

---

## Setup — Option A: GitHub Codespaces (Recommended)

This is the easiest way. Everything installs automatically.

**Step 1 — Open Codespaces**
```
1. Go to github.com/YOUR_USERNAME/IPD-25-26
2. Click the green "Code" button
3. Click "Codespaces" tab
4. Click "Create codespace on main"
```

Wait ~1 minute. VS Code opens in your browser with Python 3.10 and all packages already installed.

**Step 2 — Add your Groq API key**

Option A — Codespaces Secret (recommended, do this once):
```
1. Go to github.com → Settings → Codespaces → Secrets
2. New secret → Name: GROQ_API_KEY → Value: your key
3. Select repo: IPD-25-26 → Save
```

Option B — manually in terminal each session:
```bash
echo "GROQ_API_KEY=your_key_here" > .env
```

Get a free Groq API key at: https://console.groq.com

**Step 3 — Run**
```bash
python main.py
```

---

## Setup — Option B: Local (requires Python 3.10 or 3.11)

> ⚠️ Python 3.12+ breaks EasyOCR. Use 3.10 or 3.11 only.

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/IPD-25-26.git
cd IPD-25-26/backend

# 2. Create a virtual environment with Python 3.10
py -3.10 -m venv venv          # Windows
python3.10 -m venv venv        # Mac/Linux

# 3. Activate it
venv\Scripts\activate          # Windows
source venv/bin/activate       # Mac/Linux

# 4. Install packages
pip install -r requirements.txt

# 5. Add your API key
echo "GROQ_API_KEY=your_key_here" > .env

# 6. Run
python main.py
```

---

## Running the Pipeline

**1. Put a test PDF in the `testCases/` folder**

Supported documents:
- Form 16 (Part A and B)
- Bank statements
- Salary slips
- Form 26AS

**2. Update the file path in `main.py`**

```python
files = ["testCases/your_document.pdf"]
```

**3. Run**

```bash
python main.py
```

**4. Output**

Results are printed to the terminal and saved to `output/itr_extracted.json`.

```
📊  EXTRACTED ITR PARAMETERS
════════════════════════════════════════════════════
👤 Personal
─────────────────────────────────────────────────
  name                           Rajesh Kumar
  pan                            ABCDE1234F
  age                            32

💼 Salary
─────────────────────────────────────────────────
  gross_salary                   ₹ 12,00,000
  ...
```

---

## Verify Your Environment

Run this to check all packages are installed correctly:

```bash
python check_env.py
```

Expected output:
```
✅ pymupdf
✅ pdfplumber
✅ easyocr
✅ groq
✅ dotenv
✅ langchain
✅ faiss
✅ sentence-transformers
✅ pydantic
```

---

## Parameters Extracted (22 total)

| Category | Parameters |
|----------|-----------|
| Personal | name, pan, age |
| Salary | gross_salary, basic_salary, hra_received, rent_paid, other_allowances, standard_deduction |
| Other Income | capital_gains, house_property_income, business_income, other_income |
| Deductions | deduction_80C, deduction_80D, deduction_80G, interest_on_home_loan |
| Tax Paid | tds_salary, tds_bank, advance_tax, self_assessment_tax |
| Filing | regime (old/new) |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | ✅ Yes | Get free at console.groq.com |

---

## Important Notes

- Never commit your `.env` file — it is in `.gitignore`
- Never share your Groq API key publicly
- The `documents/` and `output/` folders are also gitignored
- First run downloads ~100MB EasyOCR model — this is normal

---

## Troubleshooting

**`easyocr` not found / NameError**
→ Make sure `import easyocr` is at the top of `extractor.py` before it is used

**`FileNotFoundError: no such file`**
→ Run `find /workspaces -name "*.pdf"` to find your PDF and update the path in `main.py`

**`GROQ_API_KEY not set`**
→ Check your `.env` file exists and contains the key, or set it as a Codespaces Secret

**EasyOCR crashes PC / high RAM usage**
→ Use Codespaces instead of running locally — EasyOCR needs ~2GB RAM

**Python version error**
→ Make sure you are using Python 3.10 or 3.11, not 3.12 or 3.14
