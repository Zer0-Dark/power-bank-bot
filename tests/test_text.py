"""Bidi helpers. Small surface, but everything user-facing depends on it."""

from powerbank.core.text import FSI, PDI, cmd, code, ltr


def test_ltr_wraps_in_isolates():
    assert ltr("@user") == f"{FSI}@user{PDI}"


def test_ltr_accepts_non_strings():
    assert ltr(436677576) == f"{FSI}436677576{PDI}"


def test_code_puts_isolates_outside_the_tag():
    # Inside the tag they would render as stray characters in the code span.
    assert code(123) == f"{FSI}<code>123</code>{PDI}"


def test_cmd_isolates_only_the_command_token():
    assert cmd("add") == f"{FSI}/add{PDI}"


def test_isolate_characters_are_the_real_codepoints():
    assert FSI == "⁨"
    assert PDI == "⁩"
