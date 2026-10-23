"""Instalador / wizard de Astrax: registra el servidor en los clientes MCP detectados.

Uso:
    uvx --from git+https://github.com/AstraxOf/astrax-mcp.git astrax-install --yes
    astrax-install                 # asistente interactivo
    astrax-install --list          # ver clientes detectados
    astrax-install --uninstall     # quitar solo la entrada "astrax"

Garantías: solo toca la clave "astrax" dentro de "mcpServers"; conserva el resto
del archivo; hace copia de seguridad antes de escribir; escritura atómica; y si el
JSON existente es inválido, NO lo modifica.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from . import __version__
from .config import AUTO_APROBABLES, TOOL_AUTORIZAR

SERVER_KEY = "astrax"
GIT_URL = "git+https://github.com/AstraxOf/astrax-mcp.git"


class ErrorInstalacion(Exception):
    pass


# --------------------------------------------------------------------------- #
# Detección de sistema operativo y clientes
# --------------------------------------------------------------------------- #


def nombre_so() -> str:
    return {"win32": "Windows", "darwin": "macOS"}.get(sys.platform, "Linux")


def _base_app_dir() -> Path:
    """Directorio de datos de aplicaciones del usuario según el SO."""
    home = Path.home()
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming")
    if sys.platform == "darwin":
        return home / "Library" / "Application Support"
    return Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")


@dataclass
class Cliente:
    id: str
    nombre: str
    rutas: list[Path]
    soporta_always_allow: bool = False
    nota: str = field(default="")

    def detectadas(self) -> list[Path]:
        """Rutas de config cuyo archivo o carpeta contenedora ya existe."""
        return [r for r in self.rutas if r.exists() or r.parent.exists()]

    def destinos(self, forzar: bool) -> list[Path]:
        encontradas = self.detectadas()
        if encontradas:
            return encontradas
        return [self.rutas[0]] if forzar else []


def definir_clientes() -> list[Cliente]:
    base = _base_app_dir()
    home = Path.home()
    editores = ["Code", "Code - Insiders", "VSCodium", "Cursor", "Windsurf"]

    def vscode(extension: str, archivo: str) -> list[Path]:
        return [
            base / e / "User" / "globalStorage" / extension / "settings" / archivo for e in editores
        ]

    return [
        Cliente("claude-desktop", "Claude Desktop", [base / "Claude" / "claude_desktop_config.json"]),
        Cliente(
            "roo-code",
            "Roo Code",
            vscode("rooveterinaryinc.roo-cline", "mcp_settings.json"),
            soporta_always_allow=True,
        ),
        Cliente(
            "cline",
            "Cline",
            vscode("saoudrizwan.claude-dev", "cline_mcp_settings.json"),
            soporta_always_allow=True,
        ),
        Cliente("cursor", "Cursor", [home / ".cursor" / "mcp.json"]),
        Cliente("windsurf", "Windsurf", [home / ".codeium" / "windsurf" / "mcp_config.json"]),
        Cliente("gemini-cli", "Gemini CLI", [home / ".gemini" / "settings.json"]),
    ]


# --------------------------------------------------------------------------- #
# Construcción de la entrada del servidor
# --------------------------------------------------------------------------- #


def _paquete_instalado() -> bool:
    try:
        importlib.metadata.version("astrax-mcp")
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


def resolver_fuente(fuente: str) -> tuple[str, dict[str, Any]]:
    """Devuelve (fuente_efectiva, {command, args[, env]}) para el cliente MCP."""
    uvx = shutil.which("uvx")
    if fuente == "auto":
        fuente = "git" if uvx else "local"
    if fuente in ("git", "pypi"):
        if not uvx:
            raise ErrorInstalacion(
                "No se encontró 'uvx'. Instala uv (https://docs.astral.sh/uv/) o usa --source local."
            )
        args = ["--from", GIT_URL, "astrax-mcp"] if fuente == "git" else ["astrax-mcp"]
        return fuente, {"command": uvx, "args": args}  # ruta absoluta: los clientes GUI no heredan PATH
    entrada: dict[str, Any] = {"command": sys.executable, "args": ["-m", "astrax_mcp"]}
    if not _paquete_instalado():
        entrada["env"] = {"PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    return "local", entrada


def fusionar_entrada(previo: Any, nueva: dict[str, Any], auto_aprobar: bool) -> dict[str, Any]:
    """Actualiza command/args/env conservando cualquier otro campo del usuario."""
    resultado: dict[str, Any] = dict(previo) if isinstance(previo, dict) else {}
    resultado["command"] = nueva["command"]
    resultado["args"] = nueva["args"]
    env_previo = resultado.get("env") if isinstance(resultado.get("env"), dict) else {}
    env = {**env_previo, **nueva.get("env", {})}
    if env:
        resultado["env"] = env
    if auto_aprobar:
        previos = resultado.get("alwaysAllow") if isinstance(resultado.get("alwaysAllow"), list) else []
        lista = list(dict.fromkeys([*previos, *AUTO_APROBABLES]))
        resultado["alwaysAllow"] = [t for t in lista if t != TOOL_AUTORIZAR]
    return resultado


# --------------------------------------------------------------------------- #
# Lectura / escritura segura del JSON
# --------------------------------------------------------------------------- #


def leer_config(ruta: Path) -> dict[str, Any]:
    if not ruta.exists():
        return {}
    texto = ruta.read_text(encoding="utf-8-sig")
    if not texto.strip():
        return {}
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ErrorInstalacion(f"JSON inválido en {ruta} ({exc}); no se modificó.") from None
    if not isinstance(datos, dict):
        raise ErrorInstalacion(f"{ruta} no contiene un objeto JSON; no se modificó.")
    return datos


def escribir_config(ruta: Path, datos: dict[str, Any]) -> Path | None:
    """Backup + escritura atómica. Devuelve la ruta del backup (si lo hubo)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if ruta.exists() and ruta.stat().st_size > 0:
        backup = ruta.with_name(f"{ruta.name}.astrax-bak-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(ruta, backup)
    tmp = ruta.with_name(ruta.name + ".astrax-tmp")
    tmp.write_text(json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, ruta)
    return backup


def aplicar(
    ruta: Path,
    cliente: Cliente,
    entrada: dict[str, Any],
    *,
    auto_aprobar: bool,
    desinstalar: bool,
    dry_run: bool,
) -> str:
    """Modifica solo mcpServers.astrax. Devuelve el resultado en una palabra/frase."""
    config = leer_config(ruta)
    servidores = config.get("mcpServers", {})
    if not isinstance(servidores, dict):
        raise ErrorInstalacion(f"'mcpServers' en {ruta} no es un objeto; no se modificó.")
    previo = servidores.get(SERVER_KEY)

    if desinstalar:
        if previo is None:
            return "sin cambios (no estaba instalado)"
        servidores = {k: v for k, v in servidores.items() if k != SERVER_KEY}
        resultado = "eliminado"
    else:
        nueva = fusionar_entrada(previo, entrada, auto_aprobar and cliente.soporta_always_allow)
        if previo == nueva:
            return "sin cambios (ya estaba al día)"
        servidores = {**servidores, SERVER_KEY: nueva}
        resultado = "actualizado" if previo is not None else "añadido"

    config["mcpServers"] = servidores
    if dry_run:
        return f"{resultado} (simulación, no se escribió nada)"
    backup = escribir_config(ruta, config)
    return resultado + (f" (copia: {backup.name})" if backup else "")


# --------------------------------------------------------------------------- #
# CLI / wizard
# --------------------------------------------------------------------------- #


def _preguntar(texto: str, defecto: str = "") -> str:
    try:
        return input(texto).strip() or defecto
    except EOFError:
        return defecto


def _seleccion_interactiva(clientes: list[Cliente], detectados: list[Cliente]) -> list[Cliente]:
    print("\nClientes MCP:")
    for i, c in enumerate(clientes, 1):
        marca = "detectado" if c in detectados else "no detectado"
        print(f"  {i}. {c.nombre:<15} [{marca}]")
    resp = _preguntar("\n¿Dónde instalar? (ej. 1,3 | Enter = todos los detectados): ")
    if not resp:
        return detectados
    elegidos = []
    for trozo in resp.replace(" ", "").split(","):
        if trozo.isdigit() and 1 <= int(trozo) <= len(clientes):
            elegidos.append(clientes[int(trozo) - 1])
    return elegidos


def _parser() -> argparse.ArgumentParser:
    ids = [c.id for c in definir_clientes()]
    p = argparse.ArgumentParser(
        prog="astrax-install",
        description="Instala Astrax MCP en tus clientes de IA (Claude Desktop, Roo Code, Cline, Cursor...).",
    )
    p.add_argument("-c", "--client", action="append", choices=ids, metavar="ID",
                   help=f"cliente destino (repetible). IDs: {', '.join(ids)}")
    p.add_argument("-y", "--yes", action="store_true",
                   help="sin preguntas: instala en todos los clientes detectados")
    p.add_argument("--source", choices=["auto", "git", "pypi", "local"], default="auto",
                   help="de dónde ejecuta el cliente el servidor (por defecto: git con uvx, o local)")
    p.add_argument("--auto-approve", action="store_true",
                   help="Roo Code/Cline: añade alwaysAllow a todas las herramientas EXCEPTO "
                        f"{TOOL_AUTORIZAR} (una sola confirmación por tarea)")
    p.add_argument("--uninstall", action="store_true", help="elimina la entrada 'astrax'")
    p.add_argument("--dry-run", action="store_true", help="muestra qué se haría sin escribir")
    p.add_argument("--list", action="store_true", help="lista clientes detectados y sale")
    p.add_argument("--version", action="version", version=f"astrax-install {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    args = _parser().parse_args(argv)
    clientes = definir_clientes()
    detectados = [c for c in clientes if c.detectadas()]
    print(f"Astrax {__version__} · Sistema: {nombre_so()}")

    if args.list:
        for c in clientes:
            rutas = c.detectadas()
            print(f"- {c.id:<15} {'detectado' if rutas else 'no detectado'}")
            for r in rutas:
                try:
                    ya = SERVER_KEY in leer_config(r).get("mcpServers", {})
                except (ErrorInstalacion, OSError):
                    ya = False
                print(f"    {r}{'  [astrax instalado]' if ya else ''}")
        return 0

    interactivo = sys.stdin.isatty() and not args.yes and not args.client
    if args.client:
        elegidos = [c for c in clientes if c.id in args.client]
    elif interactivo:
        elegidos = _seleccion_interactiva(clientes, detectados)
    else:
        elegidos = detectados

    if not elegidos:
        print("\nNo se detectó ningún cliente MCP. Configúralo manualmente con este bloque:\n")
        try:
            _, entrada = resolver_fuente(args.source)
        except ErrorInstalacion as exc:
            print(f"ERROR: {exc}")
            return 1
        print(json.dumps({"mcpServers": {SERVER_KEY: entrada}}, indent=2, ensure_ascii=False))
        print("\nO indica un cliente concreto: astrax-install --client claude-desktop")
        return 2

    auto_aprobar = args.auto_approve
    if interactivo and not args.uninstall and any(c.soporta_always_allow for c in elegidos):
        r = _preguntar(
            "¿Aprobar automáticamente las herramientas de Astrax en Roo/Cline, salvo la "
            "autorización de tarea? [s/N]: "
        ).lower()
        auto_aprobar = r in ("s", "si", "sí", "y", "yes")

    entrada: dict[str, Any] = {}
    if not args.uninstall:
        try:
            fuente, entrada = resolver_fuente(args.source)
        except ErrorInstalacion as exc:
            print(f"ERROR: {exc}")
            return 1
        print(f"Fuente: {fuente} -> {entrada['command']} {' '.join(entrada['args'])}")

    errores = 0
    for c in elegidos:
        destinos = c.destinos(forzar=bool(args.client))
        for ruta in destinos:
            try:
                res = aplicar(ruta, c, entrada, auto_aprobar=auto_aprobar,
                              desinstalar=args.uninstall, dry_run=args.dry_run)
                print(f"[OK]    {c.nombre}: {res}\n        {ruta}")
            except (ErrorInstalacion, OSError) as exc:
                errores += 1
                print(f"[ERROR] {c.nombre}: {exc}\n        {ruta}")

    if not args.uninstall and not args.dry_run and errores < len(elegidos):
        print("\nListo. Reinicia el cliente (cierra Claude Desktop por completo) para cargar Astrax.")
        print("Claude Code:  claude mcp add astrax -- uvx --from " + GIT_URL + " astrax-mcp")
        if any(c.soporta_always_allow for c in elegidos) and not auto_aprobar:
            print("Tip: usa --auto-approve para evitar confirmaciones en cada herramienta (Roo/Cline).")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
