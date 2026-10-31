# Control gestual → micro:bit por BLE (MediaPipe + OpenCV + bleak)

Control proporcional de velocidad de un carrito con micro:bit usando un solo
punto de cada mano: la muñeca. Arriba produce avance, abajo reversa y la zona
STOP ocupa el centro. Cada mano controla su propia rueda.

| Gesto                          | Comando           | Efecto                     |
| ------------------------------ | ----------------- | -------------------------- |
| Mano **izquierda**             | afecta a `L`      | rueda izquierda            |
| Mano **derecha**               | afecta a `R`      | rueda derecha              |
| Muñeca sobre STOP              | `n` > 0           | esa rueda avanza           |
| Muñeca dentro de STOP          | `0`               | esa rueda parada           |
| Muñeca bajo STOP               | `n` < 0           | esa rueda retrocede        |
| Sólo una mano visible          | la otra rueda = 0 | giro sobre esa rueda       |
| Ninguna mano en cámara         | `z`               | parada de emergencia       |

`n` va de **-255 a 255**. El panel permite ajustar la zona STOP, el suavizado
y el factor; el máximo efectivo nunca supera `max_speed` (hasta 255).

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
  presentation/          panel OpenCV y dashboard web local
    web/                 HTML, CSS y JavaScript del navegador
  main.py                bucle principal y modos --image/--list-devices
config/                  settings.yaml y gestures.yaml
docs/                    arquitectura, SOLID, instalación y API
design/                  diseño de referencia (pen.dev)
```

Más detalle en [`docs/architecture.md`](docs/architecture.md) y
[`docs/api_reference.md`](docs/api_reference.md).

## Uso

```bash
python main.py                        # dashboard en http://127.0.0.1:8765
python main.py --dry-run              # sólo visión, sin Bluetooth
python main.py --no-web-ui            # usar la ventana OpenCV
python main.py --web-port 9000        # cambiar puerto local
python main.py --list-devices         # ver dispositivos BLE y sus MAC
python main.py --address XX:XX:...    # otra MAC
python main.py --name "BBC micro:bit" # conectar por nombre
python main.py --debug                # métricas crudas en el panel
python main.py --image mano.jpg       # calibrar con una foto fija
```

Teclas: `q` o `ESC` para salir (al salir se envía `z`), `h` invierte las manos
si el orden físico depende de la cámara.

La configuración vive en dos YAML y los flags de CLI la sobrescriben:

- `config/settings.yaml`: cámara, MediaPipe, BLE y control.
- `config/gestures.yaml`: zona STOP, suavizado y `control_mode` (`own`/`both`).

```bash
python main.py --config config/settings.yaml --gestures config/gestures.yaml
python main.py --step 8 --min-interval 0.06
```

Precedencia: valores por defecto < YAML < CLI. Las rutas relativas de los YAML
se resuelven desde la raíz del proyecto.

La ventana abre a pantalla completa con la cámara a la izquierda y los paneles
de ruedas, estado y configuración a la derecha, siguiendo los controles del
diseño Pencil. Haz clic en los campos numéricos para editarlos; Enter o salir
del campo aplica y escribe automáticamente el valor en YAML. Arrastra el slider
vertical rojo para cambiar el multiplicador en pasos de 0,1; el valor aparece
dentro de la perilla. Pulsa el icono `i` junto a cada ajuste para abrir su ayuda
en un modal. El switch **EN MARCHA** pausa o reanuda el control (al pausar se
envía `z`). Usa el botón ⛶ del encabezado o `f` para alternar pantalla completa;
la interfaz se escala al área disponible.

Parámetros interesantes (los mostrados son los de `config/settings.yaml`):

| Flag              | Default | Descripción                                        |
| ----------------- | ------- | -------------------------------------------------- |
| `--max-speed`     | 255     | Velocidad máxima enviada                           |
| `--speed-multiplier` | 1.0   | Factor de salida (0.0–1.5), limitado a `max_speed` |
| `--step`          | 5       | Cambio mínimo para reenviar (histéresis)           |
| `--min-interval`  | 0.05    | Segundos mínimos entre escrituras BLE              |
| `--heartbeat`     | 1.0     | Reenvío periódico si no hay cambios (keep-alive)   |
| `--smoothing`     | 0.35    | Filtro EMA (más alto = más reactivo, más ruido)    |
| `--deadzone`      | 0.08    | Media anchura normalizada de la zona STOP          |
| `--lost-grace`    | 0.15    | Segundos antes de soltar una mano perdida          |
| `--swap-hands`    | on      | Invierte izquierda/derecha (tecla `h` en vivo)     |
| `--single-hand`   | `own`   | Con una sola mano: `own` = su rueda, `both` = las dos |

## Posición de muñeca y zona STOP

La aplicación conserva y suaviza únicamente la muñeca (landmark 0) de cada
mano. Su posición vertical se normaliza respecto al centro de la imagen.
MediaPipe detecta la mano con su modelo, pero la aplicación solo guarda, filtra,
dibuja y usa ese punto para controlar el movimiento.

```
posición = 1 - 2 × muñeca_y
```

`deadzone` ajusta el ancho de STOP tanto en el cálculo como en la banda dibujada
sobre la cámara. Fuera de ella, la velocidad se escala proporcionalmente y se
multiplica por `speed_multiplier`.

```
velocidad = signo(posición) × max(0, (abs(posición) - deadzone) / (1 - deadzone))
            × max_speed × speed_multiplier
```

La salida se limita a `±max_speed`; `max_speed` se valida entre 1 y 255, así
que el factor nunca hace que el carro reciba un valor superior a su límite.

Con `--image foto.jpg` se imprime la posición de muñeca y la velocidad.

### ¿Izquierda o derecha?

MediaPipe asume que la imagen ya viene espejada (selfie). El programa voltea el
frame con `--mirror` (por defecto), así que la etiqueta del modelo se usa tal
cual; si desactivas el espejo, se invierte automáticamente. Si aun así la mano
izquierda mueve el motor derecho, pulsa **`h`** en la ventana (o arranca con
`--swap-hands`). La cámara separa visualmente las zonas de mano izquierda y
derecha; cada rueda muestra la velocidad efectiva después de STOP y del factor.

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
