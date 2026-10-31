# Refactor SOLID

## Antes

Todo vivía en un único `main.py` de ~1000 líneas: configuración, modelo de
MediaPipe, cálculo de extensión, enlace BLE, captura de cámara, dibujo y bucle
principal. Cualquier cambio (por ejemplo, probar otro transporte) obligaba a
tocar el mismo archivo y arrastraba dependencias de hardware.

## Después

| Principio | Dónde se aplica |
| --------- | --------------- |
| **S**ingle Responsibility | Cada módulo tiene una tarea: `CommandGate` decide *cuándo* enviar; `CarController` orquesta; `MediaPipeHandTracker` reconoce; `BleUartSender` transporta; `overlay` dibuja. |
| **O**pen/Closed | `ICommandSender` permite añadir transportes (BLE, dry-run, mocks) sin modificar `CarController`. `IGestureRecognizer` permite sustituir MediaPipe. |
| **L**iskov | `DryRunCommandSender` y `BleUartSender` cumplen el mismo contrato observable (`connected`, `sent`, `dropped`, `last_error`, `send`, `close`). |
| **I**nterface Segregation | Contratos pequeños y específicos: reconocer manos y enviar mensajes, nada más. |
| **D**ependency Inversion | `CarController` depende de `IGestureRecognizer`/`ICommandSender` y de entidades del dominio, no de MediaPipe ni bleak. `ConfigurationPanelController` depende de `IConfigStore`, no de YAML directamente. |

## Correspondencia con el código original

| Original | Nuevo |
| -------- | ----- |
| `Settings` + `parse_args` | `pc_app/config.py` (YAML + CLI) |
| `HandPose` | `pc_app/domain/entities/hand_pose.py` |
| `command_payload` + cuantización | `pc_app/domain/entities/wheel_command.py` |
| `CommandGate` | `pc_app/application/command_gate.py` |
| `HandTracker` | `pc_app/infrastructure/mediapipe_tracker.py` |
| `BleUartLink` | `pc_app/infrastructure/ble_uart.py` |
| `FrameGrabber` | `pc_app/infrastructure/camera.py` |
| `ensure_model` | `pc_app/infrastructure/model_loader.py` |
| `render` / `draw_hand` | `pc_app/presentation/overlay.py` |
| `asyncio` loop / `run` | `pc_app/application/car_controller.py` + `pc_app/main.py` |
| `main.py` | Lanzador compatible que delega en `pc_app.main.main` |
| — | `pc_app/infrastructure/config_store.py` (persistencia del panel) |
| — | `pc_app/application/config_panel.py` (eventos de Configuración) |

## Comportamiento preservado

- Un mensaje BLE por rueda, nunca `R150,L150`.
- `z` al arrancar, al perder una mano tras `lost_grace` y al salir.
- EMA por `(lado, dedo)`, reinicio al perder todas las manos.
- Espejo aplicado **antes** de la inferencia.
- Histéresis sobre la velocidad continua, no sobre la cuantizada.
- `--single-hand own|both` y tecla `h` para invertir lados.
- El esqueleto de la mano no lleva etiqueta IZQ/DER; esa información vive en
  el panel.

## Verificación

Al no existir suite de tests, la comprobación es:

```bash
.venv/bin/python -m py_compile main.py pc_app/**/*.py
.venv/bin/python main.py --help
.venv/bin/python main.py --image foto.jpg
.venv/bin/python main.py --dry-run --no-preview
```

También se probaron `CommandGate` y `CarController` con un `ICommandSender`
falso: cuantización, histéresis, `z` inicial/final, gracia de pérdida y
`single_hand=both`.
