"""Acceso perezoso a pyautogui + utilidades de captura y validación."""

from typing import Any

from PIL import Image, ImageDraw

from .utils import AstraxError

VALID_BUTTONS = frozenset({"left", "right", "middle"})
_pag: Any = None


def pag() -> Any:
    """Importa pyautogui bajo demanda (arranque rápido; falla solo si se usa sin pantalla)."""
    global _pag
    if _pag is None:
        import pyautogui

        pyautogui.FAILSAFE = True  # mover el ratón a una esquina aborta
        pyautogui.PAUSE = 0.1
        _pag = pyautogui
    return _pag


def tamano_logico() -> tuple[int, int]:
    """(ancho, alto) en el sistema de coordenadas de pyautogui."""
    size = pag().size()
    return int(size.width), int(size.height)


def capturar_normalizada(marcar_cursor: bool = False) -> Image.Image:
    """Captura reescalada al tamaño lógico: coordenadas de imagen == coordenadas de clic."""
    imagen: Image.Image = pag().screenshot().convert("RGB")
    tamano = tamano_logico()
    if imagen.size != tamano:
        imagen = imagen.resize(tamano, Image.Resampling.LANCZOS)
    if marcar_cursor:
        cx, cy = pag().position()
        dibujo = ImageDraw.Draw(imagen)
        r = 10
        dibujo.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 0, 0), width=3)
        dibujo.line((cx - r - 6, cy, cx + r + 6, cy), fill=(255, 0, 0), width=2)
        dibujo.line((cx, cy - r - 6, cx, cy + r + 6), fill=(255, 0, 0), width=2)
    return imagen


def validar_coordenadas(x: int, y: int) -> None:
    ancho, alto = tamano_logico()
    if not (0 <= x < ancho and 0 <= y < alto):
        raise AstraxError(
            f"coordenadas ({x}, {y}) fuera de pantalla. Rango válido: x 0-{ancho - 1}, y 0-{alto - 1}."
        )


def validar_boton(boton: str) -> str:
    b = boton.strip().lower()
    if b not in VALID_BUTTONS:
        raise AstraxError(f"botón '{boton}' no válido. Usa: {', '.join(sorted(VALID_BUTTONS))}.")
    return b


def validar_teclas(teclas: list[str]) -> list[str]:
    normalizadas = [t.strip().lower() for t in teclas]
    invalidas = [t for t in normalizadas if t not in pag().KEYBOARD_KEYS]
    if invalidas:
        raise AstraxError(
            f"teclas no válidas: {', '.join(invalidas)}. Ejemplos: enter, esc, tab, win, ctrl, "
            "alt, shift, backspace, delete, up, down, left, right, f5, a-z, 0-9."
        )
    return normalizadas
