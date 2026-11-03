"""Building blocks for the 3D explorer's models (explore_models.py, explore_vehicles.py): parts, wheels,
sloped glass, and a whole car's shared parts (body, doors, lights, seats, wheels, brakes, springs).
The shapes are described in explore_models.py."""

from __future__ import annotations

import math

X, Z = [0, 0, math.pi / 2], [math.pi / 2, 0, 0]      # turn a cylinder to lie along x, or along z
FLAT = [math.pi / 2, 0, 0]                            # a ring (torus) lying flat

GROUPS = {
    "body": "Body",
    "powertrain": "Engine and drive",
    "running": "Wheels, brakes and suspension",
    "chassis": "Frame",
    "interior": "Inside",
    "electrical": "Electrics and lights",
}


def part(pid, name, group, desc, out, *shapes, colour=None):
    p = {"id": pid, "name": name, "group": group, "desc": desc, "out": out, "shapes": list(shapes)}
    if colour:
        p["colour"] = colour                         # its own colour, where one group would make all alike
    return p


def wheel(x, z, r=0.62, tube=0.2, y=None):
    y = r + tube if y is None else y
    return [{"t": "torus", "s": [r, tube], "p": [x, y, z]},
            {"t": "cyl", "s": [r * 0.82, r * 0.82, tube * 1.6], "p": [x, y, z], "r": Z}]


def pane(x0, y0, x1, y1, width, z=0.0, thick=0.06):
    """A flat panel (glass, a cover) from (x0, y0) to (x1, y1) seen from the side."""
    return {"t": "box", "s": [math.hypot(x1 - x0, y1 - y0), thick, width], "p": [(x0 + x1) / 2, (y0 + y1) / 2, z],
            "r": [0, 0, math.atan2(y1 - y0, x1 - x0)]}


def rod(a, b, radius):
    """A straight tube from point a to point b."""
    return {"t": "tube", "pts": [list(a), list(b)], "s": [radius]}


def car(*, length, width, wheel_r, tube, xf, xr, track, body_y, body_h, roof, roof_y, rake=0.55, back=0.6,
        seats_x=-0.7, rear_seats_x=None, dash_x=1.0, chassis=True, bonnet="Bonnet (hood)",
        bonnet_desc="The hinged cover over the engine bay, opened for servicing.", drive_desc="") -> list[dict]:
    """The parts every car here shares; the model adds what drives it."""
    top = body_y + body_h / 2
    rr, rf = roof                                    # the roof's rear and front edge, along x
    gf = (roof_y - top) / math.tan(rake)             # how far the windscreen runs forward
    gr = (roof_y - top) / math.tan(back)
    gw = width - 0.7
    wy = wheel_r + tube
    front, rear = length / 2, -length / 2
    side_len = (rf + gf * 0.55) - (rr - gr * 0.55)
    parts = [
        part("body_shell", "Body shell", "body",
             "The outer skin and the cabin with its glass. It keeps out wind and rain, shapes how the air "
             "flows over the car, and protects the people inside.",
             [0, 3.6, 0],
             {"t": "box", "s": [length - 0.6, body_h, width], "p": [0, body_y, 0]},
             {"t": "box", "s": [rf - rr, 0.08, gw], "p": [(rf + rr) / 2, roof_y, 0]},
             pane(rf, roof_y, rf + gf, top, gw), pane(rr - gr, top, rr, roof_y, gw),
             {"t": "box", "s": [side_len, roof_y - top - 0.06, 0.05],
              "p": [(rf + gf * 0.55 + rr - gr * 0.55) / 2, (roof_y + top) / 2, gw / 2]},
             {"t": "box", "s": [side_len, roof_y - top - 0.06, 0.05],
              "p": [(rf + gf * 0.55 + rr - gr * 0.55) / 2, (roof_y + top) / 2, -gw / 2]}),
        part("bonnet", bonnet, "body", bonnet_desc, [2.4, 3.8, 0],
             {"t": "box", "s": [max(0.6, front - 0.3 - (rf + gf)), 0.08, width - 0.3],
              "p": [(rf + gf + front - 0.3) / 2, top + 0.05, 0]}),
        part("doors", "Doors", "body",
             "Hinged at the front; inside each are the window glass, its motor and a side-impact beam.",
             [0, 0.8, 0],
             {"t": "box", "s": [min(2.3, rf - rr + 0.6), body_h + 0.35, 0.1],
              "p": [(rf + rr) / 2 + 0.3, body_y + 0.15, width / 2 + 0.06], "out": [0, 0.8, 2.8]},
             {"t": "box", "s": [min(2.3, rf - rr + 0.6), body_h + 0.35, 0.1],
              "p": [(rf + rr) / 2 + 0.3, body_y + 0.15, -width / 2 - 0.06], "out": [0, 0.8, -2.8]}),
        part("bumpers", "Bumpers", "body",
             "Absorb low-speed knocks; the front one guides air to the radiators through its grille.",
             [0, 0.2, 0],
             {"t": "box", "s": [0.3, 0.5, width + 0.1], "p": [front - 0.15, body_y - 0.3, 0], "out": [3.0, 0.2, 0]},
             {"t": "box", "s": [0.3, 0.5, width + 0.1], "p": [rear + 0.15, body_y - 0.3, 0], "out": [-3.0, 0.2, 0]}),
        part("lights", "Headlights and tail lights", "electrical",
             "LED headlights light the road without dazzling others; the red tail lights brighten when you "
             "brake.",
             [0, 1.4, 0],
             *[{"t": "box", "s": [0.25, 0.2, 0.7], "p": [x * (front - 0.25), body_y + 0.15, z * (width / 2 - 0.45)],
                "out": [x * 3.4, 1.4, z * 1.0]} for x in (1, -1) for z in (1, -1)]),
        part("seats", "Seats", "interior",
             "Hold you in place and carry the seat-belt anchors; the front ones slide and recline.",
             [-0.4, 2.0, 0],
             *[s for z in (1, -1) for s in (
                 {"t": "box", "s": [0.9, 0.22, 0.8], "p": [seats_x, body_y - 0.35, 0.75 * z], "out": [-0.4, 2.0, 0.7 * z]},
                 {"t": "box", "s": [0.2, 0.95, 0.8], "p": [seats_x - 0.5, body_y + 0.15, 0.75 * z], "r": [0, 0, 0.2],
                  "out": [-0.4, 2.0, 0.7 * z]})]),
        part("steering", "Steering wheel and column", "interior",
             "Turning the wheel turns the column, which moves a rack that swings the front wheels.",
             [1.0, 2.6, 0.8],
             {"t": "torus", "s": [0.32, 0.05], "p": [dash_x - 0.45, top + 0.05, 0.75], "r": [0, math.pi / 2, 0]},
             {"t": "cyl", "s": [0.05, 0.05, 1.1], "p": [dash_x + 0.05, top - 0.2, 0.75], "r": [0, 0, 1.1]}),
        part("dashboard", "Dashboard", "interior",
             "The instruments, the screen and the air vents, with the heater and air-conditioning behind.",
             [1.2, 2.2, 0], {"t": "box", "s": [0.45, 0.4, width - 0.6], "p": [dash_x, top - 0.1, 0]}),
    ]
    if rear_seats_x is not None:
        parts.append(part("rear_seats", "Rear seats", "interior",
                          "A bench for passengers; it folds down to make the boot bigger.", [-1.2, 2.2, 0],
                          {"t": "box", "s": [0.8, 0.22, width - 0.9], "p": [rear_seats_x, body_y - 0.3, 0]},
                          {"t": "box", "s": [0.2, 0.9, width - 0.9], "p": [rear_seats_x - 0.45, body_y + 0.2, 0],
                           "r": [0, 0, 0.2]}))
    if chassis:
        parts.append(part("chassis", "Chassis frame", "chassis",
                          "The strong frame everything is bolted to; it carries the loads from the wheels and "
                          "keeps the car stiff so the suspension can do its work.",
                          [0, -2.8, 0],
                          {"t": "box", "s": [length - 1.0, 0.14, 0.16], "p": [0, body_y - 0.85, 0.9]},
                          {"t": "box", "s": [length - 1.0, 0.14, 0.16], "p": [0, body_y - 0.85, -0.9]},
                          *[{"t": "box", "s": [0.14, 0.14, 1.8], "p": [x, body_y - 0.85, 0]} for x in (xf, 0, xr)]))
    for x, end in ((xf, "front"), (xr, "rear")):
        for z, side in ((1, "left"), (-1, "right")):
            parts.append(part(f"wheel_{end}_{side}", f"{end.capitalize()} {side} wheel", "running",
                              "The rim and the tyre: the tyre's small contact patch is all that holds the car "
                              "to the road, for grip, braking and steering." + drive_desc,
                              [0.6 if x > 0 else -0.6, 0, 2.6 * z], *wheel(x, track * z, wheel_r, tube)))
    parts.append(part("brakes", "Disc brakes", "running",
                      "A disc spins with each wheel; pressing the pedal squeezes pads onto it with the caliper, "
                      "turning the car's motion into heat.",
                      [0, 0, 0],
                      *[{"t": "cyl", "s": [wheel_r * 0.68, wheel_r * 0.68, 0.06], "p": [x, wy, (track - 0.33) * z],
                         "r": Z, "out": [0.4 * math.copysign(1, x), 0, 1.9 * z]} for x in (xf, xr) for z in (1, -1)],
                      *[{"t": "box", "s": [0.25, 0.3, 0.16], "p": [x + 0.3, wy + 0.2, (track - 0.33) * z],
                         "out": [0.4 * math.copysign(1, x), 0, 1.9 * z]} for x in (xf, xr) for z in (1, -1)]))
    parts.append(part("suspension", "Suspension springs and dampers", "running",
                      "Springs let each wheel follow bumps; dampers stop the bouncing, so the tyres stay pressed "
                      "to the road and the ride stays calm.",
                      [0, 1.2, 0],
                      *[{"t": "spring", "s": [0.16, 0.7, 6, 0.035], "p": [x, wy + 0.2, (track - 0.6) * z],
                         "out": [0.3 * math.copysign(1, x), 1.2, 1.3 * z]} for x in (xf, xr) for z in (1, -1)]))
    return parts


__all__ = ["FLAT", "GROUPS", "X", "Z", "car", "pane", "part", "rod", "wheel"]
