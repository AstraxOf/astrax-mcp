import asyncio
import json

import pytest

from astrax_mcp import config, installer, state, system
from astrax_mcp.state import TaskStore
from astrax_mcp.utils import AstraxError


@pytest.fixture()
def store(tmp_path, monkeypatch):
    s = TaskStore(tmp_path / "estado.json")
    monkeypatch.setattr(state, "store", s)
    return s


# ----------------------------- motor de tareas ---------------------------- #
def test_flujo_completo_y_revocacion(store):
    t = store.crear("Carta", ["Redactar", "Adjuntar", "Enviar"], ["pantalla", "raton_teclado"])
    assert t["estado"] == "pendiente_autorizacion"
    assert store.verificar_permiso("pantalla").startswith("ERROR")  # sin autorizar
    store.autorizar()
    assert store.verificar_permiso("pantalla") is None
    assert "ERROR" in store.verificar_permiso("terminal")  # no solicitado

    ev, t = store.completar_paso("ok", {"pdf_generado": "/tmp/carta.pdf"}, True)
    assert ev == "siguiente" and t["paso_actual"] == 2
    assert store.resumen()["datos"] == {"pdf_generado": "/tmp/carta.pdf"}
    store.completar_paso("ok", None, True)
    ev, t = store.completar_paso("ok", None, True)
    assert ev == "completada" and t["estado"] == "completada"
    assert store.verificar_permiso("pantalla").startswith("ERROR")  # permisos revocados
    assert store.limpiar() is True and store.resumen() is None


def test_bloqueo_tras_fallos_repetidos(store):
    store.crear("x", ["a", "b"], [])
    store.autorizar()
    assert store.completar_paso("f", None, False)[0] == "reintento"
    assert store.completar_paso("f", None, False)[0] == "reintento"
    assert store.completar_paso("f", None, False)[0] == "bloqueada"


def test_validaciones(store):
    with pytest.raises(AstraxError):
        store.crear("x", [], [])
    with pytest.raises(AstraxError):
        store.crear("x", ["a"], ["root"])
    store.crear("x", ["a"], [])
    store.autorizar()
    with pytest.raises(AstraxError):
        store.crear("otra", ["a"], [])  # no se pisa una tarea en curso
    with pytest.raises(AstraxError):
        store.guardar("k", "x" * 5000)
    with pytest.raises(AstraxError):
        store.guardar("clave inválida!", "v")


def test_expiracion(store, monkeypatch):
    monkeypatch.setattr(state, "SESSION_MINUTES", -1)
    store.crear("x", ["a"], ["pantalla"])
    store.autorizar()
    assert "expir" in store.verificar_permiso("pantalla")


# --------------------------------- terminal -------------------------------- #
@pytest.mark.parametrize("cmd", ["rm -rf /", "rm -fr ~", "mkfs.ext4 /dev/sda1", "shutdown -h now", "format C:"])
def test_comandos_peligrosos_bloqueados(cmd):
    assert system.comando_peligroso(cmd)


@pytest.mark.parametrize("cmd", ["ls -la", "git status", "rm temp.txt", "python script.py"])
def test_comandos_normales_permitidos(cmd):
    assert not system.comando_peligroso(cmd)


# --------------------------------- instalador ------------------------------ #
ENTRADA = {"command": "/usr/bin/uvx", "args": ["--from", installer.GIT_URL, "astrax-mcp"]}
ROO = installer.Cliente("roo-code", "Roo", [], soporta_always_allow=True)
CLAUDE = installer.Cliente("claude-desktop", "Claude", [])


def _aplicar(ruta, cliente=CLAUDE, **kw):
    kw = {"auto_aprobar": False, "desinstalar": False, "dry_run": False, **kw}
    return installer.aplicar(ruta, cliente, ENTRADA, **kw)


def test_instalador_conserva_otros_servidores_y_hace_backup(tmp_path):
    ruta = tmp_path / "cfg.json"
    ruta.write_text(json.dumps({"theme": "dark", "mcpServers": {"otro": {"command": "x"}}}))
    assert "añadido" in _aplicar(ruta)
    datos = json.loads(ruta.read_text())
    assert datos["theme"] == "dark" and datos["mcpServers"]["otro"] == {"command": "x"}
    assert datos["mcpServers"]["astrax"]["command"] == "/usr/bin/uvx"
    assert list(tmp_path.glob("cfg.json.astrax-bak-*"))
    assert "sin cambios" in _aplicar(ruta)  # idempotente


def test_instalador_no_toca_json_invalido(tmp_path):
    ruta = tmp_path / "cfg.json"
    ruta.write_text("{ esto no es json")
    with pytest.raises(installer.ErrorInstalacion):
        _aplicar(ruta)
    assert ruta.read_text() == "{ esto no es json"


def test_instalador_crea_archivo_y_desinstala(tmp_path):
    ruta = tmp_path / "sub" / "cfg.json"
    assert "añadido" in _aplicar(ruta)
    assert "eliminado" in _aplicar(ruta, desinstalar=True)
    assert "astrax" not in json.loads(ruta.read_text())["mcpServers"]


def test_auto_aprobar_excluye_autorizacion_y_respeta_campos(tmp_path):
    ruta = tmp_path / "cfg.json"
    ruta.write_text(json.dumps({"mcpServers": {"astrax": {"command": "old", "alwaysAllow": ["mi_tool"], "timeout": 99}}}))
    _aplicar(ruta, ROO, auto_aprobar=True)
    e = json.loads(ruta.read_text())["mcpServers"]["astrax"]
    assert e["timeout"] == 99 and "mi_tool" in e["alwaysAllow"]
    assert config.TOOL_AUTORIZAR not in e["alwaysAllow"]
    assert "astrax_clic" in e["alwaysAllow"]


def test_dry_run_no_escribe(tmp_path):
    ruta = tmp_path / "cfg.json"
    assert "simulación" in _aplicar(ruta, dry_run=True)
    assert not ruta.exists()


# ------------------------------- servidor MCP ------------------------------ #
def test_servidor_registra_todas_las_herramientas(store):
    pytest.importorskip("mcp")
    from astrax_mcp.server import crear_servidor

    mcp = crear_servidor()
    tools = asyncio.run(mcp.list_tools())
    assert {t.name for t in tools} == set(config.TODAS_LAS_HERRAMIENTAS)


def test_accion_sin_tarea_devuelve_guia(store):
    pytest.importorskip("mcp")
    from astrax_mcp.server import crear_servidor

    mcp = crear_servidor()
    res = asyncio.run(mcp.call_tool("astrax_clic", {"x": 1, "y": 1}))
    texto = json.dumps(res, default=str)
    assert "astrax_tarea_crear" in texto
