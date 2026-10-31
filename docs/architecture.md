# Arquitectura

`PCAPP` es una aplicación de escritorio que lee la webcam, reconoce gestos de
mano con MediaPipe y envía órdenes de velocidad a un carrito con micro:bit por
BLE UART. El código sigue una separación por capas estilo SOLID: el dominio no
conoce OpenCV, MediaPipe ni bleak, y las dependencias apuntan siempre hacia
dentro.

## Capas y responsabilidades

| Capa | Ruta | Responsabilidad |
| ---- | ---- | --------------- |
| Dominio | `pc_app/domain/` | Entidades (`HandPose`, `WheelCommand`, `PanelConfig`) y contratos (`IGestureRecognizer`, `ICommandSender`, `IConfigStore`). Sin dependencias de infraestructura. |
| Configuración | `pc_app/config.py` | Carga de `config/settings.yaml` + `config/gestures.yaml`, validación y sobrescritura por CLI. |
| Aplicación | `pc_app/application/` | `CommandGate` (cuándo enviar), `CarController` (orquestación, gracia de pérdida, parada segura) y `ConfigurationPanelController` (eventos del panel de ajustes). |
| Infraestructura | `pc_app/infrastructure/` | MediaPipe (`MediaPipeHandTracker`), webcam (`FrameGrabber`), BLE (`BleUartSender`), dry-run, descarga del modelo y persistencia YAML (`YamlConfigStore`). |
| Presentación | `pc_app/presentation/` | Panel OpenCV (`overlay.py`) y ventana (`window.py`). El diseño de escritorio vive en `design/car_control_ui.pen`. |
| Entrada | `pc_app/main.py`, `main.py` | Composición de dependencias, bucle asíncrono, fábrica `build_config_panel()` y modos `--image` / `--list-devices`. |

Dirección de dependencias:

```
main -> application -> domain
  |          ^
  v          |
infrastructure / presentation
```

`domain` no importa nada de las capas externas. `application` sólo depende de
`domain` y de `Settings`. La infraestructura implementa los contratos del
dominio.

## Flujo de un frame

1. `FrameGrabber` lee la webcam en un hilo y publica el último frame.
2. El bucle de `pc_app/main.py` detecta un frame nuevo y aplica el espejo si
   `settings.mirror`.
3. `MediaPipeHandTracker.process()` corre en un `ThreadPoolExecutor` de un
   worker (nunca en el event loop) y devuelve `{"L": HandPose, "R": HandPose}`.
4. `CarController.update()` calcula la velocidad de cada rueda, aplica
   `--single-hand`, la gracia de pérdida por lado y llama a `CommandGate.feed()`.
5. Si la puerta decide enviar, `ICommandSender.send()` encola los mensajes
   (`L{n}` y `R{n}` como elementos separados, o `z`).
6. `BleUartSender` los escribe en escrituras BLE independientes.
7. La capa de presentación dibuja el esqueleto y el panel de estado.

## Seguridad y protocolo

- `z` se envía al arrancar, cuando una rueda lleva más de `lost_grace` sin
  mano, y al salir (`close("z")`).
- El firmware **no** acepta dos motores en una línea. `WheelCommand.messages()`
  devuelve `("z",)` si ambas ruedas están a 0; en caso contrario devuelve
  `(f"L{left}", f"R{right}")`, que el transporte escribe por separado.
- Las UUID son las del firmware del proyecto: escritura
  `6e400003-b5a3-f393-e0a9-e50e24dcca9e`, notificación
  `6e400002-b5a3-f393-e0a9-e50e24dcca9e`. Están invertidas respecto al NUS
  estándar a propósito.
- La cola BLE es de tamaño 1: si el enlace va lento se descarta la orden
  antigua y se conserva la más reciente.

## Configuración

Precedencia: valores por defecto de `Settings` < YAML < flags de CLI.

- `config/settings.yaml`: cámara, MediaPipe, BLE, control y runtime.
- `config/gestures.yaml`: `smoothing`, `deadzone` y `control_mode` (`own`/`both`).
  `deadzone` define la banda STOP de velocidad y su altura visible.

Las rutas relativas de los YAML se resuelven desde la raíz del proyecto, no
desde el directorio de trabajo. `BASE_DIR` se calcula a partir de
`pc_app/config.py`.

## Panel de configuración (UI)

El dashboard web sirve cámara y controles en `127.0.0.1` (puerto configurable,
8765 por defecto): zonas ADELANTE/STOP/ATRÁS a la izquierda, ruedas, estado y
ajustes a la derecha. El botón ⛶ y `f` alternan pantalla completa; `h` invierte
la asignación; `q`/`ESC` sale. El multiplicador va de 0 a 1,5 en pasos de 0,1
y su valor se centra en la perilla. Las ayudas de los ajustes se abren mediante
iconos `i` en un modal centrado.

Controles y destino en los YAML:

| Control de la UI | Campo | Archivo |
| ---------------- | ----- | ------- |
| Modo `OWN` / `BOTH` | `control_mode` y `control.single_hand` | `config/gestures.yaml` + `config/settings.yaml` |
| Dispositivo BLE | `ble.device_name` | `config/settings.yaml` |
| Dirección MAC | `ble.address` | `config/settings.yaml` |
| Espejo de cámara | `camera.mirror` | `config/settings.yaml` |
| Zona STOP y suavizado | `calibration.deadzone` / `calibration.smoothing` | `config/gestures.yaml` |
| Paso, pérdida y multiplicador | `control.step` / `control.lost_grace` / `control.speed_multiplier` | `config/settings.yaml` |

La aplicación conserva y suaviza solo el punto de muñeca (landmark 0) de cada
mano. Los parámetros `curl_lo` / `curl_hi` siguen en los YAML por compatibilidad
con configuraciones anteriores y ya no intervienen en el control.
MediaPipe produce la detección de mano; la lógica posterior solo conserva y
consume la muñeca.

Flujo de eventos:

1. `build_config_panel(settings)` crea un `ConfigurationPanelController` con
   `YamlConfigStore`.
2. Al abrir la pantalla, el controlador lee ambos YAML (`read_panel()`).
3. Cada campo llama a su evento `set_*`; el valor validado se aplica en caliente
   al objeto `Settings` y se escribe de inmediato en los YAML.
4. El siguiente frame usa el valor nuevo. Un cambio de nombre/MAC BLE se aplica
   en la siguiente reconexión del enlace.

La escritura es quirúrgica: `YamlConfigStore` sustituye sólo los escalares
gestionados por la UI y conserva comentarios, orden y el resto de claves.
