"""Construcción y arranque del servidor MCP."""

from . import control, system, tasks, vision
from .compat import MCPServer
from .config import SERVER_NAME
from .utils import log

INSTRUCCIONES = (
    "Astrax controla la pantalla REAL del usuario. Velocidad y ahorro de tokens: "
    "MIRA UNA VEZ, PLANIFICA VARIAS ACCIONES y envíalas JUNTAS en astrax_acciones (3-20 por "
    "llamada). Nunca hagas una acción por turno si puedes encadenarlas (mover+clic, clic+escribir+"
    "enter, abrir app+esperar+clic). La respuesta ya trae la captura final: no llames a "
    "astrax_ver_pantalla después. Coordenadas = píxeles de la ÚLTIMA imagen recibida (el servidor "
    "convierte la escala); la marca roja es el cursor. Encadena solo lo predecible: si el siguiente "
    "clic depende de lo que aparezca (menú, diálogo, página que carga), corta el lote ahí y mira. "
    "Usa 'esperar' tras abrir apps/páginas y 'captura' (fotograma barato) para ver pasos intermedios. "
    "Flujo de permisos: 1) astrax_tarea_crear con TODO el plan y los permisos de la tarea completa; "
    "2) muestra plan y permisos y pide UNA confirmación; con su 'sí' llama a astrax_tarea_autorizar; "
    "3) por paso: astrax_tarea_estado (no releas historial), actúa con lotes, cierra con "
    "astrax_tarea_completar_paso guardando rutas/datos clave, no contenidos largos; "
    "4) al cerrar el último paso se revocan los permisos. "
    "JUEGOS y apps en tiempo real: usa mantener{teclas,seg|mientras} para movimiento continuo, "
    "repetir para pulsaciones seguidas, arrastrar/raton_abajo para mouse, y varias 'captura' dentro "
    "del lote para ver la evolución. Tu latencia limita juegos muy rápidos: elige acciones "
    "tolerantes (mantener, repetir) y verifica por fotogramas. "
    "Si una acción falla, el lote se detiene y recibes la imagen actual: no repitas a ciegas. "
    "Mover el ratón a una esquina aborta todo."
)


def crear_servidor() -> MCPServer:
    mcp = MCPServer(SERVER_NAME, instructions=INSTRUCCIONES)
    for modulo in (tasks, vision, control, system):
        modulo.register(mcp)
    return mcp


def run() -> None:
    log("Iniciando servidor Astrax (stdio)...")
    crear_servidor().run(transport="stdio")
