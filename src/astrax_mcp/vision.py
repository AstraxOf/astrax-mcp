"""Percepción: ver y capturar la pantalla."""

import io
from pathlib import Path

from . import gui
from .compat import MCPImage
from .config import JPEG_QUALITY, SCOPE_PANTALLA, SCREENSHOT_DIR
from .utils import accion, log


def register(mcp) -> None:
    @mcp.tool()
    @accion(SCOPE_PANTALLA)
    def astrax_ver_pantalla() -> MCPImage:
        """VE la pantalla (imagen JPEG). Coordenadas 1:1 con astrax_clic; círculo rojo = cursor.

        Úsala para verificar el resultado de una acción, no a ciegas tras cada paso trivial.
        """
        imagen = gui.capturar_normalizada(marcar_cursor=True)
        buffer = io.BytesIO()
        imagen.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        log(f"Imagen enviada ({imagen.size[0]}x{imagen.size[1]}, {buffer.tell()} bytes)")
        return MCPImage(data=buffer.getvalue(), format="jpeg")

    @mcp.tool()
    @accion(SCOPE_PANTALLA)
    def astrax_capturar_pantalla(nombre_archivo: str = "astrax_screen.png") -> str:
        """Guarda la pantalla como PNG y devuelve su ruta (la IA no la abre; para VER usa astrax_ver_pantalla)."""
        nombre = Path(nombre_archivo).name or "astrax_screen.png"
        if not nombre.lower().endswith(".png"):
            nombre += ".png"
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        destino = (SCREENSHOT_DIR / nombre).resolve()
        imagen = gui.capturar_normalizada()
        imagen.save(destino, format="PNG")
        log(f"Captura guardada en {destino}")
        return str(destino)

    @mcp.tool()
    @accion()
    def astrax_info_pantalla() -> str:
        """Tamaño de la pantalla en píxeles (origen arriba-izquierda). Llámala una vez."""
        ancho, alto = gui.tamano_logico()
        return f"Pantalla: {ancho}x{alto} px (x: 0-{ancho - 1}, y: 0-{alto - 1})."
