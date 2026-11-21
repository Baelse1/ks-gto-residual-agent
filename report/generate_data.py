"""Create LaTeX data tables from archived calculations and audit records."""
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {}


def read(path):
    raw = (ROOT / path).read_bytes()
    SOURCES[path] = sha256(raw).hexdigest()
    return raw


def load(path):
    return json.loads(read(path))


def scale(value):
    mantissa, exponent = f"{value:.2e}".split("e")
    return rf"{mantissa}\times 10^{{{int(exponent)}}}"


def main(output):
    output.mkdir(parents=True, exist_ok=True)
    smoke = load("evidence/stage1/numerics.json")
    base = load("evidence/stage3/lih-baseline.json")
    nominal = load("evidence/stage3/lih-level3.json")
    sens = load("evidence/stage3/sensitivity-summary.json")
    scf = load("evidence/stage3/lih-low-max-cycle.json")["fits"][0]
    linear = load("evidence/stage3/lih-near-linear.json")
    first = load("evidence/stage4/results/15/stage4_probe.json")
    repeated = load("evidence/stage4/results/17/stage4_followup.json")
    ablation = load("evidence/stage4/results/21/stage4_followup.json")
    sweep = load("evidence/stage4/results/33/stage4_probe.json")
    audit = load("evidence/stage4/audit.json")
    state = load("evidence/stage4/agent/checkpoint.json")
    verification = load("evidence/stage4/reproduction-check.json")
    read("evidence/stage4/agent/events.jsonl")
    read("evidence/stage4/ranking.png")
    read("config/agent.stage4.json")
    assert audit["journal_sha256"] == SOURCES["evidence/stage4/agent/events.jsonl"]
    assert state["config_sha256"] == SOURCES["config/agent.stage4.json"]
    actions = {row["action"]: row for row in audit["scientific_tool_actions"]}
    assert len(actions) == state["steps_total"]
    assert [actions[n]["exit_code"] for n in (14, 15, 17, 21, 28, 30, 32, 33)] == [0, 0, 0, 0, 1, 1, 0, 0]
    assert actions[4]["http_status"] == 403 and actions[6]["http_status"] == 200
    assert first["rankings"] == repeated["rankings"]
    for r in verification["comparisons"]:
        assert r["max_abs_difference"] == 0
        assert SOURCES[f"evidence/stage4/results/{r['source_result']}"] == r["source_sha256"]
    for step in (13, 20, 27, 31):
        revision = actions[step]["revision"]
        read(revision)
        assert SOURCES[revision] == actions[step]["sha256"]
    for step in (15, 17, 21, 33):
        for artifact in actions[step]["artifacts"]:
            assert SOURCES[artifact["archive"]] == artifact["sha256"]

    table = []
    for rows in zip(*(nominal["trajectories"][key] for key in ("local", "global", "fixed")), strict=True):
        a, b, c = rows
        assert a["budget_ao"] == b["budget_ao"] == c["budget_ao"]
        errors = [f'{row["deviations"]["cc-pvqz"]["absolute_ha"] * 1000:.3f}' for row in rows]
        table.append(" & ".join([str(a["budget_ao"]), str(a["nao"]), *errors]) + r" \\")

    candidates = {row["id"]: row for row in first["candidates"]}
    assert all(r["status"] == "ok" and r["scf"]["nao"] == 7 for r in candidates.values())
    margins = {key: 1000 * (candidates["H_s20"][key] - candidates["Li_s08"][key])
               for key in ("frozen_drop_ha", "frozen_density_total_drop_ha", "scf_drop_ha")}
    atom_gaps = []
    for grid in ("3", "4"):
        conditions = ablation["grids"][grid]
        assert set(conditions["original"]["strategy_choices"].values()) == {"Li_s32"}
        changed = conditions["without_Li_s32"]
        assert set(changed["strategy_choices"].values()) == {"Li_s08"}
        rows = {row["id"]: row for row in changed["candidates"]}
        assert all(row["status"] == "ok" and row["ao_cost"] == 1 for row in rows.values())
        gap = 1000 * (rows["H_s20"]["scf_drop_ha"] - rows["Li_s08"]["scf_drop_ha"])
        assert round(gap, 3) == round(margins["scf_drop_ha"], 3)
        points = sweep["grids"][grid]["partition_sweep"]
        assert {r["partition_gamma"] for r in points} == {0.25, 0.5, 1.0}
        assert all(set(r["strategy_choices"].values()) == {"Li_s08"} for r in points)
        atom_gaps.extend(r["li_minus_h_squared"] for r in points)

    diag = base["diagnostics"]["base"]
    frozen = diag["frozen"]
    assert frozen["separation_ha"] > 0 and frozen["sin_theta_fro"] <= frozen["bound"]
    assert frozen["bound"] > math.sqrt(2)
    assert smoke["frozen_sin_theta_frobenius"] <= smoke["frozen_sin_theta_bound"]
    assert not scf["converged"] and linear["fits"][-1]["status"] == "rejected_overlap"
    paired = next(r["values"] for r in sens["paired_strategy_differences"]
                  if r["budget_ao"] == 5 and r["left"] == "local" and r["right"] == "fixed")
    gains = [r["error_right_minus_left_mha"] for r in paired]
    values = {
        "ToolCount": len(actions), "CallCount": audit["model_calls_total"],
        "EnergyQZ": f'{base["references"]["cc-pvqz"]["energy_ha"]:.10f}',
        "EnergyFiveZ": f'{base["references"]["cc-pv5z"]["energy_ha"]:.10f}',
        "ReferenceGap": f'{1000*sens["reference_differences_ha"]["3"]:.3f}',
        "DictGap": f'{1000*(base["references"]["dictionary_full"]["energy_ha"]-base["references"]["cc-pvqz"]["energy_ha"]):.3f}',
        "MinGain": f"{min(gains):.4f}", "MaxGain": f"{max(gains):.4f}",
        "OldDual": scale(diag["old_stationarity_dual"]), "NewDual": scale(diag["candidate_space_dual"]),
        "HoldoutDual": scale(math.sqrt(diag["holdout_outside_union"]["dual_squared"])),
        "QuadError": scale(sens["greatest_quadrature_relative_closure"]),
        "OverlapRatio": scale(sens["lowest_successful_overlap_ratio"]),
        "HtwoSymmetry": scale(sens["h2_atom_relative_difference"]),
        "BadGradient": f'{scf["old_eigen_residual_dual"]:.5f}',
        "SmokeDelta": f'{smoke["frozen_separation_ha"]:.5f}',
        "SmokeError": f'{smoke["frozen_sin_theta_frobenius"]:.5f}',
        "SmokeBound": f'{smoke["frozen_sin_theta_bound"]:.5f}',
        "BaseDelta": f'{frozen["separation_ha"]:.5f}', "BaseError": f'{frozen["sin_theta_fro"]:.5f}',
        "BaseBound": f'{frozen["bound"]:.5f}',
        "FrozenMargin": f'{margins["frozen_drop_ha"]:.3f}',
        "DensityMargin": f'{margins["frozen_density_total_drop_ha"]:.3f}',
        "ScfMargin": f'{margins["scf_drop_ha"]:.3f}',
        "SmallestAtomGap": scale(min(atom_gaps)), "LargestAtomGap": scale(max(atom_gaps)),
        "FirstSeconds": f'{actions[15]["elapsed_seconds"]:.3f}',
        "AblationSeconds": f'{actions[21]["elapsed_seconds"]:.3f}',
        "SweepSeconds": f'{actions[33]["elapsed_seconds"]:.3f}',
    }
    commands = [rf"\newcommand{{\{key}}}{{{value}}}" for key, value in values.items()]
    commands.append(r"\newcommand{\BaselineRows}{" + "\n".join(table) + "}")
    (output / "data.tex").write_text("\n".join(commands) + "\n", encoding="utf-8")
    (output / "inputs.json").write_text(json.dumps({"source_sha256": SOURCES, "report_values": values}, indent=2) + "\n",
                                        encoding="utf-8")
    print(f"Verified {len(SOURCES)} sources and wrote {len(values)} report values.")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
