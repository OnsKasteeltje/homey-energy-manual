from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_ev_hard_max_is_16a_end_to_end():
    adapter = read("docs/javascripts/ev-power-adapter-shadow-v0.1.js")
    renderer = read("docs/javascripts/live-energy-v2.8.108.js")
    controller = read("docs/javascripts/tesla-deadline-controller-v2.8.115.js")
    worker = read("cloudflare/tesla-deadline-worker.js")

    assert 'EV_HARD_MAX_CURRENT_A = 16' in adapter
    assert 'Math.min(\n    EV_HARD_MAX_CURRENT_A' in adapter

    # Website input itself must never offer a value above 16 A.
    assert 'class=\"tesla-inline-amps\" type=\"number\" min=\"6\" max=\"16\"' in renderer

    # Browser-side save validation rejects crafted/local values >16 A.
    assert 'maxA>16' in controller

    # Backend independently rejects direct/crafted requests >16 A.
    assert 'maxA > 16' in worker
