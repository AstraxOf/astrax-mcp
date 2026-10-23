# 🛰️ Astrax

### **A.S.T.R.A.X.** — *Agentic System Telemetry, Realtime Automation & X-control*

Servidor **MCP (Model Context Protocol)** en Python que le da a tu IA **ojos y manos** sobre tu pantalla: ver, hacer clic, escribir y ejecutar tareas de varios pasos **sin saturar el contexto**.

Compatible con **Claude Desktop, Roo Code, Cline, Cursor, Windsurf, Gemini CLI, OpenCode** y cualquier cliente MCP con transporte `stdio`. Funciona con modelos locales (Ollama) y APIs comerciales (Claude, Gemini…).

📺 **Tutorial en YouTube:** [@AstraxOf](https://youtube.com/@AstraxOf)
💬 **Contacto en Telegram:** [@RufusOficial](https://t.me/RufusOficial)

---

## ⚡ Instalación a 1 clic

Necesitas [`uv`](https://docs.astral.sh/uv/) (instala Python y dependencias solo):

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Después, **un solo comando** detecta tu sistema operativo y tus clientes MCP, y registra Astrax en ellos:

```bash
uvx --from git+https://github.com/AstraxOf/astrax-mcp.git astrax-install --yes
```

Reinicia tu cliente (en Claude Desktop, ciérralo por completo) y listo.

> Cuando el paquete esté publicado en PyPI bastará `uvx astrax-mcp` para ejecutar el servidor y `uvx --from astrax-mcp astrax-install --yes` para instalarlo.

### 🤖 Instrucción para IAs (agentes con acceso a terminal)

Si eres una IA y el usuario te pide instalar Astrax, ejecuta exactamente esto y pídele que reinicie su cliente MCP. **No edites archivos JSON a mano.**

```bash
uvx --from git+https://github.com/AstraxOf/astrax-mcp.git astrax-install --yes
```

Variantes útiles:

| Comando | Qué hace |
|---|---|
| `astrax-install --list` | Muestra clientes detectados y si Astrax ya está instalado |
| `astrax-install --client claude-desktop` | Instala solo en un cliente (repetible). IDs: `claude-desktop`, `roo-code`, `cline`, `cursor`, `windsurf`, `gemini-cli` |
| `astrax-install --auto-approve` | Roo Code / Cline: añade `alwaysAllow` a todas las herramientas **excepto** `astrax_tarea_autorizar` (ver [Permisos](#-permisos-una-sola-autorización-por-tarea)) |
| `astrax-install --dry-run` | Muestra qué haría sin escribir nada |
| `astrax-install --uninstall` | Elimina solo la entrada `astrax` |
| `astrax-install --source local` | Usa el Python actual en vez de `uvx` |

El instalador **solo toca la clave `astrax`** dentro de `mcpServers`: conserva tus otros servidores, crea una copia `.astrax-bak-<fecha>` antes de escribir, guarda de forma atómica y **no modifica archivos con JSON inválido**.

**Claude Code:** `claude mcp add astrax -- uvx --from git+https://github.com/AstraxOf/astrax-mcp.git astrax-mcp`

<details>
<summary>Instalación desde un clon del repositorio</summary>

```bash
git clone https://github.com/AstraxOf/astrax-mcp.git
cd astrax-mcp
python install.py          # asistente interactivo (equivale a astrax-install)
```

</details>

---

## 🧠 Motor paso a paso por estado temporal

Los modelos ligeros (Ollama) se saturan y alucinan cuando el contexto crece con historial y capturas de pantalla viejas. Astrax lo evita **aislando el contexto en un archivo de estado local**: `.astrax_task_state.json`.

1. **Desglose.** Ante una petición compleja (*"Redacta una carta para X con mis datos, prepárala y envíala a tal correo"*), la IA llama a `astrax_tarea_crear` y guarda el plan como pasos ordenados.
2. **Lectura directa.** Para cada paso, la IA llama a `astrax_tarea_estado`: recibe solo el **paso actual, el siguiente y los datos guardados** (un JSON de unas pocas líneas) en lugar de releer toda la conversación, el prompt inicial o capturas pasadas.
3. **Caché de salidas.** Al cerrar un paso con `astrax_tarea_completar_paso`, la IA guarda lo relevante, por ejemplo `{"pdf_generado": "/rutas/carta.pdf"}`. El paso siguiente (adjuntar al correo) consulta solo ese dato y usa la ruta exacta, sin adivinarla.
4. **Cierre.** Al terminar el último paso la tarea queda `completada`, los permisos se **revocan** y se borran las capturas temporales. `astrax_tarea_limpiar` elimina el archivo.

Detalles que protegen al modelo:

- **Guarda rutas, no contenidos:** cada dato admite hasta 4000 caracteres; si es más, la herramienta pide guardarlo en un archivo y almacenar la ruta.
- **Anti-bucles:** un paso que falla 3 veces pasa a `bloqueada` y la IA debe parar y explicar al usuario qué ocurrió.
- **Una imagen por lote, no por acción:** `astrax_acciones` ejecuta varias acciones y devuelve **una sola** captura final (reducida automáticamente para gastar menos tokens).
- **Ubicación:** carpeta privada del usuario (`~/.cache/astrax`, `~/Library/Caches/astrax` o `%LOCALAPPDATA%\astrax`), con permisos restringidos. Cámbiala con `ASTRAX_HOME`.

---

## 🔐 Permisos: una sola autorización por tarea

Antes de ejecutar nada, la IA declara **todo lo que necesitará la tarea completa** en `astrax_tarea_crear`:

| Permiso | Habilita |
|---|---|
| `pantalla` | `astrax_ver_pantalla`, `astrax_capturar_pantalla` y la captura final/intermedia de `astrax_acciones` |
| `raton_teclado` | todas las acciones de ratón y teclado de `astrax_acciones` (clic, arrastrar, escribir, mantener teclas, scroll…) |
| `portapapeles` | `astrax_portapapeles` y escritura de texto no ASCII (ñ, tildes, emojis) dentro de un lote |
| `terminal` | `astrax_ejecutar_comando` y la acción `comando` de un lote |

Después muestra el plan y los permisos, **pide tu confirmación una sola vez** y llama a `astrax_tarea_autorizar`. Desde ese momento puede trabajar de forma desatendida durante la sesión (60 min por defecto, `ASTRAX_SESSION_MINUTES`). Las herramientas de acción **rechazan** cualquier uso fuera de una tarea autorizada o de un permiso no solicitado. Con `astrax_acciones` los permisos se comprueban **para el lote completo antes de empezar**: o se puede todo, o no se mueve nada.

**Cómo evitar las confirmaciones por paso en tu cliente:** el servidor no puede saltarse las confirmaciones que muestra el cliente. Por eso `astrax-install --auto-approve` (Roo Code / Cline) marca como "permitir siempre" todas las herramientas *excepto* `astrax_tarea_autorizar`: tu cliente te pregunta **una vez**, justo en la autorización, y no durante la ejecución. En otros clientes (p. ej. Claude Desktop) elige "Permitir siempre" en esa herramienta o en el resto cuando te lo pida.

Para volver al comportamiento anterior sin tareas ni sesiones: `ASTRAX_REQUIRE_SESSION=0`.

---

## ✨ ¿Qué puede hacer?

| Herramienta | Descripción |
|---|---|
| `astrax_tarea_crear` | Guarda el plan por pasos y los permisos que necesita la tarea completa |
| `astrax_tarea_autorizar` | Concede los permisos tras la confirmación del usuario |
| `astrax_tarea_estado` | Lee el paso actual, el siguiente y los datos guardados |
| `astrax_tarea_guardar` | Guarda un dato clave (rutas, ids…) |
| `astrax_tarea_completar_paso` | Cierra el paso, guarda salidas y devuelve el siguiente |
| `astrax_tarea_limpiar` | Borra el estado y las capturas temporales |
| `astrax_acciones` | **Multi-acción**: ejecuta N acciones de ratón/teclado en una sola llamada y devuelve una captura final (ver [Multi-acción](#-multi-acción-una-mirada-muchas-acciones)) |
| `astrax_ver_pantalla` | La IA ve la pantalla (marca roja en el cursor). Admite `escala` y `region` (zoom para leer texto pequeño) |
| `astrax_capturar_pantalla` | Guarda un PNG y devuelve la ruta |
| `astrax_info_pantalla` | Tamaño real de la pantalla y escala de imagen por defecto |
| `astrax_portapapeles` | Lee o escribe el portapapeles |
| `astrax_ejecutar_comando` | Ejecuta un comando de shell con timeout y salida recortada |

Ejemplo de prompt:

> *"Usa Astrax: redacta una carta para Ana con mis datos, guárdala como PDF y envíala a ana@ejemplo.com con el asunto 'Propuesta'."*

---

## ⚡ Multi-acción: una mirada, muchas acciones

Antes, cada acción era un turno: *mirar → mover el ratón → mirar → clic → mirar → escribir…* Cada turno costaba una ida y vuelta al modelo (latencia) y una imagen (tokens).

Ahora la IA **mira una vez, planifica y manda varias acciones juntas** con `astrax_acciones`, y recibe **una sola** captura al final:

```json
{"acciones": [
  {"a": "atajo", "teclas": ["ctrl", "l"]},
  {"a": "escribir", "texto": "youtube.com", "enter": true},
  {"a": "esperar", "seg": 2},
  {"a": "clic", "x": 640, "y": 90},
  {"a": "escribir", "texto": "lofi", "enter": true}
]}
```

Cinco acciones = **1 llamada y 1 imagen** (antes: 5 y 5).

> **Migración (v0.3.0):** `astrax_clic`, `astrax_doble_clic`, `astrax_escribir`, `astrax_tecla`, `astrax_atajo`, `astrax_scroll` y `astrax_esperar` se sustituyen por `astrax_acciones` (menos herramientas = menos tokens de definición en cada turno). Si usas `alwaysAllow`, vuelve a ejecutar `astrax-install --auto-approve`.

### Acciones disponibles

| Acción | Campos | Para qué |
|---|---|---|
| `mover` / `mover_rel` | `x,y` / `dx,dy` | Posicionar el cursor (hover, mirar con el ratón) |
| `clic` | `x,y`, `b` (left/right/middle), `n` (1-3) | Clic; sin `x,y` clica donde está el cursor |
| `doble_clic` | `x,y` | Abrir archivos, seleccionar palabra |
| `arrastrar` | `x,y,x2,y2`, `dur` | Arrastrar y soltar, seleccionar, mover ventanas |
| `raton_abajo` / `raton_arriba` | `b`, `x,y` | Pulsar/soltar el botón por separado |
| `escribir` | `texto`, `enter` | Teclea texto (ñ, tildes y emojis vía portapapeles) |
| `tecla` | `tecla`, `n` | Una tecla, o atajo con `"ctrl+l"` |
| `atajo` | `teclas: [...]` | 2-4 teclas a la vez |
| `abajo` / `arriba` | `teclas` | Mantener/soltar teclas manualmente |
| `mantener` | `teclas` y/o `b`, `seg` (≤10), `mientras: [acciones]` | Mantener pulsado mientras pasa algo (correr, apuntar, cargar un disparo) |
| `scroll` | `n` (positivo = arriba), `x,y` | Rueda del ratón |
| `esperar` | `seg` | Esperar a que cargue |
| `captura` | `escala`, `region: [x,y,w,h]` | Fotograma intermedio barato (hasta 5 por lote) |
| `portapapeles` | `op` (leer/escribir), `texto` | Leer/escribir el portapapeles |
| `comando` | `cmd`, `timeout`, `dir` | Shell (requiere permiso `terminal`) |
| `repetir` | `n` (≤50), `acciones` | Bucle (máx. 2 niveles; máx. 80 acciones por lote tras expandir) |

Opciones de la llamada: `captura_final` (por defecto `true`), `escala` (0.2-1.0) y `espera_final` (segundos que se deja asentar la interfaz antes de la foto).

### Garantías

- **Validación previa de todo el lote.** Antes de mover nada se hace una pasada en seco con los mismos manejadores que la ejecución real: teclas inexistentes, coordenadas fuera de pantalla, campos que faltan, comandos peligrosos, límite de tiempo y permisos. Si algo falla, **no se ejecuta ninguna acción** y se indica cuál es.
- **Si falla una acción durante la ejecución,** el lote se detiene, se informa cuántas se hicieron y se envía la captura del estado real.
- **Nada queda pulsado.** Teclas y botones mantenidos se sueltan siempre al terminar, incluso con error o fail-safe.
- **Fail-safe intacto:** ratón a una esquina = aborto inmediato.

### Menos tokens sin perder precisión

Las imágenes se reducen automáticamente (lado mayor `ASTRAX_MAX_LADO`, por defecto 1280 px). La IA da siempre **coordenadas en píxeles de la última imagen que recibió** y el servidor las convierte a la pantalla real; no hay cuentas que hacer. Para leer texto pequeño: `astrax_ver_pantalla` con `region` (zoom 1:1) o una acción `captura` con `region`.

### 🎮 Modo juego y tareas "como un humano"

Con ratón, teclado, arrastre, teclas mantenidas, bucles y fotogramas intermedios, la IA puede usar casi cualquier programa o juego como lo haría una persona. Ejemplo (plataformas):

```json
{"acciones": [
  {"a": "mantener", "teclas": ["right"], "mientras": [
    {"a": "esperar", "seg": 0.4}, {"a": "tecla", "tecla": "space"},
    {"a": "esperar", "seg": 0.6}, {"a": "tecla", "tecla": "space"}
  ]},
  {"a": "captura"},
  {"a": "tecla", "tecla": "x"}
]}
```

Para jugar: pide *"Usa Astrax para jugar a X"*, autoriza la tarea con `pantalla` + `raton_teclado` y (si quieres sesiones largas) sube `ASTRAX_SESSION_MINUTES`.

**Limitación real:** la IA decide por turnos y cada llamada tiene la latencia del modelo. Funcionan muy bien los juegos por turnos, de puzles, estrategia, cartas, navegador, idle/clicker y plataformas pausados o tolerantes. Los juegos que exigen reflejos de milisegundos (shooters, ritmo rápido) solo se pueden jugar de forma limitada: `mantener`, `repetir` y los fotogramas del lote reducen el problema, pero no lo eliminan. Respeta además los términos de servicio del juego (muchos online prohíben automatizar el input).

### Variables de entorno de velocidad

| Variable | Defecto | Efecto |
|---|---|---|
| `ASTRAX_MAX_LADO` | `1280` | Lado mayor de la imagen enviada (menos = menos tokens) |
| `ASTRAX_JPEG_QUALITY` | `65` | Calidad JPEG (30-95) |
| `ASTRAX_PAUSA` | `0.03` | Pausa entre acciones de un lote (s) |
| `ASTRAX_MOVE_SEG` | `0.05` | Duración del movimiento del ratón antes de clicar (s) |
| `ASTRAX_TYPE_INTERVAL` | `0.005` | Pausa entre caracteres al escribir (s) |
| `ASTRAX_ESPERA_FINAL` | `0.25` | Espera antes de la captura final (s) |
| `ASTRAX_MAX_ACCIONES` | `80` | Máximo de acciones por lote |
| `ASTRAX_MAX_TOTAL_SEG` | `60` | Máximo de esperas + mantenidos por lote (s) |

Si una app ignora clics muy rápidos, sube `ASTRAX_MOVE_SEG` (p. ej. `0.15`) y `ASTRAX_PAUSA`.

---

## ⚙️ Configuración manual

Si prefieres no usar el instalador, añade esto a tu `mcp_settings.json` (o al archivo equivalente de tu cliente):

```json
{
  "mcpServers": {
    "astrax": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/AstraxOf/astrax-mcp.git", "astrax-mcp"]
    }
  }
}
```

> En clientes de escritorio que no heredan tu `PATH`, usa la ruta absoluta de `uvx` (`which uvx` / `where uvx`). El instalador ya lo hace por ti.

---

## 🛡️ Seguridad

Astrax controla tu ratón, teclado y (si lo autorizas) tu terminal reales. Úsalo con cabeza:

- **Fail-safe activo:** mueve el ratón a una esquina de la pantalla para abortar cualquier automatización.
- **Permisos mínimos:** la IA solo recibe los permisos que declara y que tú confirmas; se revocan al terminar o al bloquearse la tarea.
- Los clics fuera de los límites de la pantalla se rechazan.
- `astrax_ejecutar_comando` bloquea patrones destructivos obvios (`rm -rf /`, `mkfs`, `format C:`, `shutdown`…). **Es una red de seguridad contra accidentes, no un sandbox.** Concede `terminal` solo si confías en la tarea y la supervisas.
- Evita ejecutarlo mientras tengas abiertos datos sensibles (contraseñas, banca, etc.).

---

## 🖥️ Notas por sistema operativo

- **Windows:** funciona sin configuración extra.
- **macOS:** concede permisos de *Grabación de pantalla* y *Accesibilidad* a tu terminal o editor.
- **Linux:** funciona en X11 (Wayland suele bloquear captura y control). Puede hacer falta `sudo apt install python3-tk python3-dev scrot xclip`.

---

## 🧩 Arquitectura

```
astrax-mcp/
├── pyproject.toml          # entry points: astrax-mcp, astrax-install
├── install.py              # atajo para quien clona el repo
├── mcp_settings.json       # ejemplo (Roo Code / Cline)
├── tests/
└── src/astrax_mcp/
    ├── server.py           # construye el servidor y registra los módulos
    ├── config.py           # constantes, rutas y variables ASTRAX_*
    ├── state.py            # motor del archivo de estado de tareas (sin dependencias de MCP)
    ├── tasks.py            # herramientas MCP del gestor de tareas
    ├── permissions.py      # verificación de permisos de sesión
    ├── vision.py           # captura y visión de pantalla
    ├── acciones.py         # motor multi-acción: validación en seco, ejecución, bucles, mantener
    ├── control.py          # herramienta MCP astrax_acciones
    ├── system.py           # terminal y portapapeles
    ├── gui.py              # acceso perezoso a pyautogui + validaciones
    ├── utils.py            # log a stderr, errores uniformes, truncado
    ├── compat.py           # SDK MCP v1 (FastMCP) / v2 (MCPServer)
    └── installer.py        # wizard de instalación multiplataforma
```

- Basado en el SDK oficial de MCP para Python. `compat.py` usa `MCPServer` (v2) y recurre a `FastMCP` (v1.x); `pyproject.toml` fija `mcp<2` como en la configuración original: quita el tope cuando pruebes el SDK v2.
- Transporte `stdio`; todos los logs van a `stderr` para no corromper el flujo JSON-RPC.
- Las capturas se normalizan al tamaño lógico de pantalla (HiDPI/Retina) y se reducen según `ASTRAX_MAX_LADO`; el servidor recuerda la escala de la última imagen y convierte las coordenadas. La calidad JPEG se ajusta con `ASTRAX_JPEG_QUALITY` (30-95, por defecto 65).
- Tests: `pip install -e ".[dev]" && pytest`

---

## 🤝 Contribuciones / Community

Astrax es **Open Source** y crece con la comunidad. Si quieres sumarte, eres bienvenido: puedes abrir *issues*, enviar *pull requests*, proponer ideas, probar Astrax en otros sistemas o clientes MCP y reportar errores.

- 📧 **Correo de contacto:** [avpn497@gmail.com](mailto:avpn497@gmail.com)
- 📢 **Canal oficial de Telegram:** [https://t.me/AstraxMCP](https://t.me/AstraxMCP) — únete al canal para aportar, hacer preguntas o reportar problemas.
- 📺 **YouTube:** [@AstraxOf](https://youtube.com/@AstraxOf) — tutoriales y novedades
- 💬 **Creador en Telegram:** [@RufusOficial](https://t.me/RufusOficial)

Si te sirvió el proyecto, deja una ⭐ en el repositorio y suscríbete al canal.

---

<p align="center">Hecho con 💙 por <b>Rufus</b> · <a href="https://youtube.com/@AstraxOf">@AstraxOf</a></p>
