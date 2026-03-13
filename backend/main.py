from core.extractor import extract_itr_parameters, display_results, save_results
from core.tax_engine import calculate_tax, print_tax_summary
from core.optimizer import run_all_scenarios, print_optimization_report
import json

files = ["testCases/Form16.pdf"]

if __name__ == "__main__":
    # Stage 1 — Extract
    params = extract_itr_parameters(files)
    display_results(params)

    # Stage 2 — Calculate
    tax_result = calculate_tax(params)
    print_tax_summary(tax_result)

    # Stage 3 — Optimize
    optimization = run_all_scenarios(params, tax_result)
    print_optimization_report(optimization)

    # Save
    with open("output/tax_result.json", "w") as f:
        json.dump(tax_result, f, indent=2)
    with open("output/optimization.json", "w") as f:
        json.dump(optimization, f, indent=2)