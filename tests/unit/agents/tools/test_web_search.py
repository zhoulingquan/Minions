# -*- coding: utf-8 -*-
"""Security and formatting tests for built-in web tools."""

from __future__ import annotations

import socket
import importlib

import httpx
import pytest
from agentscope.message import ToolResultState

from minions.agents.tools import web_search as web_search_func
from minions.agents.tools.web_search import (
    _readable_text,
    _validate_public_url,
    web_fetch,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://[::1]/admin",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.2/private",
        "http://localhost:8000/",
        "https://user:password@example.com/",
    ],
)
async def test_validate_public_url_rejects_local_and_credential_urls(url):
    with pytest.raises(ValueError):
        await _validate_public_url(url)


@pytest.mark.asyncio
async def test_validate_public_url_rejects_hostname_resolving_private(
    monkeypatch,
):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.5", 80)),
        ],
    )
    with pytest.raises(ValueError, match="non-public"):
        await _validate_public_url("http://internal.example/")


@pytest.mark.asyncio
async def test_validate_public_url_accepts_public_resolution(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("93.184.216.34", 443),
            ),
        ],
    )
    assert (
        await _validate_public_url("https://example.com/") == "93.184.216.34"
    )


@pytest.mark.asyncio
async def test_fetch_connects_to_the_validated_ip(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("93.184.216.34", 443),
            ),
        ],
    )
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = request.url
        captured["host"] = request.headers["host"]
        captured["sni_hostname"] = request.extensions.get("sni_hostname")
        return httpx.Response(
            200,
            headers={"content-type": "text/plain"},
            content=b"safe",
        )

    module = importlib.import_module("minions.agents.tools.web_search")
    body, content_type = await module._fetch_public_text(
        "https://example.com/resource",
        transport=httpx.MockTransport(handler),
    )

    assert body == "safe"
    assert content_type == "text/plain"
    assert captured["url"] == httpx.URL(
        "https://93.184.216.34/resource",
    )
    assert captured["host"] == "example.com"
    assert captured["sni_hostname"] == "example.com"


def test_readable_text_removes_hidden_html_and_normalizes_blocks():
    text = _readable_text(
        "<html><body><h1>Title</h1><script>secret()</script>"
        "<p>Hello <b>world</b>.</p></body></html>",
        "text/html; charset=utf-8",
    )
    assert "Title" in text
    assert "Hello world" in text
    assert "secret" not in text


@pytest.mark.asyncio
async def test_web_fetch_rejects_private_url_without_request():
    chunk = await web_fetch("http://127.0.0.1/secrets")
    assert chunk.state == ToolResultState.ERROR
    assert "private" in chunk.content[0].text.lower()


@pytest.mark.asyncio
async def test_web_fetch_returns_extracted_text(monkeypatch):
    async def fake_fetch(_url):
        return "<p>Hello from Minions</p>", "text/html"

    module = importlib.import_module("minions.agents.tools.web_search")
    monkeypatch.setattr(module, "_fetch_public_text", fake_fetch)
    chunk = await web_fetch("https://example.com/")
    assert chunk.state == ToolResultState.SUCCESS
    assert chunk.content[0].text == "Hello from Minions"


def test_web_tools_are_exported_from_builtin_package():
    assert callable(web_search_func)
