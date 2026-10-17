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
- **Sin imágenes pesadas en el historial:** las acciones devuelven texto corto; solo `astrax_ver_pantalla` devuelve imagen, cuando hace falta verificar.
- **Ubicación:** carpeta privada del usuario (`~/.cache/astrax`, `~/Library/Caches/astrax` o `%LOCALAPPDATA%\astrax`), con permisos restringidos. Cámbiala con `ASTRAX_HOME`.

---

## 🔐 Permisos: una sola autorización por tarea

Antes de ejecutar nada, la IA declara **todo lo que necesitará la tarea completa** en `astrax_tarea_crear`:

| Permiso | Habilita |
|---|---|
| `pantalla` | `astrax_ver_pantalla`, `astrax_capturar_pantalla` |
| `raton_teclado` | clic, doble clic, teclas, atajos, scroll, escribir |
| `portapapeles` | `astrax_portapapeles` y escritura de texto no ASCII (ñ, tildes, emojis) |
| `terminal` | `astrax_ejecutar_comando` |

Después muestra el plan y los permisos, **pide tu confirmación una sola vez** y llama a `astrax_tarea_autorizar`. Desde ese momento puede trabajar de forma desatendida durante la sesión (60 min por defecto, `ASTRAX_SESSION_MINUTES`). Las herramientas de acción **rechazan** cualquier uso fuera de una tarea autorizada o de un permiso no solicitado.

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
| `astrax_ver_pantalla` | **La IA ve la pantalla**: captura como imagen (marca roja en el cursor) |
| `astrax_capturar_pantalla` | Guarda un PNG y devuelve la ruta |
| `astrax_info_pantalla` | Ancho y alto de la pantalla |
| `astrax_clic` / `astrax_doble_clic` | Clic en `(x, y)` con validación de límites |
| `astrax_escribir` | Teclea texto (soporta `ñ`, tildes y emojis vía portapapeles) |
| `astrax_tecla` / `astrax_atajo` | Teclas sueltas y atajos (`["ctrl", "t"]`…) |
| `astrax_scroll` | Rueda del ratón arriba/abajo |
| `astrax_esperar` | Espera a que cargue una app o página |
| `astrax_portapapeles` | Lee o escribe el portapapeles |
| `astrax_ejecutar_comando` | Ejecuta un comando de shell con timeout y salida recortada |

Ejemplo de prompt:

> *"Usa Astrax: redacta una carta para Ana con mis datos, guárdala como PDF y envíala a ana@ejemplo.com con el asunto 'Propuesta'."*

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
    ├── control.py          # ratón, teclado, scroll, esperas
    ├── system.py           # terminal y portapapeles
    ├── gui.py              # acceso perezoso a pyautogui + validaciones
    ├── utils.py            # log a stderr, errores uniformes, truncado
    ├── compat.py           # SDK MCP v1 (FastMCP) / v2 (MCPServer)
    └── installer.py        # wizard de instalación multiplataforma
```

- Basado en el SDK oficial de MCP para Python. `compat.py` usa `MCPServer` (v2) y recurre a `FastMCP` (v1.x); `pyproject.toml` fija `mcp<2` como en la configuración original: quita el tope cuando pruebes el SDK v2.
- Transporte `stdio`; todos los logs van a `stderr` para no corromper el flujo JSON-RPC.
- Las capturas se normalizan al tamaño lógico de pantalla: las coordenadas de la imagen coinciden con las del clic, incluso en HiDPI/Retina. La calidad JPEG se ajusta con `ASTRAX_JPEG_QUALITY` (30-95, por defecto 65).
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
