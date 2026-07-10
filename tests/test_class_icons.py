from ascend.ui.class_icons import CLASS_COLORS, UNKNOWN_COLOR, class_color, class_icon


def test_every_playable_class_has_an_icon_and_color(qtbot):
    for class_name in CLASS_COLORS:
        icon = class_icon(class_name)
        assert not icon.isNull(), f"missing icon for {class_name}"
        assert class_color(class_name) == CLASS_COLORS[class_name]


def test_all_thirteen_classes_are_mapped(qtbot):
    assert len(CLASS_COLORS) == 13


def test_unknown_class_gets_neutral_fallback(qtbot):
    icon = class_icon("Not A Real Class")
    assert not icon.isNull()
    assert class_color("Not A Real Class") == UNKNOWN_COLOR


def test_none_class_gets_neutral_fallback(qtbot):
    icon = class_icon(None)
    assert not icon.isNull()
    assert class_color(None) == UNKNOWN_COLOR


def test_class_name_is_case_and_whitespace_tolerant(qtbot):
    assert class_color("  Mage  ") == CLASS_COLORS["Mage"]
    assert class_color("mage") == CLASS_COLORS["Mage"]
    assert class_color("MAGE") == CLASS_COLORS["Mage"]
