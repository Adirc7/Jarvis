# Jarvis on the PC: programs, power, files, three claps and "Hey Jarvis"

## Say it

| You | Jarvis |
|---|---|
| "open MATLAB", "RStudio open karanna", "open Zoom" | opens it from the Start menu (any installed program; never a shell like PowerShell or cmd, a system tool, an uninstaller or a file path) |
| "lock the screen", "lock karanna" | locks at once |
| "put the computer to sleep", "sign me out" | asks first |
| "shut down the computer", "restart", "ෂට්ඩවුන් කරන්න" | asks first, then waits 30 seconds |
| "cancel the shutdown", "undo that" | stops a shutdown or restart that hasn't happened yet |
| "where's my DWBI report?", "kidney notebook eka kohed?" | finds it by words in its name, newest first |
| "what's in it?", "read the second one" | reads it (text, PDF, Word, PowerPoint, Excel, code) and tells you the main points |

## Jarvis asks, you answer

Before anything risky (sleep, sign out, restart, shut down, moving a file to the recycle folder, running
MATLAB code), the box opens and Jarvis says the question. Answer by:

- **a click**: "Yes, do it" or Cancel;
- **your voice**: hold push-to-talk and say "yes", "ඔව්", "hari" or "no", "එපා" (typing it works too);
- **your hand**: hold a thumbs up for a second (thumbs down cancels). The camera must be on
  (`/camera on`, or `[gestures] enabled = true`).

No answer in 60 seconds cancels. A muddled answer ("yes, no, wait") counts as no. Anything else said
while the box is open gets "I'm waiting for a yes or a no". Words in a web page or a file never answer.
The action log (`logs/actions-*.jsonl`) records how each was confirmed: click, voice, typed or thumbs.

## Your files

Only these folders, read-only: `[tools] search_folders` (Desktop, Documents, Downloads by default), plus
`allowed_folders` and Jarvis's own folder. Your projects on D: need adding, in
`config/settings.local.toml`:

```toml
[tools]
search_folders = ["~/Desktop", "~/Documents", "~/Downloads", "D:/"]
```

Never listed or read: `.env` files, keys and certificates, password databases, anything named like a
secret, token or API key, and tool folders (`.git`, `node_modules`, `.venv`). A file's text goes to the
model as data to answer from, never as instructions.

## Clap three times to open Jarvis

A small program with no window listens for claps while Jarvis isn't running:

```
scripts\clap_launcher.cmd install      start it now, and at every sign-in
scripts\clap_launcher.cmd test         see each clap it hears (to tune [clap] in settings)
scripts\clap_launcher.cmd uninstall    stop it for good
```

Three loud, even claps (each 0.2 to 0.9 seconds after the one before, about equally loud, at least
35 dB above the room), then quiet, with no key or mouse button pressed in the 4 seconds around them: Jarvis starts as the desktop icon
starts him (if he's already running, his window comes to the front). Two claps are Jarvis's own double
clap; four or more (applause) and knocks (low-pitched) do nothing. Nothing is recorded: each 10 ms of
sound is measured and dropped. Its log is `logs/clap_launcher.log`. `scripts\update.cmd` stops it while it
installs and starts it again after.

## "Hey Jarvis" without the key

Say "Hey Jarvis" and he answers "Yes, sir?" and listens until you pause, as after a double clap; then
speak normally (in Sinhala too, once Friday is on). openWakeWord's small model runs on the CPU, about
2.5 ms per 80 ms of sound; nothing is recorded or sent. It's deaf while Jarvis speaks and for a second
after (his own "Jarvis" would wake it), and while you hold the key.

- On: `[wake_word] enabled = true` in `config/settings.local.toml` (or `/wake on`), `/wake off` to stop,
  `/wake` to see the best score lately.
- If it wakes by itself, raise `threshold` (0.5 by default; "Hey Jarvis" scores about 0.99, "Jarvis"
  alone and "Hey Travis" about 0.9). If it misses you, lower it a little.
- The model files (about 7 MB) download once, to `models/openwakeword`. The pre-trained "hey jarvis"
  model is CC BY-NC-SA 4.0: fine for a non-commercial project like this one.
