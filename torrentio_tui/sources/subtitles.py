"""Subtitle providers: SubDB (keyless, hash-based) and OpenSubtitles.com.

Providers plug in behind one interface — adding another is a subclass +
one line in `load_subtitle_providers()`. When `[subtitles] enabled =
true`, playback auto-attaches the best-matching subtitle (preferred
languages first) to streams that don't already carry one; anything a
provider can't do (missing API key, hash-only provider with no local
file, network error) is skipped quietly so subtitles never break
playback.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path

from torrentio_tui.languages import SUBTITLE_LANGUAGE_CODES
from torrentio_tui.models import Episode, SearchResult, StreamLink
from torrentio_tui.proxy import ProxyError, open_url
from torrentio_tui.sources.base import SourceError

_USER_AGENT = "torrentio-tui/0.4 (+https://github.com/yubiiixtreme/torrentio-tui)"

# ISO-639-2/T (our config, e.g. "eng") <-> ISO-639-1 (subtitle APIs, "en").
_TO_639_1 = {code: lang.value for code, lang in SUBTITLE_LANGUAGE_CODES.items()}
_TO_639_2 = {lang.value: code for code, lang in SUBTITLE_LANGUAGE_CODES.items()}


def _to_639_1(code: str) -> str | None:
    if code in _TO_639_1:
        return _TO_639_1[code]
    return code if code in _TO_639_2 else None


def _to_639_2(code: str) -> str:
    return _TO_639_2.get(code, code)


@dataclasses.dataclass(frozen=True, slots=True)
class SubtitleFile:
    """One downloadable subtitle candidate from a provider."""

    url: str
    """Direct download URL — or an opaque provider reference when the real
    link needs a second call (see `SubtitleProvider.download_url`)."""
    lang: str
    """ISO-639-2/T code (e.g. "eng"), normalized by the provider."""
    name: str = ""
    provider_id: str = ""


class SubtitleProvider(ABC):
    id: str
    name: str

    @abstractmethod
    def search(
        self,
        title: str,
        *,
        imdb_id: str | None = None,
        season: int | None = None,
        episode: int | None = None,
        file_hash: str | None = None,
    ) -> list[SubtitleFile]:
        """Return subtitle candidates. Raise `SourceError` when the
        provider can't answer (not configured, offline, ...)."""

    def download_url(self, sub: SubtitleFile) -> str:
        """Resolve `sub` to a real download URL. Default: already direct."""
        return sub.url


def opensubtitles_hash(path: Path) -> str:
    """SubDB/OpenSubtitles-style hash: md5(first 64KB + last 64KB)."""
    chunk = 65536
    with path.open("rb") as fh:
        head = fh.read(chunk)
        try:
            fh.seek(-chunk, 2)
        except OSError:
            tail = b""
        else:
            tail = fh.read(chunk)
    return hashlib.md5(head + tail).hexdigest()


class SubDBProvider(SubtitleProvider):
    """SubDB — keyless hash lookup (`api.thesubdb.com`). Works only when
    the video file is local (hash of the actual bytes)."""

    id = "subdb"
    name = "SubDB (hash match, no key)"

    API = "https://api.thesubdb.com"

    def __init__(self, timeout: float = 15.0, proxy_url: str | None = None) -> None:
        self.timeout = timeout
        self.proxy_url = proxy_url

    def search(self, title, *, imdb_id=None, season=None, episode=None, file_hash=None):
        if not file_hash:
            raise SourceError("SubDB needs the video file hash (local files only)")
        url = f"{self.API}/?action=search&hash={file_hash}"
        try:
            with open_url(url, self.timeout, self.proxy_url, {"User-Agent": _USER_AGENT}) as resp:
                available = resp.read().decode("utf-8", errors="replace")
        except ProxyError as exc:
            raise SourceError(str(exc)) from exc
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return []
            raise SourceError(f"SubDB failed (HTTP {exc.code})") from exc
        except urllib.error.URLError as exc:
            raise SourceError(f"SubDB network error: {exc.reason}") from exc
        files = []
        for lang_639_1 in available.replace(" ", "").split(","):
            lang_639_1 = lang_639_1.strip()
            if not lang_639_1:
                continue
            files.append(
                SubtitleFile(
                    url=f"{self.API}/?action=download&hash={file_hash}&language={lang_639_1}",
                    lang=_to_639_2(lang_639_1),
                    name=f"{title} [{lang_639_1}]",
                    provider_id=self.id,
                )
            )
        return files


class OpenSubtitlesProvider(SubtitleProvider):
    """OpenSubtitles.com REST API. Search needs an API key (free at
    opensubtitles.com); downloading additionally needs username+password
    for the auth token. Without credentials every call raises and the
    orchestrator skips this provider."""

    id = "opensubtitles"
    name = "OpenSubtitles.com"

    API = "https://api.opensubtitles.com/api/v1"

    def __init__(
        self,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 15.0,
        proxy_url: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.username = username
        self.password = password
        self.timeout = timeout
        self.proxy_url = proxy_url
        self._token: str | None = None

    def _headers(self, auth: bool = False) -> dict[str, str]:
        if not self.api_key:
            raise SourceError(
                "OpenSubtitles needs an API key: set "
                "[subtitles] opensubtitles_api_key in config.toml"
            )
        headers = {"Api-Key": self.api_key, "Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {self._auth_token()}"
        return headers

    def _request(self, method: str, path: str, payload: dict | None = None):
        """JSON request honoring the proxy (socks via `socks_proxy`)."""
        from torrentio_tui.proxy import socks_proxy

        data = json.dumps(payload).encode() if payload is not None else None
        headers = self._headers(auth=path == "/download")
        req = urllib.request.Request(f"{self.API}{path}", data=data, headers=headers, method=method)
        try:
            with socks_proxy(self.proxy_url):
                if self.proxy_url and self.proxy_url.startswith(("http://", "https://")):
                    from torrentio_tui.proxy import build_opener

                    with build_opener(self.proxy_url).open(req, timeout=self.timeout) as resp:
                        return json.loads(resp.read().decode("utf-8", errors="replace"))
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8", errors="replace"))
        except ProxyError as exc:
            raise SourceError(str(exc)) from exc
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                self._token = None  # stale token — next call re-logs-in
                raise SourceError("OpenSubtitles rejected the credentials") from exc
            raise SourceError(f"OpenSubtitles failed (HTTP {exc.code})") from exc
        except urllib.error.URLError as exc:
            raise SourceError(f"OpenSubtitles network error: {exc.reason}") from exc
        except (json.JSONDecodeError, TimeoutError) as exc:
            raise SourceError(f"OpenSubtitles bad response: {exc}") from exc

    def _auth_token(self) -> str:
        if self._token:
            return self._token
        if not (self.username and self.password):
            raise SourceError(
                "OpenSubtitles downloads need username+password: set "
                "[subtitles] opensubtitles_username/_password"
            )
        data = self._request(
            "POST", "/login", {"username": self.username, "password": self.password}
        )
        token = data.get("token") if isinstance(data, dict) else None
        if not token:
            raise SourceError("OpenSubtitles login failed")
        self._token = str(token)
        return self._token

    def search(self, title, *, imdb_id=None, season=None, episode=None, file_hash=None):
        params: dict[str, str] = {}
        if imdb_id:
            params["imdb_id"] = imdb_id.removeprefix("tt")
        else:
            params["query"] = title
        if season is not None and episode is not None:
            params["season"] = str(season)
            params["episode"] = str(episode)
        query = urllib.parse.urlencode(params)
        data = self._request("GET", f"/subtitles?{query}")
        files = []
        rows = data.get("data") if isinstance(data, dict) else None
        for row in rows or []:
            attrs = row.get("attributes") or {} if isinstance(row, dict) else {}
            attrs = row.get("attributes") or {} if isinstance(row, dict) else {}
            lang_639_1 = str(attrs.get("language", ""))
            for f in attrs.get("files") or []:
                if not isinstance(f, dict) or f.get("file_id") is None:
                    continue
                files.append(
                    SubtitleFile(
                        url=str(f["file_id"]),  # resolved via download_url()
                        lang=_to_639_2(lang_639_1),
                        name=str(f.get("file_name", title)),
                        provider_id=self.id,
                    )
                )
        return files

    def download_url(self, sub: SubtitleFile) -> str:
        try:
            file_id = int(sub.url)
        except (ValueError, TypeError) as exc:
            raise SourceError(f"Bad OpenSubtitles file id: {sub.url!r}") from exc
        data = self._request("POST", "/download", {"file_id": file_id})
        link = data.get("link") if isinstance(data, dict) else None
        if not link:
            raise SourceError("OpenSubtitles returned no download link")
        return str(link)


_AVAILABLE_PROVIDERS: dict[str, type[SubtitleProvider]] = {
    SubDBProvider.id: SubDBProvider,
    OpenSubtitlesProvider.id: OpenSubtitlesProvider,
}


def available_provider_ids() -> list[str]:
    return list(_AVAILABLE_PROVIDERS.keys())


def load_subtitle_providers(config) -> list[SubtitleProvider]:
    """Build the enabled providers from `[subtitles]`. Unconfigured ones
    are still built — they raise `SourceError` on use and the
    orchestrator skips them."""
    sub_cfg = config.subtitles
    providers: list[SubtitleProvider] = []
    for provider_id in sub_cfg.providers:
        if provider_id == SubDBProvider.id:
            providers.append(
                SubDBProvider(timeout=sub_cfg.timeout_seconds, proxy_url=config.network.proxy_url)
            )
        elif provider_id == OpenSubtitlesProvider.id:
            providers.append(
                OpenSubtitlesProvider(
                    api_key=sub_cfg.opensubtitles_api_key,
                    username=sub_cfg.opensubtitles_username,
                    password=sub_cfg.opensubtitles_password,
                    timeout=sub_cfg.timeout_seconds,
                    proxy_url=config.network.proxy_url,
                )
            )
    return providers


def _download_to_cache(
    url: str, cache_key: str, lang: str, timeout: float, proxy_url: str | None
) -> str | None:
    """Fetch subtitle bytes into the cache; return the local path, or
    None when the fetch fails (caller falls back to the remote URL)."""
    from torrentio_tui.config import cache_dir

    try:
        with open_url(url, timeout, proxy_url, {"User-Agent": _USER_AGENT}) as resp:
            body = resp.read()
    except Exception:
        return None
    if not body or len(body) > 2_000_000:
        return None
    safe_key = re.sub(r"[^A-Za-z0-9_.-]", "_", cache_key)[:80] or "sub"
    dest = cache_dir() / "subtitles" / f"{safe_key}.{lang}.srt"
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
    except OSError:
        return None
    return str(dest)


def attach_subtitles(
    stream: StreamLink, item: SearchResult, episode: Episode, config
) -> StreamLink:
    """Best-effort subtitle attach for one playback. Returns `stream`
    unchanged unless `[subtitles] enabled` and the stream lacks one and a
    provider has a preferred-language match. Never raises."""
    try:
        return _attach_subtitles(stream, item, episode, config)
    except Exception:
        return stream


def _attach_subtitles(
    stream: StreamLink, item: SearchResult, episode: Episode, config
) -> StreamLink:
    sub_cfg = config.subtitles
    if not sub_cfg.enabled or stream.subtitle_url:
        return stream
    preferred: list[str] = list(getattr(config.language, "subtitle_languages", ["eng"]))
    if not preferred:
        return stream

    imdb_id: str | None = None
    m = re.search(r"tt\d+", item.id)
    if m:
        imdb_id = m.group(0)

    file_hash: str | None = None
    file_path: Path | None = None
    candidate = Path(stream.url)
    if candidate.exists() and candidate.is_file():
        file_path = candidate
        try:
            file_hash = opensubtitles_hash(candidate)
        except OSError:
            file_hash = None

    best: SubtitleFile | None = None
    best_provider: SubtitleProvider | None = None
    for provider in load_subtitle_providers(config):
        try:
            files = provider.search(
                item.title,
                imdb_id=imdb_id,
                season=episode.season,
                episode=episode.number,
                file_hash=file_hash,
            )
        except SourceError:
            continue
        by_lang: dict[str, SubtitleFile] = {}
        for f in files:
            by_lang.setdefault(f.lang, f)
        # Prefs may be 639-1 ("en") or 639-2 ("eng"); providers normalize
        # to 639-2, so compare normalized forms.
        normalized_prefs = [(_to_639_2(p), p) for p in preferred]
        for norm, _raw in normalized_prefs:
            if norm in by_lang:
                best, best_provider = by_lang[norm], provider
                break
        if best is None:
            for norm, raw in normalized_prefs:
                for f in files:
                    if f.lang == norm or f.lang == raw:
                        best, best_provider = f, provider
                        break
                if best is not None:
                    break
        if best is not None:
            break
    if best is None or best_provider is None:
        return stream

    try:
        url = best_provider.download_url(best)
    except SourceError:
        return stream
    if url.startswith(("http://", "https://")):
        cache_key = file_hash or f"{item.source_id}-{imdb_id or item.id}-{episode.number or 0}"
        local = _download_to_cache(
            url, cache_key, best.lang, sub_cfg.timeout_seconds, config.network.proxy_url
        )
        url = local or url
    elif file_path is not None and not Path(url).exists():
        return stream
    return dataclasses.replace(stream, subtitle_url=url)
