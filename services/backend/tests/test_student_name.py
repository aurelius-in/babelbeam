from app.student_name import sanitize_display_name


def test_sanitize_display_name_trims_and_bounds() -> None:
    assert sanitize_display_name("  Ana  ") == "Ana"
    assert sanitize_display_name("   ") == ""
    assert sanitize_display_name(None) == ""
    long_name = "A" * 80
    assert len(sanitize_display_name(long_name)) == 40
