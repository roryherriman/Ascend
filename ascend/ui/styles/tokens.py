"""Design tokens: the single source of truth for Ascend's visual language.

Nothing outside this file should hardcode a color, spacing value, radius,
font size, or control height - reference ``DARK_TOKENS`` (or a future
``LIGHT_TOKENS``) instead, so the whole app can be retheme'd from one place.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Palette:
    # Backgrounds - three surface levels + sidebar/app, deliberately close in
    # value so grouping reads from contrast, not from a border around everything.
    bg_app: str             # main window background - deep navy-charcoal
    bg_sidebar: str          # sidebar - slightly darker than app background
    bg_secondary: str         # page container - very subtle contrast vs. app bg
    bg_card: str                # primary surface (standard panels)
    bg_card_elevated: str         # elevated surface (emphasized panels: Analyze, Profile)
    bg_card_hover: str              # hover surface
    bg_input: str
    bg_input_focus: str
    bg_overlay: str                  # loading overlay / scrim

    # Accent - Ascend blue-violet identity
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_muted: str       # low-emphasis accent background (badges, subtle highlights)
    secondary_accent: str    # violet - paired with accent for gradients/dual-series charts
    accent_cyan: str          # tertiary accent for chart series / info highlights

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
    text_muted: str
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
    lg: int = 10
    xl: int = 14
    pill: int = 999


@dataclass(frozen=True)
class TypeScale:
    """(pixel size, weight) pairs for each text role."""
    app_brand: tuple[int, int] = (20, 600)
    page_title: tuple[int, int] = (24, 600)
    page_subtitle: tuple[int, int] = (12, 400)
    panel_title: tuple[int, int] = (14, 600)
    metric_value: tuple[int, int] = (24, 600)
    kpi_label: tuple[int, int] = (10, 700)
    body: tuple[int, int] = (13, 400)
    secondary: tuple[int, int] = (12, 400)
    caption: tuple[int, int] = (11, 500)
    table_text: tuple[int, int] = (13, 400)
    badge_text: tuple[int, int] = (11, 700)

    # Backwards-compatible aliases used by earlier Phase 1 code.
    @property
    def app_title(self) -> tuple[int, int]:
        return self.app_brand

    @property
    def section_title(self) -> tuple[int, int]:
        return self.kpi_label

    @property
    def card_title(self) -> tuple[int, int]:
        return self.panel_title


@dataclass(frozen=True)
class ControlSizes:
    input_height: int = 30
    button_height: int = 30
    nav_item_height: int = 32
    table_row_height: int = 32
    icon_sm: int = 14
    icon_md: int = 18
    icon_lg: int = 24
    sidebar_width: int = 204
    kpi_chip_height: int = 56


@dataclass(frozen=True)
class Tokens:
    palette: Palette
    spacing: Spacing = field(default_factory=Spacing)
    radii: Radii = field(default_factory=Radii)
    type_scale: TypeScale = field(default_factory=TypeScale)
    control: ControlSizes = field(default_factory=ControlSizes)
    font_family: str = '"Segoe UI", "Cantarell", sans-serif'


DARK_PALETTE = Palette(
    bg_app="#070B14",
    bg_sidebar="#090E18",
    bg_secondary="#0A1220",
    bg_card="#0E1626",
    bg_card_elevated="#131D30",
    bg_card_hover="#18243A",
    bg_input="#0B1220",
    bg_input_focus="#131D30",
    bg_overlay="rgba(4, 6, 12, 0.72)",
    accent="#5B7CFF",
    accent_hover="#7B95FF",
    accent_pressed="#3F5FE0",
    accent_muted="#1B2547",
    secondary_accent="#7C5CFF",
    accent_cyan="#38BDF8",
    success="#34D399",
    success_muted="#0F3328",
    warning="#FBBF24",
    warning_muted="#3A2E10",
    error="#F87171",
    error_muted="#3A1C1C",
    info="#38BDF8",
    info_muted="#0E2F3D",
    text_primary="#F8FAFC",
    text_secondary="#A8B3C7",
    text_muted="#6B7890",
    text_disabled="#4B5568",
    text_on_accent="#FFFFFF",
    border="#22304A",
    border_strong="#324566",
    focus_ring="#5B7CFF",
    scrollbar="#22304A",
)

DARK_TOKENS = Tokens(palette=DARK_PALETTE)
