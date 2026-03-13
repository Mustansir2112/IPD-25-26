# ================================================================
#  ITR AI — Optimization / Simulation Engine
#  File    : core/optimizer.py
#  Scope   : Salaried individuals — FY 2025-26
#  Runs    : Both regimes independently
#  Purpose : Finds all legal tax-saving opportunities
#            by re-running tax engine with modified params
# ================================================================

from core.tax_engine import (
    calculate_tax,
    CAP_80C,
    CAP_80D,
    CAP_80CCD1B,
    CAP_80TTA,
    REBATE_87A_OLD_LIMIT,
    REBATE_87A_NEW_LIMIT,
)


# ── HELPERS ──────────────────────────────────────────────────

def _val(x):
    """Returns x if not None, else 0."""
    return x if x is not None else 0


def _priority(saving: float, rebate_triggered: bool = False) -> str:
    """Assigns priority based on saving amount."""
    if rebate_triggered or saving > 10_000:
        return "HIGH"
    elif saving >= 2_000:
        return "MEDIUM"
    else:
        return "LOW"


def _get_80D_cap(params: dict) -> int:
    """
    80D cap is age-dependent.
    Below 60  → ₹25,000
    60 and above → ₹50,000 (senior citizen)
    """
    age = _val(params.get("age"))
    return 50_000 if age >= 60 else CAP_80D


def run_scenario(params: dict, changes: dict, regime: str) -> float:
    """
    Core simulation function.
    Copies params, applies changes, reruns tax engine.
    Returns the final tax for the given regime.

    Args:
        params  : original 25 extracted parameters
        changes : dict of fields to override
        regime  : "old" or "new"

    Returns:
        final_tax (float) for the modified scenario
    """
    modified = {**params, **changes}
    result   = calculate_tax(modified)
    return result[f"{regime}_regime"]["final_tax"]


# ================================================================
#  SCENARIO 1 — 80C Top-up (OLD regime)
# ================================================================
def check_80C_topup(params: dict, result: dict) -> dict | None:
    """
    Checks if 80C limit (₹1,50,000) is fully utilized.
    If not, calculates tax saving from investing the unused amount.
    Only applicable in old regime.
    """
    current_80C = _val(params.get("deduction_80C"))

    if current_80C >= CAP_80C:
        return None

    unused       = CAP_80C - current_80C
    original_tax = result["old_regime"]["final_tax"]
    new_tax      = run_scenario(params, {"deduction_80C": CAP_80C}, "old")
    saving       = round(original_tax - new_tax, 2)

    if saving <= 0:
        return None

    return {
        "scenario": "80C Limit Not Fully Used",
        "priority": _priority(saving),
        "regime":   "old",
        "saving":   saving,
        "action":   f"Invest ₹{unused:,.0f} more under Section 80C",
        "message": (
            f"You have claimed ₹{current_80C:,.0f} under 80C "
            f"but the limit is ₹{CAP_80C:,.0f}. "
            f"You have ₹{unused:,.0f} of unused limit. "
            f"Investing this amount saves you ₹{saving:,.2f} in tax."
        ),
        "how": "PPF / ELSS Mutual Funds / LIC Premium / NSC / 5-year Tax Saver FD",
    }


# ================================================================
#  SCENARIO 2 — NPS Top-up 80CCD(1B) (OLD regime)
# ================================================================
def check_nps_topup(params: dict, result: dict) -> dict | None:
    """
    Checks if NPS 80CCD(1B) limit (₹50,000) is fully utilized.
    This deduction is OVER AND ABOVE the ₹1.5L 80C limit.
    Only applicable in old regime.
    """
    current_nps = _val(params.get("deduction_80CCD1B"))

    if current_nps >= CAP_80CCD1B:
        return None

    unused       = CAP_80CCD1B - current_nps
    original_tax = result["old_regime"]["final_tax"]
    new_tax      = run_scenario(params, {"deduction_80CCD1B": CAP_80CCD1B}, "old")
    saving       = round(original_tax - new_tax, 2)

    if saving <= 0:
        return None

    return {
        "scenario": "NPS Investment — Section 80CCD(1B)",
        "priority": _priority(saving),
        "regime":   "old",
        "saving":   saving,
        "action":   f"Invest ₹{unused:,.0f} more in NPS",
        "message": (
            f"You have claimed ₹{current_nps:,.0f} under 80CCD(1B) "
            f"but the limit is ₹{CAP_80CCD1B:,.0f}. "
            f"This deduction is completely separate from your ₹1.5L 80C limit. "
            f"Investing ₹{unused:,.0f} more in NPS saves you ₹{saving:,.2f} in tax."
        ),
        "how": "NPS Tier-1 Account (National Pension System)",
    }


# ================================================================
#  SCENARIO 3 — Health Insurance 80D Top-up (OLD regime)
# ================================================================
def check_80D_topup(params: dict, result: dict) -> dict | None:
    """
    Checks if 80D health insurance deduction is fully utilized.
    Cap is age-dependent:
      Below 60  → ₹25,000
      60+       → ₹50,000 (senior citizen)
    Only applicable in old regime.
    """
    cap_80D     = _get_80D_cap(params)
    current_80D = _val(params.get("deduction_80D"))

    if current_80D >= cap_80D:
        return None

    unused       = cap_80D - current_80D
    original_tax = result["old_regime"]["final_tax"]
    new_tax      = run_scenario(params, {"deduction_80D": cap_80D}, "old")
    saving       = round(original_tax - new_tax, 2)

    if saving <= 0:
        return None

    age      = _val(params.get("age"))
    cap_note = f"₹{cap_80D:,.0f} (senior citizen)" if age >= 60 else f"₹{cap_80D:,.0f}"

    return {
        "scenario": "Health Insurance — Section 80D",
        "priority": _priority(saving),
        "regime":   "old",
        "saving":   saving,
        "action":   f"Claim ₹{unused:,.0f} more under Section 80D",
        "message": (
            f"You have claimed ₹{current_80D:,.0f} under 80D "
            f"but the limit for your age group is {cap_note}. "
            f"Buying or upgrading your health insurance policy "
            f"saves you ₹{saving:,.2f} in tax."
        ),
        "how": "Health insurance premium for self / spouse / children / parents",
    }


# ================================================================
#  SCENARIO 4 — 87A Rebate Opportunity (OLD regime)
#  Includes combined scenario: 80C + NPS together close the gap
# ================================================================
def check_87A_opportunity_old(params: dict, result: dict) -> dict | None:
    """
    Checks if taxable income (old regime) is just above ₹5,00,000.
    If gap ≤ ₹75,000 and can be closed via unused 80C / NPS / combination
    → entire tax becomes ₹0 via Section 87A rebate.

    Checks three ways to close the gap:
      1. Unused 80C alone
      2. Unused NPS alone
      3. Combination of both (Option A — combined scenario)
    """
    taxable      = result["old_regime"]["taxable_income"]
    original_tax = result["old_regime"]["final_tax"]
    gap          = taxable - REBATE_87A_OLD_LIMIT

    # Not applicable conditions
    if gap <= 0:
        return None   # Already below threshold
    if gap > 75_000:
        return None   # Gap too large to realistically close
    if original_tax == 0:
        return None   # Already paying no tax

    unused_80C = max(0.0, CAP_80C     - _val(params.get("deduction_80C")))
    unused_NPS = max(0.0, CAP_80CCD1B - _val(params.get("deduction_80CCD1B")))
    total_avail = unused_80C + unused_NPS

    if total_avail < gap:
        return None   # Cannot close the gap even with all available deductions

    # ── Determine investment plan ────────────────────────────
    if unused_80C >= gap:
        # 80C alone closes the gap
        invest_80C = gap
        invest_NPS = 0
        action     = f"Invest ₹{invest_80C:,.0f} more in 80C"
        how        = "PPF / ELSS / LIC Premium / NSC"

    elif unused_NPS >= gap:
        # NPS alone closes the gap
        invest_80C = 0
        invest_NPS = gap
        action     = f"Invest ₹{invest_NPS:,.0f} more in NPS"
        how        = "NPS Tier-1 Account"

    else:
        # Combined: use all of unused 80C + remaining from NPS
        invest_80C = unused_80C
        invest_NPS = gap - unused_80C
        action     = (
            f"Invest ₹{invest_80C:,.0f} in 80C "
            f"+ ₹{invest_NPS:,.0f} in NPS (combined)"
        )
        how = "PPF/ELSS for 80C portion + NPS Tier-1 for remaining"

    # ── Build changes and verify saving ─────────────────────
    changes = {}
    if invest_80C > 0:
        changes["deduction_80C"]     = _val(params.get("deduction_80C"))     + invest_80C
    if invest_NPS > 0:
        changes["deduction_80CCD1B"] = _val(params.get("deduction_80CCD1B")) + invest_NPS

    new_tax = run_scenario(params, changes, "old")
    saving  = round(original_tax - new_tax, 2)

    if saving <= 0:
        return None

    return {
        "scenario": "Section 87A Rebate Opportunity — Old Regime",
        "priority": "HIGH",
        "regime":   "old",
        "saving":   saving,
        "action":   action,
        "message": (
            f"Your taxable income (old regime) is ₹{taxable:,.0f} — "
            f"only ₹{gap:,.0f} above the ₹{REBATE_87A_OLD_LIMIT:,.0f} rebate threshold. "
            f"{action} to bring income to ₹{REBATE_87A_OLD_LIMIT:,.0f}. "
            f"Section 87A rebate then applies → "
            f"your entire tax of ₹{original_tax:,.2f} becomes ₹0."
        ),
        "how": how,
    }


# ================================================================
#  SCENARIO 5 — 87A Rebate Opportunity (NEW regime)
# ================================================================
def check_87A_opportunity_new(params: dict, result: dict) -> dict | None:
    """
    Checks if taxable income (new regime) is just above ₹12,00,000.
    New regime has no deductions to reduce income, so can only
    suggest switching to old regime as an alternative.
    """
    taxable      = result["new_regime"]["taxable_income"]
    original_tax = result["new_regime"]["final_tax"]
    gap          = taxable - REBATE_87A_NEW_LIMIT

    if gap <= 0:
        return None
    if gap > 75_000:
        return None
    if original_tax == 0:
        return None

    return {
        "scenario": "Section 87A Rebate Threshold — New Regime",
        "priority": "HIGH",
        "regime":   "new",
        "saving":   original_tax,
        "action":   "Consider switching to Old Regime to invest and close this gap",
        "message": (
            f"Your taxable income (new regime) is ₹{taxable:,.0f} — "
            f"only ₹{gap:,.0f} above the ₹{REBATE_87A_NEW_LIMIT:,.0f} rebate threshold. "
            f"New regime does not allow deductions to close this gap. "
            f"Switching to old regime and investing ₹{gap:,.0f} in 80C/NPS "
            f"could bring your income below the threshold "
            f"and eliminate your tax of ₹{original_tax:,.2f} entirely."
        ),
        "how": "Switch to Old Regime + invest in PPF / ELSS / NPS to close the gap",
    }


# ================================================================
#  SCENARIO 6 — Regime Switch
# ================================================================
def check_regime_switch(params: dict, result: dict) -> dict | None:
    """
    Compares old vs new regime final tax.
    Only surfaces this suggestion if the user is in the WRONG regime —
    i.e. they're paying more than they need to.
    """
    old_tax  = result["old_regime"]["final_tax"]
    new_tax  = result["new_regime"]["final_tax"]
    declared = (params.get("regime") or "new").lower()

    if old_tax == new_tax:
        return None  # Both equal, no suggestion needed

    if new_tax < old_tax:
        saving = round(old_tax - new_tax, 2)
        if declared == "new":
            return None  # Already in the better regime
        return {
            "scenario": "Switch to New Regime",
            "priority": _priority(saving),
            "regime":   "new",
            "saving":   saving,
            "action":   "Switch to New Regime for this financial year",
            "message": (
                f"You are in the Old Regime but New Regime saves you ₹{saving:,.2f}. "
                f"Old Regime tax: ₹{old_tax:,.2f} → New Regime tax: ₹{new_tax:,.2f}."
            ),
            "how": "Inform your employer at start of FY or declare at ITR filing time",
        }
    else:
        saving = round(new_tax - old_tax, 2)
        if declared == "old":
            return None  # Already in the better regime
        return {
            "scenario": "Switch to Old Regime",
            "priority": _priority(saving),
            "regime":   "old",
            "saving":   saving,
            "action":   "Switch to Old Regime and invest in deductions",
            "message": (
                f"You are in the New Regime but Old Regime saves you ₹{saving:,.2f} "
                f"after all deductions. "
                f"New Regime tax: ₹{new_tax:,.2f} → Old Regime tax: ₹{old_tax:,.2f}."
            ),
            "how": "Inform your employer at start of FY or declare at ITR filing time",
        }


# ================================================================
#  SCENARIO 7 — 80G Donation Reminder (OLD regime)
# ================================================================
def check_80G_reminder(params: dict, result: dict) -> dict | None:
    """
    If no 80G deduction is claimed, reminds user that donations
    to eligible organizations are 50-100% deductible.
    This is a reminder, not a calculated saving, since we don't
    know if the user actually made donations.

    Also checks: if old regime 87A gap can be partially closed
    via donations (50% deductible), it notes this as an option.
    """
    current_80G  = _val(params.get("deduction_80G"))
    old_tax      = result["old_regime"]["final_tax"]

    if current_80G > 0:
        return None   # Already claiming 80G
    if old_tax == 0:
        return None   # No tax to save

    # Check if 87A gap exists and donations could help close it
    taxable = result["old_regime"]["taxable_income"]
    gap     = taxable - REBATE_87A_OLD_LIMIT

    if 0 < gap <= 75_000:
        # To get ₹gap deduction via 80G at 50% rate → need to donate gap*2
        donation_needed = gap * 2
        extra_note = (
            f" Note: To close your ₹{gap:,.0f} gap to the 87A threshold, "
            f"you would need to donate ₹{donation_needed:,.0f} "
            f"(50% rule gives ₹{gap:,.0f} deduction) → tax becomes ₹0."
        )
    else:
        extra_note = ""

    return {
        "scenario": "Unclaimed Donations — Section 80G (Reminder)",
        "priority": "LOW",
        "regime":   "old",
        "saving":   0.0,
        "action":   "Check if you made donations to eligible organizations",
        "message": (
            "You have not claimed any deduction under Section 80G. "
            "If you made donations this year to eligible organizations, "
            "50% to 100% of the amount is deductible — reducing your taxable income."
            + extra_note
        ),
        "how": (
            "PM CARES Fund (100%) / PM National Relief Fund (100%) / "
            "Registered NGOs (50%) / Temples & Trusts (50%)"
        ),
    }


# ================================================================
#  MASTER FUNCTION — run_all_scenarios
# ================================================================
def run_all_scenarios(params: dict, result: dict) -> dict:
    """
    Runs all 7 optimization scenarios for both regimes.
    Filters out inapplicable ones, sorts by priority + saving.

    Args:
        params : 25 extracted ITR parameters
        result : output from calculate_tax(params)

    Returns:
        dict with suggestions list + total potential saving
    """
    checks = [
        # Highest impact first in check order
        check_87A_opportunity_old(params, result),
        check_87A_opportunity_new(params, result),
        check_regime_switch(params, result),
        check_80C_topup(params, result),
        check_nps_topup(params, result),
        check_80D_topup(params, result),
        check_80G_reminder(params, result),
    ]

    # Filter out None (not applicable) results
    suggestions = [s for s in checks if s is not None]

    # Sort: priority first (HIGH → MEDIUM → LOW), then saving descending
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    suggestions.sort(key=lambda x: (priority_order[x["priority"]], -x["saving"]))

    total_saving = sum(s["saving"] for s in suggestions)

    return {
        "suggestions":            suggestions,
        "total_potential_saving": round(total_saving, 2),
        "count":                  len(suggestions),
    }


# ================================================================
#  DISPLAY — print_optimization_report
# ================================================================
def print_optimization_report(optimization: dict):
    """
    Pretty prints all optimization suggestions to terminal.
    Shows priority, saving, action, and explanation for each.
    """
    suggestions = optimization["suggestions"]
    total       = optimization["total_potential_saving"]
    count       = optimization["count"]

    print("\n" + "═" * 66)
    print("OPTIMIZATION SUGGESTIONS  —  FY 2025-26")
    # print("═" * 66)

    if not suggestions:
        print("\n Tax is fully optimized.")
        print("      No further savings found under current parameters.")
        print("\n" + "═" * 66 + "\n")
        return

    priority_icons = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}

    for i, s in enumerate(suggestions, 1):
        icon   = priority_icons[s["priority"]]
        saving = f"₹{s['saving']:,.2f}" if s["saving"] > 0 else "Reminder"

        print(f"\n  {i}[{s['priority']}]  {s['scenario']}")
        print(f"      Regime  : {s['regime'].upper()}")
        print(f"      Saving  : {saving}")
        print(f"      Action  : {s['action']}")
        print(f"      How     : {s['how']}")
        print(f"\n{s['message']}")
        print("  " + "─" * 62)

    print(f"\n  {'Total Potential Tax Saving':<40} ₹{total:>12,.2f}")
    print(f"  {'Suggestions Found':<40} {count}")
    # print("═" * 66 + "\n")