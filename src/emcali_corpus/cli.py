"""Interfaz de línea de comandos del corpus."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from emcali_corpus import __version__, config, gold
from emcali_corpus.discovery import discover_seeds, seed_from_url
from emcali_corpus.fetching import HttpClient, normalize_url
from emcali_corpus.pipeline import CaptureOutcome, Pipeline, summarize


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
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
