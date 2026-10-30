# Referencia de API

## Configuración — `pc_app/config.py`

### `Settings`

Dataclass plana con todos los parámetros. Los campos más relevantes:

| Campo | Tipo | Default | Descripción |
| ----- | ---- | ------- | ----------- |
| `address` | `str` | `E0:BE:3F:2E:C9:8A` | MAC del micro:bit |
| `name` | `str \| None` | `None` | Nombre BLE alternativo a la MAC |
| `write_uuid` | `str` | `6e400003-...` | Característica de escritura |
| `notify_uuid` | `str` | `6e400002-...` | Característica de notificación |
| `camera`, `width`, `height` | `int` | `0`, `640`, `480` | Captura |
| `mirror` | `bool` | `True` | Voltea el frame antes de inferir |
| `model` | `Path` | `hand_landmarker.task` | Modelo MediaPipe |
| `num_hands` | `int` | `2` | Manos simultáneas |
| `detect_conf`, `presence_conf`, `track_conf` | `float` | `0.6` | Umbrales MediaPipe |
| `max_speed` | `int` | `255` | Velocidad máxima |
| `step` | `int` | `8` | Cuantización / histéresis |
| `min_interval` | `float` | `0.06` | Separación mínima entre envíos |
| `heartbeat` | `float` | `1.0` | Keep-alive |
| `lost_grace` | `float` | `0.15` | Gracia al perder una mano |
| `swap_hands` | `bool` | `False` | Invierte izquierda/derecha |
| `single_hand` | `str` | `"own"` | `own` o `both` |
| `smoothing` | `float` | `0.35` | Alfa EMA |
| `deadzone` | `float` | `0.08` | Zona muerta |
| `curl_lo`, `curl_hi` | `float` | `0.30`, `0.97` | Rango de rectitud |
| `preview`, `dry_run`, `debug` | `bool` | — | Modos de ejecución |
| `image` | `Path \| None` | `None` | Imagen para calibrar |

`Settings.validate()` comprueba rangos y lanza `SystemExit` con un mensaje en
español.

### Funciones

- `load_settings(settings_path=None, gestures_path=None) -> Settings`: lee los
  dos YAML, los aplana y valida.
- `build_parser(defaults) -> argparse.ArgumentParser`: construye la CLI usando
  los valores YAML como defaults.
- `parse_args(argv=None) -> Settings`: precarga `--config`/`--gestures`,
  construye el parser y devuelve la configuración final. Cualquier `dest` del
  parser debe existir como campo de `Settings`.

## Dominio

### `HandPose` — `pc_app/domain/entities/hand_pose.py`

```python
@dataclass
class HandPose:
    side: str             # "L" | "R"
    index_ext: float      # extensión suavizada del índice (0..1)
    middle_ext: float     # extensión suavizada del medio (0..1)
    raw_index: float      # rectitud cruda (calibración)
    raw_middle: float
    landmarks: list

    def speed(self, max_speed: int) -> float:
        return (self.index_ext - self.middle_ext) * max_speed
```

### `WheelCommand` — `pc_app/domain/entities/wheel_command.py`

```python
@dataclass(frozen=True)
class WheelCommand:
    left: int
    right: int

    @classmethod
    def from_speeds(cls, left, right, *, step, max_speed) -> WheelCommand
    @classmethod
    def stop(cls) -> WheelCommand
    @property
    def is_stop(self) -> bool
    def messages(self) -> tuple[str, ...]
```

`from_speeds` cuantiza a múltiplos de `step` y recorta a `±max_speed`.
`messages()` devuelve `("z",)` si ambas ruedas son 0; si no,
`("L{left}", "R{right}")` en ese orden.

### Contratos — `pc_app/domain/interfaces/`

- `IGestureRecognizer.process(frame_bgr) -> dict[str, HandPose]` y `close()`.
- `ICommandSender`: propiedades `connected`, `sent`, `dropped`, `last_error`,
  `is_dry_run`; métodos `start()`, `send(messages: tuple[str, ...])` y
  `async close(final="z")`.

## Aplicación

### `CommandGate` — `pc_app/application/command_gate.py`

```python
CommandGate(settings)
gate.feed(speeds: dict[str, float] | None, now: float) -> WheelCommand | None
gate.last_command   # última WheelCommand enviada
gate.last_payload   # texto para el panel, p. ej. "L150 R150" o "z"
```

Aplica cuantización, histéresis sobre la velocidad continua, `min_interval` y
`heartbeat`. Cada rueda se evalúa por separado.

### `CarController` — `pc_app/application/car_controller.py`

```python
CarController(settings, sender, gate=None)
controller.start()                     # arranca el transporte y envía z
controller.update(poses, now=None)     # devuelve WheelCommand | None
controller.toggle_hands() -> bool
await controller.stop()                # cierra enviando z
controller.last_command / last_payload / sender
```

Mantiene la última pose y el último instante visto por lado para aplicar
`lost_grace`; con `single_hand="both"` copia la única velocidad a ambas ruedas.

## Infraestructura

- `MediaPipeHandTracker(settings)` — `HandLandmarker` en `RunningMode.VIDEO`,
  timestamps estrictamente crecientes, EMA por `(lado, dedo)`, lado calculado
  según `mirror`/`swap_hands`.
- `FrameGrabber(index, width, height)` — hilo de captura; `latest()` devuelve
  `(frame, seq)` y `fps`.
- `BleUartSender(settings)` — supervisor asíncrono, cola de tamaño 1,
  reconexión con backoff, una escritura por mensaje.
- `DryRunCommandSender()` — mismo contrato, sin hardware.
- `ensure_model(path)` — descarga el modelo si falta o está incompleto.

## Presentación

- `render(frame, poses, sender, fps, settings, last_payload) -> np.ndarray` —
  esqueleto + panel inferior.
- `PreviewWindow` — `show(frame) -> int`, `is_open()`, `close()`.

## Entrada

`pc_app/main.py`

- `async run(settings) -> int`: bucle principal.
- `async list_devices(timeout=8.0) -> int`: escaneo BLE.
- `run_image(settings, path) -> int`: calibración con imagen fija.
- `main(argv=None) -> int`: parseo, logging, modelo y despacho.

`main.py` (raíz) sólo importa y ejecuta `pc_app.main.main`.
