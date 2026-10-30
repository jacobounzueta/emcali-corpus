"""Configuración central: semillas, capas, política HTTP y renderizado."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict


class Viewport(TypedDict):
    """Dimensiones de la ventana usada por el navegador."""

    width: int
    height: int


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("EMCALI_DATA_DIR", PROJECT_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
GOLD_DIR = DATA_DIR / "gold"
INDEX_PATH = GOLD_DIR / "corpus.jsonl"

BASE_URL = "https://www.emcali.com.co"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
ROBOTS_URL = f"{BASE_URL}/robots.txt"

USER_AGENT = (
    "EMCALI-Corpus/0.1 (corpus academico de informacion publica; "
    "contacto: jacobo.unzueta@uao.edu.co)"
)

REQUEST_TIMEOUT_SECONDS = 30
REQUEST_DELAY_SECONDS = 0.75
MAX_RETRIES = 3

RENDER_TIMEOUT_MS = 60_000
RENDER_SETTLE_MS = 1_500
RENDER_VIEWPORT: Viewport = {"width": 1440, "height": 900}

#: Hosts cuyo contenido se renderiza cuando la página de EMCALI solo los incrusta.
TRUSTED_RENDER_HOSTS = frozenset({"portalemcali.onrender.com"})

#: Rutas transaccionales, privadas o de prueba que no forman parte del corpus.
EXCLUDED_PATH_PREFIXES = (
    "/login",
    "/iniciar-sesion",
    "/login-tramites",
    "/registrarse",
    "/registro-proveedores-lfr",
    "/dashboard",
    "/mi-cuenta",
    "/nuevo-pqrs",
    "/infopqrs",
    "/consulta-pago-proveedores",
    "/actualiza-datos-predial",
    "/embed1",
    "/embed2",
    "/test",
    "/prueba-theme-pagina",
    "/error-404",
    "/reportar-error",
    "/noticias-detalles",
    "/metricas-mile",
    "/741",
    "/750",
    "/1140",
    "/valida-carta-laboral",
    "/valida-certificado-laboral",
    "/notifica-prb",
    "/contratacion3",
    "/clausura-servicios-predios-afectados-por-sismo",
    "/atencion-y-servicio-a-la-ciudadania/pqrs",
    "/atencion-y-servicio-a-la-ciudadania/solicitud-de-informacion",
    "/atencion-y-servicio-a-la-ciudadania/proveedores/registro-proveedores",
    "/atencion-y-servicio-a-la-ciudadania/proveedores/consulta-tramite-pago-proveedores",
    "/energia/consulta-de-solicitudes",
    "/energia/formulario-de-autogeneradores",
    "/energia/formulario-de-servicio",
    "/energia/formatos-de-solicitud",
    "/w/registro-pqr",
    "/w/pagos-web",
    "/w/estilo-formulario",
    "/w/solicitud-de-registro",
)


@dataclass(frozen=True, slots=True)
class Seed:
    """Página semilla que se desea capturar."""

    url: str
    slug: str
    title: str
    section: str
    lastmod: str = ""


CURATED_SEEDS: tuple[Seed, ...] = (
    Seed("/", "inicio", "Inicio", "portada"),
    Seed("/about", "about", "Sobre nosotros", "about"),
    Seed("/energia", "energia", "Energía", "energia"),
    Seed("/acueducto", "acueducto", "Acueducto y Alcantarillado", "acueducto"),
    Seed("/telco", "telco", "Telco", "telco"),
    Seed("/sostenibilidad", "sostenibilidad", "Sostenibilidad", "sostenibilidad"),
    Seed(
        "/atencion-y-servicio-a-la-ciudadania",
        "atencion-y-servicio-a-la-ciudadania",
        "Atención y servicio a la ciudadanía",
        "atencion-y-servicio-a-la-ciudadania",
    ),
    Seed("/noticias", "noticias", "Noticias", "noticias"),
    Seed(
        "/transparencia/informacion-de-la-entidad/mision-y-vision",
        "informacion-de-la-entidad-mision-y-vision",
        "Misión y Visión",
        "transparencia",
    ),
    Seed("/transparencia/normatividad", "normatividad", "Normatividad", "transparencia"),
    Seed(
        "/proteccion-de-datos-personales",
        "proteccion-de-datos-personales",
        "Protección de datos personales",
        "proteccion-de-datos-personales",
    ),
    Seed("/mapa-sitio", "mapa-sitio", "Mapa del sitio", "mapa-sitio"),
    Seed(
        "/declaracion-de-conformidad-de-accesibilidad-y-usabilidad",
        "declaracion-de-conformidad-de-accesibilidad-y-usabilidad",
        "Declaración de conformidad de accesibilidad y usabilidad",
        "declaracion-de-conformidad-de-accesibilidad-y-usabilidad",
    ),
    Seed(
        "/notificaciones-actos-administrativos",
        "notificaciones-actos-administrativos",
        "Notificaciones de actos administrativos",
        "notificaciones-actos-administrativos",
    ),
    Seed(
        "/informacion-sobre-decisiones-que-puede-afectar-al-publico",
        "informacion-sobre-decisiones-que-puede-afectar-al-publico",
        "Información sobre decisiones que pueden afectar al público",
        "informacion-sobre-decisiones-que-puede-afectar-al-publico",
    ),
    Seed(
        "/energia/tarifas-de-energia",
        "tarifas-de-energia",
        "Tarifas de energía",
        "energia",
    ),
    Seed(
        "/acueducto/tarifas-de-acueducto",
        "tarifas-de-acueducto",
        "Tarifas de acueducto",
        "acueducto",
    ),
    Seed(
        "/atencion-y-servicio-a-la-ciudadania/metodos-de-pago",
        "metodos-de-pago",
        "Métodos de pago",
        "atencion-y-servicio-a-la-ciudadania",
    ),
    Seed(
        "/terminos-condiciones-uso-factura-digital",
        "terminos-condiciones-uso-factura-digital",
        "Términos y condiciones de uso de factura digital",
        "terminos-condiciones-uso-factura-digital",
    ),
    Seed("/telco/indicadores-pqr", "indicadores-pqr", "Indicadores PQR", "telco"),
)


def absolute_url(path: str) -> str:
    """Convierte una ruta relativa del sitio en una URL absoluta."""
    if path.startswith(("http://", "https://")):
        return path
    return f"{BASE_URL}{path if path.startswith('/') else '/' + path}"


def is_excluded(url: str) -> bool:
    """Indica si una URL queda fuera del alcance del corpus."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.hostname not in {"www.emcali.com.co", "emcali.com.co"}:
        return True
    path = parsed.path.rstrip("/") or "/"
    return any(path == prefix or path.startswith(prefix + "/") for prefix in EXCLUDED_PATH_PREFIXES)
