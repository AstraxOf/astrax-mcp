"""Percepción: ver y capturar la pantalla."""

import io
from pathlib import Path

from . import gui
from .compat import MCPImage
from .config import JPEG_QUALITY, SCOPE_PANTALLA, SCREENSHOT_DIR
from .utils import AstraxError, accion, log


def register(mcp) -> None:
    @mcp.tool()
    @accion(SCOPE_PANTALLA)
    def astrax_ver_pantalla(escala: float | None = None, region: list[int] | None = None) -> MCPImage:
        """VE la pantalla (JPEG; círculo rojo = cursor). Coordenadas = píxeles de la imagen.

        Solo para la primera mirada o para zoom: astrax_acciones ya devuelve la captura final.
        escala 0.2-1.0 (menos tokens; por defecto automática). region [x,y,ancho,alto] en píxeles
        REALES recorta y amplía a 1:1 para leer texto pequeño (no cambia el mapa de coordenadas).
        """
        reg = None
        if region is not None:
            if len(region) != 4:
                raise AstraxError("region debe ser [x, y, ancho, alto].")
            reg = (int(region[0]), int(region[1]), int(region[2]), int(region[3]))
        imagen, e = gui.capturar(escala=escala if escala is not None else (1.0 if reg else None),
                                 region=reg, marcar_cursor=True)
        buffer = io.BytesIO()
        imagen.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        log(f"Imagen enviada ({imagen.size[0]}x{imagen.size[1]}, escala {e:.2f}, {buffer.tell()} bytes)")
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
        """Tamaño real de la pantalla y escala de imagen por defecto. Llámala una vez."""
        ancho, alto = gui.tamano_logico()
        e = gui.escala_efectiva(None, ancho, alto)
        return (
            f"Pantalla real: {ancho}x{alto} px. Las imágenes se envían a escala {e:.2f} "
            f"({round(ancho * e)}x{round(alto * e)}); da coordenadas en píxeles de la imagen, "
            "el servidor las convierte."
        )
