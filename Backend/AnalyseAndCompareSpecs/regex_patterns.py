"""Shared structural regexes for specification quality analysis.

These patterns describe document syntax, not product-specific vocabulary. Keeping
them separate from scoring logic makes changes reviewable and prevents large regex
literals from obscuring the calculations in ``quality_check.py``.
"""

import re

SECTION_REGEX = re.compile(
    r"^\s*(?:section\s+)?([A-Z]?\d+(?:[.-]\d+)*)\b",
    re.IGNORECASE,
)
VALID_VPLAN_SECTION_REGEX = re.compile(r"^[A-Z]?\d+(?:[.-]\d+)*$", re.IGNORECASE)
TABLE_REF_REGEX = re.compile(
    r"\bTable\s+([A-Z]?\d+(?:[.-]\d+)*)\b",
    re.IGNORECASE,
)
SECTION_REF_REGEX = re.compile(
    r"\bSection\s+([A-Z]?\d+(?:[.-]\d+)*)\b",
    re.IGNORECASE,
)
REQUIREMENT_REGEX = re.compile(
    r"\b(?:shall|must|required\s+to|may\s+not|is\s+prohibited)\b",
    re.IGNORECASE,
)
NOTE_REGEX = re.compile(r"^\s*(?:note|warning|caution)\s*[:.-]", re.IGNORECASE)
ACRONYM_REGEX = re.compile(r"\b([A-Z][A-Z0-9]{1,})\s*[-:()]\s*([^\n]+)")
