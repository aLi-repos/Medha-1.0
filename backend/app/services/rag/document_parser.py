"""Text extraction from plain-text and Markdown documents."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class ParsedDocument:
    source_name: str
    text: str
    classification: str = "internal"


def parse_text_file(path: str, source_name: str | None = None, classification: str = "internal") -> ParsedDocument:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Document not found: {path}")
    name = source_name or os.path.basename(path)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    return ParsedDocument(source_name=name, text=text, classification=classification)


def parse_text(text: str, source_name: str, classification: str = "internal") -> ParsedDocument:
    return ParsedDocument(source_name=source_name, text=text, classification=classification)
