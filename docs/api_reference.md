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
| `speed_multiplier` | `float` | `1.0` | Factor 0.0–1.5, limitado a `max_speed` |
| `step` | `int` | `8` | Cuantización / histéresis |
| `min_interval` | `float` | `0.06` | Separación mínima entre envíos |
| `heartbeat` | `float` | `1.0` | Keep-alive |
| `lost_grace` | `float` | `0.15` | Gracia al perder una mano |
| `swap_hands` | `bool` | `True` | Invierte izquierda/derecha |
| `single_hand` | `str` | `"own"` | `own` o `both` |
| `smoothing` | `float` | `0.35` | Alfa EMA |
| `deadzone` | `float` | `0.08` | Media anchura normalizada de STOP |
| `curl_lo`, `curl_hi` | `float` | `0.30`, `0.97` | Parámetros heredados |
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
    index_ext: float      # posición de muñeca mapeada a [0,1]
    middle_ext: float     # complemento de index_ext
    raw_index: float      # posición de muñeca normalizada [-1,1]
    raw_middle: float     # misma posición por compatibilidad
    landmarks: list

    def speed(self, max_speed: int, deadzone=0.0, multiplier=1.0) -> float:
        # Aplica la banda neutra y limita la salida al máximo del motor.
        ...
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

### `PanelConfig` — `pc_app/domain/entities/panel_config.py`

```python
@dataclass(frozen=True)
class PanelConfig:
    curl_lo: float
    curl_hi: float
    control_mode: str        # "own" | "both"
    ble_address: str
    ble_name: str | None
    mirror: bool

    def validate(self) -> None
```

Representa el borrador editable de la pantalla de Configuración.

### Contratos — `pc_app/domain/interfaces/`

- `IGestureRecognizer.process(frame_bgr) -> dict[str, HandPose]` y `close()`.
- `ICommandSender`: propiedades `connected`, `sent`, `dropped`, `last_error`,
  `is_dry_run`; métodos `start()`, `send(messages: tuple[str, ...])` y
  `async close(final="z")`.
- `IConfigStore.read_panel() -> PanelConfig` y
  `write_panel(config: PanelConfig) -> None`.

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

### `ConfigurationPanelController` — `pc_app/application/config_panel.py`

```python
ConfigurationPanelController(store, settings=None)
panel.state                 # PanelConfig (valores actuales)
panel.dirty                 # True si falló la escritura automática
panel.reload()              # relee los YAML
panel.set_curl_lo(value)
panel.set_curl_hi(value)
panel.set_control_mode("own" | "both")
panel.set_ble_address(mac)
panel.set_ble_name(name | None)
panel.set_mirror(True | False)
panel.set_deadzone(value)
panel.set_smoothing(value)
panel.set_step(value)
panel.set_lost_grace(value)
panel.set_speed_multiplier(value)
panel.save()                # valida, escribe YAML y aplica a Settings
```

Cada `set_*` valida el valor, lo aplica al estado de `Settings` en memoria y lo
persiste automáticamente en el YAML correspondiente. La interfaz confirma los
campos de texto con Enter; el slider del multiplicador usa pasos de 0,1.

## Infraestructura

- `MediaPipeHandTracker(settings)` — `HandLandmarker` en `RunningMode.VIDEO`,
  timestamps estrictamente crecientes, EMA por mano, lado calculado
  según `mirror`/`swap_hands`.
- `FrameGrabber(index, width, height)` — hilo de captura; `latest()` devuelve
  `(frame, seq)` y `fps`.
- `BleUartSender(settings)` — supervisor asíncrono, cola de tamaño 1,
  reconexión con backoff, una escritura por mensaje.
- `DryRunCommandSender()` — mismo contrato, sin hardware.
- `ensure_model(path)` — descarga el modelo si falta o está incompleto.
- `YamlConfigStore(settings_path=None, gestures_path=None)` — lee y escribe
  los valores del panel. La escritura sustituye sólo los escalares editables y
  conserva comentarios y el resto del YAML.

## Presentación

- `render(frame, poses, sender, fps, settings, last_payload) -> np.ndarray` —
  cámara, zona STOP dinámica, ruedas, estado y controles.
- `PreviewWindow` — ventana completa con teclado y ratón; `f` alterna pantalla
  completa y ventana.
- `WebDashboard` (`pc_app/presentation/web_dashboard.py`) — sirve recursos
  estáticos, estado JSON y vídeo MJPEG; encola acciones y cambios de
  configuración para que los aplique el bucle principal.
- `pc_app/presentation/web/` — HTML, CSS y JavaScript del dashboard. El
  encabezado incluye pantalla completa; las ayudas de configuración abren un
  modal centrado.

## Entrada

`pc_app/main.py`

- `async run(settings) -> int`: bucle principal.
- `async list_devices(timeout=8.0) -> int`: escaneo BLE.
- `run_image(settings, path) -> int`: calibración con imagen fija.
- `build_config_panel(settings) -> ConfigurationPanelController`: fábrica del
  controlador de eventos de la pantalla de Configuración.
- `main(argv=None) -> int`: parseo, logging, modelo y despacho.

`main.py` (raíz) sólo importa y ejecuta `pc_app.main.main`.
