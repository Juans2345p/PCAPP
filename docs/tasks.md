# Estado del Proyecto - PCAPP

- [x] Configurar MCP de pen.dev en OpenCode (`~/.opencode/config.json`)
- [x] Migrar proyecto de `/home/jemv/Documentos/Py/MediaPipe` a `/home/jemv/Documentos/Pro/PCAPP`
- [x] Crear estructura de carpetas (SOLID + Config + Docs)
- [x] Diseñar UI en `design/car_control_ui.pen` mediante el MCP `pencil`
- [x] Descargar código fuente micro:bit desde MakeCode a `car_app/` (el hex
      `microbit-Carro-BLE-Plus.hex` ya está disponible; falta el fuente `.ts`)
- [x] Refactorizar `main.py` separando responsabilidades en `pc_app/`
      (Domain, Application, Infrastructure, Presentation)
- [x] Conectar carga de configuraciones desde `config/settings.yaml` y
      `config/gestures.yaml` (CLI sigue pudiendo sobrescribir)
- [x] Completar documentación técnica en `docs/`
  - [x] `docs/architecture.md`
  - [x] `docs/solid_refactor.md`
  - [x] `docs/setup.md`
  - [x] `docs/api_reference.md`
- [x] Añadir `PyYAML` a `requirements.txt` e instalarlo en `.venv`
- [x] Verificar compilación, `--help`, carga de YAML y modo `--image`
- [x] Probar `CommandGate`/`CarController` con un `ICommandSender` simulado
      (cuantización, histéresis, `z` inicial/final, `lost_grace`, `single_hand`)
