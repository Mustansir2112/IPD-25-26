from core.extractor import extract_itr_parameters, display_results, save_results
from core.tax_engine import calculate_tax, print_tax_summary
import json

files = ["testCases/Form16_2.pdf"]

if __name__ == "__main__":
    # Stage 1 — Extract
    print("=" * 50)
    print("  STAGE 1 — EXTRACTION")
    print("=" * 50)
    params = extract_itr_parameters(files)
    display_results(params)

#     params = {
#   "name": "RAHUL SHARMA",
#   "pan": "BGTPS4832M",
#   "age": 34,
#   "gross_salary": 1400000,
#   "basic_salary": 520000,
#   "hra_received": 240000,
#   "rent_paid": 180000,
#   "other_allowances": 110500,
#   "standard_deduction": 50000,
#   "capital_gains": 45000,
#   "house_property_income": -75000,
#   "business_income": 0,
#   "other_income": 28650,
#   "deduction_80C": 150000,
#   "deduction_80D": 35000,
#   "deduction_80G": 12000,
#   "interest_on_home_loan": 180000,
#   "tds_salary": 95000,
#   "tds_bank": 3200,
#   "advance_tax": 10000,
#   "self_assessment_tax": 2500,
#   "regime": "old",
#   "deduction_80CCD1B": 50000,
#   "deduction_80TTA": 10000,
#   "employer_pf": 72000
# }
    # Stage 2 — Calculate
    print("=" * 50)
    print("  STAGE 2 — TAX CALCULATION")
    print("=" * 50)
    tax_result = calculate_tax(params)
    print_tax_summary(tax_result)

    # Save both
    save_results(params, "output/itr_extracted.json")
    with open("output/tax_result.json", "w") as f:
        json.dump(tax_result, f, indent=2)
    print("💾  Saved → output/tax_result.json")