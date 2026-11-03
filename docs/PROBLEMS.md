# Worked problems: every part, step by step, with its animation

"Solve this problem: a car starts from rest and accelerates at 2.5 m/s² for
8 s ... (a) ... (b) ...", or **Solve from a photo or PDF** at the top of
Jarvis's window (or drop the file on the window, or paste a screenshot).

## Using it

| You | Jarvis |
|---|---|
| ask a problem with numbers and parts | plans it, works every step out with SymPy, opens it in his window |
| click a part, or "part b" | opens its card |
| **Hint** / "hint" | a nudge, not the answer |
| **Next step** / "next step" | one step: its goal, the equation, the worked number, the animation at that moment |
| **Back** / "back" | the step before |
| **Full solution** / "full solution" | every step of that part |
| type your answer, **Check my answer** / "I got 33.3" | marks it, and names a units slip or a wrong sign |
| **Practice: new numbers** / "practice" | the same problem with new numbers, worked out again, to try alone |
| **Summary** / "summary" | the method in a few points |
| "why do we square it?" | the model answers about the step on screen |

A photo is read by Gemini (the "vision" route in `config/settings.toml`); a
PDF's text by pypdf (a scanned PDF needs a photo or screenshot instead). A
sheet with several questions: pick one in the window.

## How it works

1. **The plan** (`knowledge/problems.py`): one model call (the "problem" route:
   gpt-oss-120b thinking, then Gemini) returns JSON: the given values in SI
   units, the parts, each step's goal, words, equation and its calculation as
   `name = expression`, and the views.
2. **SymPy works out every step**, in order (`work`). The model never writes a
   number it worked out itself: the screen shows SymPy's. A step SymPy can't
   run is shown as "not checked", and the model gets one chance to fix it.
   The step's maths is vetted like `mathcheck.py`: maths characters and known
   names only, no Python.
3. **The views** (`knowledge/problem_views.py`) take their numbers from the
   same values, so the animation and the working can't disagree: motion
   (phases, ABS or locked wheels, s-t, v-t, a-t, the area under v-t), 2D paths,
   graphs (area, tangent, Newton's method, Euler's method, Riemann sums and the
   trapezium rule), forces, circuits, reaction kinetics, titration curves
   (solved exactly from the charge balance), energy profiles, ICE tables, and
   the lessons' tested scenes, plots, diagrams and pictures. No model-drawn
   sketches: they were the blank pictures.
4. **The window** (`ui/problem.js`) draws them, and Jarvis speaks each step
   (`problem_mode.py`).

## Why hints first and one step at a time

- Step-based tutoring (feedback on each step, not only the answer) comes close
  to a human tutor (VanLehn 2011: effect size about 0.76, against 0.79 for
  human tutors).
- Worked examples, then fading them (you do more of each step), and naming
  each step's goal (subgoal labels) help students learn problem solving
  (Renkl and Atkinson; Margulieux and Catrambone).
- Letting the computer do the arithmetic makes a model's answers far more
  reliable (PAL, Gao et al. 2022): the model plans, the interpreter computes.

## Learn

- VanLehn (2011), The relative effectiveness of human tutoring, intelligent
  tutoring systems, and other tutoring systems. Educational Psychologist.
- Gao et al. (2022), PAL: Program-aided language models. arXiv 2211.10435.
- Renkl and Atkinson (2003), Structuring the transition from example study to
  problem solving in cognitive skill acquisition.

## The views for modern physics, quantum computing and more

`knowledge/problem_views_more.py`, each checked against known results in
`tests/test_problems.py`:

| View | Shows | Checked against |
|---|---|---|
| quantum (box, oscillator) | levels, ψ and \|ψ\|² at each level, a superposition sloshing in time | electron in a 1 nm box: 0.376 eV; oscillator levels 1 : 3 |
| quantum (barrier) | tunnelling: the wave moving, \|ψ\|², T and R (solved exactly by matching) | T + R = 1 |
| quantum (hydrogen) | levels, a transition's photon and its colour, radial probability | 3 → 2: 656.1 nm, red (H-alpha) |
| qcircuit | a circuit stepped gate by gate: probabilities (coloured by phase), Bloch spheres | Bell state 50/50, no Bloch direction; RY(π/2) to +x; Toffoli |
| minkowski | light cones, a moving frame's axes and grid, events in both frames, lines of simultaneity, proper times | γ = 1.25 at 0.6c; the twins: 6 years against 10 |
| black_hole | horizon, photon sphere, innermost stable orbit, curved space, Hawking temperature | the Sun: 2954 m, 6.17 × 10⁻⁸ K |
| matrix | the plane bent by a 2x2 matrix, eigenvectors, the determinant as an area | [[2, 1], [1, 2]]: λ = 1, 3, det 3 |
| distribution | normal, t, χ², exponential, uniform, binomial, Poisson: a probability as an area | ±1.96, t(5) ±2.571, χ²(3) 7.815: 0.95 |
| montecarlo | random points and the estimate converging (π, an integral) | within 0.1 of π for 4000 points |
| field | a vector field with moving particles (div and curl worked out), or a slope field with RK4 curves | (−y, x): div 0, curl 2; y' = y follows eˣ |
| molecule | any molecule in 3D from PubChem, turned with the mouse (kept on disk after once) | water: H2O, 2 bonds |
| feynman | fermions, photons, gluons, W, Z, Higgs lines, with time's direction | |
| collision | two bodies meeting, momentum and kinetic energy bars before and after | elastic 2 kg at 3 m/s on 1 kg: 1 and 4 m/s |
| rotation | a wheel under a torque (ω-t, θ-t), or shapes rolling down a slope, racing | solid sphere on 30°: a = g sinθ / 1.4 |
| pv | a PV diagram of any steps (isothermal, adiabatic, isobaric, isochoric): work, heat, ΔU, efficiency | Carnot 600 K / 300 K: 50% |
| induction | a coil turning in a field (flux and emf = −N dΦ/dt), or a rod sliding on rails (Lenz) | N B A ω = 10 V; BLv |
| doppler | moving wavefronts, the pitch ahead and behind; light too | 440 Hz at 30 m/s: 482 Hz ahead |
| interference | waves from one slit, two slits or a grating and the pattern on the screen | λL/d = 3.9 mm; 600 lines/mm: 2 orders, 20.7° |

For ideas with no exact simulation (string theory's extra dimensions, say),
the plan uses the lessons' tested visuals: Mermaid diagrams, 3D surfaces,
scenes and Wikipedia pictures, never a model-drawn sketch.

## Checking the set-up, not only the arithmetic

SymPy makes the arithmetic right; these catch a wrong set-up:

- **Units** (`knowledge/dimensions.py`): every given value is scaled by a
  made-up factor for each base unit (metres 1.7 times bigger, seconds 0.6
  times...), twice, and the steps are worked out again. A step whose result
  has the unit it claims scales by exactly the right amount; a "distance"
  that is really speed times acceleration doesn't, and is flagged (badge,
  and Jarvis says so). The model gets one chance to fix it. Steps with log,
  exp or trig, or an equilibrium constant (unitless by chemistry's
  convention), aren't checked rather than wrongly flagged.
- **Against the animation** (`problem_views.cross_check`): a view works out
  its own numbers (the motion's phase distances and times, the titration's
  equivalence point, every resistor's current...). An answer that matches
  one is marked "the animation agrees"; one where the view has numbers of
  the same kind and none matches is flagged: the steps and the view were set
  up differently.
- **Every plan is kept** in `state/problems/` (the newest 100): the
  question, the model's plan as it wrote it, and what the checks found.
  Send one when a problem looks wrong.
