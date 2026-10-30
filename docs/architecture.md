# Arquitectura

`PCAPP` es una aplicación de escritorio que lee la webcam, reconoce gestos de
mano con MediaPipe y envía órdenes de velocidad a un carrito con micro:bit por
BLE UART. El código sigue una separación por capas estilo SOLID: el dominio no
conoce OpenCV, MediaPipe ni bleak, y las dependencias apuntan siempre hacia
dentro.

## Capas y responsabilidades

| Capa | Ruta | Responsabilidad |
| ---- | ---- | --------------- |
| Dominio | `pc_app/domain/` | Entidades (`HandPose`, `WheelCommand`) y contratos (`IGestureRecognizer`, `ICommandSender`). Sin dependencias de infraestructura. |
| Configuración | `pc_app/config.py` | Carga de `config/settings.yaml` + `config/gestures.yaml`, validación y sobrescritura por CLI. |
| Aplicación | `pc_app/application/` | `CommandGate` (cuándo enviar) y `CarController` (orquestación, gracia de pérdida, parada segura). |
| Infraestructura | `pc_app/infrastructure/` | MediaPipe (`MediaPipeHandTracker`), webcam (`FrameGrabber`), BLE (`BleUartSender`), dry-run y descarga del modelo. |
| Presentación | `pc_app/presentation/` | Panel OpenCV (`overlay.py`) y ventana (`window.py`). |
| Entrada | `pc_app/main.py`, `main.py` | Composición de dependencias, bucle asíncrono y modos `--image` / `--list-devices`. |

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
- `config/gestures.yaml`: calibración (`curl_lo`, `curl_hi`, `smoothing`,
  `deadzone`) y `control_mode` (`own`/`both`).

Las rutas relativas de los YAML se resuelven desde la raíz del proyecto, no
desde el directorio de trabajo. `BASE_DIR` se calcula a partir de
`pc_app/config.py`.
