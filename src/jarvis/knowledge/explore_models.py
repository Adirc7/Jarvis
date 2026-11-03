"""The models in the 3D explorer (ui/explore.js): a sports car, a motorcycle and a four-cylinder engine.

Our own simple models, built from shapes: not copies of any maker's design. Each part has a name, a group
(its colour in the window), a short description for the side card and for Jarvis's explanation, the
shapes it's drawn with, and where it moves when the model is taken apart ("out", in the model's units at
full explode). A shape may carry its own "out" (a pair of seats, two sides of the brakes) so the halves
of one part move apart too.

Shapes (y is up, x is forward, z is to the side; angles in radians):
    {"t": "box", "s": [w, h, d], "p": [x, y, z], "r": [rx, ry, rz]}
    {"t": "cyl", "s": [radius_top, radius_bottom, height], ...}    along y unless rotated
    {"t": "torus", "s": [radius, tube], ...}                        in the x-y plane (a car wheel's)
    {"t": "sphere", "s": [radius], "sc": [x, y, z], ...}            "sc" squashes it
    {"t": "tube", "pts": [[x, y, z], ...], "s": [radius]}           a pipe through the points
    {"t": "spring", "s": [radius, height, turns, wire], ...}        a coil, along y

The idea of moving each part out along a clear direction, so round parts stay lined up and groups stay
together, follows how CAD viewers draw exploded views (docs/EXPLORE.md).
"""

from __future__ import annotations

import math
import re

from .explore_shapes import GROUPS, X, Z
from .explore_shapes import part as _part
from .explore_shapes import wheel as _wheel


def _sports_car() -> dict:
    wy = 0.82                                         # wheel centre height
    parts = [
        _part("body_shell", "Body shell", "body",
              "The painted outer skin and the cabin roof. It keeps out wind and rain, gives the car its "
              "low drag shape, and protects the people inside.",
              [0, 3.4, 0],
              {"t": "box", "s": [8.4, 0.75, 3.6], "p": [0, 1.35, 0]},
              {"t": "box", "s": [2.0, 0.08, 2.9], "p": [-0.7, 2.5, 0]},                        # roof
              {"t": "box", "s": [1.5, 0.06, 2.9], "p": [0.95, 2.12, 0], "r": [0, 0, -0.52]},   # windscreen
              {"t": "box", "s": [1.68, 0.06, 2.9], "p": [-2.45, 2.12, 0], "r": [0, 0, 0.46]},  # rear window
              {"t": "box", "s": [3.0, 0.62, 0.05], "p": [-0.75, 2.08, 1.45]},                  # side windows
              {"t": "box", "s": [3.0, 0.62, 0.05], "p": [-0.75, 2.08, -1.45]}),
        _part("hood", "Bonnet (hood)", "body",
              "The hinged cover over the engine bay, opened for servicing.",
              [2.4, 3.6, 0], {"t": "box", "s": [2.3, 0.08, 3.3], "p": [2.9, 1.76, 0]}),
        _part("door_left", "Left door", "body",
              "Hinged at the front; inside it are the window glass, its motor and a side-impact beam.",
              [0, 0.8, 2.8], {"t": "box", "s": [2.1, 1.05, 0.1], "p": [-0.2, 1.5, 1.86]}),
        _part("door_right", "Right door", "body",
              "Hinged at the front; inside it are the window glass, its motor and a side-impact beam.",
              [0, 0.8, -2.8], {"t": "box", "s": [2.1, 1.05, 0.1], "p": [-0.2, 1.5, -1.86]}),
        _part("front_bumper", "Front bumper", "body",
              "Absorbs low-speed knocks and guides air to the radiator through its grille.",
              [3.0, 0.2, 0], {"t": "box", "s": [0.3, 0.55, 3.7], "p": [4.35, 1.0, 0]}),
        _part("rear_bumper", "Rear bumper", "body",
              "Absorbs low-speed knocks at the back and holds the number plate.",
              [-3.0, 0.2, 0], {"t": "box", "s": [0.3, 0.55, 3.7], "p": [-4.35, 1.0, 0]}),
        _part("headlights", "Headlights", "electrical",
              "LED lamps with low and high beam, aimed so they light the road without dazzling others.",
              [3.6, 1.4, 0],
              {"t": "box", "s": [0.25, 0.22, 0.75], "p": [4.25, 1.45, 1.3], "out": [3.6, 1.4, 1.2]},
              {"t": "box", "s": [0.25, 0.22, 0.75], "p": [4.25, 1.45, -1.3], "out": [3.6, 1.4, -1.2]}),
        _part("taillights", "Tail lights", "electrical",
              "Red lamps that brighten when you brake, with the indicators and reversing lights.",
              [-3.6, 1.4, 0],
              {"t": "box", "s": [0.2, 0.22, 0.8], "p": [-4.25, 1.45, 1.3], "out": [-3.6, 1.4, 1.2]},
              {"t": "box", "s": [0.2, 0.22, 0.8], "p": [-4.25, 1.45, -1.3], "out": [-3.6, 1.4, -1.2]}),
        _part("engine", "Engine (V8)", "powertrain",
              "Burns fuel with air in eight cylinders arranged in a V; the pistons push a crankshaft "
              "round, which is the power that drives the wheels.",
              [1.6, 2.0, 0],
              {"t": "box", "s": [1.5, 0.7, 0.9], "p": [2.7, 1.05, 0]},
              {"t": "box", "s": [1.4, 0.45, 0.45], "p": [2.7, 1.5, 0.42], "r": [-0.5, 0, 0]},
              {"t": "box", "s": [1.4, 0.45, 0.45], "p": [2.7, 1.5, -0.42], "r": [0.5, 0, 0]},
              {"t": "cyl", "s": [0.18, 0.18, 1.3], "p": [2.7, 1.72, 0], "r": X}),
        _part("radiator", "Radiator", "powertrain",
              "Cools the engine: hot coolant flows through thin tubes and air rushing through the fins "
              "carries the heat away.",
              [3.4, 1.0, 0], {"t": "box", "s": [0.14, 0.75, 2.6], "p": [3.95, 1.05, 0]}),
        _part("gearbox", "Gearbox", "powertrain",
              "Changes the ratio between engine speed and wheel speed, so the car can pull away slowly "
              "and still cruise fast with the engine calm.",
              [0.8, -1.2, 0], {"t": "cyl", "s": [0.36, 0.3, 1.3], "p": [1.3, 0.85, 0], "r": X}),
        _part("driveshaft", "Driveshaft", "powertrain",
              "A spinning tube that carries the turning force from the gearbox to the rear axle.",
              [0, -1.7, 0], {"t": "cyl", "s": [0.09, 0.09, 3.6], "p": [-1.0, 0.62, 0], "r": X}),
        _part("differential", "Differential and rear axle", "powertrain",
              "Splits the drive between the two rear wheels and lets them turn at different speeds "
              "in a corner, where the outer wheel travels farther.",
              [-1.2, -1.5, 0],
              {"t": "sphere", "s": [0.36], "p": [-2.9, wy, 0], "sc": [1, 0.9, 1.1]},
              {"t": "cyl", "s": [0.07, 0.07, 3.0], "p": [-2.9, wy, 0], "r": Z}),
        _part("exhaust", "Exhaust system", "powertrain",
              "Carries the burnt gases away: the catalytic converter cleans them and the silencer "
              "quietens them before they leave at the back.",
              [0, -2.2, 1.8],
              {"t": "tube", "pts": [[2.3, 0.75, 0.55], [1.2, 0.45, 0.6], [-3.0, 0.45, 0.6], [-4.4, 0.55, 0.6]],
               "s": [0.08]},
              {"t": "box", "s": [1.0, 0.32, 0.55], "p": [-3.4, 0.5, 0.6]}),
        _part("fuel_tank", "Fuel tank", "powertrain",
              "Holds the petrol in front of the rear axle, where it's safest in a crash; a pump in it "
              "feeds the engine.",
              [-1.6, -0.6, 0], {"t": "box", "s": [0.9, 0.35, 1.4], "p": [-1.8, 1.05, 0]}),
        _part("battery", "Battery", "electrical",
              "12-volt store of electricity that starts the engine and runs the electrics when it's off.",
              [1.6, 2.2, -1.4], {"t": "box", "s": [0.5, 0.35, 0.35], "p": [3.4, 1.25, -1.15]}),
        _part("seats", "Seats", "interior",
              "Bucket seats that hold you in place in corners, with the seat belts' anchors.",
              [-0.4, 1.8, 0],
              {"t": "box", "s": [0.9, 0.22, 0.8], "p": [-0.7, 0.95, 0.75], "out": [-0.4, 1.8, 0.7]},
              {"t": "box", "s": [0.2, 0.95, 0.8], "p": [-1.2, 1.45, 0.75], "r": [0, 0, 0.2], "out": [-0.4, 1.8, 0.7]},
              {"t": "box", "s": [0.9, 0.22, 0.8], "p": [-0.7, 0.95, -0.75], "out": [-0.4, 1.8, -0.7]},
              {"t": "box", "s": [0.2, 0.95, 0.8], "p": [-1.2, 1.45, -0.75], "r": [0, 0, 0.2], "out": [-0.4, 1.8, -0.7]}),
        _part("steering", "Steering wheel and column", "interior",
              "Turning the wheel turns the column, which moves a rack that swings the front wheels.",
              [1.0, 2.6, 0.8],
              {"t": "torus", "s": [0.32, 0.05], "p": [0.55, 1.75, 0.75], "r": [0, math.pi / 2, 0]},
              {"t": "cyl", "s": [0.05, 0.05, 1.1], "p": [1.05, 1.5, 0.75], "r": [0, 0, 1.1]}),
        _part("dashboard", "Dashboard", "interior",
              "The instruments, the screen and the air vents, with the heater and air-conditioning behind.",
              [1.2, 2.2, 0], {"t": "box", "s": [0.45, 0.4, 3.1], "p": [1.0, 1.62, 0]}),
        _part("chassis", "Chassis frame", "chassis",
              "The strong frame everything is bolted to; it carries the loads from the wheels and keeps "
              "the car stiff so the suspension can do its work.",
              [0, -2.8, 0],
              {"t": "box", "s": [8.0, 0.14, 0.16], "p": [0, 0.5, 0.9]},
              {"t": "box", "s": [8.0, 0.14, 0.16], "p": [0, 0.5, -0.9]},
              {"t": "box", "s": [0.14, 0.14, 1.8], "p": [2.9, 0.5, 0]},
              {"t": "box", "s": [0.14, 0.14, 1.8], "p": [0, 0.5, 0]},
              {"t": "box", "s": [0.14, 0.14, 1.8], "p": [-2.9, 0.5, 0]}),
    ]
    for side, z in (("left", 1.0), ("right", -1.0)):
        for end, x in (("front", 2.9), ("rear", -2.9)):
            parts.append(_part(f"wheel_{end}_{side}", f"{end.capitalize()} {side} wheel", "running",
                               "The rim and the tyre: the tyre's small contact patch is all that holds the "
                               "car to the road, for grip, braking and steering.",
                               [0.6 if x > 0 else -0.6, 0, 2.6 * z], *_wheel(x, 1.75 * z)))
    parts.append(_part("brakes", "Disc brakes", "running",
                       "A disc spins with each wheel; pressing the pedal squeezes pads onto it with the "
                       "caliper, turning the car's motion into heat.",
                       [0, 0, 0],
                       *[{"t": "cyl", "s": [0.42, 0.42, 0.06], "p": [x, wy, 1.42 * z], "r": Z,
                          "out": [0.4 * math.copysign(1, x), 0, 1.9 * z]}
                         for x in (2.9, -2.9) for z in (1, -1)],
                       *[{"t": "box", "s": [0.25, 0.3, 0.16], "p": [x + 0.3, wy + 0.2, 1.42 * z],
                          "out": [0.4 * math.copysign(1, x), 0, 1.9 * z]}
                         for x in (2.9, -2.9) for z in (1, -1)]))
    parts.append(_part("suspension", "Suspension springs and dampers", "running",
                       "Springs let each wheel follow bumps; dampers stop the bouncing, so the tyres stay "
                       "pressed to the road and the ride stays calm.",
                       [0, 1.2, 0],
                       *[{"t": "spring", "s": [0.16, 0.7, 6, 0.035], "p": [x, 1.0, 1.15 * z],
                          "out": [0.3 * math.copysign(1, x), 1.2, 1.3 * z]}
                         for x in (2.9, -2.9) for z in (1, -1)]))
    return {"id": "sports_car", "title": "Sports car", "size": "4.4 m long, two seats, front engine, rear-wheel drive",
            "scale": 1.0, "parts": parts}


def _motorcycle() -> dict:
    r, wy = 0.85, 1.05
    parts = [
        _part("front_wheel", "Front wheel", "running",
              "Steers the bike and does most of the braking, so it carries the bigger brake discs.",
              [1.8, 0, 0], *_wheel(2.4, 0, r, 0.18)),
        _part("rear_wheel", "Rear wheel", "running",
              "Driven by the chain; its wider tyre puts the engine's power onto the road.",
              [-1.8, 0, 0], *_wheel(-2.4, 0, r, 0.2)),
        _part("frame", "Frame", "chassis",
              "Steel tubes that join the steering head, the engine and the swingarm: the bike's backbone.",
              [0, 2.6, -1.6],
              {"t": "tube", "pts": [[1.45, 2.35, 0], [0.4, 1.95, 0], [-0.7, 1.75, 0], [-1.6, 1.95, 0]], "s": [0.07]},
              {"t": "tube", "pts": [[1.45, 2.35, 0], [1.0, 1.2, 0], [0.4, 0.75, 0], [-0.5, 0.75, 0], [-0.7, 1.75, 0]],
               "s": [0.07]}),
        _part("fuel_tank", "Fuel tank", "powertrain",
              "Sits between your knees; you grip it with your legs in corners.",
              [0, 2.6, 0], {"t": "sphere", "s": [0.55], "p": [0.55, 2.2, 0], "sc": [1.5, 0.75, 0.8]}),
        _part("seat", "Seat", "interior",
              "The rider's and the passenger's seat, on the rear subframe.",
              [-0.6, 2.2, 0], {"t": "box", "s": [1.4, 0.18, 0.5], "p": [-0.8, 2.05, 0]}),
        _part("engine", "Engine", "powertrain",
              "A two-cylinder engine hung low in the frame: its weight there keeps the bike stable.",
              [0, -1.6, 0],
              {"t": "box", "s": [0.9, 0.6, 0.6], "p": [0.2, 1.05, 0]},
              {"t": "cyl", "s": [0.2, 0.2, 0.7], "p": [0.45, 1.6, 0.12], "r": [0, 0, -0.35]},
              {"t": "cyl", "s": [0.2, 0.2, 0.7], "p": [0.45, 1.6, -0.12], "r": [0, 0, -0.35]}),
        _part("gearbox", "Gearbox", "powertrain",
              "Six gears, chosen with your left foot and the clutch on the left handlebar.",
              [-0.6, -1.4, 0], {"t": "cyl", "s": [0.28, 0.28, 0.6], "p": [-0.45, 0.95, 0], "r": Z}),
        _part("chain", "Chain and sprockets", "powertrain",
              "A small sprocket on the gearbox drives a big one on the rear wheel through the chain; the "
              "sizes of the two set the final gearing.",
              [-0.8, -0.2, 1.6],
              {"t": "cyl", "s": [0.14, 0.14, 0.05], "p": [-0.45, 0.95, 0.35], "r": Z},
              {"t": "cyl", "s": [0.36, 0.36, 0.05], "p": [-2.4, wy, 0.35], "r": Z},
              {"t": "tube", "pts": [[-0.45, 1.09, 0.35], [-2.4, 1.41, 0.35]], "s": [0.03]},
              {"t": "tube", "pts": [[-0.45, 0.81, 0.35], [-2.4, 0.69, 0.35]], "s": [0.03]}),
        _part("forks", "Front forks", "running",
              "Two telescopic tubes with springs and oil inside: the front suspension, and what turns "
              "when you steer.",
              [1.3, 0.9, 0],
              {"t": "cyl", "s": [0.06, 0.06, 1.7], "p": [1.95, 1.85, 0.22], "r": [0, 0, 0.45]},
              {"t": "cyl", "s": [0.06, 0.06, 1.7], "p": [1.95, 1.85, -0.22], "r": [0, 0, 0.45]}),
        _part("handlebars", "Handlebars", "interior",
              "Steer the bike; the right grip is the throttle and front brake, the left the clutch.",
              [1.0, 2.0, 0], {"t": "tube", "pts": [[1.45, 2.7, 0.55], [1.55, 2.6, 0], [1.45, 2.7, -0.55]], "s": [0.04]}),
        _part("swingarm", "Swingarm", "running",
              "Holds the rear wheel and pivots behind the gearbox, so the wheel can move up and down.",
              [-0.9, -1.0, 0],
              {"t": "box", "s": [1.9, 0.12, 0.08], "p": [-1.45, 1.0, 0.25], "r": [0, 0, 0.03]},
              {"t": "box", "s": [1.9, 0.12, 0.08], "p": [-1.45, 1.0, -0.25], "r": [0, 0, 0.03]}),
        _part("rear_shock", "Rear shock absorber", "running",
              "A spring and damper between the frame and the swingarm: the rear suspension.",
              [-0.6, 1.4, 0], {"t": "spring", "s": [0.1, 0.7, 7, 0.025], "p": [-1.0, 1.25, 0], "r": [0, 0, 0.5]}),
        _part("exhaust", "Exhaust", "powertrain",
              "Takes the burnt gases from the cylinders to the silencer under the seat.",
              [0, -0.8, -1.8],
              {"t": "tube", "pts": [[0.55, 1.6, -0.25], [0.7, 0.55, -0.3], [-0.6, 0.5, -0.35], [-1.6, 1.1, -0.35]],
               "s": [0.06]},
              {"t": "cyl", "s": [0.15, 0.13, 0.8], "p": [-1.8, 1.2, -0.35], "r": [0, 0, 1.25]}),
        _part("headlight", "Headlight", "electrical",
              "Lights the road ahead and makes the bike easy to see.",
              [1.6, 1.0, 0], {"t": "cyl", "s": [0.2, 0.17, 0.2], "p": [1.75, 2.35, 0], "r": X}),
        _part("radiator", "Radiator", "powertrain",
              "Cools the engine's coolant with the air that hits the front of the bike.",
              [1.2, -0.4, 0], {"t": "box", "s": [0.08, 0.6, 0.55], "p": [1.0, 1.45, 0], "r": [0, 0, 0.2]}),
        _part("brakes", "Disc brakes", "running",
              "A disc on each wheel and a caliper that squeezes it; the front one does most of the work.",
              [0, 0, 0],
              {"t": "cyl", "s": [0.42, 0.42, 0.04], "p": [2.4, wy, 0.2], "r": Z, "out": [1.8, 0, 1.0]},
              {"t": "cyl", "s": [0.3, 0.3, 0.04], "p": [-2.4, wy, -0.2], "r": Z, "out": [-1.8, 0, -1.0]}),
        _part("battery", "Battery", "electrical",
              "Starts the engine and powers the lights, under the seat.",
              [-0.6, 0.6, 1.4], {"t": "box", "s": [0.3, 0.25, 0.2], "p": [-0.6, 1.6, 0]}),
    ]
    return {"id": "motorcycle", "title": "Motorcycle", "size": "2.1 m long, two cylinders, chain drive",
            "scale": 1.3, "parts": parts}


def _engine() -> dict:
    xs = [-1.35, -0.45, 0.45, 1.35]                   # the four cylinders along the crankshaft
    parts = [
        _part("block", "Engine block", "powertrain",
              "Cast metal holding the four cylinders, with passages for coolant and oil around them.",
              [0, 0, 0], {"t": "box", "s": [3.8, 1.6, 1.4], "p": [0, 0, 0]}),
        _part("head", "Cylinder head", "powertrain",
              "Closes the top of the cylinders; it holds the valves, the spark plugs and the camshaft.",
              [0, 2.2, 0], {"t": "box", "s": [3.8, 0.55, 1.4], "p": [0, 1.1, 0]}),
        _part("cam_cover", "Camshaft cover", "powertrain",
              "Keeps the oil around the camshaft in, and dirt out.",
              [0, 4.6, 0], {"t": "box", "s": [3.6, 0.3, 1.2], "p": [0, 1.55, 0]}),
        _part("camshaft", "Camshaft", "powertrain",
              "Its lobes push the valves open at exactly the right moment; it turns at half the "
              "crankshaft's speed.",
              [0, 3.6, 0], {"t": "cyl", "s": [0.08, 0.08, 3.6], "p": [0, 1.3, 0], "r": X}),
        _part("valves", "Valves", "powertrain",
              "Two per cylinder: the intake valve lets the air and fuel in, the exhaust valve lets the "
              "burnt gas out.",
              [0, 3.0, 0],
              *[{"t": "cyl", "s": [0.03, 0.03, 0.55], "p": [x, 0.85, dz]} for x in xs for dz in (0.25, -0.25)]),
        _part("spark_plugs", "Spark plugs", "electrical",
              "A spark at the top of each cylinder lights the squeezed fuel and air.",
              [0, 5.4, 0], *[{"t": "cyl", "s": [0.06, 0.06, 0.6], "p": [x, 1.5, 0]} for x in xs]),
        _part("pistons", "Pistons", "powertrain",
              "Slide up and down in the cylinders; the burning gas pushes them down, and that push is "
              "the engine's power.",
              [0, 1.4, 1.6], *[{"t": "cyl", "s": [0.36, 0.36, 0.45], "p": [x, 0.35, 0]} for x in xs]),
        _part("rods", "Connecting rods", "powertrain",
              "Link each piston to the crankshaft, turning the up-and-down push into rotation.",
              [0, 0.3, 2.4], *[{"t": "box", "s": [0.12, 0.9, 0.12], "p": [x, -0.2, 0]} for x in xs]),
        _part("crankshaft", "Crankshaft", "powertrain",
              "The offset throws turn the pistons' push into rotation; it carries the flywheel and "
              "drives everything else.",
              [0, -2.0, 0],
              {"t": "cyl", "s": [0.12, 0.12, 4.4], "p": [0, -0.75, 0], "r": X},
              *[{"t": "box", "s": [0.14, 0.35, 0.3], "p": [x, -0.62, 0]} for x in xs]),
        _part("oil_pan", "Oil pan (sump)", "powertrain",
              "Holds the engine oil at the bottom; the pump sends it to every moving part.",
              [0, -3.6, 0], {"t": "box", "s": [3.6, 0.55, 1.3], "p": [0, -1.1, 0]}),
        _part("flywheel", "Flywheel", "powertrain",
              "A heavy disc that smooths the separate pushes of the pistons and meets the clutch.",
              [-2.4, -0.4, 0], {"t": "cyl", "s": [0.75, 0.75, 0.15], "p": [-2.15, -0.5, 0], "r": X}),
        _part("timing_belt", "Timing belt", "powertrain",
              "Keeps the camshaft in step with the crankshaft: if it slips, valves and pistons can collide.",
              [2.6, 0, 0],
              {"t": "tube", "pts": [[2.0, 1.3, 0.25], [2.0, -0.75, 0.25], [2.0, -0.75, -0.25], [2.0, 1.3, -0.25],
                                    [2.0, 1.3, 0.25]], "s": [0.04]}),
        _part("intake", "Intake manifold", "powertrain",
              "Shares the incoming air between the four cylinders.",
              [0, 0.6, 2.8],
              *[{"t": "tube", "pts": [[x, 1.1, 0.7], [x, 1.25, 1.2], [0, 1.4, 1.5]], "s": [0.08]} for x in xs]),
        _part("exhaust_manifold", "Exhaust manifold", "powertrain",
              "Collects the hot gases from the four cylinders into one pipe.",
              [0, 0.6, -2.8],
              *[{"t": "tube", "pts": [[x, 0.95, -0.7], [x, 0.7, -1.1], [0.5, 0.3, -1.3]], "s": [0.07]} for x in xs]),
    ]
    tones = {"block": "#8fa7ba", "head": "#4de1ff", "cam_cover": "#2f9fc4", "camshaft": "#b48cff", "valves": "#64efb7",
             "pistons": "#ffb43b", "rods": "#ff8c5a", "crankshaft": "#ff5fa2", "oil_pan": "#6f8fa3",
             "flywheel": "#ffd166", "timing_belt": "#e0e0ff", "intake": "#7ad7ff", "exhaust_manifold": "#ff766f"}
    for part in parts:
        if part["id"] in tones:
            part["colour"] = tones[part["id"]]
    return {"id": "engine", "title": "Four-cylinder engine", "size": "inline four, overhead camshaft",
            "scale": 1.6, "parts": parts}


def _all() -> list[dict]:
    from .explore_vehicles import VEHICLES
    models = [_sports_car(), _motorcycle(), _engine(), *(make() for make in VEHICLES)]
    likes = {"sports_car": "Toyota Supra, BMW M4, Ford Mustang", "motorcycle": "a sports or touring motorcycle",
             "engine": "most small cars"}
    for m in models:
        m.setdefault("like", likes.get(m["id"], ""))
    return models


ORDER = ["sports_car", "supercar", "electric_car", "hybrid_car", "pickup_4x4", "three_wheeler", "motorcycle",
         "scooter", "bicycle", "engine"]
MODELS = {m["id"]: m for m in sorted(_all(), key=lambda m: ORDER.index(m["id"]))}
# Words that name each model, brands included: a brand points to the type it's built like inside.
# Checked in this order, most particular first ("electric car" before "car", "car engine" is the engine).
WORDS = {
    "three_wheeler": ("three wheeler", "threewheeler", "tuk", "tuktuk", "tuk tuk", "trishaw", "bajaj", "auto rickshaw",
                      "ත්‍රීවීල්", "ත්‍රී රෝද"),
    "scooter": ("scooter", "scooty", "vespa", "dio", "activa"),
    "bicycle": ("bicycle", "bicycles", "cycle", "pushbike", "push bike", "බයිසිකල්"),
    "supercar": ("supercar", "supercars", "super car", "super cars", "lamborghini", "lambo", "ferrari", "mclaren",
                 "mid engine", "huracan", "aventador"),
    "electric_car": ("electric car", "electric vehicle", "ev", "evs", "tesla", "byd", "leaf", "electric cars",
                     "විදුලි කාර්"),
    "hybrid_car": ("hybrid", "hybrids", "prius", "aqua", "vezel", "හයිබ්‍රිඩ්"),
    "pickup_4x4": ("pickup", "pick up", "4x4", "four wheel drive", "4wd", "hilux", "land cruiser", "jeep", "suv",
                   "suvs", "l200", "ranger", "defender", "off road", "offroad"),
    "engine": ("engine", "engines", "motor", "එන්ජින්"),
    "motorcycle": ("motorcycle", "motorbike", "bike", "bikes", "motor bike", "sport bike", "බයික්", "යතුරුපැදි"),
    "sports_car": ("car", "cars", "vehicle", "vehicles", "sports car", "supra", "bmw", "mustang",
                   "corvette", "nissan gtr", "කාර්", "වාහන"),
}


def model_for(text: str) -> str | None:
    """Which model a request names ("take the engine apart" -> "engine", "a Prius" -> the hybrid); None when
    it names none."""
    t = text.lower()
    plain = " " + " ".join(re.sub(r"[^a-z0-9\s]", " ", t).split()) + " "
    for key, words in WORDS.items():
        if any((f" {w} " in plain) if w.isascii() else (w in t) for w in words):
            return key
    return None


def find_part(model: dict, text: str) -> dict | None:
    """The part a phrase names ("the gear box", "radiator"), by its name or id."""
    t = " " + text.lower().replace("-", " ") + " "
    best, best_len = None, 0
    for part in model["parts"]:
        names = {part["name"].lower(), part["id"].replace("_", " ")}
        names |= {n.split(" (")[0] for n in names} | {n.replace("gearbox", "gear box") for n in names}
        names |= {n.split(" and ")[0] for n in names}
        for n in names:
            if f" {n} " in t or f" {n}s " in t or (n.endswith("s") and f" {n[:-1]} " in t):
                if len(n) > best_len:
                    best, best_len = part, len(n)
    return best


__all__ = ["GROUPS", "MODELS", "ORDER", "find_part", "model_for"]
