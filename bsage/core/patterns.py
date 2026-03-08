"""Shared regex patterns used across BSage modules."""

from __future__ import annotations

import re

# Wiki-link extraction: [[target]] or [[target|display text]]
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")

# Matches the ``related:`` key in all supported YAML formats:
#   - Block list (indented):     related:\n  - item
#   - Block list (no-indent):    related:\n- item
#   - Inline array:              related: ['[[a]]', '[[b]]']
#   - Scalar:                    related: value
# Uses [^\n]* to match the full first line (avoids premature stop on ``]``
# chars inside wikilinks like ``[[note]]``).
# The continuation lines pattern uses ``[ \t]*-`` (zero or more spaces then
# dash) to handle both indented and unindented YAML list items.
RELATED_RE = re.compile(
    r"^related:[ \t]*(?:\[[^\n]*\]|[^\n]*)(?:\n[ \t]*-[^\n]*)*\n?",
    re.MULTILINE,
)
