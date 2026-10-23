"""Interacción con el SO: portapapeles y terminal (ambos exigen permiso explícito)."""

import re
import subprocess
from pathlib import Path

from .config import MAX_SALIDA, SCOPE_PORTAPAPELES, SCOPE_TERMINAL
from .utils import AstraxError, accion, log, truncar

# Red de seguridad contra accidentes obvios de modelos ligeros. NO es un sandbox.
_PELIGROSOS = [
    r"\brm\s+(-\w*[rR]\w*\s+)*-\w*[fF]\w*\s+(/|~|\*|\$HOME)(\s|$)",
    r"\brm\s+(-\w*[fF]\w*\s+)*-\w*[rR]\w*\s+(/|~|\*|\$HOME)(\s|$)",
    r"\bmkfs(\.\w+)?\b",
    r"\bdd\b.*\bof=/dev/",
    r":\(\)\s*\{.*\};\s*:",
    r"\bformat\s+[a-zA-Z]:",
    r"\b(del|erase)\s+/[sfqSFQ].*\b[a-zA-Z]:\\",
    r"\brmdir\s+/s\s+/q\s+[a-zA-Z]:\\",
    r"\bRemove-Item\b.*-Recurse.*\b[a-zA-Z]:\\\s*($|[;|])",
    r"\b(shutdown|reboot|halt|poweroff)\b",
]
_PELIGROSOS_RE = [re.compile(p, re.IGNORECASE) for p in _PELIGROSOS]


def comando_peligroso(comando: str) -> bool:
    return any(p.search(comando) for p in _PELIGROSOS_RE)


def portapapeles_op(operacion: str, texto: str = "") -> str:
    """Lee o escribe el portapapeles (reutilizado por la herramienta y por el lote)."""
    try:
        import pyperclip
    except ImportError:
        raise AstraxError("falta 'pyperclip' (en Linux además xclip o xsel).") from None
    a = operacion.strip().lower()
    if a == "leer":
        return truncar(pyperclip.paste(), MAX_SALIDA) or "(portapapeles vacío)"
    if a == "escribir":
        pyperclip.copy(texto)
        return f"OK: {len(texto)} caracteres copiados."
    raise AstraxError("operacion debe ser 'leer' o 'escribir'.")


def ejecutar_shell(comando: str, timeout_seg: int = 30, directorio: str | None = None) -> str:
    """Ejecuta un comando de shell (reutilizado por la herramienta y por el lote)."""
    if not comando.strip():
        raise AstraxError("el comando está vacío.")
    if comando_peligroso(comando):
        raise AstraxError("comando bloqueado por seguridad (patrón destructivo). Pídelo al usuario.")
    cwd = None
    if directorio:
        cwd = Path(directorio).expanduser()
        if not cwd.is_dir():
            raise AstraxError(f"el directorio '{directorio}' no existe.")
    limite = max(1, min(int(timeout_seg), 120))
    log(f"Ejecutando: {comando[:200]}")
    try:
        r = subprocess.run(  # noqa: S602 - shell=True es intencional y está bajo permiso
            comando,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=limite,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        raise AstraxError(f"el comando superó {limite} s y se canceló.") from None
    partes = [f"exit={r.returncode}"]
    if r.stdout.strip():
        partes.append("--- stdout ---\n" + truncar(r.stdout.strip(), MAX_SALIDA))
    if r.stderr.strip():
        partes.append("--- stderr ---\n" + truncar(r.stderr.strip(), MAX_SALIDA))
    return "\n".join(partes)


def register(mcp) -> None:
    @mcp.tool()
    @accion(SCOPE_PORTAPAPELES)
    def astrax_portapapeles(operacion: str, texto: str = "") -> str:
        """Portapapeles: operacion="leer" devuelve su contenido; operacion="escribir" lo reemplaza por `texto`."""
        return portapapeles_op(operacion, texto)

    @mcp.tool()
    @accion(SCOPE_TERMINAL)
    def astrax_ejecutar_comando(
        comando: str, timeout_seg: int = 30, directorio: str | None = None
    ) -> str:
        """Ejecuta un comando de shell (sin entrada interactiva). Devuelve código de salida, stdout y stderr recortados."""
        return ejecutar_shell(comando, timeout_seg, directorio)
