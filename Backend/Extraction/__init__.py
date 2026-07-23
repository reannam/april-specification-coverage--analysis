"""Specification extraction domain.

The PDF parser is imported only when extraction is requested. This keeps the
main API available when the optional native PDF dependency is not installed.
"""

from typing import Any

from Backend.Extraction.requirements import write_requirements_file


def parse_pdf(*args: Any, **kwargs: Any) -> dict:
    """Load and run the PDF parser without making it an API-startup dependency."""

    from Backend.Extraction.extractor import parse_pdf as parse_pdf_impl

    return parse_pdf_impl(*args, **kwargs)


__all__ = ["parse_pdf", "write_requirements_file"]
