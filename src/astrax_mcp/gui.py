"""Acceso perezoso a pyautogui + captura con escala + conversión de coordenadas.

Modelo de coordenadas (clave para ahorrar tokens sin romper los clics):
la IA siempre da coordenadas en PÍXELES DE LA ÚLTIMA IMAGEN DE PANTALLA COMPLETA que
recibió. El servidor recuerda la escala de esa imagen y convierte a píxeles reales.
Así se pueden enviar imágenes más pequeñas (menos tokens) sin que la IA haga cuentas.
"""

import sys
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageDraw

from .config import ESCALA_MIN, MAX_LADO_IMG
from .utils import AstraxError

VALID_BUTTONS = frozenset({"left", "right", "middle"})
_ALIAS_BOTON = {"izquierdo": "left", "derecho": "right", "medio": "middle"}
_pag: Any = None


@dataclass
class Mapa:
    """Relación imagen -> pantalla de la última captura completa entregada."""

    escala: float = 1.0


mapa = Mapa()


def pag() -> Any:
    """Importa pyautogui bajo demanda (arranque rápido; falla solo si se usa sin pantalla)."""
    global _pag
    if _pag is None:
        import pyautogui

        pyautogui.FAILSAFE = True  # mover el ratón a una esquina aborta
        pyautogui.PAUSE = 0  # las pausas las gestiona el motor de acciones
        _pag = pyautogui
    return _pag


def tamano_logico() -> tuple[int, int]:
    """(ancho, alto) en el sistema de coordenadas de pyautogui."""
    size = pag().size()
    return int(size.width), int(size.height)


def escala_efectiva(escala: float | None, ancho: int, alto: int) -> float:
    """Escala pedida (0.2-1.0) o, si es None, la automática para no superar MAX_LADO_IMG."""
    if escala is None:
        return min(1.0, MAX_LADO_IMG / max(ancho, alto))
    return max(ESCALA_MIN, min(float(escala), 1.0))


def _screenshot() -> Image.Image:
    """pyautogui primero; si falla (p. ej. Linux sin scrot/gnome-screenshot) usa PIL.ImageGrab."""
    try:
        return pag().screenshot()
    except Exception as exc:  # noqa: BLE001
        if type(exc).__name__ == "FailSafeException":
            raise
        try:
            from PIL import ImageGrab

            return ImageGrab.grab(xdisplay=None) if sys.platform.startswith("linux") else ImageGrab.grab()
        except Exception:  # noqa: BLE001
            raise exc from None


def capturar(
    escala: float | None = None,
    region: tuple[int, int, int, int] | None = None,
    marcar_cursor: bool = False,
) -> tuple[Image.Image, float]:
    """Captura (pantalla completa o región x,y,w,h en píxeles REALES). Devuelve (imagen, escala).

    Pantalla completa: actualiza el mapa de coordenadas. Región: nunca lo toca.
    """
    imagen: Image.Image = _screenshot().convert("RGB")
    ancho, alto = tamano_logico()
    if imagen.size != (ancho, alto):  # HiDPI/Retina: normaliza al tamaño lógico
        imagen = imagen.resize((ancho, alto), Image.Resampling.LANCZOS)

    ox = oy = 0
    if region is not None:
        x, y, w, h = region
        x0, y0 = max(0, min(x, ancho - 1)), max(0, min(y, alto - 1))
        x1, y1 = max(x0 + 1, min(x + w, ancho)), max(y0 + 1, min(y + h, alto))
        imagen = imagen.crop((x0, y0, x1, y1))
        ox, oy = x0, y0

    e = escala_efectiva(escala, *imagen.size)
    if marcar_cursor:
        cx, cy = pag().position()
        _marcar(imagen, cx - ox, cy - oy)
    if e < 1.0:
        nuevo = (max(1, round(imagen.size[0] * e)), max(1, round(imagen.size[1] * e)))
        imagen = imagen.resize(nuevo, Image.Resampling.LANCZOS)
    if region is None:
        mapa.escala = e
    return imagen, e


def _marcar(imagen: Image.Image, cx: int, cy: int) -> None:
    dibujo = ImageDraw.Draw(imagen)
    r = 10
    dibujo.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 0, 0), width=3)
    dibujo.line((cx - r - 6, cy, cx + r + 6, cy), fill=(255, 0, 0), width=2)
    dibujo.line((cx, cy - r - 6, cx, cy + r + 6), fill=(255, 0, 0), width=2)


def capturar_normalizada(marcar_cursor: bool = False) -> Image.Image:
    """Captura a escala 1:1 con la pantalla real (la usa astrax_capturar_pantalla)."""
    return capturar(escala=1.0, marcar_cursor=marcar_cursor)[0]


def a_pantalla(x: float, y: float) -> tuple[int, int]:
    """Convierte coordenadas de la última imagen a píxeles reales y las valida."""
    ancho, alto = tamano_logico()
    px, py = round(x / mapa.escala), round(y / mapa.escala)
    # Tolera 2 px de desbordamiento por redondeo en el borde.
    if -2 <= px < 0:
        px = 0
    if -2 <= py < 0:
        py = 0
    if ancho <= px < ancho + 2:
        px = ancho - 1
    if alto <= py < alto + 2:
        py = alto - 1
    validar_coordenadas(px, py)
    return px, py


def validar_coordenadas(x: int, y: int) -> None:
    ancho, alto = tamano_logico()
    if not (0 <= x < ancho and 0 <= y < alto):
        raise AstraxError(
            f"coordenadas ({x}, {y}) fuera de pantalla. Rango válido: x 0-{ancho - 1}, y 0-{alto - 1}."
        )


def validar_boton(boton: str) -> str:
    b = boton.strip().lower()
    b = _ALIAS_BOTON.get(b, b)
    if b not in VALID_BUTTONS:
        raise AstraxError(f"botón '{boton}' no válido. Usa: {', '.join(sorted(VALID_BUTTONS))}.")
    return b


def validar_teclas(teclas: list[str]) -> list[str]:
    normalizadas = [t.strip().lower() for t in teclas]
    invalidas = [t for t in normalizadas if t not in pag().KEYBOARD_KEYS]
    if invalidas:
        raise AstraxError(
            f"teclas no válidas: {', '.join(invalidas)}. Ejemplos: enter, esc, tab, win, ctrl, "
            "alt, shift, backspace, delete, up, down, left, right, space, f5, a-z, 0-9."
        )
    return normalizadas
