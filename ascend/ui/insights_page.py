"""Insights page - explainable score breakdown for the primary tracked character.

Shows the ScoreBreakdown produced by the scoring engine: overall score,
classification, confidence, coverage, and a per-category table with every
MetricEvidence entry. Categories that are UNAVAILABLE show their candidate
metrics as reference rows so the user can see what will be computable when
the required data arrives.

The scoring engine is called on every reload() so the view stays current
after each sync without a separate refresh button.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ascend.analysis.scoring_engine import compute_score
from ascend.analysis.scoring_models import CategoryScore, CategoryStatus, Classification, ConfidenceLevel
from ascend.data.database import Database
from ascend.data.repositories import CharacterRepository
from ascend.theme import PALETTE
from ascend.ui.components import AscendEmptyState
from ascend.ui.widgets import make_badge

# Tone map for classification -> badge tone
_CLASSIFICATION_TONE: dict[str, str] = {
    Classification.STANDOUT: "success",
    Classification.STRONG: "success",
    Classification.ABOVE_AVERAGE: "info",
    Classification.AVERAGE: "neutral",
    Classification.BELOW_AVERAGE: "warning",
    Classification.SIGNIFICANT_CONCERNS: "error",
    Classification.INSUFFICIENT_DATA: "neutral",
}

_CONFIDENCE_TONE: dict[str, str] = {
    ConfidenceLevel.HIGH: "success",
    ConfidenceLevel.MODERATE: "info",
    ConfidenceLevel.LOW: "warning",
    ConfidenceLevel.INSUFFICIENT_DATA: "neutral",
}

_STATUS_TONE: dict[str, str] = {
    CategoryStatus.AVAILABLE: "success",
    CategoryStatus.PARTIAL: "warning",
    CategoryStatus.UNAVAILABLE: "neutral",
}

_CLASSIFICATION_LABELS: dict[str, str] = {
    Classification.STANDOUT: "Standout",
    Classification.STRONG: "Strong",
    Classification.ABOVE_AVERAGE: "Above Average",
    Classification.AVERAGE: "Average",
    Classification.BELOW_AVERAGE: "Below Average",
    Classification.SIGNIFICANT_CONCERNS: "Significant Concerns",
    Classification.INSUFFICIENT_DATA: "Insufficient Data",
}

_CONFIDENCE_LABELS: dict[str, str] = {
    ConfidenceLevel.HIGH: "High",
    ConfidenceLevel.MODERATE: "Moderate",
    ConfidenceLevel.LOW: "Low",
    ConfidenceLevel.INSUFFICIENT_DATA: "Insufficient Data",
}

_METRIC_COLS = [
    ("Metric", 3), ("Raw", 1), ("Norm", 1), ("Baseline", 2),
    ("Conf x", 1), ("Size x", 1), ("Prog x", 1), ("Contrib", 1), ("Note", 3),
]


def _metric_col_header() -> QFrame:
    row = QFrame()
    row.setStyleSheet(
        f"background: {PALETTE.bg_card}; border-bottom: 1px solid {PALETTE.border};"
    )
    layout = QHBoxLayout(row)
    layout.setContentsMargins(10, 4, 10, 4)
    layout.setSpacing(6)
    for text, stretch in _METRIC_COLS:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 0.4px; color: {PALETTE.text_muted};"
        )
        layout.addWidget(lbl, stretch)
    return row


def _metric_row(m, alt: bool) -> QFrame:
    row = QFrame()
    bg = PALETTE.bg_card_hover if alt else "transparent"
    row.setStyleSheet(f"background: {bg}; border-bottom: 1px solid {PALETTE.border};")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(10, 5, 10, 5)
    layout.setSpacing(6)

    cells = [
        (m.metric_name, 3),
        (str(m.raw_value) if m.raw_value is not None else "-", 1),
        (f"{m.normalized_value:.1f}" if m.normalized_value is not None else "-", 1),
        (m.comparison_baseline, 2),
        (f"{m.confidence_modifier:.2f}", 1),
        (f"{m.sample_size_modifier:.2f}", 1),
        (f"{m.progression_modifier:.2f}", 1),
        (f"{m.final_contribution:.1f}" if m.final_contribution is not None else "-", 1),
        (m.note, 3),
    ]
    for text, stretch in cells:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size: 11px; color: {PALETTE.text_secondary};")
        lbl.setWordWrap(True)
        layout.addWidget(lbl, stretch)
    return row


def _metric_rows_widget(category: CategoryScore) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(_metric_col_header())
    for i, m in enumerate(category.metrics):
        layout.addWidget(_metric_row(m, alt=i % 2 == 1))
    return container


def _category_card(category: CategoryScore) -> QFrame:
    card = QFrame()
    card.setProperty("class", "card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 12, 16, 12)
    layout.setSpacing(8)

    header = QHBoxLayout()
    name_label = QLabel(category.name.title())
    name_label.setStyleSheet("font-size: 13px; font-weight: 600;")
    header.addWidget(name_label)
    header.addWidget(make_badge(f"Weight: {category.weight}", tone="neutral"))
    header.addWidget(make_badge(category.status.value.upper(), tone=_STATUS_TONE[category.status]))
    if category.score is not None:
        header.addWidget(make_badge(f"Score: {category.score:.1f}", tone="info"))
    header.addStretch()
    layout.addLayout(header)

    if category.note:
        note_label = QLabel(category.note)
        note_label.setProperty("class", "muted")
        note_label.setWordWrap(True)
        note_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(note_label)

    if category.metrics:
        layout.addWidget(_metric_rows_widget(category))

    return card


class InsightsPage(QWidget):
    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        self._content = QWidget()
        scroll.setWidget(self._content)

        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(16)

        title = QLabel("Insights")
        title.setObjectName("pageTitle")
        self._layout.addWidget(title)

        subtitle = QLabel(
            "Score breakdown for the primary tracked character. "
            "Every metric links back to the raw data it was computed from. "
            "Categories whose underlying data isn't available yet are listed as "
            "Unavailable — they'll become active as more data is ingested."
        )
        subtitle.setProperty("class", "muted")
        subtitle.setWordWrap(True)
        self._layout.addWidget(subtitle)

        self._body = QVBoxLayout()
        self._body.setSpacing(12)
        self._layout.addLayout(self._body)
        self._layout.addStretch()

        self._empty_state: AscendEmptyState | None = None

        self.reload()

    def reload(self) -> None:
        self._clear_body()

        chars = CharacterRepository(self.db).list_all(enabled_only=True)
        if not chars:
            self._show_empty("No characters configured yet.",
                             "Add a character on the Characters page, then sync a report.")
            return

        character = chars[0]
        breakdown = compute_score(self.db, character.id)

        # -- Summary header card -------------------------------------------------
        summary_card = QFrame()
        summary_card.setProperty("class", "card")
        s_layout = QVBoxLayout(summary_card)
        s_layout.setContentsMargins(16, 14, 16, 14)
        s_layout.setSpacing(10)

        name_row = QHBoxLayout()
        char_label = QLabel(breakdown.character_name)
        char_label.setStyleSheet("font-size: 16px; font-weight: 700;")
        name_row.addWidget(char_label)
        name_row.addStretch()

        cls_label = _CLASSIFICATION_LABELS.get(breakdown.classification, breakdown.classification)
        name_row.addWidget(make_badge(cls_label, tone=_CLASSIFICATION_TONE.get(breakdown.classification, "neutral")))
        s_layout.addLayout(name_row)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(12)

        score_text = f"{breakdown.overall_score:.1f} / 100" if breakdown.overall_score is not None else "—"
        score_lbl = QLabel(f"Overall Score: {score_text}")
        score_lbl.setStyleSheet("font-size: 13px;")
        meta_row.addWidget(score_lbl)

        conf_label = _CONFIDENCE_LABELS.get(breakdown.confidence, breakdown.confidence)
        meta_row.addWidget(make_badge(f"Confidence: {conf_label}",
                                      tone=_CONFIDENCE_TONE.get(breakdown.confidence, "neutral")))
        meta_row.addWidget(make_badge(f"Pulls: {breakdown.sample_size}", tone="neutral"))
        meta_row.addWidget(make_badge(f"Coverage: {breakdown.coverage_ratio:.0%}", tone="neutral"))
        meta_row.addStretch()
        s_layout.addLayout(meta_row)

        for note in breakdown.notes:
            note_lbl = QLabel(note)
            note_lbl.setProperty("class", "muted")
            note_lbl.setWordWrap(True)
            note_lbl.setStyleSheet("font-size: 11px;")
            s_layout.addWidget(note_lbl)

        self._body.addWidget(summary_card)

        # -- Per-category cards (AVAILABLE/PARTIAL first, then UNAVAILABLE) -----
        categories = breakdown.categories
        ordered_keys = (
            [k for k, c in categories.items() if c.status != CategoryStatus.UNAVAILABLE] +
            [k for k, c in categories.items() if c.status == CategoryStatus.UNAVAILABLE]
        )
        for key in ordered_keys:
            self._body.addWidget(_category_card(categories[key]))

    # -------------------------------------------------------------------------

    def _clear_body(self) -> None:
        while self._body.count():
            item = self._body.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if self._empty_state is not None:
            self._empty_state.setVisible(False)

    def _show_empty(self, title: str, subtitle: str) -> None:
        if self._empty_state is None:
            self._empty_state = AscendEmptyState(
                title=title,
                description=subtitle,
                icon_name="insights",
            )
            self._layout.insertWidget(self._layout.count() - 1, self._empty_state)
        else:
            self._empty_state.setVisible(True)
