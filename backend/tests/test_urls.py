from app.core.urls import extract_urls


def test_extracts_urls_from_mixed_text():
    text = "смотри https://youtu.be/abc, и ещё\nhttp://example.com/a?b=1;\nмусор www.nope.com"
    assert extract_urls(text) == ["https://youtu.be/abc", "http://example.com/a?b=1"]


def test_deduplicates_preserving_order():
    text = "https://a.example/1 https://b.example/2 https://a.example/1"
    assert extract_urls(text) == ["https://a.example/1", "https://b.example/2"]


def test_strips_trailing_punctuation_and_brackets():
    assert extract_urls("(https://a.example/x).") == ["https://a.example/x"]


def test_ignores_urls_without_host():
    assert extract_urls("https:// http://") == []


def test_empty_text():
    assert extract_urls("") == []
