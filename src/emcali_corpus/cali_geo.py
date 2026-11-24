"""Catálogo geográfico determinista de barrios, comunas y municipios atendidos por EMCALI."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CaliLocation:
    """Coordenadas verificadas de un barrio, comuna o municipio de cobertura EMCALI."""

    barrio: str
    comuna: str
    lat: float
    lng: float
    municipio: str = "Cali"


# Coordenadas reales (WGS84) de barrios, comunas y municipios de cobertura EMCALI
CALI_LOCATIONS: tuple[CaliLocation, ...] = (
    # Comuna 1 - Oeste
    CaliLocation("Terrón Colorado", "Comuna 1", 3.4578, -76.5653),
    CaliLocation("Vista Hermosa", "Comuna 1", 3.4622, -76.5712),
    CaliLocation("Aguacatal", "Comuna 1", 3.4651, -76.5554),
    # Comuna 2 - Norte
    CaliLocation("Granada", "Comuna 2", 3.4574, -76.5359),
    CaliLocation("Versalles", "Comuna 2", 3.4627, -76.5303),
    CaliLocation("San Vicente", "Comuna 2", 3.4682, -76.5269),
    CaliLocation("Santa Mónica Residencial", "Comuna 2", 3.4701, -76.5327),
    CaliLocation("Chipichape", "Comuna 2", 3.4754, -76.5284),
    CaliLocation("La Flora", "Comuna 2", 3.4852, -76.5204),
    CaliLocation("Vipasa", "Comuna 2", 3.4828, -76.5162),
    CaliLocation("Prados del Norte", "Comuna 2", 3.4765, -76.5194),
    CaliLocation("Juanambú", "Comuna 2", 3.4545, -76.5401),
    CaliLocation("Centenario", "Comuna 2", 3.4551, -76.5382),
    CaliLocation("El Peñón", "Comuna 2", 3.4496, -76.5419),
    CaliLocation("Normandía", "Comuna 2", 3.4526, -76.5484),
    CaliLocation("Menga", "Comuna 2", 3.4971, -76.5189),
    # Comuna 3 - Centro / San Antonio
    CaliLocation("Centro", "Comuna 3", 3.4516, -76.5320),
    CaliLocation("CAM", "Comuna 3", 3.4533, -76.5335),
    CaliLocation("San Antonio", "Comuna 3", 3.4465, -76.5396),
    CaliLocation("San Nicolás", "Comuna 3", 3.4563, -76.5261),
    CaliLocation("San Pedro", "Comuna 3", 3.4518, -76.5312),
    CaliLocation("El Calvario", "Comuna 3", 3.4493, -76.5281),
    CaliLocation("Santa Rosa", "Comuna 3", 3.4480, -76.5324),
    # Comuna 4 y 5 - Nororiente
    CaliLocation("Salomia", "Comuna 4", 3.4707, -76.5065),
    CaliLocation("Popular", "Comuna 4", 3.4671, -76.5112),
    CaliLocation("Sena", "Comuna 4", 3.4748, -76.5015),
    CaliLocation("La Rivera", "Comuna 5", 3.4826, -76.4945),
    CaliLocation("Chiminangos", "Comuna 5", 3.4809, -76.4979),
    CaliLocation("Torres de Comfandi", "Comuna 5", 3.4785, -76.5023),
    # Comuna 6 y 7 - Nororiente extremo
    CaliLocation("San Luis", "Comuna 6", 3.4879, -76.4896),
    CaliLocation("Petecuy", "Comuna 6", 3.4856, -76.4864),
    CaliLocation("Calimío Norte", "Comuna 6", 3.4924, -76.4867),
    CaliLocation("Alfonso López", "Comuna 7", 3.4682, -76.4862),
    CaliLocation("Siete de Agosto", "Comuna 7", 3.4628, -76.4914),
    # Comuna 8 y 9 - Centro-Oriente
    CaliLocation("Villanueva", "Comuna 8", 3.4491, -76.5094),
    CaliLocation("La Floresta", "Comuna 8", 3.4465, -76.5142),
    CaliLocation("Santa Mónica Popular", "Comuna 8", 3.4539, -76.5078),
    CaliLocation("Alameda", "Comuna 9", 3.4375, -76.5356),
    CaliLocation("Bretaña", "Comuna 9", 3.4398, -76.5335),
    CaliLocation("Junín", "Comuna 9", 3.4378, -76.5269),
    # Comuna 10 y 11 - Centro-Sur
    CaliLocation("Cristóbal Colón", "Comuna 10", 3.4241, -76.5282),
    CaliLocation("El Guabal", "Comuna 10", 3.4281, -76.5245),
    CaliLocation("San Judas", "Comuna 10", 3.4184, -76.5236),
    CaliLocation("Ciudad Modelo", "Comuna 11", 3.4227, -76.5141),
    CaliLocation("Agua Blanca", "Comuna 11", 3.4292, -76.5071),
    # Comuna 12, 13, 14, 15, 21 - Distrito de Aguablanca / Oriente
    CaliLocation("Nueva Floresta", "Comuna 12", 3.4408, -76.5063),
    CaliLocation("El Pondaje", "Comuna 13", 3.4275, -76.4947),
    CaliLocation("Marroquín", "Comuna 14", 3.4328, -76.4819),
    CaliLocation("Alfonso Bonilla Aragón", "Comuna 14", 3.4296, -76.4792),
    CaliLocation("El Vallado", "Comuna 15", 3.4126, -76.5015),
    CaliLocation("Ciudad Córdoba", "Comuna 15", 3.4063, -76.5082),
    CaliLocation("Potrero Grande", "Comuna 21", 3.4191, -76.4697),
    CaliLocation("Desepaz", "Comuna 21", 3.4294, -76.4682),
    # Comuna 16 - Suroriente
    CaliLocation("Mariano Ramos", "Comuna 16", 3.4095, -76.5186),
    CaliLocation("Unión de Vivienda Popular", "Comuna 16", 3.4148, -76.5152),
    # Comuna 17 - Sur
    CaliLocation("El Ingenio", "Comuna 17", 3.3869, -76.5318),
    CaliLocation("Valle del Lili", "Comuna 17", 3.3746, -76.5236),
    CaliLocation("Caney", "Comuna 17", 3.3792, -76.5174),
    CaliLocation("Capri", "Comuna 17", 3.3948, -76.5393),
    CaliLocation("Limonar", "Comuna 17", 3.3991, -76.5349),
    CaliLocation("Primero de Mayo", "Comuna 17", 3.4041, -76.5341),
    CaliLocation("La Hacienda", "Comuna 17", 3.3924, -76.5446),
    CaliLocation("Bochalema", "Comuna 17", 3.3629, -76.5229),
    # Comuna 18 - Ladera Sur
    CaliLocation("Meléndez", "Comuna 18", 3.3796, -76.5471),
    CaliLocation("Nápoles", "Comuna 18", 3.3879, -76.5498),
    CaliLocation("Los Chorros", "Comuna 18", 3.3832, -76.5567),
    # Comuna 19 - Suroeste / San Fernando
    CaliLocation("San Fernando", "Comuna 19", 3.4319, -76.5435),
    CaliLocation("Tequendama", "Comuna 19", 3.4216, -76.5446),
    CaliLocation("Miraflores", "Comuna 19", 3.4394, -76.5442),
    CaliLocation("El Lido", "Comuna 19", 3.4144, -76.5469),
    CaliLocation("Pampalinda", "Comuna 19", 3.4055, -76.5504),
    CaliLocation("Santa Isabel", "Comuna 19", 3.4337, -76.5488),
    CaliLocation("Nueva Tequendama", "Comuna 19", 3.4188, -76.5459),
    CaliLocation("Champagnat", "Comuna 19", 3.4256, -76.5397),
    CaliLocation("El Refugio", "Comuna 19", 3.4071, -76.5441),
    # Comuna 20 - Siloé
    CaliLocation("Siloé", "Comuna 20", 3.4227, -76.5586),
    CaliLocation("Lleras Camargo", "Comuna 20", 3.4254, -76.5632),
    # Comuna 22 - Pance / Ciudad Jardín
    CaliLocation("Ciudad Jardín", "Comuna 22", 3.3621, -76.5367),
    CaliLocation("Pance", "Comuna 22", 3.3442, -76.5453),
    CaliLocation("Cañasgordas", "Comuna 22", 3.3563, -76.5326),
    CaliLocation("Universidad Autónoma de Occidente", "Comuna 22", 3.3536, -76.5228),
    # Municipios vecinos con cobertura EMCALI
    CaliLocation("Yumbo", "Municipio", 3.5823, -76.4915, municipio="Yumbo"),
    CaliLocation("Jamundí", "Municipio", 3.2618, -76.5363, municipio="Jamundí"),
    CaliLocation("Candelaria", "Municipio", 3.4067, -76.3482, municipio="Candelaria"),
    CaliLocation("Puerto Tejada", "Municipio", 3.2356, -76.4158, municipio="Puerto Tejada"),
)

DEFAULT_CALI_CENTER = CaliLocation("Cali (Centro)", "Comuna 3", 3.4516, -76.5320)


def _norm(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower().strip())
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


_INDEX_BY_NORM: dict[str, CaliLocation] = {_norm(loc.barrio): loc for loc in CALI_LOCATIONS}
_COMUNA_RE = re.compile(r"\bcomuna\s+(\d{1,2})\b", re.IGNORECASE)


def try_resolve_cali_location(text: str) -> CaliLocation | None:
    """Resuelve un barrio/comuna/municipio de cobertura EMCALI o devuelve None si no existe."""
    norm_text = _norm(text)
    if not norm_text:
        return None

    # Coincidencia exacta
    if norm_text in _INDEX_BY_NORM:
        return _INDEX_BY_NORM[norm_text]

    # Coincidencia por subcadena (prioriza nombres de barrio más largos para evitar colisiones)
    for key in sorted(_INDEX_BY_NORM, key=len, reverse=True):
        if len(key) >= 4 and key in norm_text:
            return _INDEX_BY_NORM[key]

    # Coincidencia por número de comuna (1 a 22 en Cali)
    match_comuna = _COMUNA_RE.search(norm_text)
    if match_comuna:
        comuna_num = int(match_comuna.group(1))
        if 1 <= comuna_num <= 22:
            target_comuna = f"Comuna {comuna_num}"
            for loc in CALI_LOCATIONS:
                if loc.comuna.lower() == target_comuna.lower():
                    return loc

    return None


def resolve_cali_location(text: str) -> CaliLocation:
    """Resuelve un barrio/comuna de Cali o cae al centro de Cali solo si se solicita fallback."""
    return try_resolve_cali_location(text) or DEFAULT_CALI_CENTER


def detect_barrios_in_text(text: str, *, limit: int = 8) -> list[CaliLocation]:
    """Detecta todos los barrios/municipios de cobertura EMCALI mencionados en un texto."""
    norm_text = _norm(text)
    if not norm_text:
        return []
    found: list[CaliLocation] = []
    seen_barrios: set[str] = set()
    for key in sorted(_INDEX_BY_NORM, key=len, reverse=True):
        if len(key) < 4:
            continue
        if re.search(rf"\b{re.escape(key)}\b", norm_text):
            loc = _INDEX_BY_NORM[key]
            if loc.barrio not in seen_barrios:
                seen_barrios.add(loc.barrio)
                found.append(loc)
                if len(found) >= limit:
                    break
    return found
