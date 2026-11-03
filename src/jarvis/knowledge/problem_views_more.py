"""More views for worked problems (problem_views.py): modern physics, quantum computing, linear algebra,
statistics, fields, molecules and particles. Each works out its numbers here (numpy, SymPy, mpmath); the
window only draws them (ui/problem.js).

  quantum         a particle in a box, a harmonic oscillator, tunnelling through a barrier, hydrogen: levels,
                  wavefunctions (and a superposition moving in time), transmission, spectral lines
  qcircuit        a quantum circuit simulated exactly (state vector): the state after each gate, the
                  measurement probabilities, and each qubit's Bloch vector
  minkowski       a spacetime diagram: light cones, a moving frame's axes, events in both frames, worldlines
                  and their proper times (the twin paradox)
  black_hole      the Schwarzschild radius, photon sphere and innermost stable orbit, and the curved space
  matrix          a 2x2 matrix bending the plane: the grid, eigenvectors, the determinant as area
  distribution    normal, binomial, Poisson, t, chi-squared, exponential, uniform: a probability as an area
  montecarlo      estimates by random sampling (pi, an integral) and how they converge
  field           a 2D vector field with moving particles, or a slope field with solution curves
  molecule        a molecule in 3D from PubChem (needs the internet, once; kept on disk)
  feynman         a Feynman diagram: fermions, photons, gluons, W, Z and Higgs lines
"""

from __future__ import annotations

import cmath
import itertools
import math
import random
import re
from pathlib import Path
from typing import Any

from .problems import ProblemError, _parse, show_number

H, HBAR, C_LIGHT, E_CHARGE, M_E, G_NEWTON = 6.62607015e-34, 1.054571817e-34, 2.99792458e8, 1.602176634e-19, \
    9.1093837015e-31, 6.67430e-11


# ---- quantum mechanics ---------------------------------------------------------------------------------------
def _quantum(spec: dict, n) -> dict:
    system = str(spec.get("system") or "box")
    m = n(spec.get("m"), M_E)
    levels = spec.get("n") if isinstance(spec.get("n"), list) else [spec.get("n") or 1]
    levels = [max(0 if system == "oscillator" else 1, int(n(k))) for k in levels[:6]]
    out: dict[str, Any] = {"kind": "quantum", "system": system, "levels": levels}
    if system == "box":
        L = n(spec.get("L"))
        if L <= 0:
            raise ProblemError("the box's width must be positive")
        energies = [(k * H) ** 2 / (8 * m * L * L) for k in levels]
        xs = [L * i / 200 for i in range(201)]
        out.update(L=L, x=xs, psi=[[math.sqrt(2 / L) * math.sin(k * math.pi * x / L) for x in xs] for k in levels])
    elif system == "oscillator":
        w = n(spec.get("omega"))
        if w <= 0:
            raise ProblemError("omega must be positive")
        x0 = math.sqrt(HBAR / (m * w))
        xs = [x0 * (-5 + 10 * i / 240) for i in range(241)]
        energies = [(k + 0.5) * HBAR * w for k in levels]
        out.update(x=xs, x0=x0, psi=[[_ho(k, x / x0) / math.sqrt(x0) for x in xs] for k in levels],
                   V=[0.5 * m * w * w * x * x for x in xs])
    elif system == "barrier":
        V0, a, E = n(spec.get("V0")) * E_CHARGE, n(spec.get("a")), n(spec.get("E")) * E_CHARGE
        if min(V0, a, E) <= 0:
            raise ProblemError("V0, a and E must be positive (V0 and E in eV)")
        k = math.sqrt(2 * m * E) / HBAR
        q = cmath.sqrt(2 * m * (E - V0)) / HBAR
        if abs(q) < 1e-30:
            raise ProblemError("E equal to V0: pick a different energy")
        T, R, coef = _barrier(k, q, a)
        xs = [a * (-2 + 5 * i / 300) for i in range(301)]
        out.update(V0=V0, a=a, E=E, T=T, R=R, T_shown=show_number(T), x=xs,
                   psi=[_barrier_psi(x, k, q, a, coef) for x in xs], wavelength=2 * math.pi / k)
        energies = [E]
    elif system == "hydrogen":
        import sympy
        from sympy.physics.hydrogen import R_nl
        Z = int(n(spec.get("Z"), 1))
        energies = [-13.605693 * Z * Z / (k * k) * E_CHARGE for k in levels]
        l = int(n(spec.get("l"), 0))
        r = sympy.Symbol("r")
        a0 = 5.29177210903e-11
        curves = []
        for k in levels[:3]:
            if l >= k:
                continue
            f = sympy.lambdify(r, R_nl(k, l, r, Z), modules=["math"])
            rs = [a0 * 25 * i / 300 for i in range(301)]
            curves.append({"n": k, "r": rs, "P": [(x / a0) ** 2 * f(x / a0) ** 2 for x in rs]})
        out.update(Z=Z, l=l, radial=curves, a0=a0)
        if isinstance(spec.get("transition"), list) and len(spec["transition"]) == 2:
            ni, nf = (int(n(v)) for v in spec["transition"])
            dE = 13.605693 * Z * Z * abs(1 / nf ** 2 - 1 / ni ** 2) * E_CHARGE
            lam = H * C_LIGHT / dE if dE else 0.0
            out["transition"] = {"from": ni, "to": nf, "dE_eV": dE / E_CHARGE, "wavelength": lam,
                                 "shown": f"{show_number(lam * 1e9)} nm", "colour": _colour_of(lam)}
    else:
        raise ProblemError("quantum system: box, oscillator, barrier or hydrogen")
    out["E"] = energies
    out["E_eV"] = [e / E_CHARGE for e in energies]
    out["E_shown"] = [f"{show_number(e / E_CHARGE)} eV" for e in energies]
    sup = spec.get("superpose")
    if isinstance(sup, list) and len(sup) >= 2 and system in ("box", "oscillator"):
        out["superpose"] = [levels.index(int(n(k))) for k in sup if int(n(k)) in levels][:3]
    return out


def _ho(k: int, xi: float) -> float:
    """The harmonic oscillator's k-th wavefunction at xi = x / x0 (Hermite by recurrence)."""
    h0, h1 = 1.0, 2 * xi
    if k == 0:
        hk = h0
    else:
        for j in range(1, k):
            h0, h1 = h1, 2 * xi * h1 - 2 * j * h0
        hk = h1
    return hk * math.exp(-xi * xi / 2) / math.sqrt(2 ** k * math.factorial(k) * math.sqrt(math.pi))


def _barrier(k: float, q: complex, a: float):
    """A rectangular barrier from 0 to a: e^{ikx} + r e^{-ikx}; A e^{iqx} + B e^{-iqx}; t e^{ikx}."""
    import numpy as np
    M = np.array([[1, -1, -1, 0], [-1j * k, -1j * q, 1j * q, 0],
                  [0, cmath.exp(1j * q * a), cmath.exp(-1j * q * a), -cmath.exp(1j * k * a)],
                  [0, 1j * q * cmath.exp(1j * q * a), -1j * q * cmath.exp(-1j * q * a), -1j * k * cmath.exp(1j * k * a)]],
                 dtype=complex)
    rhs = np.array([-1, -1j * k, 0, 0], dtype=complex)
    r, A, B, t = np.linalg.solve(M, rhs)
    return float(abs(t) ** 2), float(abs(r) ** 2), (complex(r), complex(A), complex(B), complex(t))


def _barrier_psi(x: float, k: float, q: complex, a: float, coef) -> list[float]:
    r, A, B, t = coef
    if x < 0:
        v = cmath.exp(1j * k * x) + r * cmath.exp(-1j * k * x)
    elif x <= a:
        v = A * cmath.exp(1j * q * x) + B * cmath.exp(-1j * q * x)
    else:
        v = t * cmath.exp(1j * k * x)
    return [v.real, v.imag]


def _colour_of(lam: float) -> str:
    nm = lam * 1e9
    if nm < 380 or nm > 750:
        return "ultraviolet" if nm < 380 else "infrared"
    for edge, name in ((450, "violet"), (495, "blue"), (570, "green"), (590, "yellow"), (620, "orange"), (751, "red")):
        if nm < edge:
            return name
    return "red"


# ---- quantum circuits -------------------------------------------------------------------------------------------
def _gate(name: str, theta: float = 0.0):
    import numpy as np
    s = 1 / math.sqrt(2)
    c, si = math.cos(theta / 2), math.sin(theta / 2)
    return {"H": np.array([[s, s], [s, -s]]), "X": np.array([[0, 1], [1, 0]]), "Y": np.array([[0, -1j], [1j, 0]]),
            "Z": np.array([[1, 0], [0, -1]]), "S": np.array([[1, 0], [0, 1j]]),
            "T": np.array([[1, 0], [0, cmath.exp(1j * math.pi / 4)]]), "I": np.eye(2),
            "RX": np.array([[c, -1j * si], [-1j * si, c]]), "RY": np.array([[c, -si], [si, c]]),
            "RZ": np.array([[cmath.exp(-1j * theta / 2), 0], [0, cmath.exp(1j * theta / 2)]])}[name].astype(complex)


def _apply(state, nq: int, gate: list, n) -> Any:
    import numpy as np
    name = str(gate[0]).upper()
    psi = state.reshape([2] * nq)
    if name in ("H", "X", "Y", "Z", "S", "T", "I", "RX", "RY", "RZ"):
        q = int(n(gate[1]))
        U = _gate(name, n(gate[2]) if len(gate) > 2 else 0.0)
        psi = np.moveaxis(np.tensordot(U, np.moveaxis(psi, q, 0), axes=([1], [0])), 0, q)
    elif name in ("CNOT", "CX", "CZ"):
        c, t = int(n(gate[1])), int(n(gate[2]))
        U = _gate("X" if name != "CZ" else "Z")
        psi = psi.copy()
        idx = [slice(None)] * nq
        idx[c] = 1
        sub = psi[tuple(idx)]
        tt = t if t < c else t - 1
        psi[tuple(idx)] = np.moveaxis(np.tensordot(U, np.moveaxis(sub, tt, 0), axes=([1], [0])), 0, tt)
    elif name == "SWAP":
        a, b = int(n(gate[1])), int(n(gate[2]))
        psi = np.swapaxes(psi, a, b)
    elif name in ("CCX", "TOFFOLI"):
        c1, c2, t = (int(n(g)) for g in gate[1:4])
        psi = psi.copy()
        idx = [slice(None)] * nq
        idx[c1] = idx[c2] = 1
        sub = psi[tuple(idx)]
        tt = t - sum(1 for c in (c1, c2) if c < t)
        psi[tuple(idx)] = np.moveaxis(np.tensordot(_gate("X"), np.moveaxis(sub, tt, 0), axes=([1], [0])), 0, tt)
    else:
        raise ProblemError(f"unknown gate {name!r}")
    return psi.reshape(-1)


def _bloch(state, nq: int, q: int) -> list[float]:
    import numpy as np
    psi = np.moveaxis(state.reshape([2] * nq), q, 0).reshape(2, -1)
    rho = psi @ psi.conj().T
    return [float(2 * rho[0, 1].real), float(2 * rho[1, 0].imag), float((rho[0, 0] - rho[1, 1]).real)]


def _qcircuit(spec: dict, n) -> dict:
    import numpy as np
    nq = int(n(spec.get("qubits"), 1))
    if not 1 <= nq <= 4:
        raise ProblemError("1 to 4 qubits")
    init = str(spec.get("initial") or "0" * nq)
    if not re.fullmatch(rf"[01]{{{nq}}}", init):
        raise ProblemError("the starting state is a string of 0s and 1s, one per qubit")
    state = np.zeros(2 ** nq, dtype=complex)
    state[int(init, 2)] = 1
    gates, states = [], []

    def snap(s):
        return {"amps": [[round(float(a.real), 6), round(float(a.imag), 6)] for a in s],
                "probs": [round(float(abs(a) ** 2), 6) for a in s], "bloch": [_bloch(s, nq, q) for q in range(nq)]}
    states.append(snap(state))
    arity = {"CNOT": 2, "CX": 2, "CZ": 2, "SWAP": 2, "CCX": 3, "TOFFOLI": 3}
    for g in (spec.get("gates") or [])[:16]:
        if not isinstance(g, list) or not g:
            continue
        name = str(g[0]).upper()
        if name in ("MEASURE", "M"):
            continue
        k = arity.get(name, 1)
        if len(g) < 1 + k:
            raise ProblemError(f"gate {name} needs {k} qubit(s)")
        qs = [int(n(x)) for x in g[1:1 + k]]
        if any(not 0 <= q < nq for q in qs) or len(set(qs)) != len(qs):
            raise ProblemError(f"gate {name} on a qubit that isn't there")
        angle = n(g[2]) if name in ("RX", "RY", "RZ") and len(g) > 2 else None
        state = _apply(state, nq, [name, *qs, *([angle] if angle is not None else [])], n)
        gates.append({"name": name, "qubits": qs, "angle": angle,
                      "angle_shown": show_number(angle) if angle is not None else ""})
        states.append(snap(state))
    labels = [format(i, f"0{nq}b") for i in range(2 ** nq)]
    return {"kind": "qcircuit", "qubits": nq, "gates": gates, "states": states, "labels": labels}


# ---- relativity --------------------------------------------------------------------------------------------------
def _minkowski(spec: dict, n) -> dict:
    beta = n(spec.get("beta"), 0.0)
    if not -1 < beta < 1:
        raise ProblemError("a frame's speed must be below c (|beta| < 1)")
    g = 1 / math.sqrt(1 - beta * beta)
    events = []
    for e in (spec.get("events") or [])[:8]:
        if isinstance(e, dict):
            x, ct = n(e.get("x"), 0.0), n(e.get("ct"), 0.0)
            events.append({"name": str(e.get("name") or "")[:12], "x": x, "ct": ct,
                           "x2": g * (x - beta * ct), "ct2": g * (ct - beta * x)})
    lines = []
    for w in (spec.get("worldlines") or [])[:4]:
        if not isinstance(w, dict):
            continue
        if isinstance(w.get("path"), list):
            pts = [[n(p[0]), n(p[1])] for p in w["path"][:12] if isinstance(p, list) and len(p) == 2]
        else:
            b, x0, T = n(w.get("beta"), 0.0), n(w.get("x0"), 0.0), n(w.get("ct1"), 10.0)
            pts = [[x0, 0.0], [x0 + b * T, T]]
        tau = 0.0
        for (xa, ta), (xb, tb) in itertools.pairwise(pts):
            d = (tb - ta) ** 2 - (xb - xa) ** 2
            if d < -1e-9:
                raise ProblemError("a worldline goes faster than light")
            tau += math.sqrt(max(0.0, d))
        lines.append({"name": str(w.get("name") or "")[:16], "points": pts, "tau": tau, "tau_shown": show_number(tau)})
    span = max([5.0] + [abs(v) for e in events for v in (e["x"], e["ct"])] +
               [abs(v) for w in lines for p in w["points"] for v in p])
    return {"kind": "minkowski", "beta": beta, "gamma": g, "gamma_shown": show_number(g), "events": events,
            "worldlines": lines, "span": span * 1.15, "unit": str(spec.get("unit") or "")[:10]}


def _black_hole(spec: dict, n) -> dict:
    M = n(spec.get("M"))
    if M <= 0:
        raise ProblemError("the mass must be positive (kg)")
    rs = 2 * G_NEWTON * M / C_LIGHT ** 2
    T = HBAR * C_LIGHT ** 3 / (8 * math.pi * G_NEWTON * M * 1.380649e-23)
    return {"kind": "black_hole", "M": M, "rs": rs, "rs_shown": f"{show_number(rs)} m", "photon": 1.5 * rs,
            "isco": 3 * rs, "T_hawking": T, "T_shown": f"{show_number(T)} K",
            "lifetime_s": 5120 * math.pi * G_NEWTON ** 2 * M ** 3 / (HBAR * C_LIGHT ** 4)}


# ---- linear algebra -------------------------------------------------------------------------------------------
def _matrix(spec: dict, n) -> dict:
    import numpy as np
    A = spec.get("A")
    if not (isinstance(A, list) and len(A) == 2 and all(isinstance(r, list) and len(r) == 2 for r in A)):
        raise ProblemError("A must be a 2x2 matrix [[a, b], [c, d]]")
    M = np.array([[n(A[0][0]), n(A[0][1])], [n(A[1][0]), n(A[1][1])]])
    vals, vecs = np.linalg.eig(M)
    eig = []
    for i in range(2):
        if abs(vals[i].imag) < 1e-12:
            v = vecs[:, i].real
            eig.append({"value": float(vals[i].real), "shown": show_number(float(vals[i].real)),
                        "vector": [float(v[0]), float(v[1])]})
    vectors = [[n(v[0]), n(v[1])] for v in (spec.get("vectors") or [])[:4] if isinstance(v, list) and len(v) == 2]
    return {"kind": "matrix", "A": M.tolist(), "det": float(np.linalg.det(M)), "det_shown": show_number(float(np.linalg.det(M))),
            "eigen": eig, "complex_eigen": len(eig) < 2, "vectors": vectors,
            "images": [(M @ np.array(v)).tolist() for v in vectors]}


# ---- statistics ----------------------------------------------------------------------------------------------
def _distribution(spec: dict, n) -> dict:
    import mpmath
    kind = str(spec.get("kind") or "normal")
    p = spec.get("params") if isinstance(spec.get("params"), dict) else {}
    discrete = kind in ("binomial", "poisson")
    if kind == "normal":
        mu, sd = n(p.get("mu"), 0.0), n(p.get("sigma"), 1.0)
        pdf = lambda x: math.exp(-((x - mu) / sd) ** 2 / 2) / (sd * math.sqrt(2 * math.pi))
        cdf = lambda x: 0.5 * (1 + math.erf((x - mu) / (sd * math.sqrt(2))))
        lo, hi = mu - 4 * sd, mu + 4 * sd
    elif kind == "t":
        df = n(p.get("df"))
        pdf = lambda x: float(mpmath.gamma((df + 1) / 2) / (mpmath.sqrt(df * mpmath.pi) * mpmath.gamma(df / 2))
                              * (1 + x * x / df) ** (-(df + 1) / 2))
        cdf = lambda x: float(mpmath.quad(lambda u: pdf(float(u)), [-mpmath.inf, x]))
        lo, hi = -5.0, 5.0
    elif kind == "chi2":
        df = n(p.get("df"))
        pdf = lambda x: 0.0 if x <= 0 else float(x ** (df / 2 - 1) * mpmath.e ** (-x / 2)
                                                 / (2 ** (df / 2) * mpmath.gamma(df / 2)))
        cdf = lambda x: 0.0 if x <= 0 else float(mpmath.gammainc(df / 2, 0, x / 2, regularized=True))
        lo, hi = 0.0, max(10.0, df + 5 * math.sqrt(2 * df))
    elif kind == "exponential":
        lam = n(p.get("lam"))
        pdf = lambda x: 0.0 if x < 0 else lam * math.exp(-lam * x)
        cdf = lambda x: 0.0 if x < 0 else 1 - math.exp(-lam * x)
        lo, hi = 0.0, 5 / lam
    elif kind == "uniform":
        a, b = n(p.get("a"), 0.0), n(p.get("b"), 1.0)
        pdf = lambda x: 1 / (b - a) if a <= x <= b else 0.0
        cdf = lambda x: min(1.0, max(0.0, (x - a) / (b - a)))
        lo, hi = a - (b - a) * 0.2, b + (b - a) * 0.2
    elif kind == "binomial":
        N, pr = int(n(p.get("n"))), n(p.get("p"))
        pmf = [math.comb(N, k) * pr ** k * (1 - pr) ** (N - k) for k in range(N + 1)]
        lo, hi = 0, N
    elif kind == "poisson":
        lam = n(p.get("lam"))
        top = int(lam + 6 * math.sqrt(lam) + 6)
        pmf = [math.exp(-lam) * lam ** k / math.factorial(k) for k in range(top + 1)]
        lo, hi = 0, top
    else:
        raise ProblemError("distribution: normal, t, chi2, exponential, uniform, binomial or poisson")
    region = spec.get("region") if isinstance(spec.get("region"), dict) else {}
    a = n(region.get("from"), -math.inf if not discrete else 0)
    b = n(region.get("to"), math.inf if not discrete else hi)
    out: dict[str, Any] = {"kind": "distribution", "dist": kind, "discrete": discrete, "x": [lo, hi], "from": a, "to": b}
    if discrete:
        out["pmf"] = pmf
        prob = sum(pmf[k] for k in range(len(pmf)) if a - 1e-9 <= k <= b + 1e-9)
    else:
        out["curve"] = [[lo + (hi - lo) * i / 300, pdf(lo + (hi - lo) * i / 300)] for i in range(301)]
        prob = cdf(b) - cdf(a)
    out.update(prob=prob, shown=show_number(prob))
    return out


def _montecarlo(spec: dict, n) -> dict:
    kind = str(spec.get("kind") or "pi")
    N = max(50, min(int(n(spec.get("n"), 2000)), 5000))
    rng = random.Random(int(n(spec.get("seed"), 1)))
    pts, running, hits = [], [], 0
    if kind == "pi":
        for i in range(1, N + 1):
            x, y = rng.random(), rng.random()
            inside = x * x + y * y <= 1
            hits += inside
            pts.append([round(x, 4), round(y, 4), int(inside)])
            if i % max(1, N // 200) == 0:
                running.append([i, 4 * hits / i])
        exact, est = math.pi, 4 * hits / N
        out = {"box": [0, 1, 0, 1]}
    elif kind == "integral":
        f, _ = n.curve(str(spec.get("f")))
        a, b = n(spec.get("from")), n(spec.get("to"))
        ys = [f(a + (b - a) * i / 200) for i in range(201)]
        if any(y is None for y in ys):
            raise ProblemError("the function isn't defined over the whole range")
        top, bottom = max(0.0, *ys), min(0.0, *ys)
        total = 0.0
        for i in range(1, N + 1):
            x, y = a + (b - a) * rng.random(), bottom + (top - bottom) * rng.random()
            fx = f(x) or 0.0
            under = (0 <= y <= fx) or (fx <= y < 0)
            hits += (1 if fx >= 0 else -1) if under else 0
            total += fx
            pts.append([round(x, 5), round(y, 5), int(under)])
            if i % max(1, N // 200) == 0:
                running.append([i, (b - a) * total / i])
        import sympy
        x_ = sympy.Symbol("x")
        exact = float(sympy.N(sympy.Integral(_parse(str(spec.get("f")), n.values), (x_, a, b))))
        est = (b - a) * total / N
        out = {"box": [a, b, bottom, top], "curve": [[a + (b - a) * i / 200, ys[i]] for i in range(201)]}
    else:
        raise ProblemError("Monte Carlo: pi or integral")
    out.update(kind="montecarlo", mc=kind, n=N, points=pts, running=running, estimate=est, exact=exact,
               shown=show_number(est), exact_shown=show_number(exact))
    return out


# ---- fields ------------------------------------------------------------------------------------------------------
def _field(spec: dict, n) -> dict:
    import sympy
    x, y = sympy.Symbol("x"), sympy.Symbol("y")
    xr = [n(v) for v in (spec.get("x") or [-3, 3])[:2]]
    yr = [n(v) for v in (spec.get("y") or [-3, 3])[:2]]

    def fn(text):
        e = _parse(str(text), n.values)
        if isinstance(e, sympy.Basic) and e.free_symbols - {x, y}:
            raise ProblemError("a field may only use x, y and the problem's values")
        return sympy.lambdify((x, y), e, modules=["math"]), e
    out: dict[str, Any] = {"kind": "field", "x": xr, "y": yr}
    if spec.get("slope"):
        f, _ = fn(spec["slope"])
        grid = []
        for i in range(21):
            for j in range(17):
                px, py = xr[0] + (xr[1] - xr[0]) * i / 20, yr[0] + (yr[1] - yr[0]) * j / 16
                try:
                    grid.append([px, py, 1.0, float(f(px, py))])
                except (ValueError, ZeroDivisionError, OverflowError):
                    continue
        sols = []
        for s in (spec.get("solutions") or [])[:5]:
            if isinstance(s, list) and len(s) == 2:
                sols.append(_rk4(f, n(s[0]), n(s[1]), xr))
        out.update(mode="slope", grid=grid, solutions=sols)
    else:
        fx, ex = fn(spec.get("Fx", "0"))
        fy, ey = fn(spec.get("Fy", "0"))
        grid = []
        for i in range(17):
            for j in range(13):
                px, py = xr[0] + (xr[1] - xr[0]) * i / 16, yr[0] + (yr[1] - yr[0]) * j / 12
                try:
                    grid.append([px, py, float(fx(px, py)), float(fy(px, py))])
                except (ValueError, ZeroDivisionError, OverflowError):
                    continue
        div = sympy.simplify(sympy.diff(ex, x) + sympy.diff(ey, y))
        curl = sympy.simplify(sympy.diff(ey, x) - sympy.diff(ex, y))
        out.update(mode="vector", grid=grid, div=sympy.sstr(div).replace("**", "^"),
                   curl=sympy.sstr(curl).replace("**", "^"),
                   div_tex=sympy.latex(div), curl_tex=sympy.latex(curl))
    return out


def _rk4(f, x0: float, y0: float, xr: list[float]) -> list[list[float]]:
    out = []
    for direction in (1, -1):
        xs, ys, h, pts = x0, y0, direction * (xr[1] - xr[0]) / 200, []
        for _ in range(400):
            if not xr[0] <= xs <= xr[1] or abs(ys) > 1e6:
                break
            pts.append([xs, ys])
            try:
                k1 = f(xs, ys)
                k2 = f(xs + h / 2, ys + h * k1 / 2)
                k3 = f(xs + h / 2, ys + h * k2 / 2)
                k4 = f(xs + h, ys + h * k3)
            except (ValueError, ZeroDivisionError, OverflowError):
                break
            ys += h * (k1 + 2 * k2 + 2 * k3 + k4) / 6
            xs += h
        out = (pts[::-1] + out) if direction == -1 else pts
    return out


# ---- molecules -------------------------------------------------------------------------------------------------
MOLECULE_DIR: Path | None = None              # set by the app: where fetched molecules are kept
PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/SDF?record_type=3d"


def fetch_sdf(name: str) -> str:
    from urllib.parse import quote

    from .fetch import FetchError, get_text
    safe = re.sub(r"[^A-Za-z0-9 ,\-()']", "", name)[:60].strip().lower()
    if not safe:
        raise ProblemError("which molecule?")
    cached = MOLECULE_DIR / f"{re.sub(r'[^a-z0-9]+', '_', safe)}.sdf" if MOLECULE_DIR else None
    if cached and cached.exists():
        return cached.read_text(encoding="utf-8")
    try:
        text = get_text(PUBCHEM.format(name=quote(safe)), timeout=12)
    except FetchError as exc:
        raise ProblemError(f"PubChem didn't answer for {safe!r}: {exc}") from None
    if cached:
        try:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(text, encoding="utf-8")
        except OSError:
            pass
    return text


def parse_sdf(text: str) -> tuple[list[dict], list[list[int]]]:
    lines = text.splitlines()
    if len(lines) < 4:
        raise ProblemError("not a molecule file")
    counts = lines[3]
    try:
        na, nb = int(counts[0:3]), int(counts[3:6])
    except ValueError:
        raise ProblemError("not a molecule file") from None
    atoms, bonds = [], []
    for ln in lines[4:4 + na]:
        parts = ln.split()
        atoms.append({"x": float(parts[0]), "y": float(parts[1]), "z": float(parts[2]), "el": parts[3]})
    for ln in lines[4 + na:4 + na + nb]:
        bonds.append([int(ln[0:3]) - 1, int(ln[3:6]) - 1, int(ln[6:9])])
    if not atoms:
        raise ProblemError("no atoms in it")
    return atoms[:400], bonds[:600]


def _molecule(spec: dict, n) -> dict:
    name = str(spec.get("name") or "")
    atoms, bonds = parse_sdf(fetch_sdf(name))
    cx = sum(a["x"] for a in atoms) / len(atoms)
    cy = sum(a["y"] for a in atoms) / len(atoms)
    cz = sum(a["z"] for a in atoms) / len(atoms)
    for a in atoms:
        a["x"], a["y"], a["z"] = round(a["x"] - cx, 3), round(a["y"] - cy, 3), round(a["z"] - cz, 3)
    formula: dict[str, int] = {}
    for a in atoms:
        formula[a["el"]] = formula.get(a["el"], 0) + 1
    order = sorted(formula, key=lambda e: (e != "C", e != "H", e))
    return {"kind": "molecule", "name": name[:60], "atoms": atoms, "bonds": bonds,
            "formula": "".join(f"{e}{formula[e] if formula[e] > 1 else ''}" for e in order),
            "credit": "3D structure: PubChem (NIH)"}


# ---- particles ---------------------------------------------------------------------------------------------------
FEYNMAN_LINES = ("fermion", "antifermion", "photon", "gluon", "boson", "scalar")


def _feynman(spec: dict, n) -> dict:
    lines = []
    for ln in (spec.get("lines") or [])[:14]:
        if not isinstance(ln, dict):
            continue
        a, b = ln.get("from"), ln.get("to")
        if not (isinstance(a, list) and isinstance(b, list) and len(a) == 2 and len(b) == 2):
            continue
        kind = str(ln.get("type") or "fermion")
        lines.append({"from": [n(a[0]), n(a[1])], "to": [n(b[0]), n(b[1])],
                      "type": kind if kind in FEYNMAN_LINES else "fermion", "label": str(ln.get("label") or "")[:12]})
    if not lines:
        raise ProblemError("a Feynman diagram needs lines")
    return {"kind": "feynman", "lines": lines, "time": "right" if str(spec.get("time")) != "up" else "up",
            "title": str(spec.get("title") or "")[:60]}


MORE_BUILDERS = {"quantum": _quantum, "qcircuit": _qcircuit, "minkowski": _minkowski, "black_hole": _black_hole,
                 "matrix": _matrix, "distribution": _distribution, "montecarlo": _montecarlo, "field": _field,
                 "molecule": _molecule, "feynman": _feynman}

MORE_CATALOG = """  {"quantum": {"system": "box", "L": "L", "m": "m", "n": [1, 2, 3], "superpose": [1, 2]}}   levels, wavefunctions
     and |psi|^2 (m defaults to the electron's); "oscillator" with "omega"; "barrier" with "V0" and "E" in eV and
     width "a" (tunnelling, T and R); "hydrogen" with "n": [1, 2, 3], "l": 0, "Z": 1, "transition": [3, 2] (the photon).
     highlight: {"level": 2} or {"show": ["prob"]} or {"time": true} (the superposition moving)
  {"qcircuit": {"qubits": 2, "initial": "00", "gates": [["H", 0], ["CNOT", 0, 1], ["RY", 1, "theta"]]}}   gates H X Y Z
     S T RX RY RZ (angle in radians) CNOT CZ SWAP CCX: the state after each gate, probabilities, Bloch vectors.
     highlight: {"gate": 1} shows the state after the first gate (0: the start)
  {"minkowski": {"beta": 0.6, "events": [{"name": "A", "x": 3, "ct": 5}], "worldlines": [{"name": "twin",
     "path": [[0, 0], [4, 5], [0, 10]]}, {"name": "rocket", "beta": 0.8, "x0": 0, "ct1": 10}], "unit": "ly"}}
     a spacetime diagram (x and ct in the same unit): light cones, the moving frame's axes, both frames' coordinates,
     proper times. highlight: {"event": "A"} or {"simultaneity": true} or {"frame": true}
  {"black_hole": {"M": "M"}}   M in kg: horizon, photon sphere, ISCO, Hawking temperature. highlight: {"show": ["photon"]}
  {"matrix": {"A": [[2, 1], [1, 2]], "vectors": [[1, 0], [0, 1]]}}   the plane transformed; eigenvectors; det as area.
     highlight: {"show": ["eigen", "det"]}
  {"distribution": {"kind": "normal|t|chi2|exponential|uniform|binomial|poisson", "params": {"mu": 0, "sigma": 1,
     "df": 5, "lam": 2, "n": 10, "p": 0.3, "a": 0, "b": 1}, "region": {"from": -1.96, "to": 1.96}}}   the probability
     of the region, shaded
  {"montecarlo": {"kind": "pi|integral", "n": 2000, "f": "exp(-x^2)", "from": 0, "to": 1, "seed": 1}}
  {"field": {"Fx": "-y", "Fy": "x", "x": [-3, 3], "y": [-3, 3]}} a vector field (div and curl worked out), or
     {"field": {"slope": "x - y", "solutions": [[0, 1], [0, -1]]}} a slope field with solution curves (RK4)
  {"molecule": {"name": "caffeine"}}   the molecule in 3D (PubChem); any common name
  {"feynman": {"lines": [{"from": [0, 0], "to": [0.4, 0.5], "type": "fermion|antifermion|photon|gluon|boson|scalar",
     "label": "e-"}], "time": "right"}}   points in a 0-1 box"""


__all__ = ["MORE_BUILDERS", "MORE_CATALOG", "fetch_sdf", "parse_sdf"]
