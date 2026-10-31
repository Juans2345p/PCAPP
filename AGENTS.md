# AGENTS.md

## Project overview
- Modular app: webcam (OpenCV) + MediaPipe hand landmarks + proportional speed over BLE UART (Nordic NUS) to a BBC micro:bit car.
- Two-hand control: left hand drives the `L` wheel, right hand drives `R`. One hand visible leaves the other wheel at 0 unless `single_hand: both`; no hands at all sends `z`.
- `README.md` is user-facing docs (Spanish). Code comments, logs and the on-screen panel are Spanish too; keep that style.
- Not a git repo (the workspace may be initialized as one, but the project has no history/CI). No test suite, linter, formatter or `opencode.json` — do not invent commands for them.

## Layout
- `main.py` (root): thin compatibility launcher, delegates to `pc_app.main.main`.
- `pc_app/config.py`: flat `Settings` dataclass, YAML loader, validation, CLI parser.
- `pc_app/domain/entities/`: `HandPose`, `WheelCommand`, `PanelConfig` (no OpenCV/MediaPipe/bleak imports).
- `pc_app/domain/interfaces/`: `IGestureRecognizer`, `ICommandSender`, `IConfigStore`.
- `pc_app/application/`: `CommandGate` (when to send), `CarController` (orchestration/safety) and `ConfigurationPanelController` (settings UI events).
- `pc_app/infrastructure/`: `MediaPipeHandTracker`, `FrameGrabber`, `BleUartSender`, `DryRunCommandSender`, `YamlConfigStore`, `ensure_model`.
- `pc_app/presentation/`: `overlay.py` (skeleton + status panel), `window.py` (`cv2` window).
- `pc_app/main.py`: composition root, async loop, `--list-devices`, `--image`.
- `config/settings.yaml` and `config/gestures.yaml`: runtime defaults.
- `design/car_control_ui.pen`: design reference; two screens (live + Configuración/AJUSTES). `docs/`: technical docs.

## Run / verify
- Interpreter: `.venv/bin/python` (Python 3.11.17, deps installed, including PyYAML). System `python3` is 3.14.8 and may also have deps, but the venv is the intended target.
- Full run: `.venv/bin/python main.py` (needs a webcam; opens an OpenCV window, `q`/`ESC` exits, `h` swaps hands).
- Verification without a camera or micro:bit:
  - `.venv/bin/python main.py --image <foto.jpg>` — prints raw straightness + extension per side/finger and the resulting command; add `--swap-hands` to check the label flip. This is the calibration/debug path (it applies `mirror` first, like the live loop).
  - `.venv/bin/python main.py --dry-run --no-preview` — full loop, no BLE, still needs the webcam.
  - `.venv/bin/python -m py_compile main.py pc_app/config.py pc_app/main.py pc_app/application/*.py pc_app/domain/entities/*.py pc_app/domain/interfaces/*.py pc_app/infrastructure/*.py pc_app/presentation/*.py` — cheapest syntax gate.
- `--list-devices` scans BLE and prints MACs; it skips model download and camera.

## Configuration coupling
- `parse_args()` builds the parser from YAML defaults, then does `Settings(**vars(ns))`: every argparse `dest` **must** exist as a `Settings` field, or startup dies with `TypeError`. Add the dataclass field when adding a flag.
- `--config` and `--gestures` are consumed before constructing `Settings`; they are not fields.
- Precedence: `Settings` defaults < YAML < CLI. Relative YAML paths resolve from `BASE_DIR` (project root), not the CWD.
- Shipped YAML overrides some dataclass defaults: `step: 5`, `min_interval: 0.05`. Keep docs in sync if changed.
- `ble.device_name` is `null` by default, so `address` (MAC) is used. Setting a name makes it take precedence over the MAC; `--name` in the CLI behaves the same way.
- `config/gestures.yaml` drives `curl_lo`/`curl_hi`/`smoothing`/`deadzone` and `control_mode` (`own`/`both`).
- Config panel events: `build_config_panel(settings)` (in `pc_app/main.py`) returns a `ConfigurationPanelController` backed by `YamlConfigStore`. `set_*` updates a draft; `save()` writes `config/settings.yaml`/`config/gestures.yaml` and mutates the live `Settings`. The YAML writer is surgical (replaces only managed scalars, keeps comments/order) — do not replace it with a full `yaml.safe_dump` of the files.
- Mapping: `curl_lo/hi` -> gestures calibration; `control_mode` -> gestures top-level + settings `control.single_hand`; `ble.device_name/address` -> settings BLE; `mirror` -> settings camera. BLE changes apply on the next reconnect; the rest apply on the next frame.

## MediaPipe gotchas
- Installed version is **1.2.0: `mp.solutions` does not exist**. Tutorials using `mp.solutions.hands.Hands` fail with `AttributeError`. Use the Tasks API only: `vision.HandLandmarker` + `RunningMode.VIDEO` + `detect_for_video(image, ts_ms)`.
- `detect_for_video` requires strictly increasing timestamps; `MediaPipeHandTracker._timestamp_ms()` enforces that. Don't replace it with `int(time.time()*1000)`.
- `hand_landmarker.task` (~7.5 MB) is a runtime artifact, auto-downloaded by `ensure_model()` if missing. Default path is resolved from `BASE_DIR` (project root), not the CWD — keep it that way.
- Inference runs in a 1-worker `ThreadPoolExecutor` via `run_in_executor` from `pc_app/main.py`; camera capture runs in `FrameGrabber`. Don't call `tracker.process` on the event loop directly.
- `MediaPipeHandTracker` uses `settings.num_hands` (default 2) and `process()` returns `dict[str, HandPose]` keyed by `"L"`/`"R"` (empty `{}` when no hands). Do not revert to a single `HandPose | None`.
- EMA state is keyed by `(side, finger)`, so each hand is smoothed independently; `_ema` is cleared on total loss and pruned for vanished sides.

## BLE specifics
- UUIDs are **inverted vs. standard Nordic NUS on purpose**: write = `6e400003...`, notify = `6e400002...`. They match the user's firmware; do not "fix" them.
- Wire protocol (ASCII, `\n` terminated, **one motor per message, never comma-separated**): `L{n}` then `R{n}` with n in -255..255, sent as **two separate BLE writes** (left first, then right), and `z` as a single stop/e-stop message. The firmware cannot parse `R150,L150`. The user's older project (`../CarOpenCVBLE`) used single letters (`w`/`s`/`a`/`d`/`z`) — do not reintroduce that format here.
- `WheelCommand.messages()` owns the ASCII construction; `BleUartSender._write()` emits each tuple element as its own BLE write.
- Sending policy is deliberate: quantization to `--step`, hysteresis on the **continuous** speed (comparing quantized values causes chatter at step boundaries), `--min-interval` spacing, `--heartbeat` keep-alive, and an `asyncio.Queue(maxsize=1)` that drops the oldest command. `CommandGate.feed()` takes `{"L": float, "R": float}` and applies all of this **per wheel**. Preserve all four when touching it.
- Safety contract: `z` is sent on startup (`CarController.start`), when no hand is visible for `lost_grace` (per side, so a lost wheel goes to 0), and on exit (`CarController.stop` -> `ICommandSender.close("z")`). Never remove that final stop.

## Two-hand logic
- Speed per wheel: `(index_ext - middle_ext) * max_speed`; both extended (or both curled) intentionally yields 0 for that wheel.
- Side assignment (`MediaPipeHandTracker._side`): MediaPipe labels assume a mirrored (selfie) frame. With `mirror` (default) the label is used as-is; with `--no-mirror` it is inverted. `--swap-hands` and the live `h` key (`CarController.toggle_hands`) flip it again. Frames are flipped **before** inference when `cfg.mirror`.
- `single_hand` (`own` default, or `both`): with one hand visible, `own` moves only its wheel, `both` copies that speed to both wheels.
- Finger extension = `chord / path` over the MCP→PIP→DIP→TIP chain (`_straightness`), normalized by `curl_lo`/`curl_hi` (defaults 0.30/0.97, calibrated on real open hand ≈0.99 vs fist ≈0.20), then deadzone + EMA. Changing these defaults changes the whole speed feel.
- The camera overlay draws only the hand skeleton/landmarks, deliberately **without** left/right labels (user request). Side information lives only in the panel's `IZQ`/`DER` wheel rows and in `--image` output.

## Environment
- Fedora: OpenCV needs `libgomp` and `mesa-libGL`/`libglvnd-glx`; BLE needs the `bluetooth` service. Under pure Wayland, `QT_QPA_PLATFORM=xcb` may be required for `cv2.imshow`.
- `hand_landmarker.task` is binary and regenerable — never edit or commit it by hand.
