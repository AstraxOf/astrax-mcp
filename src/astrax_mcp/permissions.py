"""Control de permisos de sesión: una autorización por tarea, no por paso."""

from . import state
from .config import REQUIRE_SESSION


def exigir(scope: str) -> str | None:
    """Devuelve None si `scope` está autorizado; si no, un mensaje de error guía."""
    if not REQUIRE_SESSION:
        return None
    return state.store.verificar_permiso(scope)
