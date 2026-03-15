# SPDX-License-Identifier: Apache-2.0
"""Document text extraction helpers for workspace imports."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree


class DocumentParseError(ValueError):
    """Raised when a workspace document cannot be parsed."""


class DocumentParser:
    """Extract text from supported workspace document formats."""

    SUPPORTED_SUFFIXES = frozenset({".txt", ".md", ".srt", ".docx", ".pdf"})
    _DOCX_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    def extract_text(self, file_path: str) -> str:
        """Extract plain text from a supported document."""
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {path}")

        suffix = path.suffix.lower()
        if suffix not in self.SUPPORTED_SUFFIXES:
            raise DocumentParseError(f"Unsupported document format: {suffix or '<none>'}")

        if suffix in {".txt", ".md", ".srt"}:
            return path.read_text(encoding="utf-8")

        if suffix == ".docx":
            return self._extract_docx_text(path)

        return self._extract_pdf_text(path)

    def _extract_docx_text(self, path: Path) -> str:
        """Extract text from DOCX, preferring python-docx but falling back to XML parsing."""
        try:
            from docx import Document  # type: ignore

            document = Document(str(path))
            paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs]
            return "\n\n".join(text for text in paragraphs if text)
        except ImportError:
            return self._extract_docx_via_zip(path)

    def _extract_docx_via_zip(self, path: Path) -> str:
        """Extract DOCX text directly from OOXML markup."""
        with zipfile.ZipFile(path) as archive:
            with archive.open("word/document.xml") as document_xml:
                root = ElementTree.fromstring(document_xml.read())

        paragraphs = []
        for paragraph in root.findall(".//w:p", self._DOCX_NAMESPACE):
            runs = [
                node.text
                for node in paragraph.findall(".//w:t", self._DOCX_NAMESPACE)
                if node.text
            ]
            text = "".join(runs).strip()
            if text:
                paragraphs.append(text)
        return "\n\n".join(paragraphs)

    def _extract_pdf_text(self, path: Path) -> str:
        """Extract text from PDF with pypdf."""
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on optional runtime
            raise DocumentParseError(
                "PDF parsing requires the 'pypdf' dependency to be installed."
            ) from exc

        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(text)
        return "\n\n".join(pages)
