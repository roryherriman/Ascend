"""Ascend's theme system: centralized tokens + modular QSS builders.

``tokens.py`` holds the single source of truth for colors, spacing, radii,
typography, elevation, and control sizing. Each other module in this package
returns a QSS *fragment* for one category of widgets (buttons, inputs,
tables, ...); ``ascend/theme.py`` assembles them into the final stylesheet.
Nothing here hardcodes a color or size outside of ``tokens.py``.
"""
from ascend.ui.styles.tokens import DARK_TOKENS, Tokens

__all__ = ["Tokens", "DARK_TOKENS"]
