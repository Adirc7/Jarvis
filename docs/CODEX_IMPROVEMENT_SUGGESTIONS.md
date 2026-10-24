# Codex improvement suggestions

> Advisory handoff for future Claude/Codex review.
>
> These are recommendations, not proof that the proposed features exist.
> Current implementation status must always be revalidated against the code,
> tests, telemetry, and latest dev log before work begins.

Reviewed locally on 2026-10-22 against commit e96040d.

**Taken up so far (Claude, 24 Oct):** sections 6 and 7 (double clap, palm)
in DECISIONS.md D29 and IMPLEMENTATION_PLAN.md (M6 "The double clap, step by
step", M8 "Palm to pause, step by step"); the UI, lifecycle and safety
sections are placed by stage in HUMANLIKE_PLAN.md. One difference: palm to
pause may start before the window (reason in IMPLEMENTATION_PLAN.md, M8).

## 1. Purpose and source-of-truth rules

This document records product, UI, multimodal-control, safety, and evaluation
recommendations discussed during the Codex review. It is intended to make a
future conversation with Claude easier without treating chat history or visual
mockups as implementation evidence.

When sources disagree, use this order:

1. DECISIONS.md for accepted design and safety decisions.
2. ROADMAP.md and IMPLEMENTATION_PLAN.md for phase and milestone ownership.
3. The latest measured entries in DEVLOG.md for current behaviour.
4. ARCHITECTURE.md for the intended system shape.
5. This file for advisory improvements that still require review.

Do not open, copy, quote, or modify .env files, credentials, tokens, API keys,
or other secret stores while reviewing this document. Their values are not
needed for planning.

### Status vocabulary

| Label | Meaning |
| --- | --- |
| Verified | Working behaviour is supported by repository evidence and a measured run or test. |
| Early slice | A limited version works, but the roadmap's full phase is not complete. |
| Foundation | Supporting code, data, or design exists, but the feature is not usable end to end. |
| Proposed | Recommendation only. Do not present it as working. |
| Deferred | Intentionally left for a later milestone. |

## 2. Current product truth

The following table is a concise handoff, not a replacement for checking the
repository.

| Area | Status at this review | Evidence and caution |
| --- | --- | --- |
| English voice loop | Verified slice | First English audio was measured at about 1.35 seconds in DEVLOG.md. Formal M0/M1 evaluation still has unfinished cases. |
| English identity | Verified | English uses Jarvis with Kokoro bm_lewis. The goal is an original British-inspired production style, not a cloned actor. |
| Sinhala identity | Early slice | Sinhala uses Friday with Kokoro bf_emma plus eSpeak Sinhala pronunciation. The dilu-to-Emma kNN-VC comparison is experimental and ongoing. |
| Tamil | Existing project scope | Tamil remains part of the documented language system. It has not been assigned the Friday identity. |
| Light memory | Early slice | src/jarvis/memory and local state/memory.json support a name, explicitly remembered facts, recent conversation, /memory, and /forget. This is not the full memory phase. |
| Request routing | Foundation with measured generated-set result | The router scored 95.8% on 15,432 generated sentences. DEVLOG.md explicitly warns that this is not real-world accuracy. |
| Intent data | Foundation | 43 intents and 15,432 generated examples exist. Data existence is not proof that a final classifier is trained or validated. |
| Tools and safety | Proposed/planned M3, Phase 2 | Must be completed before Jarvis receives broad computer-control ability. |
| Browser and YouTube voice tools | Planned after REVIEW_FIXES groups 1-2 | Semantic open/search/play/pause tools should be preferred when available; the virtual mouse remains a direct-manipulation fallback. |
| Study skill | Proposed/planned M4 | Depends on the Phase 2 safety/tool platform. |
| Desktop window and tray | Proposed/planned M6, Phase 1.6 | UI mockups are design artifacts, not a shipped desktop window. |
| News world map | Proposed/planned M7 News skill | Displayed inside the M6 Jarvis window after grounded news retrieval exists. |
| Hand gestures | Proposed/planned M8, Phase 3 | Camera must be explicitly enabled; only landmarks are processed; video is not stored. |
| AI virtual mouse | New proposal spanning M3 and M8 | Perception belongs to gestures; OS action belongs behind the Phase 2 safety boundary. |

## 3. Product identity recommendations

- Jarvis is the primary assistant and English-speaking character.
- Friday is the Sinhala-speaking character.
- A Sinhala utterance can switch to Friday according to the existing language
  rules. The word Friday must still be distinguished from the weekday.
- Tamil stays in language scope unless an explicit decision changes it.
- The visual and audio design should evoke a composed futuristic assistant
  while remaining original. Do not copy film UI screens or clone a real
  performer's voice.
- Honorifics such as "sir", the user's name, or no honorific should remain a
  setting.
- Every spoken response should also have visible captions.

## 4. UI and information architecture

### Recommended main modules

The desktop window should present one core plus skills rather than several
unrelated applications:

1. Core Assistant: conversation, current identity, listening/thinking/speaking.
2. Memory: the memory-constellation view and clear controls for review/forget.
3. System: the real request pipeline, routing, fallback, and current state.
4. Tasks: current work, queued work, completion, cancellation, and undo.
5. Diagnostics: timing, providers, sensor state, errors, and evaluation.
6. Study: marked PLANNED · M4 until it is usable.
7. Visualise, Data, Research, and News: marked PLANNED · M7 until grounded
   implementations exist.

Settings, privacy, microphone/camera control, the action log, and safety
confirmations should be global controls, not carousel slides.

### Truthful status display

Keep the labels LIVE, EARLY SLICE, FOUNDATION, PLANNED, and ERROR visible.
Visual polish must never imply that a mockup or roadmap item is operational.

Recommended persistent telemetry:

- lifecycle: STARTING, SLEEPING, AWAKE, or QUITTING;
- interaction: LISTENING, THINKING, SPEAKING, or IDLE;
- persona/language: Jarvis English, Friday Sinhala, or Tamil;
- microphone, camera, clap listener, and virtual-mouse state;
- local/cloud route and privacy status;
- current skill and current safety tier.

### Full-screen responsive layout

The UI must fit the actual browser/window viewport rather than guessing the
laptop model or display resolution.

- Use height: 100dvh for the application shell.
- Use grid rows equivalent to auto minmax(0, 1fr) auto.
- Apply min-height: 0 to nested grid/flex content regions.
- Scroll only the active content region; keep essential controls visible.
- Avoid fixed desktop-window heights.
- Collapse secondary telemetry into drawers on shorter/narrower viewports.
- Test at Windows scaling values of 100%, 125%, and 150%.
- Test 16:9 and 16:10 viewports, including compact-height cases.
- No essential control may require browser zoom-out.

### Visual language and rendering

- Deep navy/black background with restrained cyan and blue system accents.
- Preserve the accepted orb identity: Jarvis gold; Friday teal or rose.
- Amber for listening/waiting; red only for errors or dangerous actions.
- Pair every colour state with text or an icon.
- Use glow for the central core and important active states, not all text.
- Preserve readable controls when sleeping; do not dim the kill/privacy
  controls below accessible contrast.
- Respect reduced-motion preferences.
- Keep text, buttons, confirmations, and accessibility semantics in the DOM.
- Prefer SVG/CSS for the central reactor. Use WebGL for Memory, System, and Map
  only when it materially improves the information.
- Render only the active heavy visualisation and pause it when hidden.

## 5. Shared lifecycle and interaction architecture

The project lifecycle remains:

    Starting -> Sleeping -> Awake -> Sleeping
                           \-> Quit

Closing the desktop window should normally return Jarvis to Sleeping. Quit
from the tray or an explicit "Jarvis, shut down" ends the process.

All input paths should call shared controllers:

    Voice / clap / power button / keyboard
                    |
                    v
             Lifecycle controller
                    |
          HUD + speech + sensor policy

    Camera frames -> hand landmarks -> gesture router
                                      |              |
                                      v              v
                              module navigation   virtual mouse
                                                       |
                                                       v
                                                safety supervisor
                                                       |
                                                       v
                                                 native OS input

Recommended sensor/interaction substates:

- PERMISSION_REQUIRED
- CALIBRATING
- PRIVACY_SLEEP
- SLEEPING_WITH_WAKE_LISTENER
- WAKING
- AWAKE_IDLE
- LISTENING
- THINKING
- SPEAKING
- HAND_LOST
- ERROR

All controllers should expose idempotent commands. A clap, keyboard shortcut,
button, and voice command must not each mutate the UI independently.

## 6. Double-clap wake recommendation

This belongs to M6 / Phase 1.6 and should remain optional and off by default.
It is a convenience wake input, not identity, authorization, or confirmation.

The current roadmap defines two sharp peaks approximately 0.2-0.6 seconds
apart. Preserve that decision unless testing justifies a measured change.

Recommended detector behaviour:

- require explicit microphone opt-in before arming;
- calibrate ambient noise for 2-3 seconds;
- detect short acoustic transients using more than raw volume;
- maintain an adaptive noise baseline;
- use a short refractory window after the first peak;
- expire incomplete pairs and apply a global wake cooldown;
- suppress or duck detection while Jarvis speaks and briefly afterward;
- expose sensitivity, calibration, and test controls;
- display the first detected peak without waking immediately;
- keep raw audio in memory only and never save it.

Measure missed wakes and false wakes per hour with:

- Jarvis speaking;
- a film, lecture, or YouTube video playing;
- laptop fans;
- keyboard typing;
- desk taps, door knocks, and hand claps at different distances.

Do not silently expand double clap into a shutdown toggle. Sleeping, quitting,
and cancelling work have different semantics and must remain explicit.

## 7. Hand navigation recommendation

This belongs to M8 / Phase 3. Preserve the canonical gesture set:

| Gesture | Intended action |
| --- | --- |
| Open palm | Stop/pause Jarvis |
| Thumbs up/down | Feedback |
| Left/right swipe | Previous/next module |
| Point plus "this" | Deictic reference in Phase 4 |
| Double wave | Silent wake |

Implementation recommendations:

- require deliberate pose stability for approximately 0.5 seconds where the
  roadmap specifies it;
- detect swipes from temporal displacement and velocity, not one frame;
- resolve camera mirroring consistently;
- require sufficient hand presence and tracking confidence;
- apply a 600-800 ms navigation cooldown;
- process approximately 15 FPS initially and keep only the latest result;
- use MediaPipe live-stream tracking so inference does not build a stale queue;
- display the gesture currently being considered and the accepted gesture;
- keep camera use opt-in, local, and disabled outside gesture mode;
- drop frames after landmark extraction; never store video.

The gesture router must grant ownership to exactly one mode. When virtual mouse
mode is armed, slide-swipe recognition is disabled.

## 8. AI virtual mouse recommendation

### Product boundary

Browser JavaScript can interact with the Jarvis page, but it cannot provide
reliable OS-wide pointer control over browser chrome, YouTube, File Explorer,
and other desktop applications. Use a Python/native service for OS input.

Where a registered semantic tool exists, prefer it over simulated pointing:
for example, open/search through the planned browser tool and play/pause
through the planned media control. The virtual mouse is valuable for direct
selection and interfaces without an appropriate registered tool, not as a
replacement for the safer tool path.

Recommended split:

- OpenCV owns camera capture.
- MediaPipe Hand Landmarker produces the 21 landmarks.
- A gesture state machine produces semantic events.
- A safety supervisor decides whether events may become OS input.
- A replaceable mouse backend uses PyAutoGUI, pynput, or a later Windows-native
  implementation.
- The HUD receives state and telemetry through local IPC or WebSocket.
- Only one Jarvis component may own the webcam at a time.

### Recommended state machine

    DISABLED
      -> ARMING
      -> CALIBRATING
      -> POINTER_ACTIVE
           -> MOVE
           -> PINCH_PENDING
           -> SCROLLING
           -> DRAGGING (deferred)
      -> HAND_LOST / PAUSED
      -> DISABLED

Activation should require an explicit voice command, HUD button, or global
hotkey, followed by visible/audio feedback. A momentary pose alone should not
enable OS mouse control.

Recommended controls:

| Gesture/input | Action | Initial release |
| --- | --- | --- |
| Preferred-hand index only | Move pointer | Yes |
| Thumb-index short pinch | Left click | Yes |
| Index and middle extended | Relative scroll mode | Yes |
| Open palm | Pause/freeze | Yes |
| Voice/HUD/global hotkey | Enable/disable | Yes |
| Thumb-middle deliberate hold | Right click | Later |
| Thumb-index hold and movement | Drag/drop | Later |
| Double pinch/double click | Open item | Later; prefer voice-open-selected first |

Do not use index-middle pinch as an alternative left click because it conflicts
with the two-finger scroll pose.

### Pointer processing

Use a configurable inner camera region, initially around 70% of the frame, and
map it to the primary display. The preview can be mirrored while internal
coordinates remain consistent.

Use a scale-independent pinch measurement:

    pinch_ratio =
        distance(thumb_tip, index_tip)
        --------------------------------
        distance(index_mcp, pinky_mcp)

Do not use a fixed camera-pixel threshold. Add:

- different press and release thresholds (hysteresis);
- 60-120 ms pose confirmation;
- 250-400 ms click cooldown;
- mandatory release before another click;
- optional depth validation to reduce projected false pinches;
- a small stationary dead zone;
- a velocity-aware EMA or One Euro filter;
- a smooth reacquisition from the current OS cursor position.

On tracking loss, mode exit, cancellation, or any exception:

1. release every held mouse button;
2. freeze the pointer;
3. enter HAND_LOST or DISABLED;
4. require stable reacquisition before resuming.

### Windows constraints

- First release should target the primary monitor only.
- Explicitly handle Windows DPI scaling and verify camera-to-screen mapping at
  100%, 125%, and 150%.
- Preserve PyAutoGUI's corner fail-safe if PyAutoGUI is used.
- Be aware that PyAutoGUI's default pause is too large for a smooth frame-rate
  pointer; tune the backend without removing the independent kill switch.
- Jarvis remains a normal-user process and must not request administrator
  rights to control elevated applications.
- UAC/secure-desktop and higher-integrity applications are out of scope.

### Debug and user feedback

The calibration/debug view should show:

- active camera rectangle;
- selected hand and landmarks;
- raw and filtered pointer coordinates;
- gesture/mode name;
- pinch ratio and thresholds;
- confidence, FPS, and end-to-end latency.

After calibration, the OpenCV window should be minimised or replaced by a
small non-focus-stealing status overlay so it does not steal clicks from the
target application.

## 9. Critical safety and privacy invariants

These recommendations must not weaken D25 or Phase 2.

- Voice, clap, and gestures never authorize a risky action.
- Only a deliberate physical click/tap may confirm an "ask first" action.
- When a safety confirmation opens, suspend virtual-mouse injection.
- The confirmation UI must not rely only on browser event isTrusted, because a
  native injected OS event may still arrive as a trusted-looking browser event.
- Voice and gesture may cancel a pending action.
- Ctrl+Alt+K remains the canonical global kill switch.
- All tools are registered, schema-validated, risk-tiered, verified, logged,
  and limited to configured allowed folders.
- No raw shell is exposed to the model.
- Reversible actions keep undo information.
- Delete means a recoverable move according to the Phase 2 design.
- Text from files, web pages, articles, and tool output remains untrusted data,
  never instructions.
- Jarvis never runs as administrator.
- Camera frames and wake-listener audio remain local and are dropped.
- Physical keyboard and mouse control remain available at all times.

File Explorer integration must still obey allowed/private folder policy. A
virtual pointer is not permission to expose or manipulate arbitrary files.

## 10. Recommended phased integration

The visual design can be prototyped early, but sensor and OS-control features
must not bypass their roadmap dependencies.

1. Synchronise the checkout and revalidate current repository truth.
2. Complete REVIEW_FIXES groups 1 and 2, in order, with their specified tests.
3. Build M3 / Phase 2 safety gate, confirmation, action log, undo, and tests.
4. Build the responsive M6 window shell with manual/keyboard operation.
5. Add captions, persona/language state, privacy controls, and sensor status.
6. Add optional double-clap wake and evaluate false wakes.
7. Add HUD-only camera landmark and gesture visualisation.
8. Add deliberate swipe navigation with the shared gesture router.
9. Add explicitly armed primary-monitor pointer movement.
10. Add left click and relative scrolling.
11. Add file selection plus voice-assisted "open selected".
12. Add right click, drag/drop, and multi-monitor support only after the
    reliability targets are met.
13. Add the grounded News map and other M7 skills after their data paths exist.

REVIEW_FIXES.md is present at the reviewed revision. Its groups 1 and 2 are
prerequisites for the planned browser tools and should be completed before
expanding computer control. Group 3 may remain deferred as that document says.

## 11. Acceptance criteria

### Desktop UI

- Essential controls remain visible without browser zoom.
- No panel overlap or inaccessible bottom content at supported viewport sizes.
- Manual and keyboard operation work when sensors are unavailable.
- Planned modules never appear as live.
- Standby preserves readable privacy and wake state.

### Double clap

- No self-trigger from Jarvis speech.
- Permission denial falls back cleanly to manual controls.
- Missed-wake and false-wake rates are reported.
- No unintended wake during the defined media, fan, typing, and desk-tap test.

### Module gestures

- One deliberate swipe produces exactly one module transition.
- No module transition occurs while virtual mouse mode is active.
- Hand loss or low confidence causes a safe pause.
- Per-gesture accuracy and false activations per hour are reported.

### Virtual mouse

- Median end-to-end pointer latency target is below approximately 100 ms.
- At least 95% selection success on normal-sized targets in controlled tests.
- No unintended click during a 30-minute normal-use stress test.
- Held buttons are released on hand loss, exit, kill switch, and exceptions.
- Reacquisition does not jump the cursor across the screen.
- The physical emergency control works every time.
- A virtual-mouse event cannot confirm an "ask first" action.

### Privacy and safety

- No raw camera video is stored.
- No wake-listener audio is stored.
- Sensor activation is visible and independently controllable.
- Tool access outside allowed folders is refused.
- Safety-test-set result remains zero unsafe actions before release.

## 12. Suggested code boundaries

Even if an early prototype begins in one script, keep these responsibilities
separate:

- LifecycleController
- SensorPermissionController
- ClapDetector
- CameraSource
- HandTracker
- GestureRouter
- ModuleNavigationController
- PointerFilter
- ScreenMapper
- VirtualMouseStateMachine
- NativeMouseBackend
- SafetySupervisor
- HUDTelemetryBridge
- DebugRenderer

Each component should emit semantic events rather than directly changing
unrelated UI or operating-system state.

## 13. Claude review checklist

Before implementing anything from this document, Claude should:

1. Confirm the intended branch/commit and synchronise missing documentation.
2. Inspect current code and tests without reading secret/environment files.
3. Revalidate every status in the current-product-truth table.
4. Identify which accepted decisions would change and request approval first.
5. Preserve existing voice, memory, language, routing, and telemetry behaviour.
6. Produce a staged plan with rollback points before sensor or OS-input work.
7. Implement the smallest safe slice and test it before adding more gestures.
8. Keep mockups and future modules labelled as proposed.
9. Record measured results in DEVLOG.md instead of claiming completion from
   code presence alone.

### Decisions still requiring confirmation

- Desktop shell choice and the local IPC mechanism.
- Exact first-release module order.
- Whether the microphone may remain armed for optional clap wake after opt-in.
- Camera service ownership and startup policy.
- Virtual-mouse primary-monitor-only scope for version one.
- The global virtual-mouse enable/disable shortcut, while preserving
  Ctrl+Alt+K as the universal cancellation switch.
- How the confirmation UI proves that a physical click, rather than injected
  Jarvis input, authorized an "ask first" action.
- Which measured evidence moves each proposal to Foundation, Early slice, or
  Verified.
