import pytest
from scripts.traffic import options


@pytest.mark.parametrize("url", ["http://example.com/api/work", "http://localhost.evil/api/work",
    "https://127.0.0.1/api/work", "http://127.0.0.1/other", "http://user:pass@localhost/api/work"])
def test_external_or_ambiguous_targets_rejected(url):
    with pytest.raises(SystemExit):
        options(["errors", "--url", url])


@pytest.mark.parametrize("flag,value", [("--duration", "1801"), ("--rate", "51"),
    ("--fraction", "1.1"), ("--latency-ms", "2001"), ("--workers", "9")])
def test_unsafe_parameters_rejected(flag, value):
    with pytest.raises(SystemExit):
        options(["errors", flag, value])


def test_default_local_lab():
    assert options(["baseline"]).url == "http://127.0.0.1:8000/api/work"
