"""Motor multi-acción: varias acciones de ratón/teclado en UNA sola llamada.

Por qué existe: con "una acción por turno" cada clic cuesta una ida y vuelta al modelo
(latencia) + una captura (tokens). Aquí la IA mira UNA vez, planifica N acciones y las
manda juntas; recibe una sola captura final (y opcionalmente fotogramas intermedios).

Garantías:
  * Se valida TODO el lote (formato, teclas, coordenadas, tiempo) y los permisos ANTES de mover
    nada, con una pasada en seco que usa los mismos manejadores que la ejecución real.
  * Si una acción falla, se detiene, se devuelve cuál falló y se envía la captura actual.
  * Teclas/botones mantenidos se sueltan SIEMPRE al terminar (aunque haya error o fail-safe).
  * El fail-safe de pyautogui (esquina de la pantalla) sigue abortando todo.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from PIL import Image

from . import gui, system
from .config import (
    ESCRIBIR_INTERVALO,
    MAX_ACCIONES,
    MAX_BUCLE,
    MAX_FRAMES,
    MAX_MANTENER_SEG,
    MAX_TOTAL_SEG,
    MOVER_SEG,
    PAUSA_ENTRE_ACCIONES,
    SCOPE_INPUT,
    SCOPE_PANTALLA,
    SCOPE_PORTAPAPELES,
    SCOPE_TERMINAL,
)
from .utils import AstraxError, log


# --------------------------------------------------------------------------- #
# Modelo
# --------------------------------------------------------------------------- #
@dataclass
class Accion:
    nombre: str
    p: dict[str, Any]
    hijas: list["Accion"] = field(default_factory=list)  # solo `mantener` con `mientras`


@dataclass
class Resultado:
    ok: bool = True
    hechas: int = 0
    total: int = 0
    error: str = ""
    salidas: list[str] = field(default_factory=list)
    frames: list[tuple[str, Image.Image, float]] = field(default_factory=list)  # (etiqueta, img, escala)
    segundos: float = 0.0
    rechazado: bool = False  # el lote no pasó la validación previa: NO se ejecutó nada


class Contexto:
    def __init__(self, seco: bool = False) -> None:
        self.seco = seco  # pasada de validación: no toca el sistema ni duerme
        self.capturas = 0
        self.teclas_abajo: set[str] = set()
        self.botones_abajo: set[str] = set()
        self.seg_gastados = 0.0
        self.res = Resultado()
        self.indice = 0

    def gastar(self, seg: float) -> None:
        self.seg_gastados += seg
        if self.seg_gastados > MAX_TOTAL_SEG:
            raise AstraxError(
                f"el lote supera {MAX_TOTAL_SEG:.0f} s de esperas/mantenidos. Divídelo en varias llamadas."
            )

    def dormir(self, seg: float) -> None:
        if seg > 0:
            self.gastar(seg)
            if not self.seco:
                time.sleep(seg)


# --------------------------------------------------------------------------- #
# Lectura de parámetros
# --------------------------------------------------------------------------- #
def _num(p: dict, k: str, defecto: float | None = None, minimo: float | None = None,
         maximo: float | None = None) -> float:
    v = p.get(k, defecto)
    if v is None:
        raise AstraxError(f"falta el campo '{k}'.")
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise AstraxError(f"'{k}' debe ser un número (recibí {v!r}).") from None
    if minimo is not None:
        v = max(minimo, v)
    if maximo is not None:
        v = min(maximo, v)
    return v


def _punto(p: dict, kx: str = "x", ky: str = "y", obligatorio: bool = True) -> tuple[int, int] | None:
    if kx not in p and ky not in p:
        if obligatorio:
            raise AstraxError(f"faltan '{kx}' e '{ky}'.")
        return None
    if (kx in p) != (ky in p):
        raise AstraxError(f"indica '{kx}' e '{ky}' juntos.")
    return gui.a_pantalla(_num(p, kx), _num(p, ky))


def _texto(p: dict, k: str) -> str:
    v = p.get(k)
    if not isinstance(v, str) or not v:
        raise AstraxError(f"falta el campo de texto '{k}'.")
    return v


def _lista_teclas(p: dict, k: str = "teclas") -> list[str]:
    v = p.get(k)
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list) or not v:
        raise AstraxError(f"'{k}' debe ser una lista de teclas.")
    return gui.validar_teclas([str(t) for t in v])


def _mover_a(pt: tuple[int, int] | None, dur: float) -> None:
    if pt is not None:
        gui.pag().moveTo(pt[0], pt[1], duration=dur)


# --------------------------------------------------------------------------- #
# Manejadores (cada uno: (ctx, p) -> texto opcional)
# --------------------------------------------------------------------------- #
def _h_mover(ctx: Contexto, p: dict) -> None:
    _mover_a(_punto(p), _num(p, "dur", MOVER_SEG, 0, 3))


def _h_mover_rel(ctx: Contexto, p: dict) -> None:
    gui.pag().moveRel(int(_num(p, "dx", 0)), int(_num(p, "dy", 0)), duration=_num(p, "dur", 0, 0, 3))


def _h_clic(ctx: Contexto, p: dict, forzar_n: int | None = None) -> None:
    b = gui.validar_boton(str(p.get("b", "left")))
    n = forzar_n or int(_num(p, "n", 1, 1, 3))
    pt = _punto(p, obligatorio=False)
    _mover_a(pt, _num(p, "dur", MOVER_SEG, 0, 3))
    gui.pag().click(clicks=n, interval=0.05, button=b)


def _h_doble_clic(ctx: Contexto, p: dict) -> None:
    _h_clic(ctx, p, forzar_n=2)


def _h_arrastrar(ctx: Contexto, p: dict) -> None:
    b = gui.validar_boton(str(p.get("b", "left")))
    origen = _punto(p, "x", "y")
    destino = _punto(p, "x2", "y2")
    _mover_a(origen, MOVER_SEG)
    gui.pag().mouseDown(button=b)
    ctx.botones_abajo.add(b)
    try:
        gui.pag().moveTo(destino[0], destino[1], duration=_num(p, "dur", 0.3, 0.1, 5))
    finally:
        gui.pag().mouseUp(button=b)
        ctx.botones_abajo.discard(b)


def _h_raton_abajo(ctx: Contexto, p: dict) -> None:
    b = gui.validar_boton(str(p.get("b", "left")))
    _mover_a(_punto(p, obligatorio=False), MOVER_SEG)
    gui.pag().mouseDown(button=b)
    ctx.botones_abajo.add(b)


def _h_raton_arriba(ctx: Contexto, p: dict) -> None:
    b = gui.validar_boton(str(p.get("b", "left")))
    _mover_a(_punto(p, obligatorio=False), MOVER_SEG)
    gui.pag().mouseUp(button=b)
    ctx.botones_abajo.discard(b)


def _h_escribir(ctx: Contexto, p: dict) -> None:
    texto = _texto(p, "texto")
    _num(p, "intervalo", ESCRIBIR_INTERVALO, 0, 0.5)
    if ctx.seco:
        return
    if texto.isascii():
        gui.pag().write(texto, interval=_num(p, "intervalo", ESCRIBIR_INTERVALO, 0, 0.5))
    else:
        try:
            import pyperclip
        except ImportError:
            raise AstraxError("texto no ASCII: instala 'pyperclip' para el modo portapapeles.") from None
        previo = pyperclip.paste()
        try:
            pyperclip.copy(texto)
            gui.pag().hotkey("command" if sys.platform == "darwin" else "ctrl", "v")
            time.sleep(0.15)  # deja que la app lea el portapapeles antes de restaurarlo
        finally:
            pyperclip.copy(previo)
    if p.get("enter"):
        gui.pag().press("enter")


def _h_tecla(ctx: Contexto, p: dict) -> None:
    t = str(p.get("tecla", "")).strip()
    if not t:
        raise AstraxError("falta el campo 'tecla'.")
    n = int(_num(p, "n", 1, 1, 50))
    if "+" in t and len(t) > 1:  # "ctrl+l" == atajo
        norm = gui.validar_teclas([x for x in t.split("+") if x])
        for _ in range(n):
            gui.pag().hotkey(*norm)
        return
    norm = gui.validar_teclas([t])
    gui.pag().press(norm[0], presses=n, interval=_num(p, "intervalo", 0.02, 0, 2))


def _h_atajo(ctx: Contexto, p: dict) -> None:
    norm = _lista_teclas(p)
    if not 2 <= len(norm) <= 4:
        raise AstraxError("un atajo necesita entre 2 y 4 teclas.")
    gui.pag().hotkey(*norm)


def _h_abajo(ctx: Contexto, p: dict) -> None:
    for t in _lista_teclas(p, "teclas" if "teclas" in p else "tecla"):
        gui.pag().keyDown(t)
        ctx.teclas_abajo.add(t)


def _h_arriba(ctx: Contexto, p: dict) -> None:
    for t in _lista_teclas(p, "teclas" if "teclas" in p else "tecla"):
        gui.pag().keyUp(t)
        ctx.teclas_abajo.discard(t)


def _h_mantener(ctx: Contexto, p: dict, hijas: list[Accion]) -> None:
    """Mantiene teclas (y/o botón) pulsadas `seg` segundos y/o mientras corren `mientras`."""
    teclas = _lista_teclas(p) if ("teclas" in p or "tecla" in p) else []
    b = gui.validar_boton(str(p["b"])) if "b" in p else None
    if not teclas and not b:
        raise AstraxError("mantener necesita 'teclas' y/o 'b' (botón del ratón).")
    seg = _num(p, "seg", 0 if hijas else 0.5, 0, MAX_MANTENER_SEG)
    for t in teclas:
        gui.pag().keyDown(t)
        ctx.teclas_abajo.add(t)
    if b:
        gui.pag().mouseDown(button=b)
        ctx.botones_abajo.add(b)
    try:
        for h in hijas:
            _ejecutar_una(ctx, h)
        ctx.dormir(seg)
    finally:
        for t in teclas:
            gui.pag().keyUp(t)
            ctx.teclas_abajo.discard(t)
        if b:
            gui.pag().mouseUp(button=b)
            ctx.botones_abajo.discard(b)


def _h_scroll(ctx: Contexto, p: dict) -> None:
    _mover_a(_punto(p, obligatorio=False), MOVER_SEG)
    gui.pag().scroll(int(_num(p, "n", 0, -30, 30)))


def _h_esperar(ctx: Contexto, p: dict) -> None:
    ctx.dormir(_num(p, "seg", 1.0, 0.05, 15))


def _h_captura(ctx: Contexto, p: dict) -> None:
    """Fotograma intermedio (barato: escala 0.4 por defecto). No cambia el mapa de coordenadas."""
    if ctx.capturas >= MAX_FRAMES - 1:  # reserva un hueco para la captura final
        raise AstraxError(f"máximo {MAX_FRAMES - 1} capturas intermedias por llamada.")
    ctx.capturas += 1
    region = None
    if "region" in p:
        r = p["region"]
        if not (isinstance(r, list) and len(r) == 4):
            raise AstraxError("'region' debe ser [x, y, ancho, alto] (coordenadas de la última imagen).")
        # La región se da en coordenadas de la última imagen; se convierte a píxeles reales.
        e = gui.mapa.escala
        x0, y0 = gui.a_pantalla(_num({"v": r[0]}, "v"), _num({"v": r[1]}, "v"))
        region = (x0, y0, round(_num({"v": r[2]}, "v") / e), round(_num({"v": r[3]}, "v") / e))
    esc = _num(p, "escala", 1.0 if region else 0.4, 0.2, 1.0)
    if ctx.seco:
        return
    previa = gui.mapa.escala
    try:
        img, e = gui.capturar(escala=esc, region=region, marcar_cursor=True)
    finally:
        gui.mapa.escala = previa  # el mapa solo lo fija la imagen FINAL
    etiqueta = f"tras acción {ctx.indice}" + (f", región x,y,w,h reales={region}" if region else "")
    ctx.res.frames.append((etiqueta, img, e))


def _h_portapapeles(ctx: Contexto, p: dict) -> None:
    if str(p.get("op", "")).strip().lower() not in ("leer", "escribir"):
        raise AstraxError("portapapeles: 'op' debe ser 'leer' o 'escribir'.")
    if ctx.seco:
        return
    out = system.portapapeles_op(str(p.get("op", "")), str(p.get("texto", "")))
    if str(p.get("op", "")).lower() == "leer":
        ctx.res.salidas.append(f"[{ctx.indice}] portapapeles: {out}")


def _h_comando(ctx: Contexto, p: dict) -> None:
    if ctx.seco:
        if system.comando_peligroso(_texto(p, "cmd")):
            raise AstraxError("comando bloqueado por seguridad (patrón destructivo). Pídelo al usuario.")
        _num(p, "timeout", 30, 1, 120)
        return
    out = system.ejecutar_shell(_texto(p, "cmd"), int(_num(p, "timeout", 30, 1, 120)), p.get("dir"))
    ctx.res.salidas.append(f"[{ctx.indice}] comando: {out}")


Handler = Callable[..., None]
# nombre -> (scope requerido, manejador)
REGISTRO: dict[str, tuple[str | None, Handler]] = {
    "mover": (SCOPE_INPUT, _h_mover),
    "mover_rel": (SCOPE_INPUT, _h_mover_rel),
    "clic": (SCOPE_INPUT, _h_clic),
    "doble_clic": (SCOPE_INPUT, _h_doble_clic),
    "arrastrar": (SCOPE_INPUT, _h_arrastrar),
    "raton_abajo": (SCOPE_INPUT, _h_raton_abajo),
    "raton_arriba": (SCOPE_INPUT, _h_raton_arriba),
    "escribir": (SCOPE_INPUT, _h_escribir),
    "tecla": (SCOPE_INPUT, _h_tecla),
    "atajo": (SCOPE_INPUT, _h_atajo),
    "abajo": (SCOPE_INPUT, _h_abajo),
    "arriba": (SCOPE_INPUT, _h_arriba),
    "mantener": (SCOPE_INPUT, _h_mantener),
    "scroll": (SCOPE_INPUT, _h_scroll),
    "esperar": (None, _h_esperar),
    "captura": (SCOPE_PANTALLA, _h_captura),
    "portapapeles": (SCOPE_PORTAPAPELES, _h_portapapeles),
    "comando": (SCOPE_TERMINAL, _h_comando),
}
_ALIAS = {"click": "clic", "type": "escribir", "key": "tecla", "wait": "esperar", "hotkey": "atajo",
          "drag": "arrastrar", "screenshot": "captura", "move": "mover", "hold": "mantener",
          "doble": "doble_clic", "repeat": "repetir"}


# --------------------------------------------------------------------------- #
# Parseo / validación (todo antes de ejecutar nada)
# --------------------------------------------------------------------------- #
def parsear(lista: Any, profundidad: int = 0) -> list[Accion]:
    """Convierte la lista cruda en acciones, expandiendo `repetir`. Lanza AstraxError con el índice."""
    if not isinstance(lista, list) or not lista:
        raise AstraxError("'acciones' debe ser una lista no vacía.")
    if profundidad > 2:
        raise AstraxError("bucles anidados a más de 2 niveles.")
    salida: list[Accion] = []
    for i, cruda in enumerate(lista, 1):
        if not isinstance(cruda, dict):
            raise AstraxError(f"acción #{i}: debe ser un objeto, p. ej. {{\"a\":\"clic\",\"x\":10,\"y\":20}}.")
        nombre = str(cruda.get("a") or cruda.get("accion") or "").strip().lower()
        nombre = _ALIAS.get(nombre, nombre)
        if nombre == "repetir":
            n = int(_num(cruda, "n", 1, 1, MAX_BUCLE))
            hijas = parsear(cruda.get("acciones"), profundidad + 1)
            salida.extend(a for _ in range(n) for a in hijas)
        elif nombre in REGISTRO:
            hijas = []
            if nombre == "mantener" and cruda.get("mientras") is not None:
                hijas = parsear(cruda["mientras"], profundidad + 1)
            salida.append(Accion(nombre, cruda, hijas))
        else:
            raise AstraxError(
                f"acción #{i}: '{nombre or '?'}' no existe. Válidas: {', '.join(REGISTRO)}, repetir."
            )
        if len(salida) > MAX_ACCIONES:
            raise AstraxError(f"más de {MAX_ACCIONES} acciones tras expandir bucles. Divide el lote.")
    return salida


def _aplanar(acciones: list[Accion]) -> list[Accion]:
    plano: list[Accion] = []
    for a in acciones:
        plano.append(a)
        plano.extend(_aplanar(a.hijas))
    return plano


def scopes_necesarios(acciones: list[Accion], captura_final: bool) -> list[str]:
    """Permisos que exige el lote completo (para rechazarlo entero si falta alguno)."""
    scopes: dict[str, None] = {}
    if captura_final:
        scopes[SCOPE_PANTALLA] = None
    for a in _aplanar(acciones):
        sc = REGISTRO[a.nombre][0]
        if sc:
            scopes[sc] = None
        if a.nombre == "escribir" and isinstance(a.p.get("texto"), str) and not a.p["texto"].isascii():
            scopes[SCOPE_PORTAPAPELES] = None
    return list(scopes)


# --------------------------------------------------------------------------- #
# Ejecución
# --------------------------------------------------------------------------- #
def _ejecutar_una(ctx: Contexto, a: Accion) -> None:
    ctx.indice += 1
    _, handler = REGISTRO[a.nombre]
    try:
        if a.nombre == "mantener":
            handler(ctx, a.p, a.hijas)
        else:
            handler(ctx, a.p)
    except AstraxError as exc:
        raise AstraxError(f"acción {ctx.indice} ({a.nombre}): {exc}") from None
    ctx.res.hechas = ctx.indice
    if PAUSA_ENTRE_ACCIONES and not ctx.seco:
        time.sleep(PAUSA_ENTRE_ACCIONES)


def _soltar_todo(ctx: Contexto) -> None:
    """Red de seguridad: nunca dejes teclas o botones pulsados."""
    try:
        for t in list(ctx.teclas_abajo):
            gui.pag().keyUp(t)
        for b in list(ctx.botones_abajo):
            gui.pag().mouseUp(button=b)
    except Exception as exc:  # noqa: BLE001
        log(f"No pude soltar todo: {exc!r}")
    ctx.teclas_abajo.clear()
    ctx.botones_abajo.clear()


class _PagSeco:
    """Proxy de pyautogui para la pasada en seco: lee (tamaño, teclas válidas), no actúa."""

    _LECTURA = frozenset({"size", "position", "KEYBOARD_KEYS", "screenshot"})

    def __init__(self, real: Any) -> None:
        self._real = real

    def __getattr__(self, nombre: str) -> Any:
        if nombre in self._LECTURA:
            return getattr(self._real, nombre)
        return lambda *a, **k: None


def prevalidar(acciones: list[Accion]) -> None:
    """Recorre TODO el lote sin tocar el sistema: teclas, coordenadas, campos y presupuesto de tiempo.

    Usa los mismos manejadores que la ejecución real (proxy mudo de pyautogui), así lo que
    valida es exactamente lo que se ejecutaría. Si algo falla, no se mueve ni se pulsa nada.
    """
    real = gui.pag()
    gui._pag = _PagSeco(real)  # noqa: SLF001
    try:
        ctx = Contexto(seco=True)
        for a in acciones:
            _ejecutar_una(ctx, a)
    finally:
        gui._pag = real  # noqa: SLF001


def ejecutar(acciones: list[Accion], captura_final: bool, escala: float | None,
             espera_final: float) -> Resultado:
    try:
        prevalidar(acciones)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo de validación = lote rechazado
        if type(exc).__name__ == "FailSafeException":
            raise
        return Resultado(ok=False, total=len(_aplanar(acciones)), error=str(exc), rechazado=True)

    ctx = Contexto()
    ctx.res.total = len(_aplanar(acciones))
    t0 = time.monotonic()
    try:
        for a in acciones:
            _ejecutar_una(ctx, a)
    except AstraxError as exc:
        ctx.res.ok, ctx.res.error = False, str(exc)
    except Exception as exc:  # noqa: BLE001
        if type(exc).__name__ == "FailSafeException":
            _soltar_todo(ctx)
            raise  # el decorador @accion lo convierte en el mensaje de fail-safe
        ctx.res.ok, ctx.res.error = False, f"acción {ctx.indice}: {exc}"
    finally:
        _soltar_todo(ctx)

    # Captura final: también tras un error, para que la IA vea el estado real.
    if captura_final or not ctx.res.ok:
        if espera_final > 0:
            time.sleep(espera_final)
        try:
            img, e = gui.capturar(escala=escala, marcar_cursor=True)
            ctx.res.frames.append(("final", img, e))
        except Exception as exc:  # noqa: BLE001
            ctx.res.salidas.append(f"(no pude capturar la pantalla final: {exc})")
    ctx.res.segundos = time.monotonic() - t0
    return ctx.res
