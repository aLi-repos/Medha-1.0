"""Split documents into overlapping text chunks for embedding."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DocumentChunk:
    source_name: str
    chunk_index: int
    text: str
    start_char: int
    end_char: int
    classification: str = "internal"


def chunk_text(
    text: str,
    source_name: str,
    chunk_size: int = 512,
    overlap: int = 64,
    classification: str = "internal",
) -> list[DocumentChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")

    chunks: list[DocumentChunk] = []
    start = 0
    index = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk_text_str = text[start:end]
        if chunk_text_str.strip():
            chunks.append(DocumentChunk(
                source_name=source_name,
                chunk_index=index,
                text=chunk_text_str,
                start_char=start,
                end_char=end,
                classification=classification,
            ))
            index += 1
        if end == len(text):
            break
        start += chunk_size - overlap

    return chunks
