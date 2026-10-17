"""Utilidades compartidas: logging a stderr, errores uniformes y truncado.

IMPORTANTE: en stdio, stdout es el canal JSON-RPC. Nunca uses print() sin
file=sys.stderr. Usa siempre `log()`.
"""

import functools
import sys

MSG_FAILSAFE = "ERROR: fail-safe activado (cursor en una esquina). Acción abortada."


class AstraxError(Exception):
    """Error esperado, con un mensaje pensado para que lo lea el modelo."""


def log(mensaje: str) -> None:
    print(f"[Astrax] {mensaje}", file=sys.stderr, flush=True)


def truncar(texto: str, limite: int) -> str:
    """Recorta conservando principio y final (los errores suelen estar al final)."""
    if len(texto) <= limite:
        return texto
    cabeza = int(limite * 0.4)
    cola = limite - cabeza
    omitidos = len(texto) - limite
    return f"{texto[:cabeza]}\n[... {omitidos} caracteres omitidos ...]\n{texto[-cola:]}"


def accion(scope: str | None = None):
    """Decorador de herramientas: exige permiso de sesión y unifica los errores.

    Cualquier fallo se devuelve como texto "ERROR: ..." (nunca rompe el servidor).
    """

    def decorador(fn):
        @functools.wraps(fn)
        def envoltura(*args, **kwargs):
            if scope is not None:
                from . import permissions  # import tardío: evita ciclos

                denegado = permissions.exigir(scope)
                if denegado:
                    return denegado
            try:
                return fn(*args, **kwargs)
            except AstraxError as exc:
                return f"ERROR: {exc}"
            except Exception as exc:  # noqa: BLE001
                if type(exc).__name__ == "FailSafeException":
                    return MSG_FAILSAFE
                log(f"Error en {fn.__name__}: {exc!r}")
                return f"ERROR: {fn.__name__} falló: {exc}"

        return envoltura

    return decorador
