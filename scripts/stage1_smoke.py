"""Check a nested Gaussian basis and frozen residual on one LiH geometry."""
import argparse
import json
import platform
from pathlib import Path
from time import perf_counter

import numpy as np
import pyscf
import scipy
from scipy.linalg import eigh
from pyscf import dft, gto, lib


def main(output):
    lib.num_threads(1)
    atoms = "Li 0 0 0; H 0 0 3"
    common = dict(atom=atoms, unit="Bohr", charge=0, spin=0, verbose=0)
    base = gto.M(basis="sto-3g", **common)
    shells = {"Li": [[0, [0.08, 1.0]]], "H": [[0, [0.20, 1.0]]]}
    union = gto.M(
        basis={a: gto.basis.load("sto-3g", a) + extra for a, extra in shells.items()},
        **common,
    )
    # Check the actual union shell order by comparing its AO functions through overlaps.
    indices = []
    cross = gto.intor_cross("int1e_ovlp", base, union)
    base_loc = base.ao_loc_nr()
    loc = union.ao_loc_nr()
    for shell in range(base.nbas):
        a0, a1 = base_loc[shell:shell + 2]
        u0, u1 = base.bas_atom(shell), base.bas_angular(shell)
        candidates = [
            j for j in range(union.nbas)
            if union.bas_atom(j) == u0 and union.bas_angular(j) == u1
        ]
        matches = [
            j for j in candidates if loc[j + 1] - loc[j] == a1 - a0
            and np.allclose(cross[a0:a1, loc[j]:loc[j + 1]], np.eye(a1-a0),
                            rtol=0, atol=1e-12)
        ]
        assert len(matches) == 1, matches
        j = matches[0]
        indices.extend(range(loc[j], loc[j + 1]))
    ib = np.array(indices)
    ic = np.setdiff1d(np.arange(union.nao_nr()), ib)

    def setup(mol, grid=None):
        mf = dft.RKS(mol)
        mf.xc = "LDA_X,VWN"
        mf.grids.level = 3
        mf.small_rho_cutoff = 0
        mf.chkfile = None
        mf.conv_tol = 1e-11
        mf.conv_tol_grad = 1e-8
        if grid is not None:
            mf.grids = grid
        return mf

    start = perf_counter()
    mf = setup(base)
    mf.kernel()
    full = setup(union, mf.grids)
    S = full.get_ovlp()
    C = mf.mo_coeff[:, mf.mo_occ > 0]
    U = np.zeros((len(S), C.shape[1]))
    U[ib] = C
    F = full.get_hcore() + full.get_veff(dm=2 * U @ U.T)
    Fbase = mf.get_hcore() + mf.get_veff(dm=mf.make_rdm1())
    M = U.T @ F @ U
    r = F @ U - S @ U @ M
    G = 2 * union.intor_symmetric("int1e_kin") + S
    Gbb = G[np.ix_(ib, ib)]
    Gbc = G[np.ix_(ib, ic)]
    H = G[np.ix_(ic, ic)] - Gbc.T @ np.linalg.solve(Gbb, Gbc)
    corrected = r[ic] - Gbc.T @ np.linalg.solve(Gbb, r[ib])
    old_sq = np.sum(r[ib] * np.linalg.solve(Gbb, r[ib]))
    new_sq = np.sum(corrected * np.linalg.solve(H, corrected))
    full_sq = np.sum(r * np.linalg.solve(G, r))
    Sbb = S[np.ix_(ib, ib)]
    vals, V = eigh(F, S)
    nocc = U.shape[1]
    separation = vals[nocc] - np.linalg.eigvalsh(M)[-1]
    frozen_error = np.linalg.norm(V[:, nocc:].T @ S @ U)
    bound = np.sqrt(np.sum(r * np.linalg.solve(S, r))) / separation
    full.kernel()
    report = dict(
        python=platform.python_version(), pyscf=pyscf.__version__,
        numpy=np.__version__, scipy=scipy.__version__,
        atoms=atoms, unit="Bohr", charge=0, spin=0, xc=mf.xc, grid_level=3,
        grid_points=len(mf.grids.weights), scf_energy_tol=mf.conv_tol,
        scf_gradient_tol=mf.conv_tol_grad, threads=lib.num_threads(),
        base_basis="sto-3g", added_shells=shells, base_ao=len(ib), union_ao=len(S),
        base_converged=bool(mf.converged), union_converged=bool(full.converged),
        base_energy_ha=float(mf.e_tot), union_energy_ha=float(full.e_tot),
        embedding_overlap_error=float(np.linalg.norm(Sbb - mf.get_ovlp())),
        embedding_fock_error=float(np.linalg.norm(F[np.ix_(ib, ib)] - Fbase)),
        old_eigen_residual_frobenius=float(np.linalg.norm(Fbase @ C -
                                                       Sbb @ C * mf.mo_energy[mf.mo_occ > 0])),
        old_stationarity_dual=float(np.sqrt(old_sq)), new_space_dual=float(np.sqrt(new_sq)),
        squared_dual_closure_error=float(abs(full_sq - old_sq - new_sq)),
        orthogonality_error=float(np.linalg.norm(U.T @ S @ U - np.eye(nocc))),
        union_overlap_min_eigenvalue=float(np.linalg.eigvalsh(S)[0]),
        frozen_separation_ha=float(separation), frozen_sin_theta_frobenius=float(frozen_error),
        frozen_sin_theta_bound=float(bound),
        elapsed_s=perf_counter() - start,
    )
    contents = json.dumps(report, indent=2, allow_nan=False) + "\n"
    output.write_text(contents, encoding="utf-8")
    print(contents, end="")
    assert mf.converged and full.converged
    assert report["embedding_overlap_error"] < 1e-12
    assert report["embedding_fock_error"] < 1e-10
    assert report["orthogonality_error"] < 1e-10
    assert report["old_stationarity_dual"] < 1e-7
    assert report["new_space_dual"] > 1e-5
    assert report["squared_dual_closure_error"] < 1e-12
    assert separation > 0 and frozen_error <= bound + 1e-12


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    main(parser.parse_args().output)
