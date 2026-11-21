"""Build a compact table and paired sensitivity checks from saved baseline runs."""
import argparse
import csv
from itertools import combinations
import json
from pathlib import Path

STRATEGIES = ("local", "global", "fixed")
REFERENCES = ("cc-pvqz", "cc-pv5z")


def load(directory, name):
    return json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))


def summarize(directory):
    reports = [load(directory, f"lih-level{level}") for level in (3, 4, 5)]
    baseline = load(directory, "lih-baseline")
    h2 = load(directory, "h2-symmetry")
    failure = load(directory, "lih-low-max-cycle")
    linear = load(directory, "lih-near-linear")
    assert all(report["status"] == "ok" for report in [baseline, h2, *reports])
    assert failure["status"] == "failed" and not failure["fits"][0]["converged"]
    assert linear["status"] == "failed" and linear["fits"][-1]["status"] == "rejected_overlap"
    assert linear["diagnostics"]["base"]["projected"]["rank"] < linear["diagnostics"]["base"]["projected"]["raw_dimension"]

    rows = []
    for report in reports:
        trajectories = report["trajectories"]
        levels = [row["budget_ao"] for row in trajectories["local"]]
        expected = [0]
        for angular in report["config"]["shell_angular_momentum_schedule"]:
            expected.append(expected[-1] + 2 * angular + 1)
        assert levels == expected
        fits = {entry["label"]: entry for entry in report["fits"]}
        for strategy in STRATEGIES:
            assert [row["budget_ao"] for row in trajectories[strategy]] == levels
            for row in trajectories[strategy]:
                fit = fits[row["fit"]]
                assert fit["converged"] and fit["status"] == "ok"
                rows.append({
                    "grid_level": report["grid_level"], "strategy": strategy,
                    "budget_ao": row["budget_ao"], "nao": row["nao"],
                    "selected": row.get("selected", ""), "energy_ha": row["energy_ha"],
                    "abs_qz_mha": row["deviations"]["cc-pvqz"]["absolute_ha"] * 1000,
                    "abs_5z_mha": row["deviations"]["cc-pv5z"]["absolute_ha"] * 1000,
                    "scf_seconds": fit["wall_seconds"], "scf_cycles": fit["cycles"],
                    "orthogonality_fro": fit["overlap_orthogonality"],
                })
        assert all(fit["grid_sha256"] == report["grid_protocol"]["sha256"] for fit in fits.values())

    paired = []
    for budget in levels[1:]:
        for left, right in combinations(STRATEGIES, 2):
            values = []
            for report in reports:
                def lookup(strategy):
                    return next(r for r in report["trajectories"][strategy] if r["budget_ao"] == budget)
                a, b = lookup(left), lookup(right)
                for name in REFERENCES:
                    values.append({
                        "grid_level": report["grid_level"], "reference": name,
                        "error_right_minus_left_mha": (
                            b["deviations"][name]["absolute_ha"] - a["deviations"][name]["absolute_ha"]
                        ) * 1000,
                    })
            paired.append({"budget_ao": budget, "left": left, "right": right, "values": values})

    h2_scores = h2["diagnostics"]["base"]["local_squared"]
    hs = list(h2_scores.values())
    rel_symmetry = abs(hs[0] - hs[1]) / max(hs)
    assert rel_symmetry < 1e-8
    fits = [r for report in reports for r in report["fits"]]
    result = {
        "grid_levels": [r["grid_level"] for r in reports],
        "reference_differences_ha": {
            str(r["grid_level"]): r["references"]["cc-pvqz"]["energy_ha"] - r["references"]["cc-pv5z"]["energy_ha"]
            for r in reports
        },
        "lowest_successful_overlap_ratio": min(r["overlap"]["relative_min"] for r in fits),
        "greatest_old_eigen_dual": max(r["old_eigen_residual_dual"] for r in fits),
        "greatest_quadrature_relative_closure": max(
            diag["quadrature_relative_closure"] for r in reports for diag in r["diagnostics"].values()
        ),
        "h2_atom_relative_difference": rel_symmetry,
        "first_step_exhaustive": {
            str(r["grid_level"]): {
                "score_order": [v["id"] for v in sorted(r["first_step_exhaustive"], key=lambda v: -v["score"])],
                "energy_drop_order": [v["id"] for v in sorted(r["first_step_exhaustive"], key=lambda v: -v["drop_ha"])],
            } for r in reports
        },
        "paired_strategy_differences": paired,
    }
    with (directory / "matched-budget.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (directory / "sensitivity-summary.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(f"Checked {len(rows)} matched-budget table rows and the H2, SCF, and overlap controls.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    summarize(parser.parse_args().directory)
