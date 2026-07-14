# -*- coding: utf-8 -*-
"""Read-only web search and fetch tools with SSRF-resistant URL handling."""

from __future__ import annotations

import asyncio
import html
import ipaddress
import logging
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx
from agentscope.message import TextBlock, ToolResultState
from agentscope.tool import ToolChunk

from ...runtime.tool_registry import tool_descriptor

logger = logging.getLogger(__name__)

_TAVILY_SEARCH_URL = "https://api.tavily.com/search"
_TIMEOUT_SECONDS = 30.0
_MAX_RESULTS = 5
_MAX_FETCH_BYTES = 2 * 1024 * 1024
_MAX_OUTPUT_CHARS = 120_000
_MAX_REDIRECTS = 5
_TEXT_CONTENT_TYPES = (
    "text/",
    "application/xhtml+xml",
    "application/xml",
    "application/json",
)
_BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "div",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tr",
    "ul",
}


def _result(text: str, *, ok: bool) -> ToolChunk:
    return ToolChunk(
        is_last=True,
        state=ToolResultState.SUCCESS if ok else ToolResultState.ERROR,
        content=[TextBlock(type="text", text=text)],
    )


def _is_public_ip(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False


async def _validate_public_url(url: str) -> str:
    """Validate a public URL and return an address safe to connect to."""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must use http:// or https:// and include a host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs containing credentials are not allowed")

    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(
        ".localhost",
    ):
        raise ValueError("Local and private network addresses are not allowed")

    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not literal.is_global:
            raise ValueError(
                "Local and private network addresses are not allowed",
            )
        return str(literal)

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = await asyncio.to_thread(
            socket.getaddrinfo,
            host,
            port,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ValueError(f"Unable to resolve URL host: {host}") from exc
    addresses = {str(info[4][0]) for info in infos if info[4]}
    if not addresses or any(not _is_public_ip(addr) for addr in addresses):
        raise ValueError("URL host resolves to a non-public network address")
    return sorted(addresses)[0]


class _ReadableHTMLParser(HTMLParser):
    """Small dependency-free visible-text extractor."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._hidden_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._hidden_depth += 1
        elif not self._hidden_depth and tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._hidden_depth = max(0, self._hidden_depth - 1)
        elif not self._hidden_depth and tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._hidden_depth and data.strip():
            self.parts.append(data)

    def text(self) -> str:
        raw = html.unescape(" ".join(self.parts))
        raw = re.sub(r"[ \t\f\v]+", " ", raw)
        raw = re.sub(r" *\n *", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _readable_text(body: str, content_type: str) -> str:
    if "html" not in content_type.lower():
        return body.strip()[:_MAX_OUTPUT_CHARS]
    parser = _ReadableHTMLParser()
    parser.feed(body)
    return parser.text()[:_MAX_OUTPUT_CHARS]


async def _fetch_public_text(
    url: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[str, str]:
    """Fetch a public text resource, validating every redirect target."""
    current = url
    timeout = httpx.Timeout(_TIMEOUT_SECONDS)
    for _ in range(_MAX_REDIRECTS + 1):
        address = await _validate_public_url(current)
        original_url = httpx.URL(current)
        pinned_url = original_url.copy_with(host=address)
        # A fresh client per hop prevents a TLS connection pinned for one
        # hostname from being reused after a cross-host redirect to the same IP.
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            transport=transport,
            trust_env=False,
            headers={
                "User-Agent": "Minions/2.0 (+https://github.com/zhoulingquan/Minions)",
                "Accept": "text/html,text/plain,application/xhtml+xml,application/json,application/xml;q=0.9,*/*;q=0.1",
            },
        ) as client:
            async with client.stream(
                "GET",
                pinned_url,
                headers={"Host": original_url.netloc.decode("ascii")},
                extensions={
                    "sni_hostname": original_url.raw_host.decode("ascii"),
                },
            ) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("Redirect response has no Location")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                content_type = (
                    response.headers.get("content-type") or "text/plain"
                ).lower()
                if not any(
                    content_type.startswith(prefix) for prefix in _TEXT_CONTENT_TYPES
                ):
                    raise ValueError(
                        f"Unsupported Content-Type: {content_type}",
                    )
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > _MAX_FETCH_BYTES:
                    raise ValueError("Response exceeds the 2 MiB fetch limit")
                payload = bytearray()
                async for chunk in response.aiter_bytes():
                    payload.extend(chunk)
                    if len(payload) > _MAX_FETCH_BYTES:
                        raise ValueError("Response exceeds the 2 MiB fetch limit")
                encoding = response.charset_encoding or "utf-8"
                return payload.decode(encoding, errors="replace"), content_type
    raise ValueError(f"Too many redirects (limit: {_MAX_REDIRECTS})")


@tool_descriptor(async_execution=True)
async def web_search(search_term: str) -> ToolChunk:
    """Search the public web for current information and source URLs."""
    query = (search_term or "").strip()
    if not query:
        return _result("Error: search_term is empty.", ok=False)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                _TAVILY_SEARCH_URL,
                headers={
                    "Content-Type": "application/json",
                    "X-Tavily-Access-Mode": "keyless",
                },
                json={
                    "query": query,
                    "max_results": _MAX_RESULTS,
                    "search_depth": "basic",
                },
            )
            response.raise_for_status()
            results = response.json().get("results", [])
        lines: list[str] = []
        for index, item in enumerate(results[:_MAX_RESULTS], start=1):
            lines.append(f"[{index}] {item.get('title', '')}")
            lines.append(f"URL: {item.get('url', '')}")
            if item.get("content"):
                lines.append(str(item["content"]))
            lines.append("")
        return _result(
            ("\n".join(lines).strip() or "No results found.")[:_MAX_OUTPUT_CHARS],
            ok=True,
        )
    except Exception as exc:  # noqa: BLE001 - tool errors are user-visible
        logger.warning("web_search failed: %s", exc)
        return _result(f"web_search failed: {exc}", ok=False)


@tool_descriptor(async_execution=True)
async def web_fetch(url: str) -> ToolChunk:
    """Fetch readable text from a public HTTP(S) URL.

    Localhost, private/link-local/reserved addresses, credential-bearing URLs,
    binary responses, oversized responses and unsafe redirect targets are
    rejected before their content is returned.
    """
    target = (url or "").strip()
    if not target:
        return _result("Error: url is empty.", ok=False)
    try:
        body, content_type = await _fetch_public_text(target)
        text = _readable_text(body, content_type)
        return _result(text or "No readable content found.", ok=True)
    except Exception as exc:  # noqa: BLE001 - tool errors are user-visible
        logger.warning("web_fetch failed: %s", exc)
        return _result(f"web_fetch failed: {exc}", ok=False)


__all__ = ["web_fetch", "web_search"]
