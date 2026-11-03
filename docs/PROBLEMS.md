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
