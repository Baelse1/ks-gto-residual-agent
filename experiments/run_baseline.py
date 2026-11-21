"""Run the small-molecule baseline or matched-AO augmentation comparisons."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys

import h5py
import numpy as np
import pyscf
import scipy

from .gaussian_rks import NumericalIssue, System

STRATEGIES = ("local", "global", "fixed")


def clock():
    return datetime.now(timezone.utc).isoformat()


class Journal:
    def __init__(self, output, args, config, config_sha):
        self.output = output
        self.path = output.with_suffix(".jsonl")
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise FileExistsError(output)
        self.path.touch(exist_ok=False)
        self.report = {
            "status": "running", "started_utc": clock(), "case": args.case,
            "mode": args.mode, "grid_level": args.level, "command_args": sys.argv[1:],
            "config_sha256": config_sha, "config": config,
            "source_sha256": {
                path.name: sha256(path.read_bytes()).hexdigest()
                for path in (Path(__file__), Path(__file__).with_name("gaussian_rks.py"))
            },
            "versions": {"python": platform.python_version(), "pyscf": pyscf.__version__,
                         "libxc": pyscf.dft.libxc.__version__, "numpy": np.__version__,
                         "scipy": scipy.__version__, "h5py": h5py.__version__},
            "references": {}, "fits": [], "diagnostics": {},
            "trajectories": {}, "first_step_exhaustive": [],
        }
        self.save()
        self.event("start", case=args.case, level=args.level, mode=args.mode)

    def save(self):
        temp = self.output.with_suffix(".json.tmp")
        temp.write_text(json.dumps(self.report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        temp.replace(self.output)

    def event(self, name, **fields):
        row = {"time_utc": clock(), "event": name, **fields}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
        print(json.dumps(row, allow_nan=False), flush=True)

    def fit(self, system, label, ids=(), basis=None):
        self.event("scf_start", label=label, shells=ids, basis=basis or system.config["base_basis"])
        mf, row = system.solve(system.molecule(ids, basis=basis))
        row.update(label=label, shells=list(ids), basis=basis or system.config["base_basis"])
        self.report["fits"].append(row)
        self.save()
        self.event("scf_end", label=label, status=row["status"], energy_ha=row.get("energy_ha"),
                   nao=row["nao"], wall_seconds=row["wall_seconds"])
        if row["status"] != "ok":
            raise NumericalIssue(f"{label}: {row['status']}; raw SCF diagnostics saved.")
        return mf, row

    def diagnose(self, system, mf, label, ids):
        row = system.diagnose(mf, ids)
        self.report["diagnostics"][label] = row
        self.save()
        self.event("diagnostic", label=label, old_dual=row["old_stationarity_dual"],
                   candidate_dual=row.get("candidate_space_dual"),
                   quadrature_relative_closure=row.get("quadrature_relative_closure"))
        if row["occupied_moment_fro"] > system.tol["linear_check"]:
            raise NumericalIssue(f"{label}: occupied moment is too large.")
        if row["old_stationarity_dual"] > system.tol["stationarity_dual"]:
            raise NumericalIssue(f"{label}: old-space stationarity failed.")
        if "projected" in row:
            errors = [row["riesz_abs_closure"], row["occupied_rotation_squared_diff"]]
            if row["dual_abs_closure"] is not None:
                errors.append(row["dual_abs_closure"])
            if max(errors) > system.tol["linear_check"]:
                raise NumericalIssue(f"{label}: projected algebra failed.")
            if row["quadrature_relative_closure"] > system.tol["quadrature_relative"]:
                raise NumericalIssue(f"{label}: atom integral closure failed.")
        if "frozen" in row:
            check = row["frozen"]
            if (check["bound"] is not None
                    and check["sin_theta_fro"] > check["bound"] + system.tol["linear_check"]):
                raise NumericalIssue(f"{label}: finite frozen bound check failed.")
        return row

    def finish(self, status, error=None):
        self.report.update(status=status, finished_utc=clock())
        if error is not None:
            self.report["error"] = {"type": type(error).__name__, "message": str(error)}
        self.save()
        self.event("stop", status=status, error=self.report.get("error"))


def tied_max(items, value, tolerance):
    ceiling = max(map(value, items))
    return [item for item in items if ceiling - value(item) <= tolerance * max(abs(ceiling), 1e-30)]


def select(diagnostics, strategy, angular, tolerance):
    pool = [r for r in diagnostics["candidates"] if r["eligible"] and r["l"] == angular]
    if not pool:
        raise NumericalIssue(f"No admissible candidate with l={angular}.")
    atoms = []
    if strategy == "local":
        scores = diagnostics["local_squared"]
        available = [name for name in scores if any(r["label"] == name for r in pool)]
        atoms = tied_max(available, scores.__getitem__, tolerance)
        pool = [r for r in pool if r["label"] == atoms[0]]
    matches = pool[:1] if strategy == "fixed" else tied_max(pool, lambda r: r["score"], tolerance)
    return matches[0], {"eligible_pool": [r["id"] for r in pool],
                        "score_ties": [r["id"] for r in matches], "atom_ties": atoms}


def deviations(row, reference):
    return {
        name: {"signed_ha": row["energy_ha"] - ref["energy_ha"],
               "absolute_ha": abs(row["energy_ha"] - ref["energy_ha"])}
        for name, ref in reference.items()
    }


def compare(journal, system, base, base_diag, reference):
    schedule = system.config["shell_angular_momentum_schedule"]
    for item in base_diag["candidates"]:
        if item["eligible"] and item["l"] == schedule[0]:
            _, fit = journal.fit(system, f"first:{item['id']}", (item["id"],))
            journal.report["first_step_exhaustive"].append({
                "id": item["id"], "nao": fit["nao"], "score": item["score"], "energy_ha": fit["energy_ha"],
                "drop_ha": base["energy_ha"] - fit["energy_ha"], "deviations": deviations(fit, reference),
            })
            journal.save()

    for strategy in STRATEGIES:
        selected = []
        previous, diag = base, base_diag
        trajectory = [{"budget_ao": 0, "nao": base["nao"], "energy_ha": base["energy_ha"],
                       "fit": "base", "diagnostic": "base", "deviations": deviations(base, reference)}]
        journal.report["trajectories"][strategy] = trajectory
        expected_ao = base["nao"]
        for iteration, angular in enumerate(schedule, start=1):
            candidate, details = select(diag, strategy, angular, system.tol["score_tie_relative"])
            name = candidate["id"]
            selected.append(name)
            expected_ao += 2*angular + 1
            label = f"{strategy}:{iteration}"
            journal.event("selection", label=label, shell=name, angular=angular,
                          score=candidate["score"], budget_ao=expected_ao-base["nao"], **details)
            mf, current = journal.fit(system, label, tuple(selected))
            if current["nao"] != expected_ao or current["nao"] - previous["nao"] != candidate["ao_cost"]:
                raise NumericalIssue(f"{label}: AO budget mismatch.")
            diag = journal.diagnose(system, mf, label, selected)
            trajectory.append({
                "budget_ao": current["nao"] - base["nao"], "nao": current["nao"],
                "selected": name, "fit": label, "diagnostic": label, "selection": details,
                "energy_ha": current["energy_ha"], "wall_seconds_scf": current["wall_seconds"],
                "wall_seconds_diagnostic": diag["wall_seconds"],
                "energy_drop_from_previous_ha": previous["energy_ha"] - current["energy_ha"],
                "deviations": deviations(current, reference),
            })
            journal.save()
            previous = current


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/stage3.json"))
    parser.add_argument("--case", choices=("lih", "h2"), default="lih")
    parser.add_argument("--mode", choices=("baseline", "comparison"), required=True)
    parser.add_argument("--level", type=int)
    parser.add_argument("--max-cycle", type=int, help="Override SCF cycles for a diagnostic run")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.config.read_bytes()
    config = json.loads(raw)
    args.level = config["grid"]["default_level"] if args.level is None else args.level
    if args.max_cycle is not None:
        if args.max_cycle < 1:
            parser.error("--max-cycle must be positive.")
        config["scf"]["max_cycle"] = args.max_cycle
    if args.output.suffix != ".json":
        parser.error("--output must have a .json suffix.")
    journal = Journal(args.output, args, config, sha256(raw).hexdigest())
    try:
        system = System(config, args.case, args.level)
        journal.report["grid_protocol"] = system.grid_protocol
        mf, base = journal.fit(system, "base")
        diag = journal.diagnose(system, mf, "base", [])
        reference = journal.report["references"]
        for basis in config["reference_basis"]:
            _, reference[basis] = journal.fit(system, basis, basis=basis)
        _, reference["dictionary_full"] = journal.fit(system, "dictionary_full", tuple(system.dictionary))
        journal.report["base_deviations"] = deviations(base, reference)
        if args.mode == "comparison":
            compare(journal, system, base, diag, reference)
    except (Exception, KeyboardInterrupt) as error:
        journal.finish("failed", error)
        return 1
    journal.finish("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
