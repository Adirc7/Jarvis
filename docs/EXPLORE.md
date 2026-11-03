# The 3D explorer: take it apart with your hand

Ask Jarvis to show you a car (sports, supercar, electric, hybrid, 4x4
pickup), a three-wheeler, a motorcycle, a scooter, a bicycle or an engine
taken apart, and his window shows it in 3D. Your hand, seen by the laptop's camera, takes it
apart and puts it back. Point and pinch at a part to pull it out, and Jarvis
explains it. (Adhi's idea, 3 Nov, after seeing a webcam app that does this
with vehicles and anatomy.)

## Use it

- **Open it:** "show me a car taken apart", "explode the engine", "how is a
  motorcycle built", or `/explore engine`. The camera turns on for it if it
  was off, and off again when you close it.
- **Your hand:**

  | Do this | It does |
  |---|---|
  | Open your hand slowly | Takes it apart: how open your hand is, is how far apart it is |
  | Make a fist | Puts it back together |
  | Move or twist your open hand | Turns it; raising your hand tilts it |
  | Point, then pinch (thumb tip to index tip) | Pulls that part out; Jarvis explains it |
  | Two hands apart or together | Zoom |
  | Peace sign, held half a second | The next model |

- **Voice:** "take it apart", "put it back together", "what's the gearbox?",
  "show me the radiator", "next model", "close the 3D view".
- **Mouse:** drag to turn, scroll to zoom, click a part, the Take apart / Put
  together buttons, the slider, and the model buttons.

While it's open, the explorer owns your hand: an open palm takes the model
apart instead of stopping Jarvis (one mode owns the hand at a time, D29).

## How it works

- **Models** (`src/jarvis/knowledge/explore_models.py`, `explore_vehicles.py`,
  shared parts in `explore_shapes.py`): our own, built from shapes (boxes,
  cylinders, wheels, pipes, springs), not copies of any maker's design. Each
  part has a name, a group (its colour), a description, and where it moves
  when the model comes apart. As in CAD viewers' exploded views, each part
  moves out along a clear direction so round parts stay lined up and groups
  stay together.

  | Model | Parts | Built inside like |
  |---|---|---|
  | Sports car (front engine, rear-wheel drive) | 26 | Toyota Supra, BMW M4, Ford Mustang |
  | Mid-engine supercar | 24 | Lamborghini Huracan, Ferrari 296, McLaren 750S |
  | Electric car | 25 | Tesla Model 3, BYD Seal, Nissan Leaf |
  | Hybrid car | 25 | Toyota Prius, Aqua, Corolla Hybrid |
  | 4x4 pickup | 23 | Toyota Hilux, Mitsubishi L200, Ford Ranger |
  | Three-wheeler (tuk-tuk) | 17 | Bajaj RE, TVS King, Piaggio Ape |
  | Motorcycle | 17 | a sports or touring motorcycle |
  | Scooter | 16 | Honda Dio or Activa, Yamaha Ray ZR, Vespa |
  | Bicycle | 10 | a road or mountain bike |
  | Four-cylinder engine | 14 | most small cars |

  **Types, not brands** (Adhi asked for every brand's cars, 3 Nov): a
  brand's real design and badge belong to it, and makers don't publish their
  3D parts, so there's nothing to download for "every brand". How cars differ
  inside is mostly by type, so each model is a type, and a brand points to
  the type it's built like: "take a Lamborghini apart" opens the supercar,
  "show me a Prius in 3D" the hybrid. Asked about a brand while the explorer
  is open ("how does a Tesla work?"), Jarvis puts that type on screen and the
  language model answers, with the web tools for current facts.
- **Hands** (`src/jarvis/perception/hand_controls.py`): MediaPipe's gesture
  recognizer, already running for palm-to-pause, gives each hand's 21 points
  and a gesture (Closed_Fist, Open_Palm, Pointing_Up, Victory, ...). From the
  points: how open the hand is (the fingertips' distance from the wrist, in
  hand sizes, so it works near and far), a pinch (thumb tip to index tip,
  with the index reaching out, so a fist isn't a pinch), the pointer, and
  how far the hand leans. About 15 times a second, only the points go to the
  window; no picture is kept or sent.
- **The window** (`src/jarvis/ui/explore.js`): Three.js, a see-through
  "hologram" look, labels in two columns joined to their parts, your hand
  drawn as a skeleton, and the part card.
- **Explaining** (`src/jarvis/explore_mode.py`): a picked part goes to the
  language model with its description as background, for two or three spoken
  sentences; with no connection, Jarvis reads the description.

## Ideas to take it further

- More models: a bus, a lorry, a jet engine, the human heart, a computer.
- Real CAD models (glTF) where the licence allows, split into named parts.
- A "step by step" mode: parts come off in the order a mechanic would remove
  them, with Jarvis narrating each one.
- A gesture threshold check like palm_report.py, from your own hand: how
  open is "open" and how close is a pinch on your camera.

## Learn

- MediaPipe gesture recognizer: the 7 built-in gestures, handedness, 21
  landmarks, live-stream mode
  ([guide](https://developers.google.com/edge/mediapipe/solutions/vision/gesture_recognizer)).
- Exploded views in CAD viewers: moving parts out from the assembly's
  centre, by sub-assembly, along axes
  ([C3D Labs](https://c3dlabs.com/blog/tech-tips/how-to-explode-a-3d-model-with-c3d-vision/)).
