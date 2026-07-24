# -*- coding: utf-8 -*-
"""Tests for optional, fail-soft semantic embedding support."""

import asyncio

import pytest

from minions.sage.embeddings import (
    EmbeddingService,
    LocalHashEmbeddingProvider,
)


class _Provider:
    dimensions = 3

    async def embed(self, _text: str):
        return (0.1, 0.2, 0.3)


class _WrongDimensions:
    dimensions = 2

    async def embed(self, _text: str):
        return (0.1,)


class _SlowProvider:
    dimensions = 1

    async def embed(self, _text: str):
        await asyncio.sleep(0.05)
        return (0.1,)


@pytest.mark.asyncio
async def test_embedding_service_validates_dimensions() -> None:
    result = await EmbeddingService(_Provider()).embed("invoice review")
    assert result.vector == (0.1, 0.2, 0.3)
    assert result.degradation == ""

    invalid = await EmbeddingService(_WrongDimensions()).embed("invoice")
    assert invalid.vector is None
    assert invalid.degradation == "semantic_dimension_mismatch"


@pytest.mark.asyncio
async def test_embedding_service_times_out_without_failing_recall() -> None:
    result = await EmbeddingService(
        _SlowProvider(),
        timeout_seconds=0.001,
    ).embed(
        "invoice",
    )
    assert result.vector is None
    assert result.degradation == "semantic_timeout"


@pytest.mark.asyncio
async def test_local_chinese_embedding_is_deterministic() -> None:
    provider = LocalHashEmbeddingProvider(dimensions=128)
    first = await provider.embed("客户月度对账复核")
    second = await provider.embed("客户月度对账复核")
    related = await provider.embed("月度客户对账流程")
    unrelated = await provider.embed("招聘候选人面试安排")

    assert first == second
    assert sum(value * value for value in first) == pytest.approx(1.0)
    assert sum(a * b for a, b in zip(first, related, strict=True)) > sum(
        a * b for a, b in zip(first, unrelated, strict=True)
    )
