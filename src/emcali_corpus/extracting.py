"""Extracción de contenido editorial: HTML → Markdown, sin depender de la red."""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from emcali_corpus import config
from emcali_corpus.models import ExtractedDocument

HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
INLINE_TAGS = {
    "a",
    "abbr",
    "b",
    "bdi",
    "bdo",
    "cite",
    "code",
    "data",
    "del",
    "dfn",
    "em",
    "i",
    "ins",
    "kbd",
    "mark",
    "q",
    "s",
    "samp",
    "small",
    "span",
    "strong",
    "sub",
    "sup",
    "time",
    "u",
    "var",
}
BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "details",
    "div",
    "dl",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "header",
    "hgroup",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "ul",
}
DROP_TAGS = {
    "canvas",
    "dialog",
    "form",
    "iframe",
    "input",
    "noscript",
    "script",
    "select",
    "style",
    "svg",
    "template",
    "textarea",
}
DROP_SELECTORS = (
    ".barra-mile",
    ".dialog-portal",
    ".drawer-portal",
    "#_rht_toaster",
    "#hrefFm",
)
DECORATIVE_ALT = re.compile(
    r"^(arrow|icon|decorative|tangara|divider|certification|facebook icon|"
    r"whatsapp|accesibilidad|logo|banner|image)",
    re.IGNORECASE,
)
NOISE_LINE = re.compile(
    r"^(?:"
    r"número de visitas a esta página.*|"
    r"fecha de publicación\s*:.*|"
    r"última modificación\s*:.*|"
    r"desarrollado por liferay|"
    r"saltar al contenido principal|"
    r"oculto|"
    r"compartir|"
    r"imprimir|"
    r"leer en voz alta|"
    r"ver (?:más|todo)|"
    r"ir a noticias|"
    r"conoce más|"
    r"accesibilidad|"
    r"haz clic aquí.*|"
    r"leer más|"
    r"(?:es|en)|"
    r"\d{1,2}/\d{1,2}/\d{2,4}(?:,?\s*\d{1,2}:\d{2})?|"
    r"\d{1,2}:\d{2}(?:\s*[ap]\.?\s*m\.?)?|"
    r"-{1,3}|"
    r"\d{1,3}(?:\.\d{3})*"
    r")$",
    re.IGNORECASE,
)
TITLE_SUFFIX = re.compile(r"\s*[-\u2013|]\s*EMCALI\s*$", re.IGNORECASE)
CTA_SUFFIX = re.compile(r"\s*(?:Ver más|Ver todo|Leer más)\s*$", re.IGNORECASE)
NOISE_HEADING = re.compile(
    r"^#{1,6}\s+(?:conoce más|accesibilidad|es|en)$",
    re.IGNORECASE,
)
_CTA_LINE = re.compile(
    r"^\[(?:haz clic aquí[^\]]*|ver más|ver todo|ir a noticias|leer más)\]\([^)]*\)$",
    re.IGNORECASE,
)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u200b", "")).strip()


def _escape(text: str) -> str:
    return text.replace("[", r"\[").replace("]", r"\]")


def _absolute(base_url: str, href: str) -> str:
    if not href or href.startswith(("#", "javascript:", "data:")):
        return ""
    absolute = urljoin(base_url, href.strip())
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https", "mailto", "tel"}:
        return ""
    return urlunparse(parsed._replace(fragment=""))


def _attr(node: Tag, name: str) -> str:
    """Devuelve un atributo HTML como texto, tolerando valores multivaluados."""
    value = node.get(name)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return ""


def find_content_frame(
    html: str,
    page_url: str,
    *,
    trusted_hosts: frozenset[str] = config.TRUSTED_RENDER_HOSTS,
    max_wrapper_chars: int = 300,
) -> str:
    """Devuelve la URL del iframe cuando la página es solo un envoltorio."""
    soup = BeautifulSoup(html, "lxml")
    candidates: list[str] = []
    for iframe in soup.find_all("iframe"):
        source = _attr(iframe, "src") or _attr(iframe, "data-src")
        if not source:
            continue
        absolute = urljoin(page_url, source)
        host = (urlparse(absolute).hostname or "").lower()
        if host in trusted_hosts:
            candidates.append(absolute)
    for node in soup.find_all(list(DROP_TAGS - {"iframe"})):
        node.decompose()
    if len(_clean(soup.get_text(" ", strip=True))) > max_wrapper_chars:
        return ""
    return candidates[0] if candidates else ""


def _meta_content(soup: BeautifulSoup, *, name: str = "", prop: str = "") -> str:
    if name:
        node = soup.find("meta", attrs={"name": re.compile(f"^{re.escape(name)}$", re.I)})
    elif prop:
        node = soup.find("meta", attrs={"property": prop})
    else:
        return ""
    if node and isinstance(node, Tag):
        return _clean(_attr(node, "content"))
    return ""


def extract_metadata(soup: BeautifulSoup, page_url: str) -> dict[str, str]:
    """Obtiene título, descripción, canonical e idioma del documento."""
    title = ""
    if soup.title and soup.title.string:
        title = _clean(soup.title.string)
    title = TITLE_SUFFIX.sub("", title).strip()
    if not title or title.casefold() == "emcali":
        title = _meta_content(soup, prop="og:title") or _meta_content(soup, name="twitter:title")
        title = TITLE_SUFFIX.sub("", title).strip()
    if not title:
        heading = soup.find(["h1", "h2"])
        title = _clean(heading.get_text(" ", strip=True)) if heading else ""

    description = _meta_content(soup, name="description") or _meta_content(
        soup, prop="og:description"
    )
    generic_description = (
        "admin template" in description.lower()
        or description.lower().startswith("empresas municipales de cali")
        or description.casefold() == "emcali"
    )
    if generic_description:
        description = ""

    canonical = ""
    link = soup.find("link", attrs={"rel": re.compile("canonical", re.I)})
    if link and isinstance(link, Tag):
        canonical = _absolute(page_url, _attr(link, "href"))

    html_tag = soup.find("html")
    language = "es"
    if html_tag and isinstance(html_tag, Tag):
        language = (_attr(html_tag, "lang") or "es").split("-")[0].lower()

    return {
        "title": title,
        "description": description,
        "canonical_url": canonical,
        "language": language,
    }


def _top_level(nodes: list[Tag]) -> list[Tag]:
    selected = {id(node) for node in nodes}
    return [
        node
        for node in nodes
        if not any(id(parent) in selected for parent in node.parents if isinstance(parent, Tag))
    ]


class MarkdownRenderer:
    """Conversor de DOM a Markdown que conserva la estructura editorial."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.links: list[str] = []
        self.images: list[str] = []

    def render(self, roots: list[Tag]) -> str:
        blocks: list[str] = []
        for root in roots:
            self._render_container(root, blocks)
        return self._normalize(blocks)

    def _is_hidden(self, node: Tag) -> bool:
        if node.has_attr("hidden") or _attr(node, "aria-hidden") == "true":
            return True
        style = _attr(node, "style").replace(" ", "").lower()
        return "display:none" in style or "visibility:hidden" in style

    def _image(self, node: Tag) -> str:
        # El corpus es textual: se registran las URLs, pero no se insertan en Markdown.
        source = _attr(node, "src") or _attr(node, "data-src")
        alt = _clean(_attr(node, "alt"))
        if not source or source.startswith("data:"):
            return ""
        if DECORATIVE_ALT.match(alt) or len(alt) < 4:
            return ""
        absolute = _absolute(self.base_url, source)
        if absolute and absolute not in self.images:
            self.images.append(absolute)
        return ""

    def _inline(self, node: Tag) -> str:
        return self._inline_nodes(list(node.children))

    def _inline_nodes(self, nodes: Iterable[object]) -> str:
        parts: list[str] = []
        for child in nodes:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                text = re.sub(r"\s+", " ", str(child).replace("\xa0", " "))
                if text.strip():
                    parts.append(_escape(text))
                continue
            if not isinstance(child, Tag):
                continue
            name = child.name.lower()
            if name in DROP_TAGS or name in {"ul", "ol", "table"} or self._is_hidden(child):
                continue
            if name == "br":
                parts.append("\n")
            elif name == "img":
                parts.append(self._image(child))
            elif name == "a":
                href = _absolute(self.base_url, _attr(child, "href"))
                text = self._inline(child)
                if href:
                    if href not in self.links:
                        self.links.append(href)
                    parts.append(f"[{text}]({href})" if text else "")
                else:
                    parts.append(text)
            elif name in {"strong", "b"}:
                text = self._inline(child)
                parts.append(f"**{text}**" if text else "")
            elif name in {"em", "i"}:
                text = self._inline(child)
                parts.append(f"*{text}*" if text else "")
            elif name in {"code", "kbd", "samp"}:
                text = _clean(child.get_text(" ", strip=True))
                parts.append(f"`{text}`" if text else "")
            elif name in {"del", "s"}:
                text = self._inline(child)
                parts.append(f"~~{text}~~" if text else "")
            else:
                parts.append(self._inline(child))
        text = "".join(parts)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" +([,.;:!?])", r"\1", text)
        return text.strip(" \t")

    def _has_block_children(self, node: Tag) -> bool:
        return any(
            isinstance(child, Tag)
            and (child.name.lower() in BLOCK_TAGS or child.name.lower() in HEADINGS)
            for child in node.find_all(True, recursive=True)
        )

    def _flush(self, buffer: list[str], blocks: list[str]) -> None:
        text = _clean("".join(buffer))
        if text and re.search(r"\w", text):
            blocks.append(text)
        buffer.clear()

    def _render_container(self, node: Tag, blocks: list[str]) -> None:
        buffer: list[str] = []
        for child in node.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                text = re.sub(r"\s+", " ", str(child).replace("\xa0", " "))
                if text.strip():
                    buffer.append(_escape(text))
                continue
            if not isinstance(child, Tag):
                continue
            name = child.name.lower()
            if name in DROP_TAGS or name in {"nav", "footer"} or self._is_hidden(child):
                continue
            if name in INLINE_TAGS or name in {"img", "br"}:
                if name == "img":
                    image = self._image(child)
                    if image:
                        buffer.append(image)
                    continue
                if name == "a" and self._has_block_children(child):
                    self._flush(buffer, blocks)
                    self._render_block(child, blocks)
                    continue
                buffer.append(self._inline(child))
                continue
            self._flush(buffer, blocks)
            self._render_block(child, blocks)
        self._flush(buffer, blocks)

    def _render_block(self, node: Tag, blocks: list[str]) -> None:
        name = node.name.lower()
        if name in HEADINGS:
            text = self._inline(node)
            if text:
                blocks.append(f"{'#' * HEADINGS[name]} {text}")
            return
        if name == "p":
            text = self._inline(node)
            if text:
                blocks.append(text)
            return
        if name in {"ul", "ol"}:
            rendered = self._render_list(node, 0)
            if rendered:
                blocks.append(rendered)
            return
        if name == "table":
            rendered = self._render_table(node)
            if rendered:
                blocks.append(rendered)
            return
        if name == "blockquote":
            inner: list[str] = []
            self._render_container(node, inner)
            quoted = "\n".join(
                f"> {line}" if line else ">" for line in "\n\n".join(inner).splitlines()
            )
            if quoted:
                blocks.append(quoted)
            return
        if name == "pre":
            code = node.get_text("\n", strip=False).strip("\n")
            if code:
                blocks.append(f"```\n{code}\n```")
            return
        if name == "hr":
            blocks.append("---")
            return
        if name == "img":
            image = self._image(node)
            if image:
                blocks.append(image)
            return
        if name == "a":
            if self._has_block_children(node):
                self._render_container(node, blocks)
                return
            text = self._inline(node)
            if text:
                blocks.append(text)
            return
        if name == "dl":
            for entry in node.find_all(["dt", "dd"], recursive=True):
                text = self._inline(entry)
                if not text:
                    continue
                blocks.append(f"**{text}**" if entry.name == "dt" else text)
            return
        if name == "details":
            summary = node.find("summary")
            if isinstance(summary, Tag):
                text = self._inline(summary)
                if text:
                    blocks.append(f"**{text}**")
            self._render_container(node, blocks)
            return
        if name in {"figure", "figcaption"}:
            if self._has_block_children(node):
                self._render_container(node, blocks)
            else:
                text = self._inline(node)
                if text:
                    blocks.append(f"*{text}*" if name == "figcaption" else text)
            return
        if name == "button":
            # Los botones de las landings contienen tarjetas editoriales: se desenvuelven.
            self._render_container(node, blocks)
            return
        if self._has_block_children(node):
            self._render_container(node, blocks)
            return
        text = self._inline(node)
        if text:
            blocks.append(text)

    def _render_list(self, node: Tag, depth: int) -> str:
        ordered = node.name.lower() == "ol"
        lines: list[str] = []
        for index, item in enumerate(node.find_all("li", recursive=False), start=1):
            nested = [
                child for child in item.find_all(["ul", "ol"]) if child.find_parent("li") is item
            ]
            inline_nodes = [
                child
                for child in item.children
                if not (isinstance(child, Tag) and child.name.lower() in {"ul", "ol"})
            ]
            text = _clean(self._inline_nodes(inline_nodes))
            marker = f"{index}." if ordered else "-"
            if text:
                lines.append(f"{'  ' * depth}{marker} {text}")
            for child in nested:
                rendered = self._render_list(child, depth + 1)
                if rendered:
                    lines.append(rendered)
        return "\n".join(lines)

    def _render_table(self, node: Tag) -> str:
        rows: list[list[str]] = []
        for row in node.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if not cells:
                continue
            values = []
            for cell in cells:
                text = _clean(self._inline(cell).replace("\n", " "))
                values.append(text.replace("|", r"\|"))
            rows.append(values)
        if not rows:
            return ""
        width = max(len(row) for row in rows)
        normalized = [row + [""] * (width - len(row)) for row in rows]
        header = normalized[0]
        separator = ["---"] * width
        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(separator) + " |",
        ]
        lines.extend("| " + " | ".join(row) + " |" for row in normalized[1:])
        return "\n".join(lines)

    def _normalize(self, blocks: list[str]) -> str:
        seen: set[str] = set()
        output: list[str] = []
        for block in blocks:
            lines: list[str] = []
            for raw_line in block.splitlines():
                line = raw_line.rstrip()
                if not line.strip():
                    continue
                stripped = line.lstrip()
                is_nested_item = (
                    stripped.startswith(("- ", "* ")) or stripped[:3].strip().rstrip(".").isdigit()
                )
                if not is_nested_item:
                    line = stripped
                if "|" in line and not line.startswith("|") and line.count("|") >= 3:
                    lines.extend(part.strip() for part in line.split("|") if part.strip())
                else:
                    lines.append(line)
            deduped: list[str] = []
            block_seen: set[str] = set()
            for line in lines:
                key = _clean(line)
                if key in block_seen:
                    continue
                block_seen.add(key)
                deduped.append(line)
            lines = deduped
            cleaned = "\n".join(lines).strip()
            if not cleaned:
                continue
            if (
                NOISE_LINE.match(cleaned)
                or NOISE_HEADING.match(cleaned)
                or _CTA_LINE.match(cleaned)
            ):
                continue
            cleaned = CTA_SUFFIX.sub("", cleaned).rstrip()
            key = _clean(cleaned)
            if key in seen:
                continue
            if output and _clean(output[-1]) == key:
                continue
            seen.add(key)
            output.append(cleaned)
        text = "\n\n".join(output)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"\n[ \t]+\n", "\n\n", text)
        return text.strip()


def extract_document(
    html: str,
    *,
    source_url: str,
    title_hint: str = "",
    used_frame: bool = False,
    frame_url: str = "",
) -> ExtractedDocument:
    """Convierte HTML en un documento Markdown con metadatos."""
    soup = BeautifulSoup(html, "lxml")
    metadata = extract_metadata(soup, source_url)

    for node in soup.find_all(list(DROP_TAGS)):
        node.decompose()
    for selector in DROP_SELECTORS:
        for node in soup.select(selector):
            node.decompose()

    roots = _top_level(soup.find_all("main"))
    if not roots:
        for selector in ("#main-content", "[role='main']", "#content", "body"):
            candidate = soup.select_one(selector)
            if isinstance(candidate, Tag):
                roots = [candidate]
                break
    if not roots:
        roots = [soup.body] if soup.body else []

    renderer = MarkdownRenderer(source_url)
    body = renderer.render(roots)

    title = title_hint or metadata["title"]
    if not title:
        title = "Documento sin título"

    if body:
        first_line = body.splitlines()[0]
        if first_line.startswith("# "):
            first_heading = _clean(first_line.lstrip("# "))
            if first_heading.casefold() == title.casefold():
                body = body.split("\n", 1)[1].lstrip("\n")

    return ExtractedDocument(
        title=title,
        body=body,
        description=metadata["description"],
        canonical_url=metadata["canonical_url"],
        language=metadata["language"],
        links=renderer.links,
        images=renderer.images,
        used_frame=used_frame,
        frame_url=frame_url,
    )


def compose_body(title: str, body: str) -> str:
    """Añade el H1 del título y normaliza la jerarquía de encabezados."""
    heading = f"# {title}"
    stripped = body.lstrip()
    if stripped.startswith("# "):
        first_line = stripped.splitlines()[0]
        if _clean(first_line.lstrip("# ")).casefold() == title.casefold():
            return _demote_extra_h1(stripped, title).rstrip() + "\n"
    return _demote_extra_h1(f"{heading}\n\n{stripped}", title).rstrip() + "\n"


def _demote_extra_h1(body: str, title: str) -> str:
    """Convierte H1 posteriores en H2 para no duplicar el título del documento."""
    lines = body.splitlines()
    seen_title = False
    output: list[str] = []
    for line in lines:
        if line.startswith("# ") and not line.startswith("## "):
            text = _clean(line[2:])
            if not seen_title and text.casefold() == title.casefold():
                seen_title = True
                output.append(line)
                continue
            output.append(f"## {text}")
            continue
        output.append(line)
    return "\n".join(output)
