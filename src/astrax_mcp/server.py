"""Construcción y arranque del servidor MCP."""

from . import control, system, tasks, vision
from .compat import MCPServer
from .config import SERVER_NAME
from .utils import log

INSTRUCCIONES = (
    "Astrax controla la pantalla REAL del usuario. Flujo obligatorio: "
    "1) Si la petición tiene varios pasos, llama a astrax_tarea_crear con TODO el plan y los "
    "permisos de la tarea completa. "
    "2) Muestra plan y permisos al usuario y pide UNA sola confirmación; con su 'sí' llama a "
    "astrax_tarea_autorizar. "
    "3) En cada paso: lee astrax_tarea_estado (no releas historial ni capturas viejas), actúa en "
    "bucle ver->actuar->verificar (astrax_ver_pantalla solo cuando haga falta verificar) y cierra "
    "con astrax_tarea_completar_paso guardando rutas y datos clave, no contenidos largos. "
    "4) Al cerrar el último paso la tarea termina y los permisos se revocan. "
    "Nunca adivines coordenadas: calcúlalas de la última captura (la marca roja es el cursor). "
    "No repitas a ciegas una acción fallida. Mover el ratón a una esquina aborta todo."
)


def crear_servidor() -> MCPServer:
    mcp = MCPServer(SERVER_NAME, instructions=INSTRUCCIONES)
    for modulo in (tasks, vision, control, system):
        modulo.register(mcp)
    return mcp


def run() -> None:
    log("Iniciando servidor Astrax (stdio)...")
    crear_servidor().run(transport="stdio")
