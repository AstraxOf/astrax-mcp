"""Tests del motor multi-acción con un pyautogui falso (no necesita pantalla)."""

import asyncio
from types import SimpleNamespace

import pytest
from PIL import Image

from astrax_mcp import acciones as motor
from astrax_mcp import config, gui, state
from astrax_mcp.state import TaskStore
from astrax_mcp.utils import AstraxError


class FalsoPag:
    """Registra llamadas; pantalla 1000x500."""

    KEYBOARD_KEYS = ["a", "d", "w", "ctrl", "l", "shift", "enter", "space", "right", "left", "esc"]

    def __init__(self):
        self.llamadas: list[tuple] = []
        self.falla_en: str | None = None

    def size(self):
        return SimpleNamespace(width=1000, height=500)

    def screenshot(self):
        return Image.new("RGB", (1000, 500), "white")

    def position(self):
        return (10, 10)

    def _reg(self, nombre, *a, **k):
        if self.falla_en == nombre:
            raise RuntimeError("fallo simulado")
        self.llamadas.append((nombre, a, k))

    def __getattr__(self, nombre):
        if nombre.startswith("_"):
            raise AttributeError(nombre)
        return lambda *a, **k: self._reg(nombre, *a, **k)


@pytest.fixture()
def pag(monkeypatch):
    f = FalsoPag()
    monkeypatch.setattr(gui, "_pag", f)
    gui.mapa.escala = 1.0
    monkeypatch.setattr(motor, "PAUSA_ENTRE_ACCIONES", 0)
    return f


@pytest.fixture()
def store(tmp_path, monkeypatch):
    s = TaskStore(tmp_path / "estado.json")
    monkeypatch.setattr(state, "store", s)
    return s


def nombres(pag):
    return [c[0] for c in pag.llamadas]


def correr(lista, captura_final=True, escala=None):
    acc = motor.parsear(lista)
    return motor.ejecutar(acc, captura_final, escala, 0)


# ------------------------------- ejecución -------------------------------- #
def test_lote_se_ejecuta_en_orden_y_devuelve_una_imagen(pag):
    res = correr([
        {"a": "mover", "x": 100, "y": 100},
        {"a": "clic", "x": 100, "y": 100},
        {"a": "escribir", "texto": "hola", "enter": True},
        {"a": "tecla", "tecla": "ctrl+l"},
    ])
    assert res.ok and res.hechas == res.total == 4
    assert nombres(pag) == ["moveTo", "moveTo", "click", "write", "press", "hotkey"]
    assert [f[0] for f in res.frames] == ["final"]


def test_error_detiene_el_lote_y_envia_captura(pag):
    pag.falla_en = "click"
    res = correr([{"a": "mover", "x": 1, "y": 1}, {"a": "clic", "x": 5, "y": 5}, {"a": "tecla", "tecla": "enter"}])
    assert not res.ok and res.hechas == 1 and "acción 2" in res.error and "fallo simulado" in res.error
    assert "press" not in nombres(pag)  # la 3.ª no se ejecutó
    assert res.frames and res.frames[-1][0] == "final"


def test_teclas_y_botones_siempre_se_sueltan(pag):
    pag.falla_en = "press"
    res = correr([{"a": "abajo", "teclas": ["w"]}, {"a": "raton_abajo", "b": "left"}, {"a": "tecla", "tecla": "enter"}])
    assert not res.ok
    n = nombres(pag)
    assert "keyUp" in n and "mouseUp" in n


def test_mantener_con_mientras_y_suelta_al_final(pag):
    res = correr([{
        "a": "mantener", "teclas": ["right"], "seg": 0,
        "mientras": [{"a": "tecla", "tecla": "space"}, {"a": "tecla", "tecla": "space"}],
    }])
    assert res.ok
    assert nombres(pag) == ["keyDown", "press", "press", "keyUp"]


def test_repetir_expande_y_respeta_limite(pag):
    res = correr([{"a": "repetir", "n": 3, "acciones": [{"a": "tecla", "tecla": "a"}]}], captura_final=False)
    assert res.hechas == 3 and nombres(pag).count("press") == 3
    with pytest.raises(AstraxError):
        motor.parsear([{"a": "repetir", "n": 50, "acciones": [{"a": "tecla", "tecla": "a"}] * 3}])


def test_arrastrar_hace_down_move_up(pag):
    correr([{"a": "arrastrar", "x": 10, "y": 10, "x2": 200, "y2": 100}], captura_final=False)
    assert nombres(pag) == ["moveTo", "mouseDown", "moveTo", "mouseUp"]


def test_capturas_intermedias_y_maximo(pag):
    res = correr([{"a": "captura"}, {"a": "esperar", "seg": 0.05}, {"a": "captura", "escala": 0.3}])
    assert [f[0] for f in res.frames][-1] == "final" and len(res.frames) == 3
    lista = [{"a": "captura"}] * (config.MAX_FRAMES + 1)
    r = correr(lista)
    assert r.rechazado and "capturas intermedias" in r.error  # detectado en seco


# --------------------------- validación previa ---------------------------- #
@pytest.mark.parametrize("malo", [
    [], "x", [{"a": "volar"}], [{"x": 1}], [1],
    [{"a": "repetir", "n": 2}],
])
def test_formato_invalido_se_rechaza_antes_de_ejecutar(pag, malo):
    with pytest.raises(AstraxError):
        motor.parsear(malo)
    assert pag.llamadas == []


def test_error_en_accion_tardia_no_ejecuta_ninguna(pag):
    """Una tecla inválida en la acción 3 debe rechazar el lote ANTES de mover nada."""
    res = correr([
        {"a": "clic", "x": 5, "y": 5},
        {"a": "escribir", "texto": "hola"},
        {"a": "tecla", "tecla": "noexiste"},
    ])
    assert res.rechazado and not res.ok and "acción 3" in res.error and "no válidas" in res.error
    assert pag.llamadas == [] and res.frames == []


def test_fuera_de_pantalla_rechaza_todo_el_lote(pag):
    res = correr([{"a": "tecla", "tecla": "a"}, {"a": "clic", "x": 5000, "y": 5}])
    assert res.rechazado and "fuera de pantalla" in res.error
    assert pag.llamadas == []


def test_pasada_en_seco_no_duerme_ni_escribe_portapapeles(pag, monkeypatch):
    import time as _t

    dormido = []
    monkeypatch.setattr(_t, "sleep", lambda s: dormido.append(s))
    motor.prevalidar(motor.parsear([{"a": "esperar", "seg": 10}, {"a": "escribir", "texto": "ñ"},
                                    {"a": "comando", "cmd": "echo hola"}]))
    assert dormido == [] and pag.llamadas == []


def test_comando_peligroso_se_rechaza_en_la_validacion(pag):
    res = correr([{"a": "tecla", "tecla": "a"}, {"a": "comando", "cmd": "rm -rf /"}])
    assert res.rechazado and pag.llamadas == []


def test_presupuesto_de_tiempo(pag, monkeypatch):
    monkeypatch.setattr(motor, "MAX_TOTAL_SEG", 0.1)
    res = correr([{"a": "esperar", "seg": 0.06}, {"a": "esperar", "seg": 0.06}], captura_final=False)
    assert res.rechazado and "Divídelo" in res.error  # se detecta en seco, sin esperar nada


# ----------------------------- escala/coordenadas -------------------------- #
def test_coordenadas_se_convierten_desde_la_ultima_imagen(pag):
    img, e = gui.capturar(escala=0.5)
    assert img.size == (500, 250) and gui.mapa.escala == 0.5
    correr([{"a": "clic", "x": 100, "y": 50}], captura_final=False)
    assert pag.llamadas[0][1] == (200, 100)  # 100/0.5, 50/0.5


def test_escala_automatica_limita_el_lado_mayor(pag, monkeypatch):
    monkeypatch.setattr(gui, "MAX_LADO_IMG", 500)
    img, e = gui.capturar()
    assert max(img.size) == 500 and e == 0.5


def test_fotograma_intermedio_no_cambia_el_mapa(pag):
    gui.mapa.escala = 1.0
    correr([{"a": "captura", "escala": 0.3}, {"a": "clic", "x": 100, "y": 100}], captura_final=False)
    mueve = [c for c in pag.llamadas if c[0] == "moveTo"]
    assert mueve[-1][1][:2] == (100, 100)  # no se dividió por 0.3
    assert gui.mapa.escala == 1.0


# -------------------------------- permisos --------------------------------- #
def test_scopes_del_lote_incluyen_captura_y_portapapeles():
    acc = motor.parsear([{"a": "clic", "x": 1, "y": 1}, {"a": "escribir", "texto": "ñandú"}])
    assert set(motor.scopes_necesarios(acc, True)) == {"pantalla", "raton_teclado", "portapapeles"}
    assert set(motor.scopes_necesarios(acc, False)) == {"raton_teclado", "portapapeles"}


def test_lote_es_todo_o_nada_si_falta_un_permiso(pag, store):
    pytest.importorskip("mcp")
    from astrax_mcp.server import crear_servidor

    store.crear("t", ["a"], ["raton_teclado"])  # sin 'pantalla'
    store.autorizar()
    mcp = crear_servidor()
    res = asyncio.run(mcp.call_tool("astrax_acciones", {"acciones": [{"a": "clic", "x": 1, "y": 1}]}))
    assert "pantalla" in str(res)
    assert pag.llamadas == []  # no se movió nada


def test_herramienta_completa_devuelve_texto_e_imagen(pag, store):
    pytest.importorskip("mcp")
    from astrax_mcp.server import crear_servidor

    store.crear("t", ["a"], ["raton_teclado", "pantalla"])
    store.autorizar()
    mcp = crear_servidor()
    res = asyncio.run(mcp.call_tool(
        "astrax_acciones",
        {"acciones": [{"a": "clic", "x": 10, "y": 10}, {"a": "escribir", "texto": "hi"}], "espera_final": 0},
    ))
    contenido = res[0] if isinstance(res, tuple) else res
    tipos = [c.type for c in contenido]
    assert tipos == ["text", "image"]
    assert "OK: 2/2" in contenido[0].text
