"""Publishable manuscript exports from a Project."""

from __future__ import annotations

import html
import io
import json
import re
import zipfile
from xml.sax.saxutils import escape as xml_escape

from app.models.schemas import Project


def _slug(title: str) -> str:
    s = re.sub(r"[^\w\s-]", "", title or "manuscript", flags=re.U)
    s = re.sub(r"[-\s]+", "-", s.strip()).strip("-").lower()
    return s or "manuscript"


def _sorted_chapters(project: Project):
    return sorted(project.chapters or [], key=lambda c: c.order)


_SCENE_BREAK_RE = re.compile(
    r"^(?:\*\s*\*\s*\*|\*\*\*|---|—{2,}|#{3,}|·\s*·\s*·)$"
)


def _paragraphs(text: str) -> list[str]:
    """Plain paragraph strings (no scene-break detection)."""
    return [b for b, k in _novel_blocks(text) if k == "p"]


def _novel_blocks(text: str) -> list[tuple[str, str]]:
    """
    Split manuscript text into novel blocks.

    Returns list of (kind, text) where kind is 'p' | 'break'.
    Single newlines inside a paragraph become spaces (ebook-friendly).
    """
    if not (text or "").strip():
        return []
    chunks = re.split(r"\n\s*\n", text.strip())
    out: list[tuple[str, str]] = []
    for raw in chunks:
        block = raw.strip()
        if not block:
            continue
        # Normalize internal newlines → spaces (avoids jagged ebook lines)
        flat = re.sub(r"[ \t]*\n[ \t]*", " ", block)
        flat = re.sub(r" {2,}", " ", flat).strip()
        if _SCENE_BREAK_RE.match(flat):
            out.append(("break", ""))
        else:
            out.append(("p", flat))
    return out


def _chapter_heading_parts(title: str, index: int) -> tuple[str, str | None]:
    """
    Split 'Chapter 3: The Bus' into (kicker, subtitle).
    """
    t = (title or f"Chapter {index}").strip()
    m = re.match(
        r"^(chapter\s+(\d+|[ivxlcdm]+))\s*[:.\-—–]\s*(.+)$",
        t,
        flags=re.I,
    )
    if m:
        return m.group(1).strip(), m.group(3).strip()
    m2 = re.match(r"^(chapter\s+(\d+|[ivxlcdm]+))$", t, flags=re.I)
    if m2:
        return m2.group(1).strip(), None
    # Untitled-style: use Chapter N as kicker, title as subtitle
    if not re.match(r"^chapter\b", t, flags=re.I):
        return f"Chapter {index}", t
    return t, None


def _xhtml_escape_text(s: str) -> str:
    return xml_escape(s, {"\"": "&quot;", "'": "&apos;"})


def filename_for(project: Project, fmt: str) -> str:
    base = _slug(project.title)
    ext = {
        "markdown": "md",
        "md": "md",
        "txt": "txt",
        "text": "txt",
        "html": "html",
        "docx": "docx",
        "epub": "epub",
        "json": "json",
    }.get(fmt, fmt)
    return f"{base}.{ext}"


def media_type_for(fmt: str) -> str:
    return {
        "markdown": "text/markdown; charset=utf-8",
        "md": "text/markdown; charset=utf-8",
        "txt": "text/plain; charset=utf-8",
        "text": "text/plain; charset=utf-8",
        "html": "text/html; charset=utf-8",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "epub": "application/epub+zip",
        "json": "application/json; charset=utf-8",
    }.get(fmt, "application/octet-stream")


def export_project(project: Project, fmt: str) -> bytes:
    fmt = (fmt or "markdown").lower().strip()
    if fmt in ("markdown", "md"):
        return _to_markdown(project).encode("utf-8")
    if fmt in ("txt", "text"):
        return _to_text(project).encode("utf-8")
    if fmt == "html":
        return _to_html(project).encode("utf-8")
    if fmt == "docx":
        return _to_docx(project)
    if fmt == "epub":
        return _to_epub(project)
    if fmt == "json":
        return (
            json.dumps(project.model_dump(), indent=2, ensure_ascii=False) + "\n"
        ).encode("utf-8")
    raise ValueError(f"Unsupported export format: {fmt}")


def _front_matter_lines(project: Project) -> list[str]:
    lines = [project.title or "Untitled"]
    if project.premise:
        lines.append(project.premise)
    elif project.description:
        lines.append(project.description)
    if project.genre:
        lines.append(project.genre)
    return lines


def _to_markdown(project: Project) -> str:
    parts: list[str] = [f"# {project.title or 'Untitled'}", ""]
    if project.premise:
        parts += [f"*{project.premise}*", ""]
    elif project.description:
        parts += [f"*{project.description}*", ""]
    if project.genre:
        parts += [f"**Genre:** {project.genre}", ""]

    if project.characters:
        parts += ["## Dramatis Personae", ""]
        for c in project.characters:
            role = f" — {c.role}" if c.role else ""
            parts.append(f"- **{c.name}**{role}")
        parts.append("")

    for i, ch in enumerate(_sorted_chapters(project), start=1):
        title = ch.title or f"Chapter {i}"
        parts += [f"## {title}", ""]
        body = (ch.content or "").strip()
        if body:
            parts.append(body)
        else:
            parts.append("*(empty)*")
        parts += ["", ""]

    if (project.world_notes or "").strip():
        parts += ["## World Notes", "", project.world_notes.strip(), ""]

    return "\n".join(parts).rstrip() + "\n"


def _to_text(project: Project) -> str:
    parts: list[str] = []
    for line in _front_matter_lines(project):
        parts.append(line)
    parts += ["", "=" * 40, ""]

    for i, ch in enumerate(_sorted_chapters(project), start=1):
        title = ch.title or f"Chapter {i}"
        parts += [title, "-" * len(title), "", (ch.content or "").strip(), "", ""]

    return "\n".join(parts).rstrip() + "\n"


def _html_body_from_blocks(blocks: list[tuple[str, str]], *, first_nofirst: bool = True) -> str:
    parts: list[str] = []
    first_p = True
    for kind, text in blocks:
        if kind == "break":
            parts.append('<p class="scenebreak">* * *</p>')
            first_p = True
            continue
        cls = ' class="first"' if first_p and first_nofirst else ""
        parts.append(f"<p{cls}>{html.escape(text)}</p>")
        first_p = False
    return "".join(parts) if parts else "<p class=\"first\"><em>(empty)</em></p>"


def _to_html(project: Project) -> str:
    title = html.escape(project.title or "Untitled")
    meta_bits = []
    if project.premise:
        meta_bits.append(
            f"<p class='premise'><em>{html.escape(project.premise)}</em></p>"
        )
    if project.genre:
        meta_bits.append(f"<p class='genre'>{html.escape(project.genre)}</p>")

    chapters_html = []
    for i, ch in enumerate(_sorted_chapters(project), start=1):
        kicker, sub = _chapter_heading_parts(ch.title or f"Chapter {i}", i)
        if sub:
            head = (
                f"<p class='ch-kicker'>{html.escape(kicker)}</p>"
                f"<h2 class='ch-title'>{html.escape(sub)}</h2>"
            )
        else:
            head = f"<h2 class='ch-title'>{html.escape(kicker)}</h2>"
        body = _html_body_from_blocks(_novel_blocks(ch.content or ""))
        chapters_html.append(
            f"<section class='chapter' id='ch-{i}'>\n{head}\n{body}\n</section>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title}</title>
  <style>
    @page {{ size: 5.5in 8.5in; margin: 0.75in 0.7in; }}
    body {{
      max-width: 32rem; margin: 2rem auto; padding: 0 1.25rem 4rem;
      font-family: "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
      font-size: 12pt; line-height: 1.55; color: #1a1814;
      background: #faf8f2;
      hyphens: auto; -webkit-hyphens: auto;
    }}
    header.titlepage {{
      min-height: 70vh; display: flex; flex-direction: column;
      justify-content: center; align-items: center; text-align: center;
      page-break-after: always;
    }}
    h1.title {{
      font-weight: 600; font-size: 2rem; letter-spacing: 0.04em;
      margin: 0 0 1.5rem; text-wrap: balance;
    }}
    .premise {{ font-style: italic; color: #4a4338; max-width: 22rem; }}
    .genre {{ font-size: 0.85rem; letter-spacing: 0.12em; text-transform: uppercase;
              color: #7a6f5c; margin-top: 2rem; }}
    .chapter {{ page-break-before: always; }}
    .chapter:first-of-type {{ page-break-before: auto; }}
    .ch-kicker {{
      text-align: center; text-indent: 0 !important; font-size: 0.8rem;
      letter-spacing: 0.18em; text-transform: uppercase; color: #665b4a;
      margin: 3rem 0 0.5rem;
    }}
    .ch-title {{
      text-align: center; font-weight: 600; font-size: 1.35rem;
      margin: 0 0 2.25rem; page-break-after: avoid;
    }}
    p {{ margin: 0; text-indent: 1.5em; text-align: justify; }}
    p.first {{ text-indent: 0; margin-top: 0; }}
    p.scenebreak {{
      text-indent: 0; text-align: center; margin: 1.4em 0;
      letter-spacing: 0.45em; color: #665b4a;
    }}
    @media print {{
      body {{ background: white; margin: 0; max-width: none; padding: 0; }}
    }}
  </style>
</head>
<body>
  <header class="titlepage">
    <h1 class="title">{title}</h1>
    {"".join(meta_bits)}
  </header>
  {"".join(chapters_html)}
</body>
</html>
"""


def _to_docx(project: Project) -> bytes:
    try:
        from docx import Document
        from docx.shared import Pt
    except ImportError as exc:
        raise RuntimeError(
            "python-docx is required for DOCX export. pip install python-docx"
        ) from exc

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    doc.add_heading(project.title or "Untitled", level=0)
    if project.premise:
        p = doc.add_paragraph()
        run = p.add_run(project.premise)
        run.italic = True
    if project.genre:
        doc.add_paragraph(f"Genre: {project.genre}")

    if project.characters:
        doc.add_heading("Dramatis Personae", level=1)
        for c in project.characters:
            line = c.name + (f" — {c.role}" if c.role else "")
            doc.add_paragraph(line, style="List Bullet")

    for i, ch in enumerate(_sorted_chapters(project), start=1):
        doc.add_heading(ch.title or f"Chapter {i}", level=1)
        paras = _paragraphs(ch.content or "")
        if not paras:
            doc.add_paragraph("(empty)")
        else:
            for para in paras:
                doc.add_paragraph(para.replace("\n", " "))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _epub_css() -> str:
    """Reflowable novel stylesheet — portrait-friendly, no fixed viewport."""
    return """
/* GhostWriter novel EPUB — reflowable, LTR, reader-controlled type size */
@namespace epub "http://www.idpf.org/2007/ops";

html {
  /* Do not set a fixed width/height/viewport — that forces landscape oddities */
  writing-mode: horizontal-tb;
  direction: ltr;
}

body {
  margin: 0;
  padding: 0;
  font-family: "Palatino Linotype", Palatino, "Book Antiqua", Georgia, "Times New Roman", serif;
  font-size: 1em;              /* respect reader default */
  line-height: 1.5;
  text-align: justify;
  widows: 2;
  orphans: 2;
  hyphens: auto;
  -epub-hyphens: auto;
  -webkit-hyphens: auto;
  adobe-hyphenate: auto;
}

/* Vertical rhythm via em so it scales with reader font size */
p {
  margin: 0;
  padding: 0;
  text-indent: 1.5em;
  line-height: 1.5;
}

p.first {
  text-indent: 0;
}

p.scenebreak {
  text-indent: 0;
  text-align: center;
  margin: 1.25em 0 1.25em 0;
  letter-spacing: 0.55em;
  font-size: 0.95em;
  page-break-inside: avoid;
}

/* —— Title page —— */
body.titlepage {
  text-align: center;
  padding: 30% 1.2em 2em 1.2em;
}

body.titlepage h1 {
  font-size: 1.85em;
  font-weight: normal;
  letter-spacing: 0.06em;
  margin: 0 0 1.75em 0;
  line-height: 1.25;
  text-align: center;
  page-break-after: avoid;
}

body.titlepage .premise {
  font-style: italic;
  font-size: 0.95em;
  text-indent: 0;
  text-align: center;
  margin: 0.75em 1em 0 1em;
  line-height: 1.45;
}

body.titlepage .genre {
  font-style: normal;
  font-size: 0.75em;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  text-indent: 0;
  text-align: center;
  margin-top: 2.5em;
  opacity: 0.75;
}

body.titlepage .byline {
  font-size: 0.9em;
  text-indent: 0;
  text-align: center;
  margin-top: 3em;
  letter-spacing: 0.04em;
}

/* —— Chapters —— */
body.chapter {
  padding: 0 0 1em 0;
}

.ch-open {
  margin: 2.5em 0 2em 0;
  text-align: center;
  page-break-after: avoid;
  -webkit-column-break-after: avoid;
  break-after: avoid;
}

.ch-kicker {
  display: block;
  font-size: 0.8em;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  text-indent: 0;
  text-align: center;
  margin: 0 0 0.6em 0;
  font-weight: normal;
}

.ch-title {
  display: block;
  font-size: 1.35em;
  font-weight: normal;
  letter-spacing: 0.03em;
  text-indent: 0;
  text-align: center;
  margin: 0;
  line-height: 1.3;
}

/* Body copy sits a beat after the opener */
.ch-open + p {
  margin-top: 0.25em;
}

/* TOC page */
body.toc {
  padding: 2em 1.2em;
}
body.toc h1 {
  font-size: 1.2em;
  font-weight: normal;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  text-align: center;
  margin: 0 0 1.75em 0;
}
body.toc ol {
  list-style: none;
  padding: 0;
  margin: 0;
}
body.toc li {
  margin: 0 0 0.85em 0;
  text-align: left;
  line-height: 1.4;
}
body.toc a {
  text-decoration: none;
  color: inherit;
}

/* Cover (SVG wrapper page) */
body.cover {
  margin: 0;
  padding: 0;
  text-align: center;
}
body.cover svg {
  width: 100%;
  height: auto;
  max-height: 100%;
}
""".strip()


def _epub_wrap(title: str, body_class: str, body_inner: str, css_href: str = "style.css") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
  "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="en">
<head>
  <meta http-equiv="Content-Type" content="application/xhtml+xml; charset=utf-8"/>
  <title>{_xhtml_escape_text(title)}</title>
  <link rel="stylesheet" type="text/css" href="{css_href}"/>
</head>
<body class="{body_class}">
{body_inner}
</body>
</html>
"""


def _epub_body_from_blocks(blocks: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    first_p = True
    for kind, text in blocks:
        if kind == "break":
            parts.append('<p class="scenebreak">* * *</p>')
            first_p = True
            continue
        cls = ' class="first"' if first_p else ""
        parts.append(f"<p{cls}>{_xhtml_escape_text(text)}</p>")
        first_p = False
    return "\n".join(parts) if parts else '<p class="first"><em>(empty)</em></p>'


def _epub_cover_svg(title: str, premise: str = "") -> str:
    """Simple portrait cover — 2:3 ratio, dark paper + gold type."""
    t = _xhtml_escape_text(title)
    # Rough wrap for long titles
    words = title.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if len(trial) > 18 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    if not lines:
        lines = [title or "Untitled"]
    lines = lines[:5]
    start_y = 420 - (len(lines) - 1) * 28
    text_nodes = []
    for i, line in enumerate(lines):
        text_nodes.append(
            f'<text x="300" y="{start_y + i * 56}" text-anchor="middle" '
            f'font-family="Georgia, serif" font-size="44" fill="#e8d5a3">{_xhtml_escape_text(line)}</text>'
        )
    sub = ""
    if premise:
        short = premise if len(premise) < 90 else premise[:87] + "…"
        sub = (
            f'<text x="300" y="620" text-anchor="middle" font-family="Georgia, serif" '
            f'font-size="18" font-style="italic" fill="#b8ae9a">{_xhtml_escape_text(short)}</text>'
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="900" viewBox="0 0 600 900" version="1.1">
  <rect width="600" height="900" fill="#16140f"/>
  <rect x="28" y="28" width="544" height="844" fill="none" stroke="#c4a35a" stroke-width="2" opacity="0.55"/>
  <rect x="40" y="40" width="520" height="820" fill="none" stroke="#c4a35a" stroke-width="0.75" opacity="0.3"/>
  <line x1="120" y1="320" x2="480" y2="320" stroke="#c4a35a" stroke-width="1" opacity="0.4"/>
  {"".join(text_nodes)}
  <line x1="120" y1="560" x2="480" y2="560" stroke="#c4a35a" stroke-width="1" opacity="0.4"/>
  {sub}
  <text x="300" y="820" text-anchor="middle" font-family="Georgia, serif" font-size="14"
        letter-spacing="4" fill="#7f725c">GHOSTWRITER</text>
</svg>
"""


def _to_epub(project: Project) -> bytes:
    """Novel-oriented reflowable EPUB 3.0 (with NCX) via stdlib zip."""
    from datetime import datetime, timezone

    title = project.title or "Untitled"
    book_id = f"urn:ghostwriter:{_slug(title)}"
    chapters = _sorted_chapters(project)
    lang = "en"
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    first_chap_href = "chap_001.xhtml" if chapters else "title.xhtml"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
""",
        )

        zf.writestr("OEBPS/style.css", _epub_css() + "\n")
        cover_svg = _epub_cover_svg(title, project.premise or project.description or "")
        zf.writestr("OEBPS/cover.svg", cover_svg)

        cover_inner = re.sub(r"<\?xml[^?]*\?>\s*", "", cover_svg)
        zf.writestr(
            "OEBPS/cover.xhtml",
            _epub_wrap(f"Cover — {title}", "cover", cover_inner),
        )

        tp_bits = [f"  <h1>{_xhtml_escape_text(title)}</h1>"]
        if project.premise:
            tp_bits.append(
                f'  <p class="premise">{_xhtml_escape_text(project.premise)}</p>'
            )
        if project.genre:
            tp_bits.append(
                f'  <p class="genre">{_xhtml_escape_text(project.genre)}</p>'
            )
        zf.writestr(
            "OEBPS/title.xhtml",
            _epub_wrap(title, "titlepage", "\n".join(tp_bits)),
        )

        toc_items = []
        for i, ch in enumerate(chapters, start=1):
            ct = ch.title or f"Chapter {i}"
            toc_items.append(
                f'    <li><a href="chap_{i:03d}.xhtml">{_xhtml_escape_text(ct)}</a></li>'
            )
        zf.writestr(
            "OEBPS/toc.xhtml",
            _epub_wrap(
                "Contents",
                "toc",
                "  <h1>Contents</h1>\n  <ol>\n"
                + ("\n".join(toc_items) if toc_items else "    <li><em>No chapters</em></li>")
                + "\n  </ol>",
            ),
        )

        manifest_items = [
            '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
            '<item id="css" href="style.css" media-type="text/css"/>',
            '<item id="cover-img" href="cover.svg" media-type="image/svg+xml" properties="cover-image"/>',
            '<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>',
            '<item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>',
            '<item id="tocpage" href="toc.xhtml" media-type="application/xhtml+xml"/>',
        ]
        spine_items = [
            '<itemref idref="cover" linear="no"/>',
            '<itemref idref="title"/>',
            '<itemref idref="tocpage"/>',
        ]
        nav_points = [
            """<navPoint id="nav-title" playOrder="1">
  <navLabel><text>Title Page</text></navLabel>
  <content src="title.xhtml"/>
</navPoint>""",
            """<navPoint id="nav-toc" playOrder="2">
  <navLabel><text>Contents</text></navLabel>
  <content src="toc.xhtml"/>
</navPoint>""",
        ]
        nav_ol = [
            '      <li><a href="title.xhtml">Title Page</a></li>',
            '      <li><a href="toc.xhtml">Contents</a></li>',
        ]
        play = 3

        for i, ch in enumerate(chapters, start=1):
            ct = ch.title or f"Chapter {i}"
            kicker, sub = _chapter_heading_parts(ct, i)
            if sub:
                opener = (
                    f'  <div class="ch-open">\n'
                    f'    <p class="ch-kicker">{_xhtml_escape_text(kicker)}</p>\n'
                    f'    <h1 class="ch-title">{_xhtml_escape_text(sub)}</h1>\n'
                    f"  </div>"
                )
            else:
                opener = (
                    f'  <div class="ch-open">\n'
                    f'    <h1 class="ch-title">{_xhtml_escape_text(kicker)}</h1>\n'
                    f"  </div>"
                )
            body = _epub_body_from_blocks(_novel_blocks(ch.content or ""))
            href = f"chap_{i:03d}.xhtml"
            zf.writestr(
                f"OEBPS/{href}",
                _epub_wrap(ct, "chapter", opener + "\n" + body),
            )
            mid = f"chap{i}"
            manifest_items.append(
                f'<item id="{mid}" href="{href}" media-type="application/xhtml+xml"/>'
            )
            spine_items.append(f'<itemref idref="{mid}"/>')
            nav_points.append(
                f"""<navPoint id="nav{i}" playOrder="{play}">
  <navLabel><text>{_xhtml_escape_text(ct)}</text></navLabel>
  <content src="{href}"/>
</navPoint>"""
            )
            nav_ol.append(
                f'      <li><a href="{href}">{_xhtml_escape_text(ct)}</a></li>'
            )
            play += 1

        zf.writestr(
            "OEBPS/nav.xhtml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang}" lang="{lang}">
<head>
  <meta charset="utf-8"/>
  <title>Navigation</title>
  <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>Contents</h1>
    <ol>
{chr(10).join(nav_ol)}
    </ol>
  </nav>
  <nav epub:type="landmarks" id="landmarks" hidden="hidden">
    <ol>
      <li><a epub:type="cover" href="cover.xhtml">Cover</a></li>
      <li><a epub:type="titlepage" href="title.xhtml">Title Page</a></li>
      <li><a epub:type="toc" href="toc.xhtml">Contents</a></li>
      <li><a epub:type="bodymatter" href="{first_chap_href}">Start</a></li>
    </ol>
  </nav>
</body>
</html>
""",
        )

        desc = project.description or project.premise or ""
        zf.writestr(
            "OEBPS/content.opf",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0"
         prefix="rendition: http://www.idpf.org/vocab/rendition/#">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{_xhtml_escape_text(title)}</dc:title>
    <dc:language>{lang}</dc:language>
    <dc:identifier id="BookId">{_xhtml_escape_text(book_id)}</dc:identifier>
    <dc:publisher>GhostWriter</dc:publisher>
    {f'<dc:description>{_xhtml_escape_text(desc)}</dc:description>' if desc else ''}
    <meta name="cover" content="cover-img"/>
    <meta property="rendition:layout">reflowable</meta>
    <meta property="rendition:orientation">auto</meta>
    <meta property="rendition:spread">none</meta>
    <meta property="dcterms:modified">{modified}</meta>
  </metadata>
  <manifest>
{chr(10).join("    " + m for m in manifest_items)}
  </manifest>
  <spine toc="ncx" page-progression-direction="ltr">
{chr(10).join("    " + s for s in spine_items)}
  </spine>
  <guide>
    <reference type="cover" title="Cover" href="cover.xhtml"/>
    <reference type="title-page" title="Title Page" href="title.xhtml"/>
    <reference type="toc" title="Contents" href="toc.xhtml"/>
    <reference type="text" title="Start" href="{first_chap_href}"/>
  </guide>
</package>
""",
        )

        zf.writestr(
            "OEBPS/toc.ncx",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN"
  "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="{_xhtml_escape_text(book_id)}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{_xhtml_escape_text(title)}</text></docTitle>
  <navMap>
{chr(10).join(nav_points)}
  </navMap>
</ncx>
""",
        )

    return buf.getvalue()


SUPPORTED_FORMATS = ("markdown", "txt", "html", "docx", "epub", "json")
