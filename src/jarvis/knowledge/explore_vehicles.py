"""More models for the 3D explorer: an electric car, a hybrid, a 4x4 pickup, a mid-engine supercar, a
three-wheeler, a scooter and a bicycle. Types, not brands: each is our own simple model of how that kind
of vehicle is built inside, and "like" names real ones laid out the same way (a fact, not a copy).
"""

from __future__ import annotations

import math

from .explore_shapes import FLAT, X, Z, car, pane, part, rod, wheel

PLAIN_WHEELS = " It turns freely: the power goes to the other axle."


def electric_car() -> dict:
    wr, tube, xf, xr, track = 0.62, 0.2, 2.9, -2.9, 1.75
    wy = wr + tube
    parts = car(length=9.2, width=3.7, wheel_r=wr, tube=tube, xf=xf, xr=xr, track=track, body_y=1.4, body_h=0.75,
                roof=(-2.0, 0.4), roof_y=2.55, rake=0.45, back=0.5, seats_x=-0.4, rear_seats_x=-2.0, dash_x=1.2,
                chassis=False, bonnet="Front boot lid",
                bonnet_desc="With no engine at the front, this opens onto a front boot (the 'frunk').")
    parts += [
        part("battery_pack", "Battery pack", "electrical",
             "Thousands of lithium-ion cells in modules, in a flat case that forms the floor: about 400 volts. "
             "Low and in the middle, its weight makes the car steady in corners.",
             [0, -2.6, 0],
             {"t": "box", "s": [5.0, 0.32, 2.9], "p": [-0.1, 0.62, 0]},
             *[{"t": "box", "s": [1.1, 0.22, 2.6], "p": [x, 0.62, 0]} for x in (-2.0, -0.75, 0.5, 1.75)]),
        part("rear_motor", "Rear drive unit (motor)", "powertrain",
             "An electric motor, a single-speed reduction gear and the differential in one unit at the rear "
             "axle. It gives full pulling power from standstill, and works as a generator when you slow down.",
             [-1.6, -1.0, 0],
             {"t": "cyl", "s": [0.34, 0.34, 0.8], "p": [xr - 0.45, wy, 0.25], "r": Z},
             {"t": "box", "s": [0.55, 0.55, 0.5], "p": [xr - 0.45, wy, -0.35]}),
        part("front_motor", "Front motor (all-wheel drive)", "powertrain",
             "A second, smaller motor on all-wheel-drive versions: each axle has its own motor, so the "
             "car shares the grip between front and rear in milliseconds.",
             [1.6, -1.0, 0], {"t": "cyl", "s": [0.28, 0.28, 0.7], "p": [xf + 0.4, wy, 0], "r": Z}),
        part("inverter", "Inverter", "electrical",
             "Turns the battery's direct current into the alternating current that spins the motors, and "
             "back again when they charge the battery while braking.",
             [-1.4, 1.4, 0], {"t": "box", "s": [0.55, 0.22, 0.8], "p": [xr - 0.45, wy + 0.5, 0]}),
        part("half_shafts", "Half-shafts", "powertrain",
             "Short shafts from the drive units to the wheels, with joints that let the wheels steer and "
             "move up and down.",
             [0, -0.4, 0],
             *[{"t": "cyl", "s": [0.07, 0.07, track - 0.5], "p": [x, wy, (track - 0.5) / 2 * z + 0.05 * z], "r": Z,
                "out": [0, -0.4, 1.2 * z]} for x in (xf + 0.4, xr - 0.45) for z in (1, -1)]),
        part("charge_port", "Charge port", "electrical",
             "Where the cable plugs in: alternating current from a home charger, or direct current from a "
             "fast charger straight to the battery.",
             [-0.6, 0.8, 2.4], {"t": "box", "s": [0.25, 0.25, 0.1], "p": [-3.9, 1.65, 1.8]}),
        part("charger", "On-board charger and DC-DC converter", "electrical",
             "The charger turns mains electricity into direct current for the battery; the converter makes "
             "12 volts for the lights, screens and pumps.",
             [-1.2, 1.6, -1.2], {"t": "box", "s": [0.6, 0.3, 0.6], "p": [-3.6, 1.3, -0.6]}),
        part("thermal", "Heat pump and coolant loop", "powertrain",
             "Keeps the battery and the motors at the right temperature, and warms the cabin using little "
             "energy, which matters for the range in the cold.",
             [2.4, 1.8, 0],
             {"t": "box", "s": [0.7, 0.4, 1.4], "p": [xf + 1.0, 1.2, 0]},
             rod([xf + 0.7, 1.0, 0.6], [-2.4, 0.85, 0.6], 0.04)),
        part("aux_battery", "12-volt battery", "electrical",
             "A small battery that wakes the car's computers, which then switch on the big battery.",
             [1.6, 2.2, -1.4], {"t": "box", "s": [0.4, 0.3, 0.3], "p": [xf + 0.6, 1.3, -1.2]}),
        part("frunk", "Front boot (frunk)", "interior",
             "Luggage space where an engine would be.",
             [1.4, 2.6, 0], {"t": "box", "s": [1.2, 0.4, 1.8], "p": [xf + 0.2, 1.45, 0]}),
    ]
    for p in parts:
        if p["id"] == "brakes":
            p["desc"] = ("Disc brakes, used less than in a petrol car: lifting off the accelerator makes the "
                         "motors brake the car and charge the battery (regenerative braking).")
    return {"id": "electric_car", "title": "Electric car", "size": "battery in the floor, a motor on each axle",
            "like": "Tesla Model 3, BYD Seal, Nissan Leaf", "scale": 1.0, "parts": parts}


def hybrid_car() -> dict:
    wr, tube, xf, xr, track = 0.6, 0.18, 2.8, -2.8, 1.7
    wy = wr + tube
    parts = car(length=8.8, width=3.6, wheel_r=wr, tube=tube, xf=xf, xr=xr, track=track, body_y=1.35, body_h=0.75,
                roof=(-1.9, 0.5), roof_y=2.55, rake=0.42, back=0.45, seats_x=-0.3, rear_seats_x=-1.9, dash_x=1.25,
                chassis=False)
    parts += [
        part("engine", "Petrol engine", "powertrain",
             "A four-cylinder engine tuned for economy rather than power (the Atkinson cycle). It switches off "
             "when it isn't needed, at a standstill or cruising gently.",
             [1.4, 2.2, -0.8],
             {"t": "box", "s": [0.9, 0.7, 1.3], "p": [xf + 0.35, 1.05, -0.25]},
             {"t": "box", "s": [0.8, 0.3, 1.2], "p": [xf + 0.35, 1.55, -0.25]}),
        part("power_split", "Power split device", "powertrain",
             "A planetary gear set: the engine, the generator and the wheels each turn one part of it, so the "
             "engine's power is shared between driving the wheels and making electricity, with no gear "
             "changes (an electronic CVT).",
             [1.2, 0, 1.2], {"t": "cyl", "s": [0.3, 0.3, 0.25], "p": [xf + 0.35, 0.95, 0.6], "r": Z}),
        part("mg1", "Motor-generator 1", "powertrain",
             "Mostly a generator: driven by the engine through the power split, it charges the battery and "
             "starts the engine.",
             [1.2, 0, 2.0], {"t": "cyl", "s": [0.36, 0.36, 0.3], "p": [xf + 0.35, 0.95, 0.88], "r": Z}),
        part("mg2", "Motor-generator 2", "powertrain",
             "The drive motor: it moves the car alone at low speeds, helps the engine when you accelerate, "
             "and charges the battery when you brake.",
             [1.2, 0, 2.8], {"t": "cyl", "s": [0.4, 0.4, 0.35], "p": [xf + 0.35, 0.95, 1.2], "r": Z}),
        part("pcu", "Power control unit", "electrical",
             "The inverter and converter: they turn the battery's direct current into alternating current "
             "for the motors, and the other way when charging.",
             [1.4, 2.6, 1.0], {"t": "box", "s": [0.7, 0.3, 0.9], "p": [xf + 0.35, 1.65, 0.6]}),
        part("hybrid_battery", "Hybrid battery", "electrical",
             "A small battery (about 1 kWh) behind or under the rear seat; it charges itself from the engine "
             "and from braking, never from a socket.",
             [-1.4, 1.6, 0], {"t": "box", "s": [0.6, 0.35, 1.6], "p": [xr + 0.55, 1.1, 0]}),
        part("fuel_tank", "Fuel tank", "powertrain",
             "Holds the petrol under the rear seat, in front of the rear axle.",
             [-0.6, -1.2, 0], {"t": "box", "s": [0.8, 0.3, 1.4], "p": [xr + 1.6, 0.75, 0]}),
        part("half_shafts", "Half-shafts", "powertrain",
             "Carry the drive from the transaxle to the front wheels, with joints that let them steer.",
             [0.6, -0.4, 0],
             *[{"t": "cyl", "s": [0.06, 0.06, track - 0.6], "p": [xf, wy, (track - 0.6) / 2 * z + 0.1 * z], "r": Z,
                "out": [0.6, -0.4, 1.2 * z]} for z in (1, -1)]),
        part("exhaust", "Exhaust", "powertrain",
             "Carries the engine's gases to the back; the catalytic converter cleans them on the way.",
             [0, -2.0, -1.6],
             rod([xf + 0.1, 0.8, -0.6], [1.5, 0.45, -0.6], 0.07), rod([1.5, 0.45, -0.6], [-4.1, 0.5, -0.6], 0.07),
             {"t": "box", "s": [0.9, 0.3, 0.5], "p": [-3.6, 0.5, -0.6]}),
        part("aux_battery", "12-volt battery", "electrical",
             "Starts the computers that switch the hybrid system on, and runs the lights and radio.",
             [-1.2, 2.0, -1.4], {"t": "box", "s": [0.4, 0.3, 0.3], "p": [xr - 0.3, 1.3, -1.1]}),
    ]
    for p in parts:
        if p["id"] == "brakes":
            p["desc"] = ("Disc brakes that share the work with motor-generator 2: gentle braking charges the "
                         "battery, and the pads only take over for harder stops.")
        elif p["id"].startswith("wheel_rear"):
            p["desc"] += PLAIN_WHEELS
    return {"id": "hybrid_car", "title": "Hybrid car", "size": "petrol engine + two motor-generators, front-wheel drive",
            "like": "Toyota Prius, Aqua, Corolla Hybrid", "scale": 1.0, "parts": parts}


def pickup_4x4() -> dict:
    wr, tube, xf, xr = 0.72, 0.26, 3.4, -3.0
    wy, track = wr + tube, 1.8
    top = 2.15
    parts = [
        part("cab", "Cab", "body",
             "The cabin for the driver and passengers, bolted onto the frame on rubber mounts that keep the "
             "frame's shaking away from you.",
             [0.6, 3.6, 0],
             {"t": "box", "s": [5.6, 0.8, 3.8], "p": [2.2, 1.75, 0]},
             {"t": "box", "s": [2.2, 0.08, 3.1], "p": [-0.1, 3.15, 0]},
             pane(1.0, 3.15, 2.3, top, 3.1), {"t": "box", "s": [0.08, 1.0, 3.1], "p": [-1.2, 2.65, 0]}),
        part("bonnet", "Bonnet (hood)", "body", "The cover over the engine bay, opened to check the oil and coolant.", [2.4, 3.8, 0],
             {"t": "box", "s": [2.6, 0.08, 3.5], "p": [3.7, top + 0.05, 0]}),
        part("bed", "Load bed", "body",
             "The open tray for cargo, with a tailgate at the back; it's a separate piece from the cab.",
             [-2.2, 1.8, 0],
             {"t": "box", "s": [3.8, 0.08, 3.6], "p": [-3.25, 1.45, 0]},
             {"t": "box", "s": [3.8, 0.8, 0.08], "p": [-3.25, 1.85, 1.78]},
             {"t": "box", "s": [3.8, 0.8, 0.08], "p": [-3.25, 1.85, -1.78]},
             {"t": "box", "s": [0.08, 0.8, 3.6], "p": [-5.15, 1.85, 0]}),
        part("doors", "Doors", "body", "Front doors, with the window glass and a side-impact beam inside.",
             [0, 0.8, 0],
             {"t": "box", "s": [1.6, 1.2, 0.1], "p": [0.6, 2.0, 1.95], "out": [0, 0.8, 2.8]},
             {"t": "box", "s": [1.6, 1.2, 0.1], "p": [0.6, 2.0, -1.95], "out": [0, 0.8, -2.8]}),
        part("ladder_frame", "Ladder frame", "chassis",
             "Two strong steel rails joined by cross-members, like a ladder: tough enough to carry heavy loads, "
             "tow and twist over rough ground. The body sits on top.",
             [0, -3.2, 0],
             {"t": "box", "s": [9.6, 0.26, 0.2], "p": [-0.6, 1.2, 0.75]},
             {"t": "box", "s": [9.6, 0.26, 0.2], "p": [-0.6, 1.2, -0.75]},
             *[{"t": "box", "s": [0.18, 0.18, 1.5], "p": [x, 1.2, 0]} for x in (4.0, 1.6, -0.8, -3.0, -5.0)]),
        part("engine", "Diesel engine", "powertrain",
             "A four-cylinder turbo diesel: strong pulling power at low speeds (torque), good for towing and "
             "climbing.",
             [0.8, 2.6, 0],
             {"t": "box", "s": [1.2, 0.8, 0.8], "p": [3.2, 1.75, 0]}, {"t": "box", "s": [1.1, 0.3, 0.7], "p": [3.2, 2.3, 0]}),
        part("turbo", "Turbocharger and intercooler", "powertrain",
             "The exhaust spins a turbine that drives a compressor, pushing more air into the engine; the "
             "intercooler cools that air so more of it fits.",
             [1.6, 1.8, 1.6],
             {"t": "sphere", "s": [0.22], "p": [2.9, 1.9, 0.62]},
             {"t": "box", "s": [0.12, 0.5, 2.2], "p": [4.6, 1.65, 0]}),
        part("gearbox", "Gearbox", "powertrain", "Six gears behind the engine, chosen with the gear lever and the clutch.", [0.4, -1.0, 0],
             {"t": "cyl", "s": [0.32, 0.26, 1.0], "p": [2.1, 1.5, 0], "r": X}),
        part("transfer_case", "Transfer case", "powertrain",
             "Splits the drive between the rear and the front axle when you choose four-wheel drive, and adds "
             "a 'low range' of extra-low gears for steep, slippery ground.",
             [0, -1.6, 1.4], {"t": "box", "s": [0.5, 0.5, 0.6], "p": [1.35, 1.3, 0.1]}),
        part("driveshafts", "Front and rear driveshafts", "powertrain",
             "Spinning shafts from the transfer case to the front and rear differentials.",
             [0, -2.2, 0],
             rod([1.35, 1.1, 0.2], [xf, wy, 0.2], 0.07), rod([1.35, 1.1, 0], [xr, wy, 0], 0.08)),
        part("front_diff", "Front differential", "powertrain",
             "Lets the front wheels turn at different speeds in a corner; in four-wheel drive it passes the "
             "power to them.",
             [1.6, -1.6, 0],
             {"t": "sphere", "s": [0.32], "p": [xf, wy, 0.2]},
             {"t": "cyl", "s": [0.06, 0.06, 2.8], "p": [xf, wy, 0], "r": Z}),
        part("rear_axle", "Rear differential and solid axle", "powertrain",
             "One rigid tube from wheel to wheel with the differential in the middle: strong and simple, and "
             "it keeps the wheels pressed down over rocks.",
             [-1.6, -1.6, 0],
             {"t": "sphere", "s": [0.38], "p": [xr, wy, 0]},
             {"t": "cyl", "s": [0.1, 0.1, 3.3], "p": [xr, wy, 0], "r": Z}),
        part("springs", "Leaf springs and coil springs", "running",
             "Stacked steel leaves at the rear carry heavy loads; coil springs at the front give a smoother "
             "ride; dampers calm both.",
             [0, 1.0, 0],
             *[{"t": "box", "s": [1.8, 0.08, 0.2], "p": [xr, 1.2, 0.95 * z], "r": [0, 0, 0.0], "out": [-0.6, 0.6, 1.4 * z]}
               for z in (1, -1)],
             *[{"t": "spring", "s": [0.17, 0.7, 6, 0.04], "p": [xf, 1.55, 0.95 * z], "out": [0.6, 1.2, 1.4 * z]}
               for z in (1, -1)]),
        part("fuel_tank", "Fuel tank", "powertrain", "Holds the diesel, outside the frame rail under the bed.",
             [-0.8, -0.4, -1.8], {"t": "box", "s": [1.1, 0.45, 0.5], "p": [-1.0, 1.05, -1.2]}),
        part("spare", "Spare wheel", "running", "Hangs under the back of the bed, lowered by a winch.",
             [-2.2, -1.4, 0], {"t": "torus", "s": [0.62, 0.2], "p": [-4.4, 0.95, 0], "r": FLAT}),
        part("skid_plate", "Skid plate", "chassis",
             "A steel plate that protects the engine and gearbox from rocks underneath.",
             [1.0, -2.6, 0], {"t": "box", "s": [1.8, 0.05, 1.4], "p": [3.0, 0.9, 0]}),
        part("seats", "Seats", "interior", "Front seats and, behind them, a rear bench.", [-0.2, 2.2, 0],
             {"t": "box", "s": [0.9, 0.22, 2.6], "p": [0.8, 1.95, 0]}, {"t": "box", "s": [0.2, 0.9, 2.6], "p": [0.3, 2.4, 0]}),
        part("lights", "Headlights and tail lights", "electrical",
             "Headlights high up for rough roads; tail lights on the back of the bed.", [0, 1.4, 0],
             *[{"t": "box", "s": [0.2, 0.25, 0.6], "p": [5.0, 1.95, 1.3 * z], "out": [3.0, 1.4, z]} for z in (1, -1)],
             *[{"t": "box", "s": [0.15, 0.5, 0.25], "p": [-5.2, 1.85, 1.65 * z], "out": [-3.0, 1.4, z]} for z in (1, -1)]),
    ]
    for x, end in ((xf, "front"), (xr, "rear")):
        for z, side in ((1, "left"), (-1, "right")):
            parts.append(part(f"wheel_{end}_{side}", f"{end.capitalize()} {side} wheel", "running",
                              "A big all-terrain tyre with deep tread for grip on mud, sand and gravel.",
                              [0.6 if x > 0 else -0.6, 0, 2.6 * z], *wheel(x, track * z, wr, tube)))
    parts.append(part("brakes", "Brakes", "running",
                      "Discs at the front, which do most of the stopping, and drums at the rear.", [0, 0, 0],
                      *[{"t": "cyl", "s": [0.45, 0.45, 0.08 if x > 0 else 0.3], "p": [x, wy, (track - 0.4) * z], "r": Z,
                         "out": [0.5 if x > 0 else -0.5, 0, 1.9 * z]} for x in (xf, xr) for z in (1, -1)]))
    return {"id": "pickup_4x4", "title": "4x4 pickup", "size": "ladder frame, turbo diesel, part-time four-wheel drive",
            "like": "Toyota Hilux, Mitsubishi L200, Ford Ranger", "scale": 0.9, "parts": parts}


def supercar() -> dict:
    wr, tube, xf, xr, track = 0.66, 0.22, 2.8, -2.9, 1.8
    wy = wr + tube
    parts = car(length=9.0, width=3.9, wheel_r=wr, tube=tube, xf=xf, xr=xr, track=track, body_y=1.15, body_h=0.6,
                roof=(-0.9, 0.3), roof_y=2.0, rake=0.36, back=0.22, seats_x=0.0, dash_x=1.4, chassis=False,
                bonnet="Front boot lid",
                bonnet_desc="Covers a small luggage space and the front radiators: the engine is behind you.")
    parts += [
        part("tub", "Carbon-fibre tub", "chassis",
             "The cabin is one stiff, light shell of carbon fibre (a monocoque); the engine and the front "
             "suspension bolt onto it.",
             [0, -2.4, 0],
             {"t": "box", "s": [2.8, 0.1, 2.6], "p": [0.2, 0.5, 0]},
             {"t": "box", "s": [2.8, 0.55, 0.1], "p": [0.2, 0.8, 1.3]},
             {"t": "box", "s": [2.8, 0.55, 0.1], "p": [0.2, 0.8, -1.3]},
             {"t": "box", "s": [0.1, 0.6, 2.6], "p": [-1.2, 0.85, 0]}),
        part("engine", "V10 engine (behind the seats)", "powertrain",
             "Ten cylinders in a V, mounted behind the driver and ahead of the rear axle (mid-engine): the "
             "heaviest part in the middle makes the car turn quickly and evenly.",
             [-0.8, 2.6, 0],
             {"t": "box", "s": [1.8, 0.55, 0.8], "p": [-2.0, 0.95, 0]},
             {"t": "box", "s": [1.7, 0.4, 0.42], "p": [-2.0, 1.35, 0.38], "r": [-0.55, 0, 0]},
             {"t": "box", "s": [1.7, 0.4, 0.42], "p": [-2.0, 1.35, -0.38], "r": [0.55, 0, 0]}),
        part("gearbox", "Dual-clutch gearbox", "powertrain",
             "Seven gears with two clutches: while one gear drives, the next is already chosen, so changes "
             "take a few thousandths of a second. The rear differential is built in (a transaxle).",
             [-2.0, -0.8, 0], {"t": "box", "s": [0.9, 0.55, 0.8], "p": [xr - 0.45, wy, 0]}),
        part("front_drive", "Front drive (all-wheel drive)", "powertrain",
             "A shaft and a small differential that send some power to the front wheels for grip out of corners.",
             [1.4, -1.6, 0],
             rod([-1.1, 0.7, 0], [xf, wy, 0], 0.06), {"t": "sphere", "s": [0.25], "p": [xf, wy, 0]}),
        part("radiators", "Side radiators", "powertrain",
             "Air from the big side intakes passes through radiators just ahead of the rear wheels, cooling "
             "the engine.",
             [0, 0.6, 0],
             *[{"t": "box", "s": [0.9, 0.55, 0.12], "p": [-1.4, 1.05, 1.6 * z], "r": [0, 0.5 * z, 0], "out": [0, 0.6, 1.8 * z]}
               for z in (1, -1)]),
        part("fuel_tank", "Fuel tank", "powertrain",
             "Between the seats and the engine, safely inside the tub's protection.",
             [-0.4, 1.6, 0], {"t": "box", "s": [0.4, 0.5, 1.6], "p": [-1.0, 1.0, 0]}),
        part("rear_wing", "Rear wing", "body",
             "Works like an upside-down aeroplane wing: at speed it pushes the rear tyres onto the road "
             "(downforce) for more grip.",
             [-1.8, 1.6, 0],
             {"t": "box", "s": [0.5, 0.06, 3.2], "p": [-4.0, 2.05, 0]},
             *[{"t": "box", "s": [0.08, 0.5, 0.06], "p": [-3.95, 1.8, 0.8 * z]} for z in (1, -1)]),
        part("diffuser", "Rear diffuser", "body",
             "Shaped channels under the back that speed up the air under the car, sucking it down onto the road.",
             [-1.8, -0.8, 0], pane(-4.4, 0.6, -3.6, 0.42, 3.0)),
        part("splitter", "Front splitter", "body",
             "A blade under the nose that splits the air: high pressure above, low below, for front grip.",
             [1.8, -0.6, 0], {"t": "box", "s": [0.6, 0.05, 3.5], "p": [4.4, 0.55, 0]}),
        part("exhaust", "Exhaust", "powertrain",
             "Short pipes straight from the engine to the back, tuned for the sound as much as the flow.",
             [-1.2, -0.4, 0],
             *[rod([-1.4, 0.95, 0.3 * z], [-4.45, 1.0, 0.3 * z], 0.08) for z in (1, -1)]),
    ]
    for p in parts:
        if p["id"] == "brakes":
            p["desc"] = ("Carbon-ceramic discs: light, and they keep working at the very high temperatures of "
                         "repeated hard stops from high speed.")
    return {"id": "supercar", "title": "Mid-engine supercar",
            "size": "V10 behind the seats, all-wheel drive, carbon-fibre tub",
            "like": "Lamborghini Huracan, Ferrari 296, McLaren 750S", "scale": 1.0, "parts": parts}


def three_wheeler() -> dict:
    fr, ft, rr, rt = 0.42, 0.14, 0.42, 0.14
    fy, xr, zt = fr + ft, -1.5, 1.15
    parts = [
        part("front_wheel", "Front wheel", "running", "The single front wheel steers, like a scooter's.",
             [1.6, 0, 0], *wheel(2.3, 0, fr, ft)),
        part("rear_wheels", "Rear wheels", "running", "Two driven wheels on the rear axle.", [-1.2, 0, 0],
             *[s for z in (1, -1) for s in wheel(xr, zt * z, rr, rt)]),
        part("front_panel", "Front panel and windscreen", "body",
             "The steel front that shields the driver, with the windscreen and its wiper above.",
             [1.6, 0.6, 0],
             {"t": "box", "s": [0.15, 1.5, 2.0], "p": [2.05, 1.65, 0]},
             pane(1.95, 2.4, 1.75, 3.45, 1.9, thick=0.05)),
        part("canopy", "Canopy and roof", "body",
             "A light frame with a fabric or metal roof and open sides: shade, rain cover and cheap to "
             "repair.",
             [0, 2.6, 0],
             {"t": "box", "s": [3.8, 0.06, 2.5], "p": [0.0, 3.55, 0]},
             *[rod([x, 1.0, 1.15 * z], [x, 3.55, 1.15 * z], 0.04) for x in (1.75, -1.75) for z in (1, -1)]),
        part("floor", "Floor and chassis", "chassis",
             "A steel floor on a central tube frame that joins the steering head to the rear axle.",
             [0, -2.0, 0],
             {"t": "box", "s": [4.0, 0.08, 2.4], "p": [0.1, 0.95, 0]},
             rod([2.0, 1.4, 0], [-1.5, 0.85, 0], 0.08)),
        part("driver_seat", "Driver's seat", "interior", "The driver sits alone in the middle, at the front.",
             [0.8, 1.6, 0],
             {"t": "box", "s": [0.6, 0.15, 0.9], "p": [1.0, 1.5, 0]}, {"t": "box", "s": [0.12, 0.6, 0.9], "p": [0.7, 1.85, 0]}),
        part("bench", "Passenger bench", "interior", "A bench for two or three passengers, over the engine.",
             [-1.0, 1.6, 0],
             {"t": "box", "s": [0.8, 0.2, 2.2], "p": [-0.7, 1.45, 0]}, {"t": "box", "s": [0.15, 0.8, 2.2], "p": [-1.15, 1.9, 0]}),
        part("engine", "Engine (single cylinder)", "powertrain",
             "A small single-cylinder engine of about 200 cc under the rear seat, running on petrol (some on "
             "LPG or CNG); air or water cooled. Small, cheap and easy to repair.",
             [-1.0, -0.6, 1.8],
             {"t": "box", "s": [0.8, 0.55, 0.6], "p": [-1.4, 1.05, 0.35]},
             {"t": "cyl", "s": [0.2, 0.2, 0.55], "p": [-1.15, 1.35, 0.35], "r": [0, 0, -0.6]}),
        part("gearbox", "Gearbox (handlebar shift)", "powertrain",
             "Four gears, changed by twisting the left handlebar grip with the clutch lever pulled.",
             [-0.6, -0.8, -1.4], {"t": "cyl", "s": [0.25, 0.25, 0.5], "p": [-1.35, 0.85, -0.25], "r": Z}),
        part("rear_axle", "Rear axle and differential", "powertrain",
             "Takes the drive from the gearbox to both rear wheels, letting them turn at different speeds "
             "in a corner.",
             [-1.0, -1.4, 0],
             {"t": "cyl", "s": [0.06, 0.06, 2.1], "p": [xr, fy, 0], "r": Z}, {"t": "sphere", "s": [0.2], "p": [xr, fy, 0]}),
        part("steering", "Handlebar and front fork", "running",
             "The driver steers with a handlebar; the fork holds the front wheel, with a spring and damper "
             "for the front suspension.",
             [1.4, 1.2, 0],
             rod([2.3, fy, 0.12], [2.0, 2.0, 0.12], 0.05), rod([2.3, fy, -0.12], [2.0, 2.0, -0.12], 0.05),
             rod([1.75, 2.35, 0.6], [1.85, 2.3, 0], 0.035), rod([1.85, 2.3, 0], [1.75, 2.35, -0.6], 0.035),
             {"t": "spring", "s": [0.1, 0.45, 6, 0.025], "p": [2.18, 1.25, 0.25], "r": [0, 0, 0.3]}),
        part("headlight", "Headlight", "electrical", "A single headlight in the front panel.", [1.6, 0.8, 0],
             {"t": "cyl", "s": [0.16, 0.13, 0.15], "p": [2.15, 2.0, 0], "r": X}),
        part("rear_suspension", "Rear suspension", "running",
             "Swinging arms with springs and dampers carry the rear wheels and the passengers' weight.",
             [-0.6, 1.2, 0],
             *[{"t": "spring", "s": [0.1, 0.5, 6, 0.025], "p": [xr + 0.2, 1.05, 0.85 * z], "out": [-0.6, 1.2, 0.8 * z]}
               for z in (1, -1)]),
        part("brakes", "Drum brakes", "running",
             "Drums on all three wheels, worked by the foot pedal: shoes press outward against the inside of "
             "each drum.",
             [0, 0, 0],
             {"t": "cyl", "s": [0.24, 0.24, 0.12], "p": [2.3, fy, -0.15], "r": Z, "out": [1.0, 0, -1.0]},
             *[{"t": "cyl", "s": [0.24, 0.24, 0.12], "p": [xr, fy, (zt - 0.25) * z], "r": Z, "out": [-0.6, 0, 1.3 * z]}
               for z in (1, -1)]),
        part("fuel_tank", "Fuel tank", "powertrain", "A small tank, often under or behind the driver's seat.",
             [0.4, 0.4, -1.6], {"t": "box", "s": [0.5, 0.3, 0.55], "p": [0.95, 1.2, 0]}),
        part("exhaust", "Exhaust", "powertrain", "Carries the engine's gases out at the rear, with a silencer.",
             [-1.2, -0.6, -1.6],
             rod([-1.2, 0.95, 0.2], [-1.9, 0.75, -0.6], 0.04), {"t": "cyl", "s": [0.1, 0.1, 0.6], "p": [-2.2, 0.75, -0.6], "r": X}),
        part("battery", "Battery", "electrical", "Powers the starter, the horn and the lights.", [0.4, 1.0, 1.2],
             {"t": "box", "s": [0.3, 0.2, 0.2], "p": [0.9, 1.15, 0.6]}),
    ]
    return {"id": "three_wheeler", "title": "Three-wheeler (tuk-tuk)",
            "size": "about 2.6 m long, a 200 cc engine at the back, handlebar steering",
            "like": "Bajaj RE, TVS King, Piaggio Ape", "scale": 1.4, "parts": parts}


def scooter() -> dict:
    r, t = 0.38, 0.13
    y = r + t
    parts = [
        part("front_wheel", "Front wheel", "running", "A small wheel (10 to 14 inches) that steers.", [1.4, 0, 0],
             *wheel(1.55, 0, r, t)),
        part("rear_wheel", "Rear wheel", "running", "Driven by the belt, bolted to the end of the engine unit.",
             [-1.4, 0, 0], *wheel(-1.45, 0, r, t)),
        part("apron", "Front shield (apron)", "body",
             "Protects your legs from wind and rain, and holds the indicators.", [1.2, 0.8, 0],
             pane(0.95, 0.85, 1.2, 2.05, 0.9, thick=0.12)),
        part("floorboard", "Floorboard", "body", "Flat, so you step through instead of swinging a leg over.",
             [0, -0.6, 0], {"t": "box", "s": [1.2, 0.1, 0.75], "p": [0.35, 0.78, 0]}),
        part("body_cover", "Rear body", "body", "The curved panels over the engine and storage.", [-0.4, 1.6, 0],
             {"t": "sphere", "s": [0.5], "p": [-0.8, 1.32, 0], "sc": [1.7, 0.75, 0.75]}),
        part("seat", "Seat", "interior", "Hinged: lift it to reach the storage and the fuel cap.", [-0.6, 2.4, 0],
             {"t": "box", "s": [1.3, 0.15, 0.55], "p": [-0.75, 1.95, 0]}),
        part("storage", "Under-seat storage", "interior", "Room for a helmet, where a motorcycle has its fuel tank.",
             [-0.6, 1.4, -1.2], {"t": "box", "s": [0.85, 0.4, 0.45], "p": [-0.6, 1.6, 0]}),
        part("engine", "Engine and swinging unit", "powertrain",
             "A small single-cylinder engine (about 110-160 cc) joined to the gearbox case, which also holds "
             "the rear wheel: the whole unit pivots and works as the rear swingarm.",
             [0, -1.4, 0],
             {"t": "box", "s": [0.45, 0.45, 0.45], "p": [-0.3, 0.85, -0.05]},
             {"t": "box", "s": [1.3, 0.32, 0.14], "p": [-0.9, 0.72, 0.3]}),
        part("cvt", "CVT belt and pulleys", "powertrain",
             "Instead of gears, a rubber belt runs between two pulleys that change size as you speed up, so "
             "the engine stays at its best speed: twist and go, no gear changes.",
             [-0.2, -0.4, 1.4],
             {"t": "cyl", "s": [0.15, 0.15, 0.06], "p": [-0.35, 0.78, 0.42], "r": Z},
             {"t": "cyl", "s": [0.22, 0.22, 0.06], "p": [-1.45, y, 0.42], "r": Z},
             rod([-0.35, 0.93, 0.42], [-1.45, y + 0.22, 0.42], 0.02), rod([-0.35, 0.63, 0.42], [-1.45, y - 0.22, 0.42], 0.02)),
        part("rear_shock", "Rear shock absorber", "running", "Between the frame and the engine unit.", [-0.4, 1.0, -1.0],
             {"t": "spring", "s": [0.08, 0.5, 6, 0.02], "p": [-1.3, 1.05, -0.25], "r": [0, 0, 0.4]}),
        part("fork", "Front fork", "running", "Telescopic tubes with springs inside: the front suspension.",
             [1.1, 0.6, 0],
             rod([1.55, y, 0.12], [1.2, 1.7, 0.12], 0.04), rod([1.55, y, -0.12], [1.2, 1.7, -0.12], 0.04)),
        part("handlebar", "Handlebar and headlight", "electrical",
             "The right grip is the throttle; both levers are brakes (no clutch on a scooter).", [1.0, 1.2, 0],
             rod([1.15, 2.15, 0.45], [1.2, 2.1, 0], 0.03), rod([1.2, 2.1, 0], [1.15, 2.15, -0.45], 0.03),
             {"t": "cyl", "s": [0.12, 0.1, 0.12], "p": [1.3, 1.95, 0], "r": X}),
        part("fuel_tank", "Fuel tank", "powertrain", "A small tank under the seat or the floorboard.", [0, 1.4, 1.4],
             {"t": "box", "s": [0.35, 0.22, 0.35], "p": [-0.15, 1.25, 0]}),
        part("exhaust", "Exhaust", "powertrain", "On the right side, under the rear body.", [-0.6, -0.4, -1.4],
             rod([-0.25, 0.7, -0.25], [-0.8, 0.55, -0.3], 0.04), {"t": "cyl", "s": [0.11, 0.1, 0.6], "p": [-1.2, 0.65, -0.32], "r": X}),
        part("brakes", "Brakes", "running", "A disc at the front and a drum at the rear, often linked.", [0, 0, 0],
             {"t": "cyl", "s": [0.24, 0.24, 0.03], "p": [1.55, y, 0.16], "r": Z, "out": [1.2, 0, 0.8]},
             {"t": "cyl", "s": [0.2, 0.2, 0.1], "p": [-1.45, y, -0.18], "r": Z, "out": [-1.2, 0, -0.8]}),
        part("battery", "Battery", "electrical", "Under the floorboard, for the starter and the lights.", [0.4, -0.8, 1.0],
             {"t": "box", "s": [0.22, 0.15, 0.14], "p": [0.4, 0.68, 0]}),
    ]
    return {"id": "scooter", "title": "Scooter", "size": "step-through frame, CVT, engine in the swingarm",
            "like": "Honda Dio or Activa, Yamaha Ray ZR, Vespa", "scale": 1.7, "parts": parts}


def bicycle() -> dict:
    r, y = 0.95, 1.0
    bb, seat_top, head_top, head_bot = (0.0, 0.75), (-0.35, 2.05), (1.15, 2.05), (1.25, 1.6)
    xf, xr = 1.75, -1.75

    def spokes(x):
        return [{"t": "cyl", "s": [0.008, 0.008, r - 0.05],
                 "p": [x + (r - 0.05) / 2 * math.cos(a), y + (r - 0.05) / 2 * math.sin(a), 0],
                 "r": [0, 0, a - math.pi / 2]} for a in [i * math.pi / 8 for i in range(16)]]

    parts = [
        part("frame", "Frame", "chassis",
             "Two triangles of tubes (the 'diamond'): light and stiff, so your pedalling goes into the road.",
             [0, 1.6, -1.2],
             rod((*seat_top, 0), (*head_top, 0), 0.04), rod((*bb, 0), (*head_bot, 0), 0.05),
             rod((*bb, 0), (*seat_top, 0), 0.045), rod((*head_top, 0), (*head_bot, 0), 0.055),
             *[rod((*bb, 0.08 * z), (xr, y, 0.1 * z), 0.03) for z in (1, -1)],
             *[rod((*seat_top, 0.06 * z), (xr, y, 0.1 * z), 0.025) for z in (1, -1)]),
        part("front_wheel", "Front wheel", "running",
             "A rim, a thin tyre and tensioned spokes: very light for its strength.", [1.4, 0, 0],
             {"t": "torus", "s": [r, 0.05], "p": [xf, y, 0]}, {"t": "cyl", "s": [0.05, 0.05, 0.2], "p": [xf, y, 0], "r": Z},
             *spokes(xf)),
        part("rear_wheel", "Rear wheel", "running", "Driven by the chain through the cassette.", [-1.4, 0, 0],
             {"t": "torus", "s": [r, 0.05], "p": [xr, y, 0]}, {"t": "cyl", "s": [0.05, 0.05, 0.2], "p": [xr, y, 0], "r": Z},
             *spokes(xr)),
        part("fork", "Fork", "running", "Holds the front wheel and turns with the handlebar.", [1.0, 0.5, 0],
             *[rod((*head_bot, 0.04 * z), (xf, y, 0.1 * z), 0.025) for z in (1, -1)]),
        part("cockpit", "Handlebar and stem", "interior", "Steering, with the brake levers and gear shifters.",
             [0.8, 1.2, 0],
             rod((1.15, 2.05, 0), (1.35, 2.15, 0), 0.03), rod((1.35, 2.15, 0.4), (1.35, 2.15, -0.4), 0.025)),
        part("saddle", "Saddle and seat post", "interior", "The post slides in the frame to set the height.",
             [-0.4, 1.4, 0],
             rod((*seat_top, 0), (-0.42, 2.35, 0), 0.025), {"t": "box", "s": [0.5, 0.08, 0.2], "p": [-0.45, 2.4, 0]}),
        part("crankset", "Pedals and crankset", "powertrain",
             "Your legs push the pedals round; the crank arms turn the chainring, the bike's engine room.",
             [0, -0.6, 1.0],
             {"t": "cyl", "s": [0.32, 0.32, 0.03], "p": [0, 0.75, 0.15], "r": Z},
             {"t": "box", "s": [0.06, 0.6, 0.04], "p": [0.1, 0.5, 0.2], "r": [0, 0, 0.35]},
             {"t": "box", "s": [0.06, 0.6, 0.04], "p": [-0.1, 1.0, -0.2], "r": [0, 0, 0.35]},
             {"t": "box", "s": [0.3, 0.05, 0.25], "p": [0.2, 0.22, 0.32]}, {"t": "box", "s": [0.3, 0.05, 0.25], "p": [-0.2, 1.28, -0.32]}),
        part("chain", "Chain", "powertrain", "Carries your effort from the chainring to the rear wheel.", [-0.8, -0.3, 1.0],
             rod((0, 1.07, 0.15), (xr, 1.18, 0.15), 0.015), rod((0, 0.43, 0.15), (xr, 0.82, 0.15), 0.015)),
        part("cassette", "Cassette and rear derailleur", "powertrain",
             "Sprockets of different sizes on the rear wheel; the derailleur moves the chain between them to "
             "change gear.",
             [-1.4, -0.2, 1.0],
             *[{"t": "cyl", "s": [0.18 - 0.02 * i, 0.18 - 0.02 * i, 0.015], "p": [xr, y, 0.08 + 0.025 * i], "r": Z}
               for i in range(6)],
             {"t": "box", "s": [0.12, 0.3, 0.05], "p": [xr + 0.05, 0.7, 0.18]}),
        part("brakes", "Disc brakes", "running", "Small discs on the hubs, squeezed by cable or hydraulic calipers.",
             [0, 0, 0],
             {"t": "cyl", "s": [0.16, 0.16, 0.02], "p": [xf, y, -0.12], "r": Z, "out": [1.2, 0, -0.8]},
             {"t": "cyl", "s": [0.14, 0.14, 0.02], "p": [xr, y, -0.12], "r": Z, "out": [-1.2, 0, -0.8]}),
    ]
    return {"id": "bicycle", "title": "Bicycle", "size": "diamond frame, chain drive, derailleur gears",
            "like": "a road or mountain bike", "scale": 1.6, "parts": parts}


VEHICLES = [electric_car, hybrid_car, pickup_4x4, supercar, three_wheeler, scooter, bicycle]

__all__ = ["VEHICLES"]
