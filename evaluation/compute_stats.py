#!/usr/bin/env python3
"""
Compute empirical statistics for the clean 40-case 4-system benchmark.
Results file schema: per_system -> list of case dicts with keys:
  case_id, department, action_alignment, conflict_awareness,
  factual_grounding, risk_foresight, composite
"""
import json, numpy as np
from scipy import stats
from pathlib import Path

RESULTS_FILE = Path(__file__).parent / "results" / "quality_experiment_results_clean4.json"

METRICS      = ["action_alignment","conflict_awareness","factual_grounding","risk_foresight","composite"]
METRIC_LABELS= ["ActAlign","ConflAware","FactGround","RiskFore","Composite"]

SYS_KEYS = {
    "G1":   "Baseline G1: Zero-Shot CoT",
    "G2":   "Baseline G2: Single-Agent Multi-Persona",
    "G3":   "Baseline G3: Hybrid RAG Single-Agent",
    "MARS": "MARS: Multi-Agent Hybrid + MMR + Cross-Dept",
}

# ── helpers ──────────────────────────────────────────────────────────────────
def load_data():
    d = json.loads(RESULTS_FILE.read_text())
    ps = d["per_system"]
    # Convert each system's list → dict keyed by case_id
    data = {}
    for short, full in SYS_KEYS.items():
        data[short] = {c["case_id"]: c for c in ps[full]}
    return data

def arr(data, system, metric):
    """Ordered numpy array of metric values for a system."""
    return np.array([
        data[system][cid][metric]
        for cid in sorted(data[system].keys())
    ])

def bootstrap_ci(x, n_boot=10000, ci=0.95, seed=42):
    rng = np.random.default_rng(seed)
    boot = rng.choice(x, size=(n_boot, len(x)), replace=True).mean(axis=1)
    lo, hi = np.percentile(boot, [(1-ci)/2*100, (1+ci)/2*100])
    return lo, hi

def cohens_d(a, b):
    sp = np.sqrt((np.var(a, ddof=1) + np.var(b, ddof=1)) / 2)
    return (np.mean(a) - np.mean(b)) / sp if sp > 0 else 0.0

def wilcox(a, b):
    try:
        w, p = stats.wilcoxon(a, b, alternative='greater')
    except ValueError:
        w, p = 0.0, 1.0
    n = len(a)
    r = 1 - (4 * w) / (n * (n + 1))   # rank-biserial correlation
    return w, p, r

def sig(p):
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"

# ── main ─────────────────────────────────────────────────────────────────────
def main():
    data = load_data()
    systems = list(SYS_KEYS.keys())

    # 1. Overall means ────────────────────────────────────────────────────────
    print("\n" + "="*92)
    print("1. OVERALL MEAN SCORES  (n=40 cases)")
    print("="*92)
    print(f"{'System':<8}" + "".join(f"{m:>12}" for m in METRIC_LABELS))
    print("-"*92)
    means = {}
    for s in systems:
        means[s] = {m: arr(data, s, m) for m in METRICS}
        row = f"{s:<8}" + "".join(f"{means[s][m].mean():>12.3f}" for m in METRICS)
        print(row)

    # 2. Bootstrap CIs for Composite ─────────────────────────────────────────
    print("\n" + "="*92)
    print("2. 95% BOOTSTRAP CIs — COMPOSITE  (10 000 resamples)")
    print("="*92)
    print(f"{'System':<8}{'Mean':>8}{'CI_lo':>10}{'CI_hi':>10}{'Width':>10}")
    print("-"*92)
    for s in systems:
        comp = means[s]["composite"]
        lo, hi = bootstrap_ci(comp)
        print(f"{s:<8}{comp.mean():>8.3f}{lo:>10.3f}{hi:>10.3f}{hi-lo:>10.3f}")

    # 3. Wilcoxon: MARS vs each baseline ─────────────────────────────────────
    print("\n" + "="*92)
    print("3. PAIRED WILCOXON SIGNED-RANK — MARS > Baseline  (Composite)")
    print("="*92)
    print(f"{'Comparison':<22}{'W':>8}{'p':>12}{'r_rb':>8}{'Cohen_d':>10}{'Sig':>6}")
    print("-"*92)
    mars_c = means["MARS"]["composite"]
    for b in ["G1","G2","G3"]:
        base_c = means[b]["composite"]
        w, p, r = wilcox(mars_c, base_c)
        d = cohens_d(mars_c, base_c)
        print(f"{'MARS > '+b:<22}{w:>8.1f}{p:>12.4f}{r:>8.3f}{d:>10.3f}{sig(p):>6}")

    # 4. Per-metric Wilcoxon vs best baseline ─────────────────────────────────
    print("\n" + "="*92)
    print("4. PER-METRIC WILCOXON — MARS vs Best Baseline")
    print("="*92)
    print(f"{'Metric':<14}{'Best':>6}{'MARS':>8}{'Base':>8}{'p':>12}{'r_rb':>8}{'Sig':>6}")
    print("-"*92)
    for m, ml in zip(METRICS, METRIC_LABELS):
        mars_m = means["MARS"][m]
        best_b = max(["G1","G2","G3"], key=lambda b: means[b][m].mean())
        base_m = means[best_b][m]
        _, p, r = wilcox(mars_m, base_m)
        print(f"{ml:<14}{best_b:>6}{mars_m.mean():>8.3f}{base_m.mean():>8.3f}{p:>12.4f}{r:>8.3f}{sig(p):>6}")

    # 5. Per-department composite breakdown ───────────────────────────────────
    print("\n" + "="*92)
    print("5. PER-DEPARTMENT COMPOSITE SCORES")
    print("="*92)
    print(f"{'Dept':<14}" + "".join(f"{s:>10}" for s in systems) + f"{'MARS_lead':>12}")
    print("-"*92)
    depts = ["Finance","Operations","R&D","Legal"]
    for dept in depts:
        row_vals = {}
        for s in systems:
            dept_cases = [v["composite"] for v in data[s].values() if v["department"] == dept]
            row_vals[s] = np.mean(dept_cases) if dept_cases else float('nan')
        best_base = max(["G1","G2","G3"], key=lambda b: row_vals[b])
        lead = row_vals["MARS"] - row_vals[best_base]
        row = f"{dept:<14}" + "".join(f"{row_vals[s]:>10.3f}" for s in systems) + f"{lead:>+12.3f}"
        print(row)

    print("\n" + "="*92)
    print("Done.")
    print("="*92)

if __name__ == "__main__":
    main()
