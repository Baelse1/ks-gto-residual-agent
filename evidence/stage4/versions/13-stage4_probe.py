"""Compare frozen and relaxed LiH rankings at the matched +1 AO budget."""
import argparse
import json
from pathlib import Path
from time import perf_counter

from scipy.linalg import eigh

if __package__:
    from .gaussian_rks import NumericalIssue, System
else:
    from gaussian_rks import NumericalIssue, System


def probe(config, level):
    system = System(config, 'lih', level)
    baseline, base_row = system.solve(system.base)
    reference_basis = config['reference_basis'][0]
    result = {'grid': system.grid_protocol, 'baseline': base_row,
              'reference_basis': reference_basis, 'candidates': [], 'rankings': {}}
    if base_row['status'] != 'ok':
        return result
    _, reference = system.solve(system.molecule(basis=reference_basis))
    result['reference'] = reference
    diagnostic = system.diagnose(baseline, ())
    for candidate in diagnostic['candidates']:
        if candidate['ao_cost'] != 1:
            continue
        start = perf_counter()
        name = candidate['id']
        row = {'id': name, 'ao_cost': 1, 'schur_score': float(candidate['score']),
               'status': 'rejected' if not candidate['eligible'] else 'pending'}
        result['candidates'].append(row)
        if not candidate['eligible']:
            row['rejection'] = candidate['rejection']
            continue
        try:
            target = system.molecule((name,))
            overlap, _ = system.metrics(target)
            if target.nao_nr() != system.base.nao_nr() + 1:
                raise NumericalIssue('Candidate does not add exactly one AO')
            _, occupied, fock, moment, _, checks = system.assemble(baseline, target, overlap)
            nocc = occupied.shape[1]
            eigenvalues, orbitals = eigh(fock, overlap, subset_by_index=(0, nocc - 1))
            row['embedding_checks'] = checks
            row['frozen_drop_ha'] = float(2 * (moment.trace() - eigenvalues.sum()))
            frozen_rks = system.rks(target)
            frozen_energy = float(frozen_rks.energy_tot(dm=2 * orbitals @ orbitals.T))
            row['frozen_density_total_drop_ha'] = base_row['energy_ha'] - frozen_energy
            _, trial = system.solve(target)
            row['scf'] = trial
            row['status'] = trial['status']
            if trial['status'] == 'ok':
                energy = trial['energy_ha']
                row['scf_drop_ha'] = base_row['energy_ha'] - energy
                row['relaxation_after_frozen_ha'] = frozen_energy - energy
                if reference['status'] == 'ok':
                    row['signed_reference_error_ha'] = energy - reference['energy_ha']
                    row['absolute_reference_error_ha'] = abs(row['signed_reference_error_ha'])
        except (NumericalIssue, ValueError, ArithmeticError) as exc:
            row.update(status='numerical_failure', error=str(exc))
        finally:
            row['wall_seconds'] = perf_counter() - start
    paired = [row for row in result['candidates'] if row['status'] == 'ok']
    for field in ('schur_score', 'frozen_drop_ha', 'frozen_density_total_drop_ha', 'scf_drop_ha'):
        result['rankings'][field] = [row['id'] for row in sorted(
            paired, key=lambda row: -row[field])]
    eligible = [row for row in diagnostic['candidates'] if row['eligible'] and row['ao_cost'] == 1]
    if eligible:
        tie = config['thresholds']['score_tie_relative']

        def first_max(rows, score):
            top = max(map(score, rows))
            return next(row for row in rows if top - score(row) <= tie * abs(top))

        labels = dict.fromkeys(row['label'] for row in eligible)
        local = first_max(labels, diagnostic['local_squared'].__getitem__)
        shell_score = lambda row: row['score']
        result['strategy_choices'] = {
            'fixed': eligible[0]['id'],
            'global': first_max(eligible, shell_score)['id'],
            'local': first_max([row for row in eligible if row['label'] == local], shell_score)['id'],
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--level', type=int)
    args = parser.parse_args()
    start = perf_counter()
    config_file = Path(__file__).resolve().parents[1] / 'config' / 'stage3.json'
    config = json.loads(config_file.read_text(encoding='utf-8'))
    level = args.level if args.level is not None else config['grid']['default_level']
    result = {'case': 'lih', 'atoms_bohr': config['molecules']['lih']['atoms'],
              'xc': config['xc'], 'base_basis': config['base_basis'], 'added_ao': 1}
    try:
        result.update(probe(config, level))
    except (NumericalIssue, ValueError, ArithmeticError) as exc:
        result.update(status='numerical_failure', error=str(exc))
    result['wall_seconds'] = perf_counter() - start
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
