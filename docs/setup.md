# Instalación y puesta en marcha

## Requisitos del sistema (Fedora Linux)

```bash
sudo dnf install libgomp mesa-libGL libglvnd-glx python3.11-devel bluez
sudo systemctl enable --now bluetooth
```

OpenCV necesita `libgomp` y `mesa-libGL`/`libglvnd-glx`. El BLE necesita el
servicio `bluetooth` activo. En Wayland puro puede hacer falta
`QT_QPA_PLATFORM=xcb` para que `cv2.imshow` abra la ventana.

## Entorno Python

Se recomienda Python 3.11 (los wheels de MediaPipe/OpenCV para 3.14 pueden
fallar). Desde la raíz del proyecto:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Dependencias principales: `mediapipe` (Tasks API), `opencv-python`, `numpy`,
`bleak` y `PyYAML` (para `config/*.yaml`).

En el primer arranque se descarga `hand_landmarker.task` (~7.5 MB) si no está
en la raíz del proyecto.

## Ejecución

```bash
.venv/bin/python main.py                        # interfaz web en http://127.0.0.1:8765
.venv/bin/python main.py --dry-run              # sólo visión, sin BLE
.venv/bin/python main.py --no-web-ui            # usar la ventana OpenCV
.venv/bin/python main.py --web-port 9000        # elegir otro puerto local
.venv/bin/python main.py --no-preview           # sin interfaz (Ctrl+C para salir)
.venv/bin/python main.py --list-devices         # escanear BLE y ver MACs
.venv/bin/python main.py --image mano.jpg       # calibrar con una foto
.venv/bin/python main.py --help
```

Teclas: `q` o `ESC` para salir; `h` invierte izquierda/derecha en caliente. La
configuración inicial corrige el orden de manos observado; al
salir se envía siempre `z`.

## Configuración

Los valores viven en dos YAML y se pueden sobrescribir con flags:

- `config/settings.yaml`: cámara, MediaPipe, BLE, control y runtime.
- `config/gestures.yaml`: zona STOP, suavizado y `control_mode`.

```bash
.venv/bin/python main.py --config config/settings.yaml --gestures config/gestures.yaml
.venv/bin/python main.py --step 8 --min-interval 0.06
.venv/bin/python main.py --name "BBC micro:bit"
```

Precedencia: valores por defecto < YAML < CLI. Las rutas relativas de los YAML
se resuelven desde la raíz del proyecto.

## Panel de Configuración (UI)

La interfaz web local muestra cámara, ruedas, estado y configuración. Abre
`http://127.0.0.1:8765` en el mismo equipo. Los campos se guardan
automáticamente; el multiplicador usa pasos de 0,1 y muestra su valor dentro de
la perilla roja. Los iconos `i` abren ayudas en un modal centrado. El botón ⛶ o
la tecla `f` activa pantalla completa. El switch pausa el control y envía `z`.
La transmisión no requiere dependencias adicionales.

Los valores configurables son:

- zona STOP y suavizado → `config/gestures.yaml`
- paso, pérdida y multiplicador → `config/settings.yaml`

En Python, `build_config_panel(settings)` crea el controlador de eventos.
Cada `set_*` aplica los cambios en caliente y los escribe automáticamente en
ambos YAML. Los cambios de `mirror`, calibración y modo
surten efecto en el siguiente frame; un cambio de MAC/nombre BLE se aplica en
la siguiente reconexión.

## Comprobaciones sin hardware

```bash
# Sintaxis de todo el paquete
.venv/bin/python -m py_compile main.py pc_app/config.py pc_app/main.py \
  pc_app/application/*.py pc_app/domain/entities/*.py \
  pc_app/domain/interfaces/*.py pc_app/infrastructure/*.py \
  pc_app/presentation/*.py

# Ayuda y carga de configuración
.venv/bin/python main.py --help

# Modelo + inferencia con una imagen (sin cámara ni micro:bit)
.venv/bin/python main.py --image /ruta/foto.jpg
```

`--image` imprime posición vertical de muñeca y velocidad por mano,
además del comando resultante. Añade `--swap-hands` para comprobar el
intercambio de lados.

## Problemas frecuentes

| Síntoma | Solución |
| ------- | -------- |
| No conecta por BLE | `main.py --list-devices`, revisa MAC/nombre y que el micro:bit no esté emparejado con otro equipo. |
| La mano izquierda mueve la rueda derecha | Pulsa `h` o usa `--swap-hands`. |
| `ModuleNotFoundError: yaml` | `pip install -r requirements.txt` dentro del venv. |
| `libGL error` / no abre ventana | Instala `mesa-libGL libglvnd-glx`; prueba `QT_QPA_PLATFORM=xcb`. |
| Va a tirones | Baja `--width/--height` o sube `--step`. |
| Se mueve con la mano quieta | Sube `--deadzone` o baja `--smoothing`. |
