"""Interfaz de línea de comandos del corpus."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from emcali_corpus import __version__, config, gold
from emcali_corpus.assistant import (
    answer_question,
    generate_faq,
    generate_summary,
    load_assistant_settings,
)
from emcali_corpus.discovery import discover_seeds, seed_from_url
from emcali_corpus.evaluation import (
    BENCHMARK_QUESTIONS,
    EVALUATION_REPORT_PATH,
    QuestionEvaluation,
    render_benchmark_markdown,
    run_benchmark_suite,
)
from emcali_corpus.fetching import HttpClient, normalize_url
from emcali_corpus.knowledge import (
    CHUNKS_PATH,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    KNOWLEDGE_BASE_PATH,
    consolidate_knowledge_base,
    export_knowledge_artifacts,
)
from emcali_corpus.pipeline import CaptureOutcome, Pipeline, summarize
from emcali_corpus.prompts import DEFAULT_STRATEGY_KEY, PROMPT_STRATEGIES


def _configure_stdout() -> None:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _progress(outcome: CaptureOutcome) -> None:
    location = f"{outcome.seed.section}/{outcome.seed.slug}"
    if outcome.status == "ok":
        detail = f"{outcome.words:,} palabras · {outcome.render_mode}".replace(",", ".")
        print(f"[OK] {location} — {outcome.title} ({detail})")
    elif outcome.status == "skipped":
        print(f"[··] {location} — {outcome.message}")
    else:
        print(f"[!!] {location} — {outcome.message}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="emcali-corpus",
        description="Captura y curaduría del sitio web de EMCALI para RAG.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser(
        "capture",
        help="Captura las semillas curadas o todo el sitemap.",
        description=(
            "Sin opciones captura las semillas curadas (portada y páginas principales). "
            "Con --all recorre el sitemap completo del sitio."
        ),
    )
    capture.add_argument("--all", action="store_true", help="capturar todas las URLs del sitemap")
    capture.add_argument(
        "--section",
        action="append",
        default=[],
        help="limitar a una sección (repetible)",
    )
    capture.add_argument("--limit", type=int, help="máximo de páginas a capturar")
    capture.add_argument("--url", action="append", default=[], help="URL adicional (repetible)")
    capture.add_argument("--force", action="store_true", help="ignorar caché y recapturar")
    capture.add_argument(
        "--no-render",
        action="store_true",
        help="no usar navegador; fallará en páginas que dependen de JavaScript",
    )
    capture.add_argument(
        "--no-news",
        action="store_true",
        help="excluir las noticias (/w/...) al recorrer el sitemap",
    )
    capture.add_argument("--quiet", action="store_true", help="ocultar el progreso por página")

    discover = subparsers.add_parser(
        "discover",
        help="Lista las semillas descubiertas en el sitemap.",
    )
    discover.add_argument("--section", action="append", default=[], help="filtrar por sección")
    discover.add_argument("--limit", type=int, help="máximo de resultados")
    discover.add_argument("--no-news", action="store_true", help="excluir noticias")
    discover.add_argument("--json", action="store_true", help="salida JSON")
    discover.add_argument("--write", type=Path, help="guardar las semillas en un archivo JSON")

    index = subparsers.add_parser(
        "index",
        help="Reconstruye corpus.jsonl a partir de los documentos gold.",
    )
    index.add_argument(
        "--check",
        action="store_true",
        help="solo verificar que el índice coincida con los archivos gold",
    )

    reprocess = subparsers.add_parser(
        "reprocess",
        help="Reextrae gold y silver desde bronze, sin volver a la red.",
    )
    reprocess.add_argument("--quiet", action="store_true", help="ocultar el progreso por página")

    status = subparsers.add_parser("status", help="Muestra el estado del corpus.")
    status.add_argument("--json", action="store_true", help="salida JSON")

    listing = subparsers.add_parser("list", help="Lista los documentos del índice.")
    listing.add_argument("--section", help="filtrar por sección")
    listing.add_argument("--limit", type=int, help="máximo de resultados")
    listing.add_argument("--json", action="store_true", help="salida JSON")

    chunk_cmd = subparsers.add_parser(
        "chunk",
        help="Consolida la base de conocimiento limpia y genera los fragmentos (chunks).",
    )
    chunk_cmd.add_argument(
        "--include-news",
        action="store_true",
        help="incluir las noticias (/w/) además de las secciones institucionales",
    )
    chunk_cmd.add_argument(
        "--curated",
        action="store_true",
        help="usar únicamente las 18 semillas curadas principales",
    )
    chunk_cmd.add_argument(
        "--section",
        action="append",
        default=[],
        help="filtrar por sección (repetible)",
    )
    chunk_cmd.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help="tamaño máximo por chunk en caracteres",
    )
    chunk_cmd.add_argument(
        "--chunk-overlap",
        type=int,
        default=DEFAULT_CHUNK_OVERLAP,
        help="solapamiento entre chunks en caracteres",
    )
    chunk_cmd.add_argument(
        "--output-md",
        type=Path,
        default=KNOWLEDGE_BASE_PATH,
        help="ruta del archivo Markdown consolidado",
    )
    chunk_cmd.add_argument(
        "--output-chunks",
        type=Path,
        default=CHUNKS_PATH,
        help="ruta del archivo JSONL de chunks",
    )

    ask_cmd = subparsers.add_parser(
        "ask",
        help="Responde una pregunta con LangChain + DeepSeek usando el corpus consolidado.",
    )
    ask_cmd.add_argument("question", help="pregunta en lenguaje natural sobre EMCALI")
    ask_cmd.add_argument(
        "--strategy",
        choices=tuple(PROMPT_STRATEGIES),
        default=DEFAULT_STRATEGY_KEY,
        help="estrategia de prompt engineering",
    )
    ask_cmd.add_argument(
        "--curated",
        action="store_true",
        help="usar solo las 18 semillas curadas en el contexto",
    )
    ask_cmd.add_argument(
        "--section",
        action="append",
        default=[],
        help="limitar el contexto a una o más secciones",
    )

    summary_cmd = subparsers.add_parser(
        "summarize",
        help="Genera un resumen ejecutivo del corpus con LangChain + DeepSeek.",
    )
    summary_cmd.add_argument("--topic", default="", help="tema o servicio en el cual enfocar")
    summary_cmd.add_argument(
        "--curated",
        action="store_true",
        help="usar solo las 18 semillas curadas en el contexto",
    )
    summary_cmd.add_argument(
        "--section",
        action="append",
        default=[],
        help="limitar el contexto a una o más secciones",
    )

    faq_cmd = subparsers.add_parser(
        "faq",
        help="Genera un listado de Preguntas Frecuentes (FAQ) con LangChain + DeepSeek.",
    )
    faq_cmd.add_argument("--count", type=int, default=8, help="cantidad de preguntas a generar")
    faq_cmd.add_argument("--topic", default="", help="tema o servicio específico")
    faq_cmd.add_argument(
        "--curated",
        action="store_true",
        help="usar solo las 18 semillas curadas en el contexto",
    )
    faq_cmd.add_argument(
        "--section",
        action="append",
        default=[],
        help="limitar el contexto a una o más secciones",
    )

    eval_cmd = subparsers.add_parser(
        "evaluate",
        help="Ejecuta la batería de 22 preguntas de prueba y guarda el informe Markdown.",
    )
    eval_cmd.add_argument("--limit", type=int, help="ejecutar solo las primeras N preguntas")
    eval_cmd.add_argument(
        "--strategy",
        choices=tuple(PROMPT_STRATEGIES),
        default=DEFAULT_STRATEGY_KEY,
        help="estrategia de prompt engineering",
    )
    eval_cmd.add_argument(
        "--curated",
        action="store_true",
        help="usar las 18 semillas curadas para evaluación rápida",
    )
    eval_cmd.add_argument(
        "--output",
        type=Path,
        default=EVALUATION_REPORT_PATH,
        help="archivo Markdown donde guardar los resultados",
    )

    return parser


def _cmd_capture(args: argparse.Namespace) -> int:
    progress = None if args.quiet else _progress
    sections = args.section or None
    with Pipeline(
        force=args.force,
        render=not args.no_render,
        include_news=not args.no_news,
        progress=progress,
    ) as pipeline:
        report = None
        if args.all:
            report = pipeline.capture_sitemap(sections=sections, limit=args.limit)
        else:
            seeds = [
                seed for seed in config.CURATED_SEEDS if not sections or seed.section in sections
            ]
            if args.limit is not None:
                seeds = seeds[: args.limit]
            urls = [normalize_url(url) for url in args.url]
            seeds.extend(seed_from_url(url) for url in urls)
            report = pipeline.capture(seeds)
        if report.captured:
            pipeline.index.flush()
        stats = pipeline.stats()

    print()
    print(summarize(report))
    print(
        f"Corpus: {stats['documents']} documentos · {stats['words']:,} palabras".replace(",", ".")
    )
    if report.errors:
        print("Revisa data/errors.jsonl para ver el detalle de los errores.")
    return 1 if report.errors else 0


def _cmd_discover(args: argparse.Namespace) -> int:
    with HttpClient() as client:
        seeds = discover_seeds(
            client,
            include_news=not args.no_news,
            sections=args.section or None,
        )
    if args.limit is not None:
        seeds = seeds[: args.limit]
    payload = [
        {"url": seed.url, "slug": seed.slug, "section": seed.section, "lastmod": seed.lastmod}
        for seed in seeds
    ]
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"{len(payload)} semillas escritas en {args.write}")
        return 0
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    for seed in seeds:
        print(f"{seed.section:20} {seed.slug:55} {seed.url}")
    print(f"\n{len(seeds)} semillas")
    return 0


def _cmd_index(args: argparse.Namespace) -> int:
    records = gold.rebuild_index_from_gold(config.GOLD_DIR)
    on_disk = gold.read_index(config.INDEX_PATH)
    if args.check:
        expected = {
            (item.get("section"), item["slug"], item.get("content_sha256")) for item in records
        }
        current = {
            (item.get("section"), item["slug"], item.get("content_sha256")) for item in on_disk
        }
        if expected == current:
            print(f"Índice consistente con {len(records)} documentos gold.")
            return 0
        missing = expected - current
        extra = current - expected
        print(f"Índice desactualizado: {len(records)} gold, {len(on_disk)} en el índice.")
        for section, slug, _ in sorted(missing)[:10]:
            print(f"  falta: {section}/{slug}")
        for section, slug, _ in sorted(extra)[:10]:
            print(f"  sobra: {section}/{slug}")
        return 1
    gold.write_index(records, config.INDEX_PATH)
    print(f"Índice reconstruido con {len(records)} documentos.")
    return 0


def _cmd_reprocess(args: argparse.Namespace) -> int:
    progress = None if args.quiet else _progress
    with Pipeline(progress=progress) as pipeline:
        report = pipeline.reprocess()
        stats = pipeline.stats()

    print()
    print(summarize(report))
    print(
        f"Corpus: {stats['documents']} documentos · {stats['words']:,} palabras".replace(",", ".")
    )
    if report.errors:
        print("Revisa data/errors.jsonl para ver el detalle de los errores.")
    return 1 if report.errors else 0


def _cmd_status(args: argparse.Namespace) -> int:
    with Pipeline() as pipeline:
        stats = pipeline.stats()
    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0
    print(f"Directorio de datos : {stats['data_dir']}")
    print(f"Documentos gold     : {stats['documents']}")
    print(f"Registros índice    : {stats['indexed']}")
    print(f"Palabras            : {stats['words']:,}".replace(",", "."))
    print(f"Renderizados        : {stats['rendered']}")
    print(f"Archivos bronze     : {stats['raw_files']}")
    print(f"Archivos silver     : {stats['silver_files']}")
    print(f"Errores registrados : {stats['errors']}")
    if stats["sections"]:
        print("\nPor sección:")
        sections = stats["sections"]
        if isinstance(sections, dict):
            for section, count in sections.items():
                print(f"  {section:25} {count}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    records = gold.read_index(config.INDEX_PATH)
    if args.section:
        records = [record for record in records if record.get("section") == args.section]
    if args.limit is not None:
        records = records[: args.limit]
    if args.json:
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return 0
    if not records:
        print("No hay documentos en el índice. Ejecuta `emcali-corpus capture`.")
        return 0
    print(f"{'SECCIÓN':18} {'SLUG':48} {'PALABRAS':>9}  TÍTULO")
    for record in records:
        print(
            f"{record.get('section', '')!s:18} "
            f"{str(record.get('slug', ''))[:48]:48} "
            f"{int(record.get('word_count', 0)):9,}  "
            f"{record.get('title', '')}".replace(",", ".")
        )
    print(f"\n{len(records)} documentos")
    return 0


def _cmd_chunk(args: argparse.Namespace) -> int:
    bundle, chunks = export_knowledge_artifacts(
        output_md=args.output_md,
        output_chunks=args.output_chunks,
        include_news=args.include_news,
        sections=args.section or None,
        curated_only=args.curated,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    print(f"Documentos consolidados : {bundle.document_count}")
    print(f"Palabras consolidadas   : {bundle.total_words:,}".replace(",", "."))
    print(f"Secciones               : {len(bundle.sections)}")
    print(f"Chunks generados        : {len(chunks):,}".replace(",", "."))
    print(f"Archivo texto limpio    : {args.output_md}")
    print(f"Archivo JSONL de chunks : {args.output_chunks}")
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    bundle = consolidate_knowledge_base(
        include_news=False,
        sections=args.section or None,
        curated_only=args.curated,
    )
    settings = load_assistant_settings()
    reply = answer_question(
        args.question,
        bundle,
        settings=settings,
        strategy_key=args.strategy,
    )
    print(reply.answer)
    return 0


def _cmd_summarize(args: argparse.Namespace) -> int:
    bundle = consolidate_knowledge_base(
        include_news=False,
        sections=args.section or None,
        curated_only=args.curated,
    )
    settings = load_assistant_settings()
    reply = generate_summary(bundle, settings=settings, focus_topic=args.topic)
    print(reply.answer)
    return 0


def _cmd_faq(args: argparse.Namespace) -> int:
    bundle = consolidate_knowledge_base(
        include_news=False,
        sections=args.section or None,
        curated_only=args.curated,
    )
    settings = load_assistant_settings()
    reply = generate_faq(
        bundle,
        settings=settings,
        num_questions=args.count,
        focus_topic=args.topic,
    )
    print(reply.answer)
    return 0


def _cmd_evaluate(args: argparse.Namespace) -> int:
    bundle = consolidate_knowledge_base(
        include_news=False,
        curated_only=args.curated,
    )
    settings = load_assistant_settings()
    questions = BENCHMARK_QUESTIONS[: args.limit] if args.limit else BENCHMARK_QUESTIONS

    def _step(idx: int, total: int, ev: QuestionEvaluation) -> None:
        mark = "OK" if ev.passed else "REV"
        cite_label = "Sí" if ev.has_source_citation else "No"
        print(
            f"[{mark}] ({idx:02d}/{total:02d}) {ev.item.category} — "
            f"Recall: {ev.keyword_recall * 100:.0f}% · Cita: {cite_label}"
        )

    evaluations = run_benchmark_suite(
        bundle,
        questions=questions,
        settings=settings,
        strategy_key=args.strategy,
        progress=_step,
    )
    report_md = render_benchmark_markdown(
        evaluations,
        model_name=settings.model,
        strategy_key=args.strategy,
        context_docs=bundle.document_count,
        context_words=bundle.total_words,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report_md, encoding="utf-8", newline="\n")
    passed = sum(1 for ev in evaluations if ev.passed)
    print(f"\nResultado: {passed}/{len(evaluations)} aprobadas. Informe en {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    _configure_stdout()
    parser = _build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "capture": _cmd_capture,
        "discover": _cmd_discover,
        "index": _cmd_index,
        "reprocess": _cmd_reprocess,
        "status": _cmd_status,
        "list": _cmd_list,
        "chunk": _cmd_chunk,
        "ask": _cmd_ask,
        "summarize": _cmd_summarize,
        "faq": _cmd_faq,
        "evaluate": _cmd_evaluate,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
