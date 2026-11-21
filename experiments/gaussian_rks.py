"""Finite Gaussian-space RKS, residual projection, and local diagnostics."""
from hashlib import sha256
from time import perf_counter

import numpy as np
from pyscf import dft, gto, lib
from scipy.linalg import eigh


class NumericalIssue(Exception):
    """An inadmissible numerical state."""


def block(matrix, rows, cols):
    return matrix[np.ix_(rows, cols)]


def spectrum(metric, scale=None):
    scale = np.sqrt(np.diag(metric)) if scale is None else scale
    normalized = metric / scale[:, None] / scale[None, :]
    values, vectors = np.linalg.eigh((normalized + normalized.T) / 2)
    return values, vectors, scale


def conditioning(metric):
    values, _, _ = spectrum(metric)
    return {
        "relative_min": float(values[0] / values[-1]),
        "scaled_min": float(values[0]),
        "scaled_max": float(values[-1]),
        "condition": float(values[-1] / values[0]) if values[0] > 0 else None,
    }


def quadratic(metric, moments):
    return float(np.sum(moments * np.linalg.solve(metric, moments)))


def embedding(old, rich):
    cross = gto.intor_cross("int1e_ovlp", old, rich)
    old_loc, new_loc = old.ao_loc_nr(), rich.ao_loc_nr()
    mapping = []
    for shell in range(old.nbas):
        a, b = old_loc[shell:shell + 2]
        matches = []
        for test in range(rich.nbas):
            if (rich.bas_atom(test) != old.bas_atom(shell)
                    or rich.bas_angular(test) != old.bas_angular(shell)
                    or not np.array_equal(rich.bas_exp(test), old.bas_exp(shell))
                    or not np.array_equal(rich.bas_ctr_coeff(test), old.bas_ctr_coeff(shell))):
                continue
            l, r = new_loc[test:test + 2]
            if r - l == b - a and np.allclose(cross[a:b, l:r], np.eye(b-a), atol=1e-12, rtol=0):
                matches.append(range(l, r))
        if len(matches) != 1:
            raise NumericalIssue(f"AO shell {shell} has {len(matches)} embedding matches.")
        mapping.extend(matches[0])
    if len(set(mapping)) != old.nao_nr():
        raise NumericalIssue("AO embedding is not injective.")
    return np.asarray(mapping, dtype=int)


class System:
    def __init__(self, config, case, level):
        self.config = config
        self.case = case
        self.level = level
        self.atoms = config["molecules"][case]["atoms"]
        self.labels = [f"{element}{i + 1}" for i, (element, _) in enumerate(self.atoms)]
        data = config["molecules"][case]
        self.dictionary = {entry[0]: entry for entry in data["candidates"]}
        self.holdout = {entry[0]: entry for entry in data["holdout"]}
        self.tol = config["thresholds"]
        lib.num_threads(config["scf"]["threads"])
        self.base = self.molecule()
        grids = dft.gen_grid.Grids(self.base)
        grids.level = level
        grids.build(with_non0tab=False)
        self.coords, self.weights = grids.coords, grids.weights
        self.grid_sha256 = sha256(self.coords.tobytes() + self.weights.tobytes()).hexdigest()
        self.grid_protocol = {
            "level": level, "points": len(self.weights), "sha256": self.grid_sha256,
            "radial_method": grids.radi_method.__name__, "angular_prune": grids.prune.__name__,
            "becke_scheme": grids.becke_scheme.__name__, "atom_radii_adjust": grids.radii_adjust.__name__,
            "small_rho_cutoff": config["grid"]["small_rho_cutoff"],
        }
        self.union = self.molecule(tuple(self.dictionary))
        self.probes = self.molecule((*self.dictionary, *self.holdout))
        self.union_S, self.union_G = self.metrics(self.union)
        self.shell_indices = self.candidate_indices()

    def molecule(self, ids=(), basis=None):
        if basis is None:
            basis = {label: gto.basis.load(self.config["base_basis"], element)
                     for label, (element, _) in zip(self.labels, self.atoms)}
            for item in ids:
                _, center, angular, exponent = (self.dictionary | self.holdout)[item]
                basis[self.labels[center]].append([angular, [exponent, 1.0]])
        return gto.M(atom=list(zip(self.labels, (xyz for _, xyz in self.atoms))), basis=basis,
                     cart=False, unit=self.config["unit"], charge=self.config["charge"],
                     spin=self.config["spin"], verbose=0, max_memory=self.config["scf"]["max_memory_mb"])

    def candidate_indices(self):
        locations = self.union.ao_loc_nr()
        by_id = {}
        for name, atom, angular, exponent in self.dictionary.values():
            matches = [
                i for i in range(self.union.nbas)
                if self.union.bas_atom(i) == atom and self.union.bas_angular(i) == angular
                and self.union.bas_exp(i).tolist() == [exponent]
                and self.union.bas_nctr(i) == 1
            ]
            if len(matches) != 1:
                raise NumericalIssue(f"Expected one full candidate shell for {name}.")
            i = matches[0]
            by_id[name] = np.arange(locations[i], locations[i + 1])
        base = set(embedding(self.base, self.union))
        candidate = [idx for indices in by_id.values() for idx in indices]
        if base.intersection(candidate) or len(set(candidate)) + len(base) != self.union.nao_nr():
            raise NumericalIssue("Candidate and base AO indices do not partition the union.")
        return by_id

    @staticmethod
    def metrics(mol):
        S = mol.intor_symmetric("int1e_ovlp")
        return S, 2 * mol.intor_symmetric("int1e_kin") + S

    def rks(self, mol):
        scf = self.config["scf"]
        mf = dft.RKS(mol)
        mf.xc = self.config["xc"]
        mf.small_rho_cutoff = self.config["grid"]["small_rho_cutoff"]
        mf.chkfile = None
        mf.conv_tol = scf["conv_tol"]
        mf.conv_tol_grad = scf["conv_tol_grad"]
        mf.max_cycle = scf["max_cycle"]
        mf.init_guess = scf["init_guess"]
        mf.grids.level = self.level
        mf.grids.coords, mf.grids.weights = self.coords, self.weights
        # The same grid geometry is used for all spaces, with basis-specific AO masks.
        mf.grids.non0tab = mf.grids.make_mask(mol, self.coords)
        mf.grids.screen_index = mf.grids.non0tab
        return mf

    def solve(self, mol):
        tic = perf_counter()
        mf = self.rks(mol)
        S = mf.get_ovlp()
        overlap = conditioning(S)
        row = {"nao": mol.nao_nr(), "overlap": overlap, "grid_level": self.level,
               "grid_points": len(self.weights), "grid_sha256": self.grid_sha256}
        if overlap["relative_min"] <= self.tol["normalized_eigen_relative"]:
            return mf, dict(row, status="rejected_overlap", converged=False, wall_seconds=perf_counter()-tic)
        energy = float(mf.kernel())
        occupied = mf.mo_occ > 0
        C = mf.mo_coeff[:, occupied]
        if not np.all(mf.mo_occ[occupied] == 2) or 2 * C.shape[1] != mol.nelectron:
            raise NumericalIssue("The solver requires equal double occupations.")
        density = mf.make_rdm1()
        F = mf.get_hcore() + mf.get_veff(dm=density)
        eps = mf.mo_energy
        r_eig = F @ C - S @ C * eps[occupied]
        _, G = self.metrics(mol)
        scf_grad = mf.get_grad(mf.mo_coeff, mf.mo_occ, F)
        row.update(
            converged=bool(mf.converged), energy_ha=energy,
            cycles=int(mf.cycles), occupied_orbitals=int(C.shape[1]), electron_count=mol.nelectron,
            overlap_orthogonality=float(np.linalg.norm(C.T @ S @ C - np.eye(C.shape[1]))),
            electron_trace_error=float(abs(np.einsum("ij,ji", density, S) - mol.nelectron)),
            old_eigen_residual_fro=float(np.linalg.norm(r_eig)),
            old_eigen_residual_dual=float(np.sqrt(quadratic(G, r_eig))),
            scf_gradient_norm=float(np.linalg.norm(scf_grad)),
            ks_gap_ha=float(min(eps[~occupied]) - max(eps[occupied])) if (~occupied).any() else None,
            wall_seconds=perf_counter()-tic,
        )
        row["status"] = "ok" if (row["converged"]
            and row["old_eigen_residual_dual"] <= self.tol["stationarity_dual"]
            and max(row["overlap_orthogonality"], row["electron_trace_error"]) <= self.tol["linear_check"]
        ) else "scf_check_failed"
        return mf, row

    def assemble(self, mf, target, S):
        ib = embedding(mf.mol, target)
        Co = mf.mo_coeff[:, mf.mo_occ > 0]
        C = np.zeros((len(S), Co.shape[1]))
        C[ib] = Co
        rich = self.rks(target)
        F = rich.get_hcore() + rich.get_veff(dm=2 * C @ C.T)
        Fo = mf.get_hcore() + mf.get_veff(dm=mf.make_rdm1())
        errors = {
            "embedding_overlap_fro": float(np.linalg.norm(block(S, ib, ib) - mf.get_ovlp())),
            "embedding_fock_fro": float(np.linalg.norm(block(F, ib, ib) - Fo)),
            "fock_symmetry_fro": float(np.linalg.norm(F - F.T)),
        }
        if max(errors.values()) > self.tol["linear_check"]:
            raise NumericalIssue(f"Failed fixed-grid embedding check: {errors}")
        M = C.T @ F @ C
        r = F @ C - S @ C @ M
        return ib, C, F, M, r, errors

    def project(self, G, r, ib, ic):
        Gbb, Gbc, Gcc = block(G, ib, ib), block(G, ib, ic), block(G, ic, ic)
        correction = np.linalg.solve(Gbb, Gbc)
        H = Gcc - Gbc.T @ correction
        moments = r[ic] - correction.T @ r[ib]
        scale = np.sqrt(np.diag(Gcc))
        values, vectors, _ = spectrum(H, scale)
        cutoff = self.tol["normalized_eigen_relative"] * max(1.0, values[-1])
        keep = values > cutoff
        Q = (vectors[:, keep] / np.sqrt(values[keep])) / scale[:, None]
        rhs = Q.T @ moments
        tail = Q @ rhs
        representer = np.zeros_like(r)
        representer[ic], representer[ib] = tail, -correction @ tail
        squared = float(np.sum(rhs * rhs))
        return {
            "dual_squared": squared, "rank": int(sum(keep)), "raw_dimension": len(ic),
            "scaled_min_eigen": float(values[0]), "scaled_max_eigen": float(values[-1]),
            "eigen_cutoff": float(cutoff),
        }, representer

    def localize(self, Z):
        accum = np.zeros(len(self.atoms))
        centers = self.union.atom_coords()
        for off in range(0, len(self.weights), 2048):
            coords = self.coords[off:off+2048]
            weights = self.weights[off:off+2048]
            ao = dft.numint.eval_ao(self.union, coords, deriv=1)
            z = ao @ Z
            energy_density = np.sum(z*z, axis=(0, 2))
            logits = -self.config["grid"]["partition_gamma"] * np.sum(
                (coords[:, None, :] - centers[None, :, :])**2, axis=2
            )
            p = np.exp(logits - logits.max(axis=1, keepdims=True))
            p /= p.sum(axis=1, keepdims=True)
            accum += (weights * energy_density) @ p
        return accum

    def diagnose(self, mf, selected):
        tic = perf_counter()
        S, G = self.union_S, self.union_G
        ib, C, F, M, r, errors = self.assemble(mf, self.union, S)
        ic = np.setdiff1d(np.arange(len(S)), ib)
        U_rank = conditioning(S)
        old_sq = quadratic(block(G, ib, ib), r[ib])
        row = {
            **errors, "union_nao": len(S), "union_overlap": U_rank,
            "old_stationarity_dual": np.sqrt(old_sq),
            "occupied_moment_fro": float(np.linalg.norm(C.T @ r)),
        }
        if len(ic):
            projected, Z = self.project(G, r, ib, ic)
            sq = projected["dual_squared"]
            local_sq = self.localize(Z)
            row.update(projected=projected, candidate_space_dual=np.sqrt(sq),
                       local_squared={label: float(x) for label, x in zip(self.labels, local_sq)},
                       quadrature_relative_closure=float(abs(sum(local_sq)-sq) / max(sq, 1e-30)),
                       riesz_abs_closure=float(abs(np.sum(Z * (G @ Z)) - sq)))
            if projected["rank"] == len(ic):
                row["dual_abs_closure"] = abs(quadratic(G, r) - old_sq - sq)
            else:
                row["dual_abs_closure"] = None
            angle = 0.37
            Q = np.eye(C.shape[1])
            if C.shape[1] >= 2:
                Q[:2, :2] = [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
            Cr = C @ Q
            rotated_r = F @ Cr - S @ Cr @ (Cr.T @ F @ Cr)
            rotated, _ = self.project(G, rotated_r, ib, ic)
            row["occupied_rotation_squared_diff"] = abs(rotated["dual_squared"] - sq)

        candidates = []
        for name, atom, angular, exponent in self.dictionary.values():
            if name in selected:
                continue
            idx = self.shell_indices[name]
            stats, _ = self.project(G, r, ib, idx)
            trial = np.r_[ib, idx]
            overlap = conditioning(block(S, trial, trial))
            eligible = (stats["rank"] == len(idx)
                        and overlap["relative_min"] > self.tol["normalized_eigen_relative"])
            candidates.append({
                "id": name, "atom": atom, "label": self.labels[atom], "l": angular,
                "exponent": exponent, "ao_cost": len(idx), "score": np.sqrt(stats["dual_squared"]),
                "projected": stats, "trial_overlap": overlap, "eligible": eligible,
                "rejection": None if eligible else "schur_rank_or_overlap",
            })
        row["candidates"] = candidates

        union_stable = U_rank["relative_min"] > self.tol["normalized_eigen_relative"]
        if union_stable:
            eig, V = eigh(F, S)
            n = C.shape[1]
            separation = float(eig[n] - np.linalg.eigvalsh(M)[-1])
            row["frozen"] = {
                "separation_ha": separation, "sin_theta_fro": float(np.linalg.norm(V[:, n:].T @ S @ C)),
                "bound": float(np.sqrt(quadratic(S, r)) / separation) if separation > 0 else None,
            }
            Sp, Gp = self.metrics(self.probes)
            _, _, _, _, rp, probe_errors = self.assemble(mf, self.probes, Sp)
            pu = embedding(self.union, self.probes)
            pi = np.setdiff1d(np.arange(self.probes.nao_nr()), pu)
            holdout, _ = self.project(Gp, rp, pu, pi)
            row["holdout_outside_union"] = {"status": "ok", **holdout, **probe_errors}
        else:
            row["holdout_outside_union"] = {"status": "skipped_union_overlap"}
        row["wall_seconds"] = perf_counter() - tic
        return row
