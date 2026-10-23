"""Herramienta MCP de control: UNA llamada = N acciones de ratón/teclado (multi-acción)."""

import io
from typing import Any

from . import acciones as motor
from . import permissions
from .compat import MCPImage
from .config import ESPERA_FINAL, JPEG_QUALITY, TOOL_ACCIONES
from .utils import accion, log


def _jpeg(imagen) -> MCPImage:
    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return MCPImage(data=buffer.getvalue(), format="jpeg")


def registrar_resultado(res: motor.Resultado) -> list[Any]:
    """Texto compacto + imágenes. Un solo bloque de texto, las imágenes a continuación."""
    if res.rechazado:
        cab = (
            f"RECHAZADO sin ejecutar nada ({res.total} acciones): {res.error} "
            "Corrige ese punto y reenvía el lote completo."
        )
    elif res.ok:
        cab = f"OK: {res.hechas}/{res.total} acciones en {res.segundos:.1f}s."
    else:
        cab = (
            f"ERROR tras {res.hechas}/{res.total} acciones: {res.error} "
            "Las siguientes NO se ejecutaron; revisa la imagen y replantea desde ahí."
        )
    partes = [cab, *res.salidas]
    for etiqueta, img, e in res.frames:
        if etiqueta == "final":
            partes.append(
                f"Imagen final {img.size[0]}x{img.size[1]} (escala {e:.2f}): "
                "usa coordenadas de ESTA imagen."
            )
        else:
            partes.append(f"Fotograma {etiqueta}, {img.size[0]}x{img.size[1]} (solo para mirar).")
    return ["\n".join(partes), *[_jpeg(img) for _, img, _ in res.frames]]


def register(mcp) -> None:
    @mcp.tool(name=TOOL_ACCIONES)
    @accion()  # los permisos se comprueban por lote completo (más abajo), no por acción
    def astrax_acciones(
        acciones: list[dict[str, Any]],
        captura_final: bool = True,
        escala: float | None = None,
        espera_final: float | None = None,
    ):
        """EJECUTA VARIAS ACCIONES EN UNA LLAMADA y devuelve UNA captura final. Mira la pantalla una vez, planifica 3-20 acciones y envíalas juntas. Coordenadas = píxeles de la ÚLTIMA imagen recibida (el servidor convierte).

        Cada acción es un objeto con "a" (tipo). Tipos y campos:
        mover{x,y} | mover_rel{dx,dy} | clic{x,y,b=left|right|middle,n=1-3} (sin x,y: donde está el cursor) | doble_clic{x,y}
        arrastrar{x,y,x2,y2,dur} | raton_abajo{b,x,y} | raton_arriba{b}
        escribir{texto,enter} | tecla{tecla,n} ("ctrl+l" vale) | atajo{teclas:[..]} | abajo{teclas} | arriba{teclas}
        mantener{teclas|b,seg<=10,mientras:[acciones]} (mantiene pulsado mientras ocurre `mientras`; se suelta siempre)
        scroll{n,x,y} (n>0 arriba) | esperar{seg} | captura{escala,region:[x,y,w,h]} (fotograma intermedio barato)
        portapapeles{op=leer|escribir,texto} | comando{cmd,timeout,dir} | repetir{n<=50,acciones:[...]}
        Si una acción falla, se detiene y recibes la imagen actual. Usa captura_final=false solo si ya sabes el resultado; escala 0.2-1.0 baja los tokens de la imagen (por defecto automática).
        """
        lista = motor.parsear(acciones)
        necesarios = motor.scopes_necesarios(lista, captura_final)
        for scope in necesarios:  # todo o nada: no se mueve nada si falta algún permiso
            denegado = permissions.exigir(scope)
            if denegado:
                return denegado
        espera = ESPERA_FINAL if espera_final is None else max(0.0, min(float(espera_final), 5.0))
        res = motor.ejecutar(lista, captura_final, escala, espera)
        log(f"Lote: {res.hechas}/{res.total} ok={res.ok} frames={len(res.frames)} {res.segundos:.2f}s")
        return registrar_resultado(res)
