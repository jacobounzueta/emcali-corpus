"""Sincronización de noticias y mantenimientos de EMCALI hacia SQLite, mapa y boletín OpenClaw."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Literal

import requests
from pydantic import BaseModel, Field

from emcali_corpus import config
from emcali_corpus.cali_geo import detect_barrios_in_text
from emcali_corpus.ops_db import (
    EmcaliOpsDatabase,
    MaintenanceCreateRequest,
    ServiceType,
    get_ops_db,
    utc_now_iso,
)

LIVE_EMCALI_NEWS_JSON_URL = os.getenv(
    "EMCALI_LIVE_NEWS_URL", "https://portalemcali.onrender.com/data/news.json"
)

# ---------------------------------------------------------------------------
# Jev News-to-Map Ingestion Gatekeeper (Choice, Noul, Score, Box)
# ---------------------------------------------------------------------------

JevNewsChoice = Literal["operational_maintenance_pin", "institutional_news"]

OPERATIONAL_TITLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\breparaci[oó]n(?:es)?\s+y\s+mantenimientos?\b", re.IGNORECASE),
    re.compile(
        r"\bmodernizaci[oó]n\s+de\s+(?:energ[ií]a|acueducto|alcantarillado|redes?|circuitos?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:suspensi[oó]n|corte|cortes|interrupci[oó]n)\s+(?:del\s+servicio|temporal|programad[oa]|de\s+(?:agua|energ[ií]a|luz))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bmantenimiento\s+(?:preventivo|correctivo|programado|en\s+redes?|de\s+(?:energ[ií]a|acueducto))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:reparaci[oó]n\s+de\s+fuga|da[nñ]o\s+en\s+(?:la\s+)?red|cambio\s+de\s+transformador|poda\s+t[eé]cnica)\b",
        re.IGNORECASE,
    ),
)

OPERATIONAL_BODY_KEYWORDS: tuple[str, ...] = (
    "suspensión del servicio",
    "suspension del servicio",
    "suspensión temporal",
    "suspension temporal",
    "corte programado",
    "cortes de energía",
    "cortes de energia",
    "cortes de agua",
    "interrupción del servicio",
    "interrupcion del servicio",
    "mantenimiento preventivo",
    "mantenimiento correctivo",
    "reparación de fuga",
    "reparacion de fuga",
    "reparaciones y mantenimientos",
    "cambio de transformador",
    "cambio de poste",
    "poda técnica",
    "poda tecnica",
    "lavado de tubería",
    "lavado de tuberia",
    "empalme de fibra",
    "sin servicio de",
)

# Compuerta NOUL: veta comunicados positivos, institucionales o de operación normal
# para que NUNCA contaminen el mapa de afectaciones/mantenimientos.
JEV_NOUL_INSTITUTIONAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:funciona|opera|operando|funcionando)\s+con\s+normalidad\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bsin\s+afectaci[oó]n(?:es)?\b|\boperaci[oó]n\s+normal\b", re.IGNORECASE),
    re.compile(
        r"\b(?:jornada\s+especial|acuerdos?\s+de\s+pago|normalizaci[oó]n\s+de\s+cartera|"
        r"alivios?\s+y\s+acuerdos?|facilidades\s+de\s+pago)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:convenio\s+interinstitucional|alianza\s+estrat[eé]gica|rendici[oó]n\s+de\s+cuentas|"
        r"obsolescencia\s+tecnol[oó]gica|retiro\s+de\s+\d+\s+veh[ií]culos|"
        r"conexiones\s+irregulares|desmontado\s+[\d.,]+\s+conexiones|"
        r"premio|reconocimiento|capacitaci[oó]n|feria\s+de\s+servicios)\b",
        re.IGNORECASE,
    ),
)


class JevNewsClassification(BaseModel):
    """Decisión estructurada System One (Jev) para decidir si una noticia genera pin en el mapa."""

    choice: JevNewsChoice
    noul_triggered: bool = False
    score: float = Field(ge=0.0, le=1.0)
    service: ServiceType
    operational_signals: list[str] = Field(default_factory=list)
    veto_signals: list[str] = Field(default_factory=list)
    rationale: str


def _infer_service(text: str) -> ServiceType:
    low = text.lower()
    if any(k in low for k in ("alcantarillado", "canal ", "aguas residuales", "ptar")):
        return "alcantarillado"
    if any(
        k in low for k in ("acueducto", "agua potable", "tubería", "tuberia", "válvula", "fuga")
    ):
        return "acueducto"
    if any(k in low for k in ("fibra", "telco", "telecomunicaci", "internet", "cable")):
        return "telco_fibra"
    return "energia"


def classify_news_event_with_jev(title: str, body: str) -> JevNewsClassification:
    """Evalúa con Jev (Choice, Noul, Score, Box) si una noticia es afectación operativa real."""
    clean_title = title.strip()
    body_head = body[:600].strip()
    combined = f"{clean_title} {body_head}"
    service = _infer_service(combined)

    # 1. Compuerta NOUL: vetar noticias positivas/institucionales que no implican corte ni obra
    veto_hits: list[str] = []
    for pat in JEV_NOUL_INSTITUTIONAL_PATTERNS:
        m = pat.search(combined)
        if m:
            veto_hits.append(m.group(0))

    if veto_hits:
        return JevNewsClassification(
            choice="institutional_news",
            noul_triggered=True,
            score=0.05,
            service=service,
            veto_signals=veto_hits,
            rationale=(
                f"Jev Noul activado: comunicado institucional/positivo ({', '.join(veto_hits)}); "
                "se clasifica como noticia general y NO se marca como afectación en el mapa."
            ),
        )

    # 2. Señales operativas de mantenimiento/afectación (título 0.60, cuerpo 0.20 c/u)
    op_signals: list[str] = []
    score = 0.0
    for pat in OPERATIONAL_TITLE_PATTERNS:
        m = pat.search(clean_title)
        if m:
            op_signals.append(f"title:{m.group(0)}")
            score += 0.60

    low_body = body_head.lower()
    for kw in OPERATIONAL_BODY_KEYWORDS:
        if kw in low_body:
            op_signals.append(f"body:{kw}")
            score += 0.25

    bounded_score = round(min(1.0, score), 2)
    if bounded_score >= 0.55:
        return JevNewsClassification(
            choice="operational_maintenance_pin",
            noul_triggered=False,
            score=bounded_score,
            service=service,
            operational_signals=op_signals[:6],
            rationale=(
                f"Jev Choice=operational_maintenance_pin (score={bounded_score}): "
                "se detectó intervención/afectación operativa verificable para georreferenciar."
            ),
        )

    return JevNewsClassification(
        choice="institutional_news",
        noul_triggered=False,
        score=bounded_score,
        service=service,
        operational_signals=op_signals[:4],
        rationale=(
            f"Jev Choice=institutional_news (score={bounded_score} < 0.55): "
            "noticia informativa sin evidencia de corte o mantenimiento activo."
        ),
    )


def _is_maintenance_news(title: str, body: str) -> bool:
    return classify_news_event_with_jev(title, body).choice == "operational_maintenance_pin"


_ISO_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_SPANISH_DATE_RE = re.compile(
    r"\b(\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre)(?:\s+de\s+20\d{2})?)\b",
    re.IGNORECASE,
)


def _extract_publication_date(item: dict[str, Any], raw_md: str, body_text: str) -> str:
    for key in ("lastmod", "published_at", "captured_at"):
        val = str(item.get(key, "") or "").strip()
        if val:
            return val[:10]
    m_iso = _ISO_DATE_RE.search(raw_md[:600])
    if m_iso:
        return m_iso.group(1)
    m_es = _SPANISH_DATE_RE.search(body_text[:500])
    if m_es:
        return m_es.group(1)
    return utc_now_iso()[:10]


def _read_gold_news_records(corpus_path: Path = config.INDEX_PATH) -> list[dict[str, Any]]:
    """Lee las noticias curadas desde data/gold/corpus.jsonl y sus archivos Markdown."""
    if not corpus_path.is_file():
        return []
    records: list[dict[str, Any]] = []
    with corpus_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            item = json.loads(raw)
            if str(item.get("section", "")).lower() != "noticias":
                continue
            raw_md = ""
            body_text = str(item.get("description", "")).strip()
            gold_rel = str(item.get("gold_path", "")).strip()
            if gold_rel:
                md_path = config.PROJECT_ROOT / gold_rel
                if not md_path.is_file():
                    md_path = config.DATA_DIR / gold_rel
                if md_path.is_file():
                    raw_md = md_path.read_text(encoding="utf-8", errors="replace")
                    body_candidate = raw_md
                    # Quitar frontmatter YAML si existe
                    if body_candidate.startswith("---"):
                        parts = body_candidate.split("---", 2)
                        if len(parts) == 3:
                            body_candidate = parts[2]
                    body_text = body_candidate.strip()
            title = str(item.get("title", "")).strip()
            if (
                not title
                or len(body_text) < 40
                or title.lower() in {"noticias", "portal de proveedores", "noticias cortes detalle"}
            ):
                continue
            url = (
                str(item.get("url") or item.get("source_url") or "").strip()
                or f"https://www.emcali.com.co/noticias/{item.get('slug', '')}"
            )
            records.append(
                {
                    "slug": str(item.get("slug", "")),
                    "title": title,
                    "url": url,
                    "date": _extract_publication_date(item, raw_md, body_text),
                    "summary": body_text[:280].replace("\n", " ").strip(),
                    "content": body_text[:3000],
                }
            )
    return records


def sync_live_emcali_news(
    ops_db: EmcaliOpsDatabase | None = None,
    *,
    limit_articles: int = 120,
    max_maintenance_pins: int = 15,
    timeout: int = 20,
) -> dict[str, Any]:
    """Descarga en vivo el feed oficial JSON de EMCALI (2026) y actualiza noticias y mapa."""
    db = ops_db or get_ops_db()
    resp = requests.get(
        LIVE_EMCALI_NEWS_JSON_URL,
        headers={"User-Agent": config.USER_AGENT},
        timeout=timeout,
    )
    resp.raise_for_status()
    payload = resp.json()
    raw_items = payload.get("news", []) if isinstance(payload, dict) else []
    if not isinstance(raw_items, list):
        return {"live_news_ingested": 0, "live_maintenance_pins": 0, "source": "live_json"}

    # Ordenar por fecha descendente antes de truncar
    raw_items.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    ingested = 0
    maint_detected = 0
    pins_created = 0

    existing_titles = {
        str(m["titulo"]).lower() for m in db.list_maintenance_points(solo_activos=False, limit=300)
    }

    for item in raw_items[:limit_articles]:
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        desc = str(item.get("description", "") or "").strip()
        raw_content = item.get("content") or desc
        if isinstance(raw_content, list):
            content_str = " ".join(str(x) for x in raw_content)
        else:
            content_str = str(raw_content)
        date_str = str(item.get("date", "") or "").strip()[:10]
        cat_raw = str(item.get("category", "") or "Noticias EMCALI").strip()
        slug_id = str(item.get("id", "") or hashlib.sha1(title.encode()).hexdigest()[:12])
        url = (
            str(item.get("url", "") or "").strip()
            or f"https://www.emcali.com.co/noticias/{slug_id}"
        )

        combined = f"{title} {desc} {content_str}"
        is_maint = (
            "reparac" in cat_raw.lower()
            or "manten" in cat_raw.lower()
            or _is_maintenance_news(title, combined)
        )
        locations = detect_barrios_in_text(combined, limit=5)
        barrio_names = [loc.barrio for loc in locations]

        today_iso = utc_now_iso()[:10]
        stable_key = (
            hashlib.sha1(f"{slug_id}|{date_str or today_iso}|{title}".encode())
            .hexdigest()[:16]
            .upper()
        )
        db.upsert_news_item(
            noticia_id=f"LIVE-{stable_key}",
            titulo=title,
            categoria="Reparaciones y Mantenimientos" if is_maint else cat_raw,
            fecha_publicacion=date_str or today_iso,
            resumen=(desc or content_str)[:300].replace("\n", " ").strip(),
            contenido=content_str[:3000],
            url=url,
            es_mantenimiento=is_maint,
            barrios=barrio_names,
        )
        ingested += 1

        if is_maint:
            maint_detected += 1
            if locations and pins_created < max_maintenance_pins:
                primary_loc = locations[0]
                if title.lower() not in existing_titles:
                    db.create_maintenance_point(
                        MaintenanceCreateRequest(
                            titulo=title[:155],
                            servicio=_infer_service(combined),
                            barrio=primary_loc.barrio,
                            descripcion=(desc or content_str)[:400],
                            brigada_asignada="Brigada EMCALI (Feed Oficial)",
                            inicio_estimado=date_str or today_iso,
                            fin_estimado="Según programación EMCALI",
                            fuente="scraping_emcali",
                            fuente_url=url,
                            created_by="live-emcali-news-feed",
                        )
                    )
                    existing_titles.add(title.lower())
                    pins_created += 1

    return {
        "source": LIVE_EMCALI_NEWS_JSON_URL,
        "live_news_ingested": ingested,
        "live_maintenance_news": maint_detected,
        "live_map_pins_created": pins_created,
    }


def sync_news_from_gold(
    ops_db: EmcaliOpsDatabase | None = None,
    *,
    corpus_path: Path = config.INDEX_PATH,
    max_maintenance_pins: int = 12,
    include_live: bool = False,
) -> dict[str, Any]:
    """Ingiere las noticias de EMCALI en SQLite y georreferencia mantenimientos en el mapa."""
    db = ops_db or get_ops_db()
    records = _read_gold_news_records(corpus_path)
    ingested = 0
    maint_news = 0
    pins_created = 0

    existing_titles = {
        str(m["titulo"]).lower() for m in db.list_maintenance_points(solo_activos=False, limit=200)
    }

    for rec in records:
        nid = hashlib.sha1(f"{rec['slug']}:{rec['title']}".encode()).hexdigest()[:12]
        combined = f"{rec['title']} {rec['content']}"
        is_maint = _is_maintenance_news(rec["title"], rec["content"])
        locations = detect_barrios_in_text(combined, limit=4)
        barrio_names = [loc.barrio for loc in locations]

        db.upsert_news_item(
            noticia_id=f"NEWS-{nid.upper()}",
            titulo=rec["title"],
            categoria="Reparaciones y Mantenimientos" if is_maint else "Noticias EMCALI",
            fecha_publicacion=rec["date"],
            resumen=rec["summary"],
            contenido=rec["content"],
            url=rec["url"],
            es_mantenimiento=is_maint,
            barrios=barrio_names,
        )
        ingested += 1

        if is_maint:
            maint_news += 1
            if locations and pins_created < max_maintenance_pins:
                primary_loc = locations[0]
                if rec["title"].lower() not in existing_titles:
                    db.create_maintenance_point(
                        MaintenanceCreateRequest(
                            titulo=rec["title"][:155],
                            servicio=_infer_service(combined),
                            barrio=primary_loc.barrio,
                            descripcion=rec["summary"][:400],
                            brigada_asignada="Brigada EMCALI (Portal Noticias)",
                            inicio_estimado=rec["date"],
                            fin_estimado="Según avance técnico",
                            fuente="scraping_emcali",
                            fuente_url=rec["url"],
                            created_by="news-sync-pipeline",
                        )
                    )
                    existing_titles.add(rec["title"].lower())
                    pins_created += 1

    result: dict[str, Any] = {
        "news_ingested": ingested,
        "maintenance_news_detected": maint_news,
        "new_map_pins_created": pins_created,
    }
    if include_live:
        try:
            result["live_feed"] = sync_live_emcali_news(
                db,
                max_maintenance_pins=max_maintenance_pins,
            )
        except Exception as exc:
            result["live_feed_error"] = str(exc)
    return result


def build_daily_newsletter_digest(
    ops_db: EmcaliOpsDatabase | None = None,
    *,
    barrio: str | None = None,
    limit_news: int = 5,
) -> dict[str, Any]:
    """Construye el boletín diario de noticias y mantenimientos para OpenClaw/WhatsApp."""
    db = ops_db or get_ops_db()
    maint = db.list_maintenance_points(barrio=barrio, solo_activos=True, limit=8)
    hotspots = db.get_failure_hotspots()
    if barrio:
        hotspots = [h for h in hotspots if barrio.lower() in h["barrio"].lower()]
    news = db.list_news(query=barrio or "", limit=limit_news)
    if not news and barrio:
        news = db.list_news(limit=limit_news)

    lines: list[str] = [
        "📰 *Boletín Diario EMCALI — Melva Asistente Operativa*",
        f"Zona de consulta: *{barrio or 'Toda Cali y área de cobertura'}*",
        "",
        f"🔧 *Mantenimientos Activos ({len(maint)}):*",
    ]
    if maint:
        for item in maint[:5]:
            fecha_rep = str(item.get("inicio_estimado") or item.get("created_at") or "")[:16]
            lines.append(
                f"• [{item['servicio'].upper()}] *{item['barrio']}* ({item['comuna']}) — "
                f"Fecha: `{fecha_rep}`: {item['titulo']} · Brigada: {item['brigada_asignada']}"
            )
    else:
        lines.append("• Sin mantenimientos activos reportados en esta zona.")

    if hotspots:
        lines.append("")
        lines.append(f"⚠️ *Alertas Ciudadanas por Fallas ({len(hotspots)} sectores):*")
        for h in hotspots[:4]:
            lines.append(
                f"• *{h['barrio']}* ({h['servicio']}): {h['report_count']} reporte(s) — "
                f"{h['severity_label']}"
            )

    if news:
        lines.append("")
        lines.append(f"📢 *Últimas Noticias EMCALI ({len(news)}):*")
        for n in news[:limit_news]:
            lines.append(f"• {n['titulo']} ({n['categoria']})")

    return {
        "barrio_filter": barrio or "Todos",
        "active_maintenances_count": len(maint),
        "hotspots_count": len(hotspots),
        "news_count": len(news),
        "subscribers_active": len(db.list_newsletter_subscribers()),
        "markdown_digest": "\n".join(lines),
    }
