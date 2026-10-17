"""Constantes y configuración (sobrescribible con variables de entorno ASTRAX_*)."""

import os
import sys
from pathlib import Path

SERVER_NAME = "Astrax"


def _env_int(nombre: str, defecto: int) -> int:
    try:
        return int(os.environ.get(nombre, defecto))
    except ValueError:
        return defecto


def _directorio_astrax() -> Path:
    """Directorio privado por usuario (no /tmp compartido): guarda estado y capturas."""
    override = os.environ.get("ASTRAX_HOME")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "astrax"


HOME_DIR = _directorio_astrax()
STATE_FILE = HOME_DIR / ".astrax_task_state.json"
SCREENSHOT_DIR = HOME_DIR / "screens"

# --- Permisos de sesión (ámbitos) ---
SCOPE_PANTALLA = "pantalla"            # ver / capturar la pantalla
SCOPE_INPUT = "raton_teclado"          # clics, teclas, atajos, scroll
SCOPE_PORTAPAPELES = "portapapeles"    # leer / escribir el portapapeles
SCOPE_TERMINAL = "terminal"            # ejecutar comandos de shell
SCOPES = (SCOPE_PANTALLA, SCOPE_INPUT, SCOPE_PORTAPAPELES, SCOPE_TERMINAL)

# Si es "0", las herramientas de acción no exigen tarea autorizada (modo legado).
REQUIRE_SESSION = os.environ.get("ASTRAX_REQUIRE_SESSION", "1") != "0"
SESSION_MINUTES = _env_int("ASTRAX_SESSION_MINUTES", 60)

# --- Límites (ahorro de tokens y anti-bucles) ---
MAX_PASOS = 30
MAX_INTENTOS = 3
MAX_DATOS = 100
MAX_DATO_CHARS = 4000
MAX_SALIDA = 4000
MAX_ESPERA_SEG = 15.0
JPEG_QUALITY = max(30, min(_env_int("ASTRAX_JPEG_QUALITY", 65), 95))

# --- Nombres de herramientas (el instalador los usa para `alwaysAllow`) ---
TOOL_AUTORIZAR = "astrax_tarea_autorizar"
TODAS_LAS_HERRAMIENTAS = (
    "astrax_tarea_crear",
    TOOL_AUTORIZAR,
    "astrax_tarea_estado",
    "astrax_tarea_guardar",
    "astrax_tarea_completar_paso",
    "astrax_tarea_limpiar",
    "astrax_info_pantalla",
    "astrax_ver_pantalla",
    "astrax_capturar_pantalla",
    "astrax_clic",
    "astrax_doble_clic",
    "astrax_escribir",
    "astrax_tecla",
    "astrax_atajo",
    "astrax_scroll",
    "astrax_esperar",
    "astrax_portapapeles",
    "astrax_ejecutar_comando",
)
# Todo menos la autorización: así el cliente pregunta UNA vez, justo ahí.
AUTO_APROBABLES = tuple(t for t in TODAS_LAS_HERRAMIENTAS if t != TOOL_AUTORIZAR)
