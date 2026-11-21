"""Test LiH grid sensitivity and a one-shell dictionary ablation at +1 AO."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from time import perf_counter

from scipy.linalg import eigh

if __package__:
    from .gaussian_rks import NumericalIssue, System
else:
    from gaussian_rks import NumericalIssue, System


def evaluate(system, baseline, baseline_row, reference, candidate):
    started = perf_counter()
    name = candidate['id']
    row = {'id': name, 'atom': candidate['label'], 'ao_cost': candidate['ao_cost'],
           'schur_score': float(candidate['score']), 'eligible': candidate['eligible']}
    try:
        if not candidate['eligible']:
            row.update(status='rejected', rejection=candidate['rejection'])
            return row
        target = system.molecule((name,))
        if target.nao_nr() != system.base.nao_nr() + 1:
            raise NumericalIssue('Expected exactly one additional AO')
        overlap, _ = system.metrics(target)
        _, occupied, fock, moment, _, checks = system.assemble(baseline, target, overlap)
        eigenvalues, orbitals = eigh(fock, overlap, subset_by_index=(0, occupied.shape[1] - 1))
        frozen_energy = float(system.rks(target).energy_tot(dm=2 * orbitals @ orbitals.T))
        _, scf = system.solve(target)
        row.update(status=scf['status'], scf=scf, embedding_checks=checks,
                   frozen_drop_ha=float(2 * (moment.trace() - eigenvalues.sum())),
                   frozen_density_total_drop_ha=baseline_row['energy_ha'] - frozen_energy)
        if scf['status'] == 'ok':
            energy = scf['energy_ha']
            row.update(scf_drop_ha=baseline_row['energy_ha'] - energy,
                       relaxation_after_frozen_ha=frozen_energy - energy)
            if reference['status'] == 'ok':
                error = energy - reference['energy_ha']
                row.update(signed_reference_error_ha=error, absolute_reference_error_ha=abs(error))
    except (NumericalIssue, ValueError, ArithmeticError) as exc:
        row.update(status='numerical_failure', error=str(exc))
    finally:
        row['wall_seconds'] = perf_counter() - started
    return row


def first_max(items, score, tolerance):
    maximum = max(map(score, items))
    return next(item for item in items if maximum - score(item) <= tolerance * abs(maximum))


def probe(config, level):
    system = System(config, 'lih', level)
    baseline, baseline_row = system.solve(system.base)
    basis = config['reference_basis'][0]
    result = {'grid': system.grid_protocol, 'baseline': baseline_row, 'reference_basis': basis}
    if baseline_row['status'] != 'ok':
        return result
    _, reference = system.solve(system.molecule(basis=basis))
    result['reference'] = reference
    restricted_config = deepcopy(config)
    dictionary = restricted_config['molecules']['lih']
    dictionary['candidates'] = [entry for entry in dictionary['candidates'] if entry[0] != 'Li_s32']
    restricted = System(restricted_config, 'lih', level)
    if restricted.grid_sha256 != system.grid_sha256:
        raise NumericalIssue('Dictionary ablation changed the grid')
    rows_by_name = {}
    for label, active in [('original', system), ('without_Li_s32', restricted)]:
        diagnostic = active.diagnose(baseline, ())
        candidates = [row for row in diagnostic['candidates'] if row['ao_cost'] == 1]
        eligible = [row for row in candidates if row['eligible']]
        local_scores = diagnostic['local_squared']
        tolerance = config['thresholds']['score_tie_relative']
        choices = {}
        if eligible:
            atoms = list(dict.fromkeys(row['label'] for row in eligible))
            atom = first_max(atoms, local_scores.__getitem__, tolerance)
            def score(row):
                return row['score']
            choices = {'fixed': eligible[0]['id'],
                       'global': first_max(eligible, score, tolerance)['id'],
                       'local': first_max([row for row in eligible if row['label'] == atom],
                                          score, tolerance)['id']}
        rows = []
        for candidate in candidates:
            name = candidate['id']
            if name not in rows_by_name or rows_by_name[name]['eligible'] != candidate['eligible']:
                rows_by_name[name] = evaluate(active, baseline, baseline_row, reference, candidate)
            rows.append(dict(rows_by_name[name], schur_score=float(candidate['score'])))
        converged = [row for row in rows if row['status'] == 'ok']
        fields = ('schur_score', 'frozen_drop_ha', 'frozen_density_total_drop_ha', 'scf_drop_ha')
        rankings = {field: [row['id'] for row in sorted(converged, key=lambda row: -row[field])]
                    for field in fields}
        result[label] = {'local_squared': local_scores, 'union_overlap': diagnostic['union_overlap'],
                         'quadrature_relative_closure': diagnostic['quadrature_relative_closure'],
                         'strategy_choices': choices, 'candidates': rows, 'rankings': rankings}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--level', type=int, action='append')
    args = parser.parse_args()
    started = perf_counter()
    path = Path(__file__).resolve().parents[1] / 'config' / 'stage3.json'
    config = json.loads(path.read_text(encoding='utf-8'))
    levels = args.level or [config['grid']['default_level'], config['grid']['sensitivity_levels'][0]]
    result = {'case': 'lih', 'atoms_bohr': config['molecules']['lih']['atoms'],
              'xc': config['xc'], 'base_basis': config['base_basis'], 'added_ao': 1,
              'shared_trials': 'Identical single-shell trial spaces share one SCF per grid.', 'grids': {}}
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
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
