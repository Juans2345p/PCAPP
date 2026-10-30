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
.venv/bin/python main.py                        # control normal
.venv/bin/python main.py --dry-run              # sólo visión, sin BLE
.venv/bin/python main.py --no-preview           # sin ventana (Ctrl+C para salir)
.venv/bin/python main.py --list-devices         # escanear BLE y ver MACs
.venv/bin/python main.py --image mano.jpg       # calibrar con una foto
.venv/bin/python main.py --help
```

Teclas: `q` o `ESC` para salir; `h` invierte izquierda/derecha en caliente. Al
salir se envía siempre `z`.

## Configuración

Los valores viven en dos YAML y se pueden sobrescribir con flags:

- `config/settings.yaml`: cámara, MediaPipe, BLE, control y runtime.
- `config/gestures.yaml`: calibración de dedos y `control_mode`.

```bash
.venv/bin/python main.py --config config/settings.yaml --gestures config/gestures.yaml
.venv/bin/python main.py --step 8 --min-interval 0.06
.venv/bin/python main.py --name "BBC micro:bit"
```

Precedencia: valores por defecto < YAML < CLI. Las rutas relativas de los YAML
se resuelven desde la raíz del proyecto.

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

`--image` imprime rectitud cruda, extensión normalizada y velocidad por mano,
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
