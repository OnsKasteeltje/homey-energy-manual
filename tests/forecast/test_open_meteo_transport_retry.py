#!/usr/bin/env python3
import importlib.util
import io
import json
import ssl
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "src/pi/ems-runtime/planner/open_meteo_transport.py"
WEATHER = ROOT / "src/pi/ems-runtime/planner/weather-forecast/fetch_weather_forecast.py"
PV = ROOT / "src/pi/ems-runtime/planner/pv-forecast/fetch_pv_forecast.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("open_meteo_transport_contract", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def response(payload):
    return io.BytesIO(json.dumps(payload).encode("utf-8"))


def main():
    helper = load_helper()

    calls = []
    sleeps = []

    def timeout_then_ok(request, timeout):
        calls.append(timeout)
        if len(calls) == 1:
            raise urllib.error.URLError(
                TimeoutError("TLS handshake operation timed out")
            )
        return response({"ok": True})

    result = helper.fetch_json_with_retry(
        object(),
        label="test-timeout",
        opener=timeout_then_ok,
        sleeper=sleeps.append,
    )
    assert result == {"ok": True}
    assert calls == [20, 20]
    assert sleeps == [2.0]

    calls.clear()
    sleeps.clear()

    def http_503_then_ok(request, timeout):
        calls.append(timeout)
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                "https://api.open-meteo.com",
                503,
                "Service Unavailable",
                None,
                None,
            )
        return response({"ok": "503-recovered"})

    result = helper.fetch_json_with_retry(
        object(),
        label="test-503",
        opener=http_503_then_ok,
        sleeper=sleeps.append,
    )
    assert result == {"ok": "503-recovered"}
    assert len(calls) == 2
    assert sleeps == [2.0]

    calls.clear()
    sleeps.clear()

    def http_400(request, timeout):
        calls.append(timeout)
        raise urllib.error.HTTPError(
            "https://api.open-meteo.com",
            400,
            "Bad Request",
            None,
            None,
        )

    try:
        helper.fetch_json_with_retry(
            object(),
            label="test-400",
            opener=http_400,
            sleeper=sleeps.append,
        )
        raise AssertionError("HTTP 400 must fail immediately")
    except urllib.error.HTTPError as exc:
        assert exc.code == 400
    assert len(calls) == 1
    assert sleeps == []

    cert_error = ssl.SSLCertVerificationError(1, "certificate verify failed")
    assert helper._is_retryable_error(cert_error) is False

    calls.clear()
    sleeps.clear()

    def always_timeout(request, timeout):
        calls.append(timeout)
        raise urllib.error.URLError(TimeoutError("still timed out"))

    try:
        helper.fetch_json_with_retry(
            object(),
            label="test-exhausted",
            opener=always_timeout,
            sleeper=sleeps.append,
        )
        raise AssertionError("second transient failure must propagate")
    except urllib.error.URLError:
        pass
    assert len(calls) == 2
    assert sleeps == [2.0]

    weather_source = WEATHER.read_text(encoding="utf-8")
    pv_source = PV.read_text(encoding="utf-8")
    for name, source in (("weather", weather_source), ("pv", pv_source)):
        assert "fetch_json_with_retry" in source, name
        assert "urllib.request.urlopen(" not in source, name

    print("PASS: bounded Open-Meteo transport retry contract")


if __name__ == "__main__":
    main()
