# Control gestual → micro:bit por BLE (MediaPipe + OpenCV + bleak)

Control proporcional de velocidad de un carrito con micro:bit usando la
**extensión del dedo índice y del dedo medio** frente a la webcam. Cada mano
controla su propia rueda, así que con las dos manos se consigue **giro
diferencial** tipo tanque.

| Gesto                          | Comando           | Efecto                     |
| ------------------------------ | ----------------- | -------------------------- |
| Mano **izquierda**             | afecta a `L`      | rueda izquierda            |
| Mano **derecha**               | afecta a `R`      | rueda derecha              |
| Índice extendido (proporción)  | `n` > 0           | esa rueda avanza           |
| Medio extendido (proporción)   | `n` < 0           | esa rueda retrocede        |
| Puño / dedos cerrados          | `0`               | esa rueda parada           |
| Sólo una mano visible          | la otra rueda = 0 | giro sobre esa rueda       |
| Ninguna mano en cámara         | `z`               | parada de emergencia       |

`n` va de **-255 a 255** y es proporcional a la rectitud del dedo
(0 % = dedo cerrado, 100 % = dedo totalmente extendido).

Ejemplos (cada rueda viaja en un mensaje BLE separado): `L200` + `R200` avanza
recto · `L80` + `R200` gira a la izquierda · `L150` + `R-150` gira sobre sí mismo.

## Requisitos (Fedora Linux)

```bash
sudo dnf install libgomp mesa-libGL libglvnd-glx python3.11-devel bluez
sudo systemctl enable --now bluetooth
```

Python 3.11 recomendado (los wheels de MediaPipe/OpenCV para 3.14 pueden fallar).

## Instalación

```bash
cd ~/Documentos/Pro/PCAPP
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

En el primer arranque se descarga automáticamente `hand_landmarker.task`
(~7.5 MB) si no está en la carpeta del proyecto.

## Estructura del código

```
main.py                  lanzador compatible -> pc_app.main
pc_app/
  config.py              Settings + carga de YAML + CLI
  domain/                HandPose, WheelCommand y contratos
  application/           CommandGate y CarController
  infrastructure/        MediaPipe, cámara, BLE, dry-run, modelo
  presentation/          panel OpenCV y ventana
  main.py                bucle principal y modos --image/--list-devices
config/                  settings.yaml y gestures.yaml
docs/                    arquitectura, SOLID, instalación y API
design/                  diseño de referencia (pen.dev)
```

Más detalle en [`docs/architecture.md`](docs/architecture.md) y
[`docs/api_reference.md`](docs/api_reference.md).

## Uso

```bash
python main.py                        # control normal
python main.py --dry-run              # sólo visión, sin Bluetooth
python main.py --list-devices         # ver dispositivos BLE y sus MAC
python main.py --address XX:XX:...    # otra MAC
python main.py --name "BBC micro:bit" # conectar por nombre
python main.py --debug                # métricas crudas en el panel
python main.py --image mano.jpg       # calibrar con una foto fija
```

Teclas: `q` o `ESC` para salir (al salir se envía `z`).

La configuración vive en dos YAML y los flags de CLI la sobrescriben:

- `config/settings.yaml`: cámara, MediaPipe, BLE y control.
- `config/gestures.yaml`: calibración de dedos y `control_mode` (`own`/`both`).

```bash
python main.py --config config/settings.yaml --gestures config/gestures.yaml
python main.py --step 8 --min-interval 0.06
```

Precedencia: valores por defecto < YAML < CLI. Las rutas relativas de los YAML
se resuelven desde la raíz del proyecto.

El diseño `design/car_control_ui.pen` incluye una pantalla **Configuración**
(pestaña `AJUSTES`) con vista previa, telemetría L/R y controles editables de
calibración, modo de control, BLE/MAC y espejo. Sus eventos están implementados
en `pc_app` mediante `ConfigurationPanelController` + `YamlConfigStore`, que
escriben directamente en ambos YAML al pulsar **Guardar Configuración**.

Parámetros interesantes (los mostrados son los de `config/settings.yaml`):

| Flag              | Default | Descripción                                        |
| ----------------- | ------- | -------------------------------------------------- |
| `--max-speed`     | 255     | Velocidad máxima enviada                           |
| `--step`          | 5       | Cambio mínimo para reenviar (histéresis)           |
| `--min-interval`  | 0.05    | Segundos mínimos entre escrituras BLE              |
| `--heartbeat`     | 1.0     | Reenvío periódico si no hay cambios (keep-alive)   |
| `--smoothing`     | 0.35    | Filtro EMA (más alto = más reactivo, más ruido)    |
| `--deadzone`      | 0.08    | Zona muerta inicial (evita derivas en reposo)      |
| `--curl-lo/hi`    | 0.30/0.97 | Rectitud que mapea a 0 % / 100 % de extensión    |
| `--lost-grace`    | 0.15    | Segundos antes de soltar una mano perdida          |
| `--swap-hands`    | off     | Invierte izquierda/derecha (tecla `h` en vivo)     |
| `--single-hand`   | `own`   | Con una sola mano: `own` = su rueda, `both` = las dos |

## Cómo se calcula la extensión

Para cada dedo se toman los 4 puntos MCP → PIP → DIP → TIP y se mide:

```
rectitud = distancia(MCP, TIP) / (|MCP-PIP| + |PIP-DIP| + |DIP-TIP|)
```

Dedo recto ≈ 0.99, dedo cerrado ≈ 0.20. Es invariante a la distancia a la
cámara, al tamaño de la mano y a su rotación. Luego se normaliza a 0..1 con
`--curl-lo/--curl-hi`, se aplica zona muerta y un filtro EMA **por mano**.

```
velocidad_izquierda = (ext_índice_izq - ext_medio_izq) * max_speed
velocidad_derecha   = (ext_índice_der - ext_medio_der) * max_speed
```

Con `--image foto.jpg` se imprimen los valores crudos de cada mano para ajustar
los rangos.

### ¿Izquierda o derecha?

MediaPipe asume que la imagen ya viene espejada (selfie). El programa voltea el
frame con `--mirror` (por defecto), así que la etiqueta del modelo se usa tal
cual; si desactivas el espejo, se invierte automáticamente. Si aun así la mano
izquierda mueve el motor derecho, pulsa **`h`** en la ventana (o arranca con
`--swap-hands`). En el vídeo ya no se etiqueta cada mano; fíjate en qué barra
de rueda (`IZQ`/`DER`) del panel se mueve al extender un dedo.

## Protocolo serie (ASCII, terminado en `\n`)

El firmware **no** acepta los dos motores en la misma línea (nada de
`R150,L150`). Cada rueda se envía en un mensaje independiente, en dos
escrituras BLE separadas, primero izquierda y después derecha:

```
L150\n         rueda izquierda +150
R150\n         rueda derecha   +150
L-80\n         rueda izquierda atrás
R0\n           rueda derecha parada
z\n            parada / e-stop (un único mensaje)
```

Ejemplo de una orden completa para avanzar recto: primero llega `L150\n` y
después `R150\n`.

## Lado micro:bit (ejemplo MakeCode)

```ts
bluetooth.startUartService()
let izq = 0
let der = 0

bluetooth.onUartDataReceived(serial.delimiters(Delimiters.NewLine), function () {
    let linea = bluetooth.uartReadUntil(serial.delimiters(Delimiters.NewLine)).trim()
    if (linea == "z") {
        izq = 0; der = 0
    } else if (linea.charAt(0) == "L") {
        izq = parseInt(linea.substr(1))
    } else if (linea.charAt(0) == "R") {
        der = parseInt(linea.substr(1))
    }
    // Sustituye por tu driver (L298N, Maqueen, Kitronik...)
    motors.dualMotorPower(Motor.M0, izq)
    motors.dualMotorPower(Motor.M1, der)
})
```

> Si tu receptor espera las órdenes antiguas (`w`, `s`, `z`…), tendrás que
> adaptarlo a este formato numérico.

## Solución de problemas

- **No conecta**: `python main.py --list-devices`, comprueba la MAC y que el
  micro:bit esté encendido y no emparejado con otro dispositivo.
- **La mano izquierda mueve la rueda derecha**: pulsa `h` en la ventana o usa
  `--swap-hands`. Comprueba en el panel qué barra de rueda se mueve.
- **Sólo quiero usar una mano**: `--single-hand both` (esa mano mueve las dos
  ruedas); por defecto `own` deja la rueda contraria parada.
- **`org.bluez.Error.NotPermitted` / permisos**: revisa `bluetoothctl` y que el
  servicio `bluetooth` esté activo.
- **`libGL error` / no abre la ventana**: instala `mesa-libGL libglvnd-glx`;
  en Wayland puro prueba `QT_QPA_PLATFORM=xcb python main.py`.
- **Va a tirones**: baja `--width/--height` a 320x240 o sube `--step`.
- **Se mueve solo con la mano quieta**: sube `--deadzone` o baja `--smoothing`.
