# main.py
from core.extractor import extract_itr_parameters, display_results, save_results

# ── Put your test PDF inside the documents/ folder ──
files = ["documents/form16.pdf"]

if __name__ == "__main__":
    print("=" * 50)
    print("  ITR AI — Extraction Pipeline")
    print("=" * 50)

    result = extract_itr_parameters(files)
    display_results(result)
    save_results(result, "output/itr_extracted.json")