"""Dashboard interactivo en Streamlit para el Taller 1 (Base de Conocimiento y Q&A EMCALI)."""

from __future__ import annotations

import json
from collections.abc import Sequence

import streamlit as st

from emcali_corpus import config
from emcali_corpus.assistant import (
    DEFAULT_MODEL,
    MissingAPIKeyError,
    generate_faq,
    generate_summary,
    load_assistant_settings,
    stream_question,
)
from emcali_corpus.evaluation import (
    BENCHMARK_QUESTIONS,
    EVALUATION_REPORT_PATH,
    render_benchmark_markdown,
)
from emcali_corpus.knowledge import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    SECTION_LABELS,
    KnowledgeBaseBundle,
    KnowledgeChunk,
    PipelineFunnelMetrics,
    available_sections,
    chunk_documents,
    compute_funnel_metrics,
    consolidate_knowledge_base,
    export_knowledge_artifacts,
    load_medallion_document_view,
)
from emcali_corpus.prompts import (
    PROMPT_STRATEGIES,
    build_qa_system_prompt,
)

MODEL_OPTIONS: dict[str, str] = {
    "DeepSeek V4.1 Flash (deepseek-flash)": DEFAULT_MODEL,
    "DeepSeek Chat (deepseek-chat)": "deepseek-chat",
}

SCOPE_MODES: dict[str, str] = {
    "Institucional Completo sin Noticias (164 docs · ~54k palabras)": "institutional",
    "Semillas Curadas Principales (18 docs · ~9.3k palabras)": "curated",
    "Selección Personalizada por Secciones": "sections",
}


@st.cache_data(show_spinner=False)
def get_cached_bundle(
    mode: str,
    selected_sections: tuple[str, ...],
    include_news: bool,
) -> KnowledgeBaseBundle:
    """Construye y almacena en caché el paquete consolidado de conocimiento."""
    if mode == "curated":
        return consolidate_knowledge_base(curated_only=True, include_news=include_news)
    if mode == "sections" and selected_sections:
        return consolidate_knowledge_base(
            sections=selected_sections,
            include_news=include_news,
        )
    return consolidate_knowledge_base(include_news=include_news)


@st.cache_data(show_spinner=False)
def get_cached_chunks(
    mode: str,
    selected_sections: tuple[str, ...],
    include_news: bool,
    chunk_size: int,
    chunk_overlap: int,
) -> list[KnowledgeChunk]:
    """Calcula y almacena en caché la segmentación en chunks del corpus activo."""
    bundle = get_cached_bundle(mode, selected_sections, include_news)
    return chunk_documents(
        bundle.documents,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


@st.cache_data(show_spinner=False)
def get_cached_funnel_metrics() -> PipelineFunnelMetrics:
    """Calcula y almacena en caché las métricas de las 5 etapas del scraping."""
    return compute_funnel_metrics()


def render_sidebar() -> tuple[
    str, float, str | None, str, str | None, KnowledgeBaseBundle, str, tuple[str, ...], bool
]:
    """Renderiza la barra lateral de configuración y devuelve los parámetros activos."""
    with st.sidebar:
        st.header("⚙️ Configuración del Sistema")

        model_label = st.selectbox(
            "Modelo DeepSeek",
            options=list(MODEL_OPTIONS),
            index=0,
            help="DeepSeek V4.1 Flash soporta hasta 1M de tokens de contexto.",
        )
        model_name = MODEL_OPTIONS[model_label]

        temperature = st.slider(
            "Temperatura",
            min_value=0.0,
            max_value=1.0,
            value=0.0,
            step=0.1,
            help="0.0 maximiza el determinismo y reduce el riesgo de alucinaciones.",
        )

        reasoning_choice = st.selectbox(
            "Esfuerzo de razonamiento",
            options=["Desactivado (Respuesta rápida)", "low", "high", "max"],
            index=0,
        )
        reasoning_effort = None if reasoning_choice.startswith("Desactivado") else reasoning_choice

        st.divider()
        st.subheader("📚 Alcance de la Base de Conocimiento")

        scope_label = st.radio(
            "Modo de contexto en el System Prompt",
            options=list(SCOPE_MODES),
            index=0,
        )
        scope_mode = SCOPE_MODES[scope_label]

        include_news = st.checkbox(
            "Incluir noticias (/w/)",
            value=False,
            help="Por defecto se usan solo las 164 páginas institucionales para mayor precisión.",
        )

        all_secs = available_sections(include_news=include_news)
        default_secs = [
            sec
            for sec in (
                "portada",
                "about",
                "energia",
                "acueducto",
                "telco",
                "atencion-y-servicio-a-la-ciudadania",
                "sostenibilidad",
                "proteccion-de-datos-personales",
                "terminos-condiciones-uso-factura-digital",
            )
            if sec in all_secs
        ]
        selected_sections: Sequence[str] = []
        if scope_mode == "sections":
            selected_sections = st.multiselect(
                "Secciones activas",
                options=all_secs,
                default=default_secs or all_secs[:5],
                format_func=lambda s: f"{SECTION_LABELS.get(s, s)} ({s})",
            )

        bundle = get_cached_bundle(scope_mode, tuple(selected_sections), include_news)
        st.metric("Documentos en contexto", f"{bundle.document_count}")
        st.metric("Palabras consolidadas", f"{bundle.total_words:,}".replace(",", "."))
        st.metric("Tokens estimados (~1.33x)", f"~{bundle.estimated_tokens:,}".replace(",", "."))

        st.divider()
        st.subheader("🎯 Estrategia de Prompt Engineering")
        strategy_key = st.selectbox(
            "Plantilla de instrucciones",
            options=list(PROMPT_STRATEGIES),
            index=0,
            format_func=lambda k: PROMPT_STRATEGIES[k].name,
        )
        st.caption(PROMPT_STRATEGIES[strategy_key].description)

        with st.expander("Editar instrucciones del System Prompt", expanded=False):
            custom_instructions = st.text_area(
                "Instrucciones del sistema",
                value=PROMPT_STRATEGIES[strategy_key].instructions,
                height=220,
            )

        if st.button("🗑️ Limpiar historial de chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    return (
        model_name,
        temperature,
        reasoning_effort,
        strategy_key,
        custom_instructions,
        bundle,
        scope_mode,
        tuple(selected_sections),
        include_news,
    )


def render_qa_tab(
    model_name: str,
    temperature: float,
    reasoning_effort: str | None,
    strategy_key: str,
    custom_instructions: str | None,
    bundle: KnowledgeBaseBundle,
) -> None:
    """Renderiza la pestaña principal del Sistema Q&A con soporte de streaming."""
    st.subheader("💬 Sistema de Preguntas y Respuestas (Q&A) — EMCALI")
    st.caption(
        f"Contexto activo: **{bundle.document_count} documentos** "
        f"(**{bundle.total_words:,} palabras**) inyectados en el System Prompt · "
        f"Estrategia: **{PROMPT_STRATEGIES[strategy_key].name}**".replace(",", ".")
    )

    with st.expander(
        "💡 Preguntas sugeridas del alcance de EMCALI (clic para probar)", expanded=False
    ):
        selected_q = st.selectbox(
            "Selecciona una pregunta de prueba:",
            options=[f"{q.id}. [{q.category}] {q.question}" for q in BENCHMARK_QUESTIONS],
        )
        if st.button("Enviar pregunta seleccionada", use_container_width=False):
            question_Obj = BENCHMARK_QUESTIONS[int(selected_q.split(".", 1)[0]) - 1]
            st.session_state.pending_question = question_Obj.question

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("reasoning"):
                with st.expander("🧠 Ver razonamiento del modelo", expanded=False):
                    st.markdown(msg["reasoning"])

    user_input = st.chat_input(
        "Escribe tu pregunta sobre EMCALI (servicios, tarifas, sedes, pagos, datos…)"
    )
    prompt_text = st.session_state.pop("pending_question", None) or user_input
    if not prompt_text:
        return

    with st.chat_message("user"):
        st.markdown(prompt_text)
    st.session_state.messages.append({"role": "user", "content": prompt_text})

    settings = load_assistant_settings(
        model=model_name,
        temperature=temperature,
        reasoning_effort=reasoning_effort,
    )

    with st.chat_message("assistant"):
        placeholder = st.empty()
        answer_acc = ""
        reasoning_acc = ""
        try:
            with st.spinner("Consultando la Base de Conocimiento de EMCALI con DeepSeek…"):
                for text_part, thought_part in stream_question(
                    prompt_text,
                    bundle,
                    settings=settings,
                    strategy_key=strategy_key,
                    custom_instructions=custom_instructions,
                    history=st.session_state.messages[:-1],
                ):
                    if thought_part:
                        reasoning_acc += thought_part
                    if text_part:
                        answer_acc += text_part
                        placeholder.markdown(f"{answer_acc}▌")
            placeholder.markdown(answer_acc or "_No se recibió respuesta del modelo._")
            if reasoning_acc.strip():
                with st.expander("🧠 Ver razonamiento del modelo", expanded=False):
                    st.markdown(reasoning_acc)
        except Exception as exc:
            st.error(f"Error al consultar el modelo DeepSeek: {exc}")
            return

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer_acc,
            "reasoning": reasoning_acc,
        }
    )


def render_summary_tab(
    model_name: str,
    temperature: float,
    reasoning_effort: str | None,
    bundle: KnowledgeBaseBundle,
) -> None:
    """Renderiza la pestaña de Resumen Ejecutivo (Tarea 1 de LLM en la rúbrica)."""
    st.subheader("📑 Generación de Resumen Ejecutivo con LangChain")
    st.markdown(
        "Sintetiza el contenido oficial consolidado de EMCALI estructurando identidad, "
        "servicios, cifras operativas, trámites y fuentes verificables."
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        focus_topic = st.text_input(
            "Enfoque opcional del resumen (deja vacío para resumen global)",
            placeholder="Ej.: Servicio de Energía, Acueducto y Alcantarillado, Factura Digital…",
        )
    with col2:
        st.write("")
        st.write("")
        run_btn = st.button("✨ Generar Resumen", type="primary", use_container_width=True)

    if run_btn:
        settings = load_assistant_settings(
            model=model_name,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
        )
        with st.spinner("Generando Resumen Ejecutivo con LangChain + DeepSeek…"):
            reply = generate_summary(bundle, settings=settings, focus_topic=focus_topic)
            st.session_state.last_summary = reply.answer

    if "last_summary" in st.session_state:
        st.markdown("---")
        st.markdown(st.session_state.last_summary)
        st.download_button(
            "⬇️ Descargar Resumen en Markdown",
            data=st.session_state.last_summary,
            file_name="resumen_ejecutivo_emcali.md",
            mime="text/markdown",
        )


def render_faq_tab(
    model_name: str,
    temperature: float,
    reasoning_effort: str | None,
    bundle: KnowledgeBaseBundle,
) -> None:
    """Renderiza la pestaña de Generación de FAQ (Tarea 2 de LLM en la rúbrica)."""
    st.subheader("❓ Generador Automático de Preguntas Frecuentes (FAQ)")
    st.markdown(
        "Construye un catálogo de Preguntas Frecuentes (FAQ) orientadas al ciudadano a partir "
        "del contexto limpio de EMCALI, incluyendo categoría y enlace oficial de respaldo."
    )

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        faq_topic = st.text_input(
            "Tema o servicio específico (opcional)",
            placeholder="Ej.: Pagos y Factura Digital, Fibra Óptica Telco, Protección de Datos…",
        )
    with col2:
        num_q = st.slider("Número de preguntas", min_value=3, max_value=15, value=8)
    with col3:
        st.write("")
        st.write("")
        faq_btn = st.button("🚀 Generar FAQ", type="primary", use_container_width=True)

    if faq_btn:
        settings = load_assistant_settings(
            model=model_name,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
        )
        with st.spinner("Generando catálogo de FAQ verificadas…"):
            reply = generate_faq(
                bundle,
                settings=settings,
                num_questions=num_q,
                focus_topic=faq_topic,
            )
            st.session_state.last_faq = reply.answer

    if "last_faq" in st.session_state:
        st.markdown("---")
        st.markdown(st.session_state.last_faq)
        st.download_button(
            "⬇️ Descargar FAQ en Markdown",
            data=st.session_state.last_faq,
            file_name="faq_emcali.md",
            mime="text/markdown",
        )


def render_knowledge_tab(
    bundle: KnowledgeBaseBundle,
    scope_mode: str,
    selected_sections: tuple[str, ...],
    include_news: bool,
    strategy_key: str,
    custom_instructions: str | None,
) -> None:
    """Renderiza las 5 etapas del scraping, el inspector Medallion y la segmentación (Chunking)."""
    st.subheader("🏗️ Pipeline de Scraping por Etapas (Bronze → Silver → Gold) y Chunks")
    st.markdown(
        "Visualización auditable de extremo a extremo del flujo **Descubrir → Extraer → "
        "Limpiar → Deduplicar → Enriquecer** sobre el portal oficial de **EMCALI**."
    )

    funnel = get_cached_funnel_metrics()
    st.markdown("### 1. Embudo del Proceso de Scraping (5 Etapas)")
    s1, s2, s3, s4, s5 = st.columns(5)
    with s1:
        st.metric(
            "1. Descubrir (Sitemap)",
            f"{funnel.urls_in_scope} URLs",
            delta=f"-{funnel.excluded_by_scope} fuera de alcance (de {funnel.sitemap_urls})",
            delta_color="off",
        )
        st.caption(
            f"Lectura de `sitemap.xml` ({funnel.sitemap_urls} rutas) y filtrado ético "
            f"(`robots.txt` + exclusión de logins/pagos)."
        )
    with s2:
        st.metric(
            "2. Extraer (Bronze)",
            f"{funnel.gold_total_docs} capturas",
            delta=(f"{funnel.browser_rendered_docs} Playwright · {funnel.http_rendered_docs} HTTP"),
            delta_color="normal",
        )
        st.caption(
            "Descarga del envoltorio Liferay y renderizado Chromium de iframes React "
            "(`portalemcali.onrender.com`)."
        )
    with s3:
        st.metric(
            "3. Limpiar (Silver)",
            f"{funnel.gold_total_docs} docs MD",
            delta=f"-{funnel.discarded_pages} descartes (<15 palabras / 404)",
            delta_color="inverse",
        )
        st.caption(
            "Extracción de `#main-content`, eliminación de cabeceras, menús, pies y "
            "plantillas vacías hacia Markdown."
        )
    with s4:
        st.metric(
            "4. Deduplicar (SHA-256)",
            f"{funnel.institutional_unique_docs} únicos",
            delta=(f"-{funnel.duplicates_removed} duplicados · {funnel.news_docs} noticias (/w/)"),
            delta_color="off",
        )
        st.caption(
            "Huella `content_sha256` sobre el cuerpo limpio para eliminar páginas "
            "repetidas entre secciones."
        )
    with s5:
        words_label = f"{funnel.institutional_words:,}".replace(",", ".")
        st.metric(
            "5. Enriquecer (Gold)",
            f"~{funnel.institutional_tokens:,} tokens".replace(",", "."),
            delta=f"{words_label} palabras · {funnel.sections_count} secciones",
            delta_color="normal",
        )
        st.caption(
            "Frontmatter YAML verificable, catálogo `corpus.jsonl`, `knowledge_base.md` "
            "y `chunks.jsonl`."
        )

    with st.expander("🛡️ Política Ética, Legal y Técnica de Captura (Verificable)", expanded=False):
        p1, p2, p3, p4 = st.columns(4)
        p1.markdown(f"**User-Agent:**\n`{config.USER_AGENT}`")
        p2.markdown(
            f"**Rate Limit y Timeout:**\n`{config.REQUEST_DELAY_SECONDS} s` entre peticiones · "
            f"Timeout `{config.REQUEST_TIMEOUT_SECONDS} s` · `{config.MAX_RETRIES}` reintentos"
        )
        p3.markdown(
            "**Hosts de iframes permitidos:**\n"
            + ", ".join(f"`{h}`" for h in sorted(config.TRUSTED_RENDER_HOSTS))
        )
        p4.markdown(
            "**Prefijos excluidos (`robots`/alcance):**\n"
            + ", ".join(f"`{p}`" for p in config.EXCLUDED_PATH_PREFIXES[:8])
            + f" (+{len(config.EXCLUDED_PATH_PREFIXES) - 8} más)"
        )

    st.markdown("---")
    st.markdown("### 2. Inspector Comparativo de Capas Medallion (Bronze → Silver → Gold)")
    if bundle.documents:
        doc_options = [
            f"[{doc.section}] {doc.title} ({doc.slug} · {doc.word_count} palabras)"
            for doc in bundle.documents
        ]
        selected_doc_label = st.selectbox(
            "Selecciona un documento del corpus para comparar su transformación:",
            options=doc_options,
            index=0,
        )
        selected_doc = bundle.documents[doc_options.index(selected_doc_label)]
        medallion_view = load_medallion_document_view(selected_doc.section, selected_doc.slug)

        info_col1, info_col2, info_col3 = st.columns(3)
        info_col1.markdown(
            f"**URL Oficial:** [{medallion_view.source_url}]({medallion_view.source_url})"
        )
        info_col2.markdown(f"**Modo de Captura:** `{medallion_view.render_mode}`")
        info_col3.markdown(
            f"**Iframe React:** `{medallion_view.iframe_url or 'No aplica (HTML directo)'}`"
        )

        layer_bronze, layer_silver, layer_gold, layer_jsonl = st.tabs(
            [
                "🥉 Capa Bronze (HTML Crudo / Iframe)",
                "🥈 Capa Silver (Markdown Limpio)",
                "🥇 Capa Gold (Frontmatter YAML + MD)",
                "📇 Registro en Índice (corpus.jsonl)",
            ]
        )
        with layer_bronze:
            st.caption(f"Origen: `{medallion_view.bronze_source}`")
            st.code(medallion_view.bronze_html[:5000], language="html")
        with layer_silver:
            st.caption(
                f"Ruta Silver: `data/processed/{medallion_view.section}/{medallion_view.slug}.md` "
                "(sin menús, scripts ni metadatos YAML)"
            )
            st.code(medallion_view.silver_markdown, language="markdown")
        with layer_gold:
            st.caption(
                f"Ruta Gold: `data/gold/{medallion_view.section}/{medallion_view.slug}.md` "
                "(con Frontmatter YAML verificable y hash SHA-256)"
            )
            st.code(medallion_view.gold_markdown_with_frontmatter, language="markdown")
        with layer_jsonl:
            st.caption("Entrada estructurada en `data/gold/corpus.jsonl`:")
            st.code(
                json.dumps(medallion_view.gold_index_record, ensure_ascii=False, indent=2),
                language="json",
            )

    st.markdown("---")
    st.markdown("### 3. Segmentación Semántica (Chunking) y Contexto Activo")
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Documentos en Contexto", f"{bundle.document_count}")
    col_b.metric("Secciones Cubiertas", f"{len(bundle.sections)}")
    col_c.metric("Palabras Limpias", f"{bundle.total_words:,}".replace(",", "."))
    col_d.metric("Tokens Estimados", f"~{bundle.estimated_tokens:,}".replace(",", "."))

    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        chunk_size = st.slider(
            "Tamaño máximo de chunk (caracteres)",
            min_value=400,
            max_value=3000,
            value=DEFAULT_CHUNK_SIZE,
            step=100,
        )
    with c2:
        chunk_overlap = st.slider(
            "Solapamiento entre chunks (caracteres)",
            min_value=0,
            max_value=600,
            value=DEFAULT_CHUNK_OVERLAP,
            step=50,
        )
    chunks = get_cached_chunks(
        scope_mode,
        selected_sections,
        include_news,
        chunk_size,
        chunk_overlap,
    )
    with c3:
        st.metric("Total de Chunks Generados", f"{len(chunks):,}".replace(",", "."))
        if st.button("💾 Exportar knowledge_base.md y chunks.jsonl", use_container_width=True):
            export_knowledge_artifacts(
                include_news=include_news,
                sections=selected_sections if scope_mode == "sections" else None,
                curated_only=(scope_mode == "curated"),
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            st.success("Archivos exportados en `data/knowledge_base.md` y `data/chunks.jsonl`.")

    st.markdown("### 4. Explorador de Fragmentos (Chunks)")
    if chunks:
        selected_chunk_idx = st.number_input(
            f"Inspeccionar chunk (1 a {len(chunks)})",
            min_value=1,
            max_value=len(chunks),
            value=1,
            step=1,
        )
        ch = chunks[int(selected_chunk_idx) - 1]
        st.info(
            f"**ID:** `{ch.chunk_id}` · **Sección:** `{ch.section}` · "
            f"**Ruta de encabezados:** `{ch.heading_path}` · "
            f"**Palabras:** {ch.word_count} · **Caracteres:** {ch.char_count}\n\n"
            f"**URL de origen:** {ch.source_url}"
        )
        st.code(ch.text, language="markdown")

    with st.expander("🔍 Ver Vista Previa del System Prompt Consolidado", expanded=False):
        full_prompt = build_qa_system_prompt(
            bundle.consolidated_text,
            strategy_key=strategy_key,
            custom_instructions=custom_instructions,
        )
        st.caption(
            f"Longitud total del System Prompt: {len(full_prompt):,} caracteres.".replace(",", ".")
        )
        st.code(
            full_prompt[:6000] + "\n\n... [truncado en la vista previa] ...", language="markdown"
        )


def render_evaluation_tab(
    model_name: str,
    temperature: float,
    reasoning_effort: str | None,
    strategy_key: str,
    bundle: KnowledgeBaseBundle,
) -> None:
    """Renderiza el laboratorio de Prompt Engineering y la batería de 22 preguntas."""
    st.subheader("🧪 Batería de Pruebas (22 Preguntas) y Experimentación de Prompts")

    st.markdown("### Comparativa de Estrategias de Prompt Engineering")
    cols = st.columns(len(PROMPT_STRATEGIES))
    for col, strategy in zip(cols, PROMPT_STRATEGIES.values(), strict=False):
        with col:
            st.markdown(f"**{strategy.name}** (`{strategy.key}`)")
            st.caption(strategy.description)
            with st.expander("Ver plantilla"):
                st.code(strategy.instructions, language="markdown")

    st.markdown("---")
    st.markdown("### Ejecución Interactiva del Benchmark (22 Preguntas)")

    col_left, col_right = st.columns([2, 1])
    with col_left:
        selected_ids = st.multiselect(
            "Selecciona las preguntas a ejecutar en vivo (o deja las 22 para corrida completa):",
            options=[q.id for q in BENCHMARK_QUESTIONS],
            default=[1, 4, 7, 10, 15, 21],
            format_func=lambda qid: (
                f"P{qid:02d} [{BENCHMARK_QUESTIONS[qid - 1].category}]: "
                f"{BENCHMARK_QUESTIONS[qid - 1].question[:65]}…"
            ),
        )
    with col_right:
        st.write("")
        st.write("")
        run_eval_btn = st.button(
            "▶️ Ejecutar preguntas seleccionadas",
            type="primary",
            use_container_width=True,
        )

    if run_eval_btn and selected_ids:
        settings = load_assistant_settings(
            model=model_name,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
        )
        subset = [q for q in BENCHMARK_QUESTIONS if q.id in selected_ids]
        progress_bar = st.progress(0.0, text="Iniciando evaluación…")

        def _on_step(idx: int, total: int, ev: object) -> None:
            progress_bar.progress(idx / total, text=f"Evaluada pregunta {idx} de {total}…")

        from emcali_corpus.evaluation import run_benchmark_suite

        evaluations = run_benchmark_suite(
            bundle,
            questions=subset,
            settings=settings,
            strategy_key=strategy_key,
            progress=_on_step,
        )
        st.session_state.last_eval_md = render_benchmark_markdown(
            evaluations,
            model_name=model_name,
            strategy_key=strategy_key,
            context_docs=bundle.document_count,
            context_words=bundle.total_words,
        )

    if "last_eval_md" in st.session_state:
        st.markdown(st.session_state.last_eval_md)

    if EVALUATION_REPORT_PATH.is_file():
        with st.expander(
            "📄 Ver Informe Completo de las 22 Preguntas (docs/evaluacion_preguntas.md)",
            expanded=False,
        ):
            st.markdown(EVALUATION_REPORT_PATH.read_text(encoding="utf-8"))


def main() -> None:
    """Punto de entrada principal de la aplicación Streamlit."""
    st.set_page_config(
        page_title="Asistente Semántico EMCALI — Taller 1",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("⚡ Núcleo de Conocimiento Semántico y Sistema Q&A — EMCALI E.I.C.E. E.S.P.")
    st.caption(
        "Módulo 1 · Técnicas Avanzadas de IA Aplicadas en Modelos de Lenguaje · "
        "LangChain + DeepSeek V4.1 Flash (`deepseek-flash`) · Universidad Autónoma de Occidente"
    )

    try:
        load_assistant_settings()
    except MissingAPIKeyError as exc:
        st.error(str(exc))
        st.code("echo 'DEEPSEEK_API_KEY=sk-...' >> .env", language="bash")
        st.stop()

    (
        model_name,
        temperature,
        reasoning_effort,
        strategy_key,
        custom_instructions,
        bundle,
        scope_mode,
        selected_sections,
        include_news,
    ) = render_sidebar()

    tab_qa, tab_kb, tab_summary, tab_faq, tab_eval = st.tabs(
        [
            "💬 Chat Q&A (con Citas)",
            "🏗️ Pipeline Scraping (Bronze → Silver → Gold)",
            "📑 Resumen Ejecutivo",
            "❓ Generador de FAQ",
            "🧪 Evaluación (22 Preguntas) y Prompts",
        ]
    )

    with tab_qa:
        render_qa_tab(
            model_name,
            temperature,
            reasoning_effort,
            strategy_key,
            custom_instructions,
            bundle,
        )
    with tab_kb:
        render_knowledge_tab(
            bundle,
            scope_mode,
            selected_sections,
            include_news,
            strategy_key,
            custom_instructions,
        )
    with tab_summary:
        render_summary_tab(model_name, temperature, reasoning_effort, bundle)
    with tab_faq:
        render_faq_tab(model_name, temperature, reasoning_effort, bundle)
    with tab_eval:
        render_evaluation_tab(
            model_name,
            temperature,
            reasoning_effort,
            strategy_key,
            bundle,
        )


if __name__ == "__main__":
    main()
