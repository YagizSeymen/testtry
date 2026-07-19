"""Bounded public-web crawler used by sourcing and deal-research workflows.

The crawler intentionally fetches a small, explicit URL set. Discovery/search
selects candidates; this module fetches only public pages that can become
traceable Memory evidence. It blocks local/private addresses, checks robots.txt,
caps response sizes, and returns structured failures rather than retry loops.
"""

from __future__ import annotations

import hashlib
import ipaddress
import os
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

import certifi

from .core import now_iso, stable_id


USER_AGENT = "VCBrainResearchBot/0.1 (+https://example.com/research)"
MAX_URLS = 12
MAX_BYTES = 1_000_000
MAX_TEXT_CHARS = 60_000
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def source_channel_for(kind: str) -> str:
    """Map normalized source kinds to the contract's discovery channels."""

    return {
        "github": "github",
        "hackathon": "hackathon",
        "paper": "paper_or_patent",
        "patent": "paper_or_patent",
        "accelerator": "accelerator",
        "product_launch": "product_launch",
    }.get(kind, "other")


class CrawlError(ValueError):
    """A controlled failure while fetching a candidate research source."""


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg", "nav", "header", "footer", "aside"}:
            self._ignored_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "nav", "header", "footer", "aside"} and self._ignored_depth:
            self._ignored_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text or self._ignored_depth:
            return
        if self._in_title:
            self.title = f"{self.title} {text}".strip()
            return
        self.parts.append(text)


def html_to_text(raw_html: str) -> tuple[str, str]:
    parser = _TextParser()
    parser.feed(raw_html)
    parser.close()
    return " ".join(parser.parts)[:MAX_TEXT_CHARS], parser.title[:500]


def validate_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise CrawlError("Only absolute http(s) URLs with a hostname may be crawled.")
    if parsed.username or parsed.password:
        raise CrawlError("URLs with embedded credentials may not be crawled.")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise CrawlError("Localhost may not be crawled.")
    try:
        addresses = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise CrawlError(f"Could not resolve host: {hostname}") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified:
            raise CrawlError("Private, local, or reserved network targets may not be crawled.")
    return url


class PublicWebCrawler:
    """Fetches a bounded set of safe, robots-permitted public pages."""

    def __init__(self, *, respect_robots: bool = True, timeout_seconds: int = 12) -> None:
        self.respect_robots = respect_robots
        self.timeout_seconds = timeout_seconds
        self._last_request_at: dict[str, float] = {}

    def crawl(self, url: str, *, kind: str = "other") -> dict[str, Any]:
        validate_public_url(url)
        parsed = urlparse(url)
        if self.respect_robots and not self._robots_allowed(parsed):
            raise CrawlError("robots.txt disallows this URL for the research crawler.")
        self._rate_limit(parsed.hostname or "")

        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain"})
        try:
            with urlopen(request, timeout=self.timeout_seconds, context=SSL_CONTEXT) as response:
                final_url = response.geturl()
                validate_public_url(final_url)
                content_type = response.headers.get_content_type()
                if content_type not in {"text/html", "text/plain"}:
                    raise CrawlError(f"Unsupported content type: {content_type}")
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise CrawlError("Page exceeded the crawler's maximum response size.")
                charset = response.headers.get_content_charset() or "utf-8"
                raw_text = body.decode(charset, errors="replace")
                if content_type == "text/html":
                    page_text, title = html_to_text(raw_text)
                else:
                    page_text, title = raw_text[:MAX_TEXT_CHARS], ""
                if not page_text.strip():
                    raise CrawlError("Page did not contain extractable text.")
                source = {
                    "source_id": stable_id("src", final_url, title),
                    "url": final_url,
                    "canonical_url": final_url,
                    "title": title or (urlparse(final_url).hostname or final_url),
                    "kind": kind if kind else "other",
                    "channel": source_channel_for(kind),
                    "content_hash": hashlib.sha256(page_text.encode("utf-8")).hexdigest(),
                    "published_at": None,
                    "raw_document_id": None,
                    "fetched_at": now_iso(),
                    "http_status": getattr(response, "status", 200),
                }
                return {"source": source, "page_text": page_text}
        except CrawlError:
            raise
        except Exception as exc:
            raise CrawlError(f"Could not fetch {url}: {exc}") from exc

    def _robots_allowed(self, parsed: Any) -> bool:
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            request = Request(robots_url, headers={"User-Agent": USER_AGENT, "Accept": "text/plain"})
            with urlopen(request, timeout=self.timeout_seconds, context=SSL_CONTEXT) as response:
                raw = response.read(256_000).decode(response.headers.get_content_charset() or "utf-8", errors="replace")
            parser.parse(raw.splitlines())
        except Exception:
            # A missing/unavailable robots file is not an instruction to block.
            return True
        return parser.can_fetch(USER_AGENT, parsed.geturl())

    def _rate_limit(self, hostname: str) -> None:
        minimum_delay = float(os.getenv("VC_BRAIN_CRAWL_DELAY_SECONDS", "0.25"))
        elapsed = time.monotonic() - self._last_request_at.get(hostname, 0.0)
        if elapsed < minimum_delay:
            time.sleep(minimum_delay - elapsed)
        self._last_request_at[hostname] = time.monotonic()


def endpoint_research_crawl(payload: dict[str, Any]) -> dict[str, Any]:
    urls = payload.get("urls")
    if not isinstance(urls, list) or not urls:
        raise ValueError("urls must be a non-empty array of public http(s) URLs.")
    if len(urls) > MAX_URLS:
        raise ValueError(f"At most {MAX_URLS} URLs may be crawled in one request.")
    source_kind = str(payload.get("source_kind") or "other")
    crawler = PublicWebCrawler()
    workers = max(1, min(4, int(os.getenv("VC_BRAIN_MAX_PARALLEL_CRAWLS", "4"))))

    def fetch(item: Any) -> tuple[str, dict[str, Any] | None, str | None]:
        url = str(item)
        try:
            return url, crawler.crawl(url, kind=source_kind), None
        except CrawlError as exc:
            return url, None, str(exc)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(fetch, urls))

    documents = [result for _, result, error in results if result is not None and error is None]
    failures = [
        {"url": url, "reason": error}
        for url, result, error in results
        if result is None and error is not None
    ]
    return {"documents": documents, "failures": failures}
