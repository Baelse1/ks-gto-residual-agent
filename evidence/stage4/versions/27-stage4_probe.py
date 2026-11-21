"""Test Gaussian partition width after the Li_s32 ablation at +1 AO."""
import argparse
import json
from pathlib import Path
from time import perf_counter

from scipy.linalg import eigh

if __package__:
    from .gaussian_rks import NumericalIssue, System
else:
    from gaussian_rks import NumericalIssue, System


GAMMAS = (0.25, 0.5, 1.0)


def first_max(items, score, tolerance):
    maximum = max(map(score, items))
    return next(item for item in items if maximum - score(item) <= tolerance * abs(maximum))


def evaluate(system, baseline, base_energy, reference, candidate):
    started = perf_counter()
    name = candidate['id']
    row = {'id': name, 'ao_cost': candidate['ao_cost'], 'schur_score': float(candidate['score'])}
    try:
        if not candidate['eligible']:
            row.update(status='rejected', rejection=candidate['rejection'])
            return row
        target = system.molecule((name,))
        if target.nao_nr() - system.base.nao_nr() != 1:
            raise NumericalIssue('Expected exactly one additional AO')
        overlap, _ = system.metrics(target)
        _, occupied, fock, moment, _, checks = system.assemble(baseline, target, overlap)
        eigenvalues, orbitals = eigh(fock, overlap, subset_by_index=(0, occupied.shape[1] - 1))
        frozen_energy = float(system.rks(target).energy_tot(dm=2 * orbitals @ orbitals.T))
        _, scf = system.solve(target)
        row.update(status=scf['status'], scf=scf, embedding_checks=checks,
                   frozen_drop_ha=float(2 * (moment.trace() - eigenvalues.sum())),
                   frozen_density_total_drop_ha=base_energy - frozen_energy)
        if scf['status'] == 'ok':
            energy = scf['energy_ha']
            row.update(scf_drop_ha=base_energy - energy,
                       relaxation_after_frozen_ha=frozen_energy - energy)
            if reference['status'] == 'ok':
                error = energy - reference['energy_ha']
                row.update(signed_reference_error_ha=error, absolute_reference_error_ha=abs(error))
    except (NumericalIssue, ValueError, ArithmeticError) as exc:
        row.update(status='numerical_failure', error=str(exc))
    finally:
        row['wall_seconds'] = perf_counter() - started
    return row


def probe(config, level):
    system = System(config, 'lih', level)
    baseline, baseline_row = system.solve(system.base)
    basis = config['reference_basis'][0]
    result = {'grid': system.grid_protocol, 'baseline': baseline_row, 'reference_basis': basis}
    if baseline_row['status'] != 'ok':
        return result
    _, reference = system.solve(system.molecule(basis=basis))
    result['reference'] = reference
    grid = config['grid']
    default_gamma = grid['partition_gamma']
    tolerance = config['thresholds']['score_tie_relative']
    overlap, metric = system.union_S, system.union_G
    old, _, _, _, residual, checks = system.assemble(baseline, system.union, overlap)
    remaining = sorted(set(range(len(overlap))) - set(old))
    projection, representer = system.project(metric, residual, old, remaining)
    result.update(embedding_checks=checks, union_projection=projection)
    points = []
    try:
        for gamma in dict.fromkeys((default_gamma, *GAMMAS)):
            grid['partition_gamma'] = gamma
            diagnostic = system.diagnose(baseline, ()) if gamma == default_gamma else None
            if diagnostic is not None:
                candidates = [row for row in diagnostic['candidates'] if row['ao_cost'] == 1]
                eligible = [row for row in candidates if row['eligible']]
                result['candidates'] = [evaluate(system, baseline, baseline_row['energy_ha'],
                                                 reference, row) for row in candidates]
            squared = system.localize(representer)
            scores = dict(zip(system.labels, map(float, squared)))
            total = projection['dual_squared']
            closure = float(abs(sum(squared) - total) / max(total, 1e-30))
            choices = {}
            if eligible:
                atoms = list(dict.fromkeys(row['label'] for row in eligible))
                atom = first_max(atoms, scores.__getitem__, tolerance)
                def score(row):
                    return row['score']
                choices = {'fixed': eligible[0]['id'],
                           'global': first_max(eligible, score, tolerance)['id'],
                           'local': first_max([row for row in eligible if row['label'] == atom],
                                              score, tolerance)['id']}
            points.append({'partition_gamma': gamma, 'local_squared': scores,
                           'li_minus_h_squared': scores['Li1'] - scores['H2'],
                           'quadrature_relative_closure': closure,
                           'strategy_choices': choices})
    finally:
        grid['partition_gamma'] = default_gamma
    result['partition_sweep'] = points
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--level', type=int, action='append')
    args = parser.parse_args()
    started = perf_counter()
    path = Path(__file__).resolve().parents[1] / 'config' / 'stage3.json'
    config = json.loads(path.read_text(encoding='utf-8'))
    lih = config['molecules']['lih']
    lih['candidates'] = [row for row in lih['candidates'] if row[0] != 'Li_s32']
    levels = args.level or [config['grid']['default_level'], config['grid']['sensitivity_levels'][0]]
    result = {'case': 'lih', 'atoms_bohr': lih['atoms'], 'xc': config['xc'],
              'base_basis': config['base_basis'], 'removed_shell': 'Li_s32',
              'added_ao': 1, 'grids': {}}
    for level in dict.fromkeys(levels):
        tic = perf_counter()
        try:
            row = probe(config, level)
        except (NumericalIssue, ValueError, ArithmeticError) as exc:
            row = {'status': 'numerical_failure', 'error': str(exc)}
        row['wall_seconds'] = perf_counter() - tic
        result['grids'][level] = row
    result['wall_seconds'] = perf_counter() - started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '
', encoding='utf-8')


if __name__ == '__main__':
    main()
