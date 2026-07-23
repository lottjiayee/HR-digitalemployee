"""Test-only PDF fixture builders -- real PDF bytes for exercising pdf_text.py and the gateway's
unparseable-file routing without needing external binary fixture files on disk."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfWriter


def build_multi_page_pdf_with_text(pages: list[list[str]]) -> bytes:
    """A real, valid multi-page PDF whose text layer, page by page, reads back as each page's own
    `lines` joined by newlines -- exercises pdf_text.py's page-by-page concatenation
    (`"\\n".join(page.extract_text() ... for page in reader.pages)`), which a single-page PDF can
    never reach."""

    def _content_stream(lines: list[str]) -> bytes:
        content_lines = []
        y = 720
        for line in lines:
            escaped = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
            content_lines.append(f"BT /F1 12 Tf 72 {y} Td ({escaped}) Tj ET")
            y -= 20
        return "\n".join(content_lines).encode("latin-1")

    font_obj_num = 3
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",  # /Pages -- filled in below once every page object's number is known
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    page_obj_nums: list[int] = []
    for lines in pages:
        content = _content_stream(lines)
        page_obj_num = len(objects) + 1
        content_obj_num = page_obj_num + 1
        page_obj_nums.append(page_obj_num)
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 "
            + str(font_obj_num).encode()
            + b" 0 R >> >> /MediaBox [0 0 612 792] /Contents "
            + str(content_obj_num).encode()
            + b" 0 R >>"
        )
        objects.append(
            b"<< /Length "
            + str(len(content)).encode()
            + b" >>\nstream\n"
            + content
            + b"\nendstream"
        )

    kids = " ".join(f"{num} 0 R" for num in page_obj_nums)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode()

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_offset = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_offset).encode() + b"\n%%EOF"

    return bytes(out)


def build_pdf_with_text(lines: list[str]) -> bytes:
    """A real, valid single-page PDF whose text layer reads back as `lines` joined by newlines."""
    return build_multi_page_pdf_with_text([lines])


def build_blank_pdf() -> bytes:
    """A real, valid single-page PDF with no text layer -- stands in for a scanned/image-only
    PDF."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def build_encrypted_pdf(password: str = "secret") -> bytes:
    """A real, valid single-page PDF that requires a password to open."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt(user_password=password)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


CORRUPTED_PDF_BYTES = b"%PDF-1.4\nthis claims to be a PDF but has no valid object/xref structure"
