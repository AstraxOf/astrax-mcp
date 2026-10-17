"""Interacción con el sistema: ratón, teclado, scroll y esperas."""

import sys
import time

from . import gui
from .config import MAX_ESPERA_SEG, SCOPE_INPUT, SCOPE_PORTAPAPELES
from .utils import AstraxError, accion, log


def register(mcp) -> None:
    @mcp.tool()
    @accion(SCOPE_INPUT)
    def astrax_clic(x: int, y: int, boton: str = "left") -> str:
        """Clic en (x, y), apuntando al CENTRO del elemento. boton: left|right|middle."""
        b = gui.validar_boton(boton)
        gui.validar_coordenadas(x, y)
        gui.pag().moveTo(x, y, duration=0.2)
        gui.pag().click(x=x, y=y, button=b)
        log(f"Clic {b} en ({x}, {y})")
        return f"OK: clic {b} en ({x}, {y})."

    @mcp.tool()
    @accion(SCOPE_INPUT)
    def astrax_doble_clic(x: int, y: int) -> str:
        """Doble clic izquierdo en (x, y) (abrir archivos/iconos, seleccionar palabra)."""
        gui.validar_coordenadas(x, y)
        gui.pag().moveTo(x, y, duration=0.2)
        gui.pag().doubleClick(x=x, y=y)
        log(f"Doble clic en ({x}, {y})")
        return f"OK: doble clic en ({x}, {y})."

    @mcp.tool()
    @accion(SCOPE_INPUT)
    def astrax_escribir(texto: str) -> str:
        """Teclea texto en el foco actual (clic antes en el campo). No-ASCII (ñ, tildes, emojis) usa el portapapeles."""
        if not texto:
            raise AstraxError("el texto está vacío.")
        if texto.isascii():
            gui.pag().write(texto, interval=0.02)
            log(f"Escritos {len(texto)} caracteres (ASCII)")
            return f"OK: {len(texto)} caracteres escritos."

        from . import permissions

        denegado = permissions.exigir(SCOPE_PORTAPAPELES)
        if denegado:
            return denegado
        try:
            import pyperclip
        except ImportError:
            raise AstraxError(
                "texto no ASCII: instala 'pyperclip' para habilitar el modo portapapeles."
            ) from None
        previo = pyperclip.paste()
        try:
            pyperclip.copy(texto)
            gui.pag().hotkey("command" if sys.platform == "darwin" else "ctrl", "v")
            time.sleep(0.15)  # deja que la app lea el portapapeles antes de restaurarlo
        finally:
            pyperclip.copy(previo)
        log(f"Pegados {len(texto)} caracteres vía portapapeles")
        return f"OK: {len(texto)} caracteres escritos (portapapeles)."

    @mcp.tool()
    @accion(SCOPE_INPUT)
    def astrax_tecla(tecla: str, repeticiones: int = 1) -> str:
        """Pulsa una tecla (enter, esc, tab, win, backspace, f5, down...) 1-20 veces."""
        teclas = gui.validar_teclas([tecla])
        veces = max(1, min(repeticiones, 20))
        gui.pag().press(teclas[0], presses=veces, interval=0.05)
        log(f"Tecla '{teclas[0]}' x{veces}")
        return f"OK: tecla '{teclas[0]}' x{veces}."

    @mcp.tool()
    @accion(SCOPE_INPUT)
    def astrax_atajo(teclas: list[str]) -> str:
        """Atajo de 2-4 teclas simultáneas, p. ej. ["ctrl","t"], ["ctrl","l"], ["alt","tab"]."""
        if not 2 <= len(teclas) <= 4:
            raise AstraxError("un atajo necesita entre 2 y 4 teclas.")
        norm = gui.validar_teclas(teclas)
        gui.pag().hotkey(*norm)
        log(f"Atajo {'+'.join(norm)}")
        return f"OK: atajo {'+'.join(norm)}."

    @mcp.tool()
    @accion(SCOPE_INPUT)
    def astrax_scroll(cantidad: int, x: int | None = None, y: int | None = None) -> str:
        """Scroll vertical: positivo = arriba, negativo = abajo (-30..30). x,y opcionales (juntos)."""
        if (x is None) != (y is None):
            raise AstraxError("indica x e y juntos, o ninguno.")
        if x is not None and y is not None:
            gui.validar_coordenadas(x, y)
            gui.pag().moveTo(x, y, duration=0.2)
        c = max(-30, min(cantidad, 30))
        gui.pag().scroll(c)
        log(f"Scroll {c}")
        return f"OK: scroll {c}."

    @mcp.tool()
    @accion()
    def astrax_esperar(segundos: float = 2.0) -> str:
        """Espera 0.1-15 s (carga de apps o páginas) antes de verificar."""
        pausa = max(0.1, min(float(segundos), MAX_ESPERA_SEG))
        time.sleep(pausa)
        return f"OK: esperé {pausa:.1f} s."
