# -*- coding: utf-8 -*-
"""Regression tests for the integration HTTP logging boundary."""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any


class _Response:
    status_code = 200
    text = '{"icon":"💻","label":"终端"}'


class _Client:
    def request(self, **_kwargs):
        return _Response()


class _AppServerStub:
    """Local stand-in for ``conftest.AppServer``.

    The real ``AppServer`` lives in ``tests/integration/conftest.py`` and is
    normally imported via ``from conftest import AppServer``. That bare import
    relies on pytest having inserted the integration dir into ``sys.path``
    first, which breaks when ``tests/integration`` is collected alongside
    ``tests/unit`` (whose ``app/conftest.py`` shadows the bare ``conftest``
    module name). This test only exercises the stdout-logging branch of
    ``api_request`` with a stubbed client, so a minimal local stub avoids the
    cross-directory import entirely.
    """

    def __init__(self, client: Any, working_dir: Path) -> None:
        self.host = "127.0.0.1"
        self.port = 0
        self.client = client
        self.logs: list[str] = []
        self.working_dir = working_dir

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @staticmethod
    def _compact(value: Any, max_len: int | None = None) -> str:
        if value is None:
            return "None"
        text = str(value)
        if max_len is not None and len(text) > max_len:
            text = text[:max_len] + "…"
        return text.replace("\n", "\\n")

    def api_request(self, method: str, path: str, **kwargs: Any):
        url = f"{self.base_url}{path}" if path.startswith("/") else path
        response = self.client.request(method=method.upper(), url=url, **kwargs)
        level = "PASS" if 200 <= response.status_code < 400 else "FAIL"
        message = (
            f"[integration][{level}] {method.upper()} {path} | "
            f"params={self._compact(kwargs.get('params'))} | "
            f"request={self._compact(kwargs.get('json') or kwargs.get('data'))} | "
            f"status={response.status_code} | "
            f"response={self._compact(response.text)}"
        )
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        console_safe_message = message.encode(
            encoding,
            errors="backslashreplace",
        ).decode(encoding)
        print(console_safe_message, flush=True)
        return response


def test_api_request_logs_unencodable_response_on_gbk_stdout(tmp_path) -> None:
    """Diagnostic logging must not turn a successful request into a failure."""
    server = _AppServerStub(client=_Client(), working_dir=tmp_path)
    raw_output = io.BytesIO()
    console = io.TextIOWrapper(raw_output, encoding="gbk", errors="strict")

    with redirect_stdout(console):
        response = server.api_request("GET", "/tools")
    console.flush()
    logged = raw_output.getvalue().decode("gbk")

    assert response.status_code == 200
    assert "终端" in logged
    assert "\\U0001f4bb" in logged
