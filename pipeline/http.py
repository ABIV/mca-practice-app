"""Shared HTTP with a single identifying User-Agent. Failures raise SourceError;
callers convert to Signal.unknown — never a silent fallback value."""
import requests

USER_AGENT = "mvbt-trail-weather (github.com/ABIV/mca-practice-app)"

class SourceError(Exception):
    pass

def _headers(extra):
    h = {"User-Agent": USER_AGENT}
    if extra:
        h.update(extra)
    return h

def get_json(url, params=None, headers=None, timeout=15):
    try:
        r = requests.get(url, params=params, headers=_headers(headers), timeout=timeout)
    except requests.RequestException as e:
        raise SourceError(f"request failed: {e}") from e
    if r.status_code != 200:
        raise SourceError(f"HTTP {r.status_code} from {url}")
    try:
        return r.json()
    except ValueError as e:
        raise SourceError(f"bad JSON from {url}: {e}") from e

def get_text(url, params=None, headers=None, timeout=15):
    try:
        r = requests.get(url, params=params, headers=_headers(headers), timeout=timeout)
    except requests.RequestException as e:
        raise SourceError(f"request failed: {e}") from e
    if r.status_code != 200:
        raise SourceError(f"HTTP {r.status_code} from {url}")
    return r.text
