# ================================================================
#  ITR AI — Tax Calculation Engine
#  File    : core/tax_engine.py
#  Scope   : Salaried individuals only
#  FY      : 2025-26
#  Regimes : Old + New (runs both, returns full comparison)
# ================================================================

# ── CONSTANTS (FY 2025-26) ────────────────────────────────────
# Hardcoded for now.
# Designed to be replaced by RAG queries in the next milestone.

# Standard deduction differs per regime
OLD_STANDARD_DEDUCTION  = 50_000      # old regime — ₹50,000
NEW_STANDARD_DEDUCTION  = 75_000      # new regime — ₹75,000 (Budget 2024)

CAP_80C                 = 150_000
CAP_80D                 = 25_000
CAP_80CCD1B             = 50_000
CAP_80TTA               = 10_000
MAX_HOUSE_PROPERTY_LOSS = 200_000     # section 24 loss cap
CESS_RATE               = 0.04
REBATE_87A_OLD_LIMIT    = 500_000     # old regime: ≤ ₹5L → tax = 0
REBATE_87A_NEW_LIMIT    = 1_200_000   # new regime: ≤ ₹12L → tax = 0 (FY 2025-26)

# ── Old regime slab boundaries ────────────────────────────────
OLD_SLAB_1 = 250_000
OLD_SLAB_2 = 500_000
OLD_SLAB_3 = 1_000_000

# ── New regime slab boundaries (FY 2025-26) ──────────────────
NEW_SLAB_1 = 400_000
NEW_SLAB_2 = 800_000
NEW_SLAB_3 = 1_200_000
NEW_SLAB_4 = 1_600_000
NEW_SLAB_5 = 2_000_000
NEW_SLAB_6 = 2_400_000


# ── HELPER ───────────────────────────────────────────────────
def _val(x):
    """Returns x if not None, else 0. Prevents None arithmetic errors."""
    return x if x is not None else 0


# ================================================================
#  STEP 1 — compute_gross_salary
# ================================================================
def compute_gross_salary(params: dict) -> float:
    """
    Uses gross_salary directly if extracted from document (Form 16).
    Falls back to summing components if gross_salary is missing.
    employer_pf intentionally excluded — not part of taxable salary.
    """
    if params.get("gross_salary") is not None:
        return float(params["gross_salary"])

    return (
        _val(params.get("basic_salary")) +
        _val(params.get("hra_received")) +
        _val(params.get("other_allowances"))
    )


# ================================================================
#  STEP 2 — compute_hra_exemption
# ================================================================
def compute_hra_exemption(params: dict) -> float:
    """
    HRA exemption = minimum of 3 conditions.
    Only applicable under old regime.
    Returns 0 if rent not paid or HRA not received.

    Case 1: Actual HRA received from employer
    Case 2: Rent paid − 10% of basic salary
    Case 3: 50% of basic salary (metro city assumed)
    """
    hra_received = _val(params.get("hra_received"))
    rent_paid    = _val(params.get("rent_paid"))
    basic_salary = _val(params.get("basic_salary"))

    if hra_received == 0 or rent_paid == 0:
        return 0.0

    case1 = hra_received
    case2 = rent_paid - (0.10 * basic_salary)
    case3 = 0.50 * basic_salary

    return max(0.0, min(case1, case2, case3))


# ================================================================
#  STEP 3 — compute_salary_income
# ================================================================
def compute_salary_income(gross_salary: float,
                           hra_exemption: float,
                           regime: str) -> float:
    """
    Deducts standard deduction and HRA exemption from gross salary.

    OLD regime:
      - Standard deduction = ₹50,000
      - HRA exemption applied

    NEW regime:
      - Standard deduction = ₹75,000
      - HRA exemption NOT applied (not allowed in new regime)

    Minimum result is 0.
    """
    if regime == "old":
        income = gross_salary - OLD_STANDARD_DEDUCTION - hra_exemption
    else:
        income = gross_salary - NEW_STANDARD_DEDUCTION

    return max(0.0, income)


# ================================================================
#  STEP 4 — compute_house_property_income
# ================================================================
def compute_house_property_income(params: dict) -> float:
    """
    Net house property = declared income − home loan interest.
    Loss is capped at ₹2,00,000 under section 24.
    """
    hp_income     = _val(params.get("house_property_income"))
    home_loan_int = _val(params.get("interest_on_home_loan"))

    net = hp_income - home_loan_int
    return max(net, -MAX_HOUSE_PROPERTY_LOSS)


# ================================================================
#  STEP 5 — compute_other_income_total
# ================================================================
def compute_other_income_total(params: dict) -> float:
    """
    Aggregates capital gains, business income, other income.
    Missing values default to 0.
    """
    return (
        _val(params.get("capital_gains")) +
        _val(params.get("business_income")) +
        _val(params.get("other_income"))
    )


# ================================================================
#  STEP 6 — compute_gross_total_income
# ================================================================
def compute_gross_total_income(salary_income: float,
                                net_house_property: float,
                                other_total: float) -> float:
    """
    GTI = all income heads combined.
    House property can be negative — reduces GTI.
    """
    return salary_income + net_house_property + other_total


# ================================================================
#  STEP 7 — compute_deductions_old_regime
# ================================================================
def compute_deductions_old_regime(params: dict,
                                   gross_total_income: float) -> dict:
    """
    Chapter VI-A deductions — OLD regime only.
    New regime does not allow these deductions.

    Caps applied:
      80C     → max ₹1,50,000
      80D     → max ₹25,000
      80G     → 50% of donated amount (no upper cap)
      80CCD1B → max ₹50,000 (NPS additional)
      80TTA   → max ₹10,000 (savings interest)

    Total deductions cannot exceed GTI.
    """
    d80C     = min(_val(params.get("deduction_80C")),     CAP_80C)
    d80D     = min(_val(params.get("deduction_80D")),     CAP_80D)
    d80G     = _val(params.get("deduction_80G")) * 0.50   # 50% rule
    d80CCD1B = min(_val(params.get("deduction_80CCD1B")), CAP_80CCD1B)
    d80TTA   = min(_val(params.get("deduction_80TTA")),   CAP_80TTA)

    total = min(
        d80C + d80D + d80G + d80CCD1B + d80TTA,
        gross_total_income   # cannot exceed GTI
    )

    return {
        "d80C":     round(d80C, 2),
        "d80D":     round(d80D, 2),
        "d80G":     round(d80G, 2),
        "d80CCD1B": round(d80CCD1B, 2),
        "d80TTA":   round(d80TTA, 2),
        "total":    round(total, 2),
    }


# ================================================================
#  STEP 8 — compute_taxable_income
# ================================================================
def compute_taxable_income(gross_total_income: float,
                            total_deductions: float) -> float:
    """
    Taxable income = GTI − deductions.
    For new regime total_deductions = 0.
    Minimum 0.
    """
    return max(0.0, gross_total_income - total_deductions)


# ================================================================
#  STEP 9a — calculate_old_regime_tax
# ================================================================
def calculate_old_regime_tax(taxable_income: float) -> float:
    """
    Old regime progressive slab tax.

    Slab structure:
      ₹0        – ₹2,50,000  →  0%
      ₹2,50,001 – ₹5,00,000  →  5%   → max ₹12,500
      ₹5,00,001 – ₹10,00,000 → 20%   → max ₹1,00,000
      ₹10,00,001+             → 30%
    """
    tax = 0.0

    if taxable_income > OLD_SLAB_1:
        tax += min(taxable_income - OLD_SLAB_1,
                   OLD_SLAB_2   - OLD_SLAB_1) * 0.05

    if taxable_income > OLD_SLAB_2:
        tax += min(taxable_income - OLD_SLAB_2,
                   OLD_SLAB_3   - OLD_SLAB_2) * 0.20

    if taxable_income > OLD_SLAB_3:
        tax += (taxable_income - OLD_SLAB_3) * 0.30

    return round(tax, 2)


# ================================================================
#  STEP 9b — calculate_new_regime_tax
# ================================================================
def calculate_new_regime_tax(taxable_income: float) -> float:
    """
    New regime progressive slab tax (FY 2025-26 revised slabs).

    Slab structure:
      ₹0         – ₹4,00,000  →  0%
      ₹4,00,001  – ₹8,00,000  →  5%   → max ₹20,000
      ₹8,00,001  – ₹12,00,000 → 10%   → max ₹40,000
      ₹12,00,001 – ₹16,00,000 → 15%   → max ₹60,000
      ₹16,00,001 – ₹20,00,000 → 20%   → max ₹80,000
      ₹20,00,001 – ₹24,00,000 → 25%   → max ₹1,00,000
      ₹24,00,001+              → 30%

    Note: 87A rebate (≤ ₹12L) makes tax = 0 for most taxpayers
    at this income level even before cess.
    """
    tax = 0.0

    if taxable_income > NEW_SLAB_1:
        tax += min(taxable_income - NEW_SLAB_1,
                   NEW_SLAB_2   - NEW_SLAB_1) * 0.05

    if taxable_income > NEW_SLAB_2:
        tax += min(taxable_income - NEW_SLAB_2,
                   NEW_SLAB_3   - NEW_SLAB_2) * 0.10

    if taxable_income > NEW_SLAB_3:
        tax += min(taxable_income - NEW_SLAB_3,
                   NEW_SLAB_4   - NEW_SLAB_3) * 0.15

    if taxable_income > NEW_SLAB_4:
        tax += min(taxable_income - NEW_SLAB_4,
                   NEW_SLAB_5   - NEW_SLAB_4) * 0.20

    if taxable_income > NEW_SLAB_5:
        tax += min(taxable_income - NEW_SLAB_5,
                   NEW_SLAB_6   - NEW_SLAB_5) * 0.25

    if taxable_income > NEW_SLAB_6:
        tax += (taxable_income - NEW_SLAB_6) * 0.30

    return round(tax, 2)


# ================================================================
#  STEP 10 — apply_rebate_87A
# ================================================================
def apply_rebate_87A(tax: float,
                      taxable_income: float,
                      regime: str) -> float:
    """
    Section 87A full rebate.
    If eligible, tax = 0 and cess = 0 automatically downstream.

    Old regime : taxable income ≤ ₹5,00,000  → tax = 0
    New regime : taxable income ≤ ₹12,00,000 → tax = 0 (FY 2025-26)
    """
    if regime == "old" and taxable_income <= REBATE_87A_OLD_LIMIT:
        return 0.0
    if regime == "new" and taxable_income <= REBATE_87A_NEW_LIMIT:
        return 0.0
    return tax


# ================================================================
#  STEP 11 — add_health_education_cess
# ================================================================
def add_health_education_cess(tax: float) -> tuple:
    """
    Adds 4% Health & Education Cess.
    If tax = 0 after rebate, cess = 0 automatically.
    Returns: (cess, final_tax)
    """
    cess      = round(tax * CESS_RATE, 2)
    final_tax = round(tax + cess, 2)
    return cess, final_tax


# ================================================================
#  STEP 12 — compute_tds_reconciliation
# ================================================================
def compute_tds_reconciliation(final_tax: float, params: dict) -> dict:
    """
    Reconciles final tax liability against tax already paid.

    total_paid = tds_salary + tds_bank + advance_tax + self_assessment_tax

    balance > 0 → user owes more tax
    balance < 0 → user gets a refund
    balance = 0 → fully settled
    """
    total_paid = (
        _val(params.get("tds_salary")) +
        _val(params.get("tds_bank")) +
        _val(params.get("advance_tax")) +
        _val(params.get("self_assessment_tax"))
    )

    balance = round(final_tax - total_paid, 2)

    return {
        "total_tax_paid": round(total_paid, 2),
        "balance_due":    round(max(0.0, balance), 2),
        "refund":         round(abs(min(0.0, balance)), 2),
        "status":         "refund"      if balance < 0 else
                          "balance_due" if balance > 0 else
                          "settled",
    }


# ================================================================
#  MASTER — calculate_tax
# ================================================================
def calculate_tax(params: dict) -> dict:
    """
    Master function. Always runs BOTH regimes regardless of
    declared regime — returns full comparison + recommendation.

    Args:
        params : dict — 25 extracted ITR parameters

    Returns:
        dict — full breakdown for old + new + recommendation
    """

    # ── Step 1: Gross Salary ─────────────────────────────────
    gross_salary = compute_gross_salary(params)

    # ── Step 2: HRA Exemption (old regime only) ───────────────
    hra_exemption = compute_hra_exemption(params)

    # ── Step 3: Net Salary Income — computed for BOTH regimes ─
    salary_income_old = compute_salary_income(gross_salary, hra_exemption, "old")
    salary_income_new = compute_salary_income(gross_salary, 0.0,           "new")

    # ── Step 4: House Property Income ────────────────────────
    net_house_property = compute_house_property_income(params)

    # ── Step 5: Other Income ─────────────────────────────────
    other_total = compute_other_income_total(params)

    # ── Step 6: Gross Total Income — both regimes ────────────
    gti_old = compute_gross_total_income(salary_income_old, net_house_property, other_total)
    gti_new = compute_gross_total_income(salary_income_new, net_house_property, other_total)

    # ── Step 7: Deductions ───────────────────────────────────
    # Old regime: Chapter VI-A deductions apply
    # New regime: no deductions (total = 0)
    deductions_old = compute_deductions_old_regime(params, gti_old)
    total_ded_old  = deductions_old["total"]
    total_ded_new  = 0.0

    # ── Step 8: Taxable Income ───────────────────────────────
    taxable_old = compute_taxable_income(gti_old, total_ded_old)
    taxable_new = compute_taxable_income(gti_new, total_ded_new)

    # ── Step 9: Slab Tax ─────────────────────────────────────
    raw_tax_old = calculate_old_regime_tax(taxable_old)
    raw_tax_new = calculate_new_regime_tax(taxable_new)

    # ── Step 10: Section 87A Rebate ──────────────────────────
    tax_after_rebate_old = apply_rebate_87A(raw_tax_old, taxable_old, "old")
    tax_after_rebate_new = apply_rebate_87A(raw_tax_new, taxable_new, "new")

    # ── Step 11: Health & Education Cess (4%) ────────────────
    cess_old, final_tax_old = add_health_education_cess(tax_after_rebate_old)
    cess_new, final_tax_new = add_health_education_cess(tax_after_rebate_new)

    # ── Step 12: TDS Reconciliation ──────────────────────────
    reconciliation_old = compute_tds_reconciliation(final_tax_old, params)
    reconciliation_new = compute_tds_reconciliation(final_tax_new, params)

    # ── Recommendation ───────────────────────────────────────
    if final_tax_new < final_tax_old:
        recommended = "new"
        savings     = round(final_tax_old - final_tax_new, 2)
    elif final_tax_old < final_tax_new:
        recommended = "old"
        savings     = round(final_tax_new - final_tax_old, 2)
    else:
        recommended = "either"
        savings     = 0.0

    return {
        "taxpayer": {
            "name":            params.get("name"),
            "pan":             params.get("pan"),
            "age":             params.get("age"),
            "regime_declared": params.get("regime", "new"),
        },
        "old_regime": {
            "standard_deduction":  OLD_STANDARD_DEDUCTION,
            "gross_salary":        gross_salary,
            "hra_exemption":       hra_exemption,
            "salary_income":       salary_income_old,
            "net_house_property":  net_house_property,
            "other_income_total":  other_total,
            "gross_total_income":  gti_old,
            "deductions":          deductions_old,
            "taxable_income":      taxable_old,
            "raw_tax":             raw_tax_old,
            "rebate_87A_applied":  tax_after_rebate_old == 0 and raw_tax_old > 0,
            "cess":                cess_old,
            "final_tax":           final_tax_old,
            "tds_reconciliation":  reconciliation_old,
        },
        "new_regime": {
            "standard_deduction":  NEW_STANDARD_DEDUCTION,
            "gross_salary":        gross_salary,
            "hra_exemption":       0.0,
            "salary_income":       salary_income_new,
            "net_house_property":  net_house_property,
            "other_income_total":  other_total,
            "gross_total_income":  gti_new,
            "deductions":          {"total": 0.0, "note": "not applicable in new regime"},
            "taxable_income":      taxable_new,
            "raw_tax":             raw_tax_new,
            "rebate_87A_applied":  tax_after_rebate_new == 0 and raw_tax_new > 0,
            "cess":                cess_new,
            "final_tax":           final_tax_new,
            "tds_reconciliation":  reconciliation_new,
        },
        "recommendation": {
            "regime":  recommended,
            "savings": savings,
            "message": f"{recommended.capitalize()} regime saves ₹{savings:,.2f}"
                       if recommended != "either"
                       else "Both regimes result in equal tax liability",
        },
    }


# ================================================================
#  DISPLAY — print_tax_summary
# ================================================================
def print_tax_summary(result: dict):
    """
    Pretty prints full dual-regime tax comparison to terminal.
    Always shows both old and new regime side by side.
    """
    tp  = result["taxpayer"]
    old = result["old_regime"]
    new = result["new_regime"]
    rec = result["recommendation"]

    def fmt(n):
        if isinstance(n, (int, float)):
            return f"₹ {n:>12,.2f}"
        return f"{'N/A':>15}"

    print("\n" + "═" * 66)
    print("    🧮  TAX CALCULATION SUMMARY  —  FY 2025-26")
    print("═" * 66)
    print(f"  Name            : {tp['name']}")
    print(f"  PAN             : {tp['pan']}")
    print(f"  Age             : {tp['age'] if tp['age'] else 'Not provided'}")
    print(f"  Declared Regime : {tp['regime_declared'].upper()}")

    rows = [
        ("Gross Salary",           old["gross_salary"],             new["gross_salary"]),
        ("Standard Deduction",     old["standard_deduction"],       new["standard_deduction"]),
        ("HRA Exemption",          old["hra_exemption"],            "N/A"),
        ("Net Salary Income",      old["salary_income"],            new["salary_income"]),
        ("House Property Income",  old["net_house_property"],       new["net_house_property"]),
        ("Other Income",           old["other_income_total"],       new["other_income_total"]),
        ("Gross Total Income",     old["gross_total_income"],       new["gross_total_income"]),
        ("─" * 34,                 "─" * 15,                       "─" * 15),
        ("80C Deduction",          old["deductions"]["d80C"],       "N/A"),
        ("80D Deduction",          old["deductions"]["d80D"],       "N/A"),
        ("80G Deduction (50%)",    old["deductions"]["d80G"],       "N/A"),
        ("80CCD(1B) Deduction",    old["deductions"]["d80CCD1B"],   "N/A"),
        ("80TTA Deduction",        old["deductions"]["d80TTA"],     "N/A"),
        ("Total Deductions",       old["deductions"]["total"],      0.0),
        ("─" * 34,                 "─" * 15,                       "─" * 15),
        ("Taxable Income",         old["taxable_income"],           new["taxable_income"]),
        ("Raw Tax (Slabs)",        old["raw_tax"],                  new["raw_tax"]),
        ("87A Rebate Applied",     "Yes" if old["rebate_87A_applied"] else "No",
                                   "Yes" if new["rebate_87A_applied"] else "No"),
        ("Cess @ 4%",              old["cess"],                     new["cess"]),
    ]

    print(f"\n  {'':34} {'OLD REGIME':>15}  {'NEW REGIME':>15}")
    print("  " + "─" * 66)

    for label, o_val, n_val in rows:
        if label.startswith("─"):
            print("  " + "─" * 66)
            continue
        marker = "    "
        o_str = fmt(o_val) if isinstance(o_val, (int, float)) else f"  {str(o_val):>13}"
        n_str = fmt(n_val) if isinstance(n_val, (int, float)) else f"  {str(n_val):>13}"
        print(f"{marker}{label:<34} {o_str}  {n_str}")

    # Final tax — highlighted
    print("  " + "═" * 66)
    print(f"  ★ {'FINAL TAX LIABILITY':<33} {fmt(old['final_tax'])}  {fmt(new['final_tax'])}")
    print("  " + "═" * 66)

    # TDS Reconciliation
    o_r = old["tds_reconciliation"]
    n_r = new["tds_reconciliation"]
    print(f"\n  {'TDS / Tax Already Paid':<34} {fmt(o_r['total_tax_paid'])}  {fmt(n_r['total_tax_paid'])}")
    print(f"  {'Balance Due':<34} {fmt(o_r['balance_due'])}  {fmt(n_r['balance_due'])}")
    print(f"  {'Refund':<34} {fmt(o_r['refund'])}  {fmt(n_r['refund'])}")
    print(f"  {'Status':<34} {o_r['status']:>15}  {n_r['status']:>15}")

    # Recommendation
    print(f"\n{'═' * 66}")
    print(f"  💡  RECOMMENDATION: {rec['message']}")
    print(f"{'═' * 66}\n")