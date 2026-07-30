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


def _paragraphs(text: str) -> list[str]:
    if not (text or "").strip():
        return []
    # Split on blank lines; keep single newlines as soft breaks inside a block
    blocks = re.split(r"\n\s*\n", text.strip())
    return [b.strip() for b in blocks if b.strip()]


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


def _to_html(project: Project) -> str:
    title = html.escape(project.title or "Untitled")
    meta_bits = []
    if project.premise:
        meta_bits.append(f"<p class='premise'><em>{html.escape(project.premise)}</em></p>")
    if project.genre:
        meta_bits.append(f"<p class='genre'>{html.escape(project.genre)}</p>")

    chapters_html = []
    for i, ch in enumerate(_sorted_chapters(project), start=1):
        ct = html.escape(ch.title or f"Chapter {i}")
        paras = "".join(
            f"<p>{html.escape(p).replace(chr(10), '<br/>')}</p>"
            for p in _paragraphs(ch.content or "")
        ) or "<p><em>(empty)</em></p>"
        chapters_html.append(
            f"<section class='chapter' id='ch-{i}'>\n"
            f"<h2>{ct}</h2>\n{paras}\n</section>"
        )

    cast = ""
    if project.characters:
        items = "".join(
            f"<li><strong>{html.escape(c.name)}</strong>"
            + (f" — {html.escape(c.role)}" if c.role else "")
            + "</li>"
            for c in project.characters
        )
        cast = f"<section class='cast'><h2>Dramatis Personae</h2><ul>{items}</ul></section>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title}</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{
      max-width: 42rem; margin: 2rem auto; padding: 0 1.25rem 4rem;
      font-family: "Literata", "Palatino Linotype", Palatino, Georgia, serif;
      font-size: 1.125rem; line-height: 1.75; color: #1a1814;
      background: #f7f4ec;
    }}
    @media (prefers-color-scheme: dark) {{
      body {{ background: #16140f; color: #ebe8e0; }}
      h1, h2 {{ color: #e8d5a3; }}
      .meta {{ color: #9a8c74; }}
    }}
    h1 {{ font-weight: 600; font-size: 2rem; margin-bottom: 0.25rem; }}
    h2 {{ font-weight: 600; font-size: 1.35rem; margin-top: 2.5rem;
         page-break-before: always; break-before: page; }}
    .chapter:first-of-type h2 {{ page-break-before: auto; break-before: auto; }}
    .meta {{ color: #665b4a; font-size: 0.95rem; margin-bottom: 2rem; }}
    .premise {{ font-size: 1.05rem; }}
    p {{ margin: 0 0 1em; text-indent: 1.5em; }}
    .chapter h2 + p, .cast p {{ text-indent: 0; }}
    ul {{ padding-left: 1.25rem; }}
    @media print {{
      body {{ background: white; color: black; margin: 0; max-width: none; }}
      h2 {{ page-break-before: always; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    <div class="meta">{"".join(meta_bits)}</div>
  </header>
  {cast}
  {"".join(chapters_html)}
  <footer class="meta" style="margin-top:3rem;font-size:0.8rem">
    Exported from GhostWriter
  </footer>
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


def _to_epub(project: Project) -> bytes:
    """Minimal EPUB 2.0 via stdlib zip — no ebooklib required."""
    title = project.title or "Untitled"
    book_id = f"ghostwriter-{_slug(title)}"
    chapters = _sorted_chapters(project)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Uncompressed mimetype first (EPUB spec)
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

        manifest_items = [
            '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
            '<item id="css" href="style.css" media-type="text/css"/>',
        ]
        spine_items = []
        nav_points = []

        css = """
body { font-family: Georgia, serif; line-height: 1.6; margin: 1em; }
h1 { font-size: 1.6em; text-align: center; margin: 2em 0 1em; }
h2 { font-size: 1.3em; margin: 1.5em 0 1em; page-break-before: always; }
p { margin: 0 0 0.9em; text-indent: 1.2em; }
h1 + p, h2 + p { text-indent: 0; }
.premise { font-style: italic; text-align: center; text-indent: 0; }
"""
        zf.writestr("OEBPS/style.css", css.strip() + "\n")

        # Title page
        title_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
  "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head><title>{xml_escape(title)}</title>
<link rel="stylesheet" type="text/css" href="style.css"/></head>
<body>
  <h1>{xml_escape(title)}</h1>
  {f'<p class="premise">{xml_escape(project.premise)}</p>' if project.premise else ''}
  {f'<p class="premise">{xml_escape(project.genre)}</p>' if project.genre else ''}
</body></html>
"""
        zf.writestr("OEBPS/title.xhtml", title_xhtml)
        manifest_items.append(
            '<item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>'
        )
        spine_items.append('<itemref idref="title"/>')
        nav_points.append(
            """<navPoint id="nav0" playOrder="1">
  <navLabel><text>Title</text></navLabel>
  <content src="title.xhtml"/>
</navPoint>"""
        )

        for i, ch in enumerate(chapters, start=1):
            ct = ch.title or f"Chapter {i}"
            paras = _paragraphs(ch.content or "")
            body = (
                "".join(
                    f"<p>{xml_escape(p).replace(chr(10), '<br/>')}</p>" for p in paras
                )
                or "<p><em>(empty)</em></p>"
            )
            xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
  "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head><title>{xml_escape(ct)}</title>
<link rel="stylesheet" type="text/css" href="style.css"/></head>
<body>
  <h2>{xml_escape(ct)}</h2>
  {body}
</body></html>
"""
            href = f"chap_{i:03d}.xhtml"
            zf.writestr(f"OEBPS/{href}", xhtml)
            mid = f"chap{i}"
            manifest_items.append(
                f'<item id="{mid}" href="{href}" media-type="application/xhtml+xml"/>'
            )
            spine_items.append(f'<itemref idref="{mid}"/>')
            nav_points.append(
                f"""<navPoint id="nav{i}" playOrder="{i + 1}">
  <navLabel><text>{xml_escape(ct)}</text></navLabel>
  <content src="{href}"/>
</navPoint>"""
            )

        opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>{xml_escape(title)}</dc:title>
    <dc:language>en</dc:language>
    <dc:identifier id="BookId">{xml_escape(book_id)}</dc:identifier>
    <dc:publisher>GhostWriter</dc:publisher>
    {f'<dc:description>{xml_escape(project.description or project.premise or "")}</dc:description>' if (project.description or project.premise) else ''}
  </metadata>
  <manifest>
    {chr(10).join(manifest_items)}
  </manifest>
  <spine toc="ncx">
    {chr(10).join(spine_items)}
  </spine>
</package>
"""
        zf.writestr("OEBPS/content.opf", opf)

        ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN"
  "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="{xml_escape(book_id)}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{xml_escape(title)}</text></docTitle>
  <navMap>
    {chr(10).join(nav_points)}
  </navMap>
</ncx>
"""
        zf.writestr("OEBPS/toc.ncx", ncx)

    return buf.getvalue()


SUPPORTED_FORMATS = ("markdown", "txt", "html", "docx", "epub", "json")
