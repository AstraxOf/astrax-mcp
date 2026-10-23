"""Motor de estado de tareas: archivo temporal aislado (.astrax_task_state.json).

La IA descompone la petición en pasos, y cada paso se ejecuta leyendo SOLO este
archivo (paso actual + datos guardados), sin releer historial ni capturas viejas.
"""

import json
import os
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import (
    MAX_DATO_CHARS,
    MAX_DATOS,
    MAX_INTENTOS,
    MAX_PASOS,
    SCOPES,
    SESSION_MINUTES,
    STATE_FILE,
)
from .utils import AstraxError, log

_CLAVE_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
GUIA_FLUJO = (
    "Flujo: astrax_tarea_crear -> mostrar plan y permisos al usuario -> "
    "astrax_tarea_autorizar(confirmacion_usuario=true)."
)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


class TaskStore:
    def __init__(self, path: Path = STATE_FILE) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ E/S
    def _leer(self) -> dict[str, Any] | None:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, OSError) as exc:
            log(f"Estado ilegible, se ignora: {exc!r}")
            return None

    def _escribir(self, tarea: dict[str, Any]) -> None:
        tarea["actualizada"] = _iso(_ahora())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(tarea, ensure_ascii=False, indent=1), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, self.path)  # escritura atómica

    def _requerir(self) -> dict[str, Any]:
        tarea = self._leer()
        if tarea is None:
            raise AstraxError("no hay tarea activa. Crea una con astrax_tarea_crear.")
        return tarea

    # ------------------------------------------------------------ validación
    @staticmethod
    def _validar_permisos(permisos: list[str] | None) -> list[str]:
        norm = list(dict.fromkeys(p.strip().lower() for p in (permisos or []) if p.strip()))
        invalidos = [p for p in norm if p not in SCOPES]
        if invalidos:
            raise AstraxError(
                f"permisos desconocidos: {', '.join(invalidos)}. Válidos: {', '.join(SCOPES)}."
            )
        return norm

    @staticmethod
    def _validar_dato(clave: str, valor: Any) -> None:
        if not _CLAVE_RE.match(clave):
            raise AstraxError(f"clave '{clave}' no válida (usa letras, números, _ . - ; máx 64).")
        try:
            tam = len(json.dumps(valor, ensure_ascii=False))
        except (TypeError, ValueError):
            raise AstraxError(f"el valor de '{clave}' no es serializable a JSON.") from None
        if tam > MAX_DATO_CHARS:
            raise AstraxError(
                f"'{clave}' ocupa {tam} caracteres (máx {MAX_DATO_CHARS}). "
                "Guarda el contenido en un archivo y almacena solo su ruta."
            )

    # ------------------------------------------------------------- operaciones
    def crear(self, objetivo: str, pasos: list[str], permisos: list[str] | None) -> dict[str, Any]:
        objetivo = (objetivo or "").strip()
        if not objetivo:
            raise AstraxError("el objetivo está vacío.")
        limpios = [p.strip() for p in pasos if isinstance(p, str) and p.strip()]
        if not 1 <= len(limpios) <= MAX_PASOS:
            raise AstraxError(f"indica entre 1 y {MAX_PASOS} pasos no vacíos.")
        solicitados = self._validar_permisos(permisos)
        with self._lock:
            actual = self._leer()
            if actual and actual.get("estado") == "en_curso":
                raise AstraxError(
                    "ya hay una tarea en curso. Termínala con astrax_tarea_completar_paso "
                    "o descártala con astrax_tarea_limpiar."
                )
            tarea = {
                "version": 1,
                "id": uuid.uuid4().hex[:8],
                "objetivo": objetivo[:500],
                "estado": "pendiente_autorizacion",
                "creada": _iso(_ahora()),
                "permisos": {"solicitados": solicitados, "concedidos": [], "expira": None},
                "pasos": [
                    {"n": i, "texto": t[:300], "estado": "pendiente", "intentos": 0, "resumen": ""}
                    for i, t in enumerate(limpios, 1)
                ],
                "paso_actual": 1,
                "datos": {},
            }
            self._escribir(tarea)
            return tarea

    def autorizar(self, permisos_extra: list[str] | None = None) -> dict[str, Any]:
        with self._lock:
            tarea = self._requerir()
            if tarea["estado"] not in ("pendiente_autorizacion", "en_curso"):
                raise AstraxError(
                    f"la tarea está '{tarea['estado']}'. Crea una nueva con astrax_tarea_crear."
                )
            extra = self._validar_permisos(permisos_extra)
            primera_vez = tarea["estado"] == "pendiente_autorizacion"
            conc = list(dict.fromkeys(tarea["permisos"]["solicitados"] + extra))
            tarea["estado"] = "en_curso"
            tarea["permisos"] = {
                "solicitados": conc,
                "concedidos": conc,
                "expira": _iso(_ahora() + timedelta(minutes=SESSION_MINUTES)),
            }
            if primera_vez:
                tarea["paso_actual"] = 1
                tarea["pasos"][0]["estado"] = "en_curso"
            self._escribir(tarea)
            return tarea

    def verificar_permiso(self, scope: str) -> str | None:
        tarea = self._leer()
        if tarea is None:
            return f"ERROR: no hay tarea autorizada. {GUIA_FLUJO}"
        estado = tarea.get("estado")
        if estado == "pendiente_autorizacion":
            return (
                "ERROR: la tarea espera la autorización del usuario. Muestra el plan y los "
                "permisos, pide UNA confirmación y llama astrax_tarea_autorizar."
            )
        if estado != "en_curso":
            return f"ERROR: la tarea está '{estado}', no hay permisos activos. {GUIA_FLUJO}"
        expira = tarea["permisos"].get("expira")
        if expira and datetime.fromisoformat(expira) < _ahora():
            return (
                "ERROR: la autorización expiró. Pide confirmación al usuario y llama "
                "astrax_tarea_autorizar(confirmacion_usuario=true)."
            )
        if scope not in tarea["permisos"]["concedidos"]:
            return (
                f"ERROR: esta tarea no tiene el permiso '{scope}'. Pide al usuario ampliarlo y "
                f"llama astrax_tarea_autorizar(confirmacion_usuario=true, permisos_extra=['{scope}'])."
            )
        return None

    def guardar(self, clave: str, valor: Any) -> dict[str, Any]:
        self._validar_dato(clave, valor)
        with self._lock:
            tarea = self._requerir()
            if clave not in tarea["datos"] and len(tarea["datos"]) >= MAX_DATOS:
                raise AstraxError(f"límite de {MAX_DATOS} datos alcanzado.")
            tarea["datos"][clave] = valor
            self._escribir(tarea)
            return tarea

    def completar_paso(
        self, resumen: str, datos: dict[str, Any] | None, exito: bool
    ) -> tuple[str, dict[str, Any]]:
        """Devuelve (evento, tarea). Eventos: siguiente | completada | reintento | bloqueada."""
        datos = datos or {}
        for k, v in datos.items():
            self._validar_dato(k, v)
        with self._lock:
            tarea = self._requerir()
            if tarea["estado"] != "en_curso":
                raise AstraxError(f"la tarea está '{tarea['estado']}'; no hay paso en curso.")
            paso = tarea["pasos"][tarea["paso_actual"] - 1]
            paso["resumen"] = (resumen or "")[:300]

            if not exito:
                paso["intentos"] += 1
                if paso["intentos"] >= MAX_INTENTOS:
                    paso["estado"] = "fallido"
                    tarea["estado"] = "bloqueada"
                    self._revocar(tarea)
                    evento = "bloqueada"
                else:
                    evento = "reintento"
                self._escribir(tarea)
                return evento, tarea

            nuevos = set(tarea["datos"]) | set(datos)
            if len(nuevos) > MAX_DATOS:
                raise AstraxError(f"límite de {MAX_DATOS} datos alcanzado.")
            tarea["datos"].update(datos)
            paso["estado"] = "hecho"
            if tarea["paso_actual"] < len(tarea["pasos"]):
                tarea["paso_actual"] += 1
                tarea["pasos"][tarea["paso_actual"] - 1]["estado"] = "en_curso"
                evento = "siguiente"
            else:
                tarea["estado"] = "completada"
                self._revocar(tarea)
                evento = "completada"
            self._escribir(tarea)
            return evento, tarea

    @staticmethod
    def _revocar(tarea: dict[str, Any]) -> None:
        tarea["permisos"]["concedidos"] = []
        tarea["permisos"]["expira"] = None

    def limpiar(self) -> bool:
        with self._lock:
            existia = self.path.exists()
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
            return existia

    def resumen(self, completo: bool = False) -> dict[str, Any] | None:
        """Vista compacta (mínimos tokens) para que la IA retome el trabajo."""
        tarea = self._leer()
        if tarea is None:
            return None
        pasos = tarea["pasos"]
        actual = tarea["paso_actual"]
        vista: dict[str, Any] = {
            "id": tarea["id"],
            "objetivo": tarea["objetivo"],
            "estado": tarea["estado"],
            "paso_actual": {"n": actual, "de": len(pasos), "texto": pasos[actual - 1]["texto"]},
            "siguiente": pasos[actual]["texto"] if actual < len(pasos) else None,
            "datos": tarea["datos"],
            "permisos": tarea["permisos"]["concedidos"],
        }
        expira = tarea["permisos"].get("expira")
        if expira:
            resto = (datetime.fromisoformat(expira) - _ahora()).total_seconds() / 60
            vista["autorizacion_min_restantes"] = max(0, round(resto))
        if completo:
            vista["pasos"] = [
                f"{p['n']}. [{p['estado']}] {p['texto']}" + (f" -> {p['resumen']}" if p["resumen"] else "")
                for p in pasos
            ]
        return vista


store = TaskStore()
