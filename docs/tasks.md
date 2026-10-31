# Estado del Proyecto - PCAPP

- [x] Configurar MCP de pen.dev en OpenCode (`~/.opencode/config.json`)
- [x] Migrar proyecto de `/home/jemv/Documentos/Py/MediaPipe` a `/home/jemv/Documentos/Pro/PCAPP`
- [x] Crear estructura de carpetas (SOLID + Config + Docs)
- [x] Diseñar el dashboard en `design/car_control_ui.pen` y llevarlo a una
      interfaz web local con cámara, zonas, ruedas, estado y configuración
  - [x] Mantener el área de cámara dividida en avance, STOP y reversa
  - [x] Guardar ajustes automáticamente y explicar cada control con ayudas
  - [x] Añadir slider vertical de multiplicador en pasos de 0,1
  - [x] Añadir control de pantalla completa en el encabezado
- [x] Descargar hex del micro:bit a `car_app/` (`microbit-Carro-BLE-Plus.hex`).
      El código fuente `.ts` de MakeCode queda fuera de alcance.
- [x] Refactorizar `main.py` separando responsabilidades en `pc_app/`
      (Domain, Application, Infrastructure, Presentation)
- [x] Conectar carga de configuraciones desde `config/settings.yaml` y
      `config/gestures.yaml` (CLI sigue pudiendo sobrescribir)
- [x] Implementar eventos del panel de Configuración
  - [x] `PanelConfig` + contrato `IConfigStore`
  - [x] `YamlConfigStore`: lectura/escritura directa de ambos YAML
  - [x] `ConfigurationPanelController`: validación, persistencia y aplicación en vivo
  - [x] Aplicación en caliente sobre el `Settings` del bucle de visión
  - [x] Fábrica `build_config_panel()` en `pc_app/main.py`
- [x] Completar documentación técnica en `docs/`
  - [x] `docs/architecture.md` (incluye panel de configuración)
  - [x] `docs/solid_refactor.md`
  - [x] `docs/setup.md`
  - [x] `docs/api_reference.md`
- [x] Añadir `PyYAML` a `requirements.txt` e instalarlo en `.venv`
- [x] Verificar compilación, `--help`, carga de YAML y modo `--image`
- [x] Probar `CommandGate`/`CarController` con un `ICommandSender` simulado
      (cuantización, histéresis, `z` inicial/final, `lost_grace`, `single_hand`)
- [x] Probar `ConfigurationPanelController` + `YamlConfigStore` con copias
      temporales de los YAML (round-trip, comentarios, validación y recarga)
