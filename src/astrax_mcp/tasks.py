"""Herramientas MCP del gestor de tareas (contexto aislado por archivo de estado)."""

import json
from typing import Any

from . import state
from .config import SCREENSHOT_DIR, SESSION_MINUTES, TOOL_AUTORIZAR
from .utils import AstraxError, accion


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _borrar_capturas() -> None:
    if SCREENSHOT_DIR.is_dir():
        for f in SCREENSHOT_DIR.glob("*.png"):
            try:
                f.unlink()
            except OSError:
                pass


def register(mcp) -> None:
    @mcp.tool()
    @accion()
    def astrax_tarea_crear(objetivo: str, pasos: list[str], permisos_requeridos: list[str]) -> str:
        """PASO 1 de toda petición multi-paso. Guarda el plan (pasos ordenados, cortos y concretos) en el archivo de estado.

        permisos_requeridos: TODO lo que necesitará la tarea completa, de entre
        pantalla, raton_teclado, portapapeles, terminal. Después muestra plan y permisos
        al usuario y pide UNA confirmación.
        """
        t = state.store.crear(objetivo, pasos, permisos_requeridos)
        plan = "\n".join(f"{p['n']}. {p['texto']}" for p in t["pasos"])
        permisos = ", ".join(t["permisos"]["solicitados"]) or "ninguno"
        return (
            f"Tarea {t['id']} creada (pendiente de autorización).\n{plan}\n"
            f"Permisos requeridos: {permisos}\n"
            "SIGUIENTE: muestra el plan y los permisos al usuario, pide UNA confirmación y, solo "
            f"con su 'sí' explícito, llama {TOOL_AUTORIZAR}(confirmacion_usuario=true)."
        )

    @mcp.tool()
    @accion()
    def astrax_tarea_autorizar(
        confirmacion_usuario: bool, permisos_extra: list[str] | None = None
    ) -> str:
        """Concede los permisos de la tarea durante la sesión. Llamar SOLO tras mostrar el plan y recibir un 'sí' explícito del usuario. Nunca sin preguntarle."""
        if not confirmacion_usuario:
            raise AstraxError("sin confirmación del usuario no se concede ningún permiso.")
        t = state.store.autorizar(permisos_extra)
        paso = t["pasos"][t["paso_actual"] - 1]
        return (
            f"OK: tarea autorizada {SESSION_MINUTES} min con permisos: "
            f"{', '.join(t['permisos']['concedidos']) or 'ninguno'}.\n"
            f"Paso {t['paso_actual']}/{len(t['pasos'])}: {paso['texto']}"
        )

    @mcp.tool()
    @accion()
    def astrax_tarea_estado(completo: bool = False) -> str:
        """Lee el estado compacto: paso actual, siguiente y datos guardados. Úsalo al empezar cada paso EN LUGAR de releer el historial o capturas viejas."""
        vista = state.store.resumen(completo)
        if vista is None:
            return "No hay tarea activa. Si la petición tiene varios pasos, usa astrax_tarea_crear."
        return _json(vista)

    @mcp.tool()
    @accion()
    def astrax_tarea_guardar(clave: str, valor: Any) -> str:
        """Guarda un dato clave de la tarea (p. ej. pdf_generado=/ruta/carta.pdf). Guarda RUTAS o valores cortos, no contenidos largos."""
        state.store.guardar(clave, valor)
        return f"OK: '{clave}' guardado."

    @mcp.tool()
    @accion()
    def astrax_tarea_completar_paso(
        resumen: str, datos: dict[str, Any] | None = None, exito: bool = True
    ) -> str:
        """Cierra el paso actual (exito=true) y devuelve el siguiente, o registra un fallo (exito=false). `datos` = salidas del paso para los siguientes. Al cerrar el último paso se revocan los permisos."""
        evento, t = state.store.completar_paso(resumen, datos, exito)
        n, total = t["paso_actual"], len(t["pasos"])
        if evento == "siguiente":
            siguiente = t["pasos"][n - 1]["texto"]
            return f"OK: paso {n - 1}/{total} hecho. SIGUIENTE paso {n}/{total}: {siguiente}"
        if evento == "completada":
            _borrar_capturas()
            return (
                "OK: tarea COMPLETADA y permisos revocados. Datos finales: "
                f"{_json(t['datos'])}. Informa al usuario; usa astrax_tarea_limpiar si ya no "
                "necesitas el estado."
            )
        intentos = t["pasos"][n - 1]["intentos"]
        if evento == "reintento":
            return (
                f"FALLO registrado en el paso {n}/{total} (intento {intentos}). Analiza la "
                "pantalla y prueba un enfoque distinto, sin repetir lo mismo."
            )
        return (
            f"BLOQUEADA: el paso {n}/{total} falló {intentos} veces y los permisos fueron "
            "revocados. Detente y explica al usuario qué falló."
        )

    @mcp.tool()
    @accion()
    def astrax_tarea_limpiar() -> str:
        """Borra el archivo de estado y las capturas temporales (descartar o cerrar una tarea)."""
        _borrar_capturas()
        return "OK: estado limpiado." if state.store.limpiar() else "OK: no había estado."
