"""Design tokens: the single source of truth for Ascend's visual language.

Nothing outside this file should hardcode a color, spacing value, radius,
font size, or control height - reference ``DARK_TOKENS`` (or a future
``LIGHT_TOKENS``) instead, so the whole app can be retheme'd from one place.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Palette:
    # Backgrounds
    bg_app: str          # main window background - near-black charcoal
    bg_secondary: str     # secondary panels / scroll areas - dark slate
    bg_sidebar: str        # sidebar - dark graphite
    bg_card: str            # elevated card background
    bg_card_hover: str
    bg_input: str
    bg_input_focus: str
    bg_overlay: str         # loading overlay / scrim

    # Accent
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_muted: str       # low-emphasis accent background (badges, subtle highlights)

    # Semantic
    success: str
    success_muted: str
    warning: str
    warning_muted: str
    error: str
    error_muted: str
    info: str
    info_muted: str

    # Text
    text_primary: str
    text_secondary: str
    text_disabled: str
    text_on_accent: str

    # Structure
    border: str
    border_strong: str
    focus_ring: str
    scrollbar: str


@dataclass(frozen=True)
class Spacing:
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32


@dataclass(frozen=True)
class Radii:
    sm: int = 4
    md: int = 8
    lg: int = 12
    xl: int = 16
    pill: int = 999


@dataclass(frozen=True)
class TypeScale:
    """(pixel size, weight) pairs for each text role."""
    app_title: tuple[int, int] = (19, 700)
    page_title: tuple[int, int] = (22, 700)
    section_title: tuple[int, int] = (12, 700)
    card_title: tuple[int, int] = (13, 600)
    metric_value: tuple[int, int] = (28, 700)
    body: tuple[int, int] = (13, 400)
    secondary: tuple[int, int] = (12, 400)
    caption: tuple[int, int] = (11, 500)
    table_text: tuple[int, int] = (13, 400)
    badge_text: tuple[int, int] = (11, 700)


@dataclass(frozen=True)
class ControlSizes:
    input_height: int = 32
    button_height: int = 34
    nav_item_height: int = 38
    table_row_height: int = 34
    icon_sm: int = 14
    icon_md: int = 18
    icon_lg: int = 24


@dataclass(frozen=True)
class Tokens:
    palette: Palette
    spacing: Spacing = field(default_factory=Spacing)
    radii: Radii = field(default_factory=Radii)
    type_scale: TypeScale = field(default_factory=TypeScale)
    control: ControlSizes = field(default_factory=ControlSizes)
    font_family: str = '"Segoe UI", "Cantarell", sans-serif'


DARK_PALETTE = Palette(
    bg_app="#111214",
    bg_secondary="#17181c",
    bg_sidebar="#15161a",
    bg_card="#1c1e23",
    bg_card_hover="#23262c",
    bg_input="#1a1c20",
    bg_input_focus="#20232a",
    bg_overlay="rgba(10, 11, 13, 0.72)",
    accent="#5B8DEF",
    accent_hover="#7AA2F2",
    accent_pressed="#4874C9",
    accent_muted="#25314a",
    success="#3ABF87",
    success_muted="#173226",
    warning="#E3A73E",
    warning_muted="#3a2d14",
    error="#E5555F",
    error_muted="#3a1c1f",
    info="#4AB8D8",
    info_muted="#123138",
    text_primary="#F1F2F4",
    text_secondary="#9599A2",
    text_disabled="#5B5E66",
    text_on_accent="#FFFFFF",
    border="#2A2D33",
    border_strong="#3A3D45",
    focus_ring="#5B8DEF",
    scrollbar="#33363d",
)

DARK_TOKENS = Tokens(palette=DARK_PALETTE)
