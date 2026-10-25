"""A thin layer over SerpApi's Python client.

It counts every search (the number on screen while a run goes), caches each
response on disk so re-running costs nothing, and never prints the API key:
the client's exception text includes the full request URL, so errors are
reported from the status code and SerpApi's own message instead.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import serpapi

# SerpApi answers an empty result page with an error string; to us it's just empty.
EMPTY = ("hasn't returned any results", "no results")


class SerpError(RuntimeError):
    pass


class Serp:
    def __init__(self, api_key: str, cache_dir: Path, refresh: bool = False, on_call=None):
        self._client = serpapi.Client(api_key=api_key, timeout=90)
        self._key = api_key
        self.cache_dir = cache_dir
        self.refresh = refresh
        self.live = 0
        self.cached = 0
        self.on_call = on_call  # callback(engine, label, cached) for progress output

    @classmethod
    def from_env(cls, cache_dir: Path, **kwargs) -> Serp:
        load_dotenv()
        key = os.environ.get("SERPAPI_API_KEY", "").strip()
        if not key:
            raise SerpError("SERPAPI_API_KEY is missing. Copy .env.example to .env and add your key.")
        return cls(key, cache_dir, **kwargs)

    def search(self, params: dict, label: str = "") -> dict:
        path = self._cache_path(params)
        if path.exists() and not self.refresh:
            self.cached += 1
            if self.on_call:
                self.on_call(params.get("engine", ""), label, True)
            return json.loads(path.read_text())["response"]

        try:
            # The client adds api_key to the dict it's given, so it gets a copy.
            data = dict(self._client.search(dict(params)))
        except serpapi.HTTPError as error:
            raise SerpError(f"SerpApi answered {error.status_code}: {error.error or 'no message'}") from None
        except (serpapi.HTTPConnectionError, serpapi.TimeoutError):
            raise SerpError("Couldn't reach SerpApi. Check your connection and try again.") from None

        self.live += 1
        if self.on_call:
            self.on_call(params.get("engine", ""), label, False)
        if not data.get("error") or is_empty(data["error"]):
            path.parent.mkdir(parents=True, exist_ok=True)
            text = json.dumps({"params": params, "response": data}, indent=1)
            path.write_text(text.replace(self._key, "[redacted]"))
        return data

    def searches_left(self) -> int | None:
        """From SerpApi's Account API, which doesn't count against the plan."""
        try:
            return dict(self._client.account()).get("total_searches_left")
        except serpapi.SerpApiError:
            return None

    def _cache_path(self, params: dict) -> Path:
        stable = "&".join(f"{k}={params[k]}" for k in sorted(params) if params[k] is not None)
        digest = hashlib.sha256(stable.encode()).hexdigest()[:24]
        return self.cache_dir / str(params.get("engine", "unknown")) / f"{digest}.json"


def is_empty(error: str) -> bool:
    return any(phrase in error.lower() for phrase in EMPTY)


def load_dotenv(path: Path = Path(".env")) -> None:
    """Reads KEY=VALUE lines into the environment without overriding what's set."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
