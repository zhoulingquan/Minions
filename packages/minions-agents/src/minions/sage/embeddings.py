"""Optional semantic embedding boundary with fail-soft validation."""

from __future__ import annotations

import asyncio
import hashlib
import math
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol


class EmbeddingProvider(Protocol):
    dimensions: int

    async def embed(self, text: str) -> tuple[float, ...]: ...


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    vector: tuple[float, ...] | None
    degradation: str = ""


class EmbeddingService:
    """Validate provider output and keep provider failure off the request path."""

    def __init__(
        self,
        provider: EmbeddingProvider,
        *,
        timeout_seconds: float = 1.5,
    ) -> None:
        if provider.dimensions < 1:
            raise ValueError("embedding dimensions must be positive")
        self.provider = provider
        self.timeout_seconds = max(0.001, float(timeout_seconds))

    async def embed(self, text: str) -> EmbeddingResult:
        try:
            vector = tuple(
                float(value)
                for value in await asyncio.wait_for(
                    self.provider.embed(text),
                    timeout=self.timeout_seconds,
                )
            )
        except TimeoutError:
            return EmbeddingResult(None, "semantic_timeout")
        except Exception:
            return EmbeddingResult(None, "semantic_provider_error")
        if len(vector) != self.provider.dimensions:
            return EmbeddingResult(None, "semantic_dimension_mismatch")
        if not all(math.isfinite(value) for value in vector):
            return EmbeddingResult(None, "semantic_invalid_vector")
        return EmbeddingResult(vector)


class LocalHashEmbeddingProvider:
    """Offline multilingual n-gram vectors used as the stable local baseline."""

    model = "local-hash-v1"
    min_similarity = 0.18
    _ZH_ALIASES = (
        ("核账", "对账"),
        ("月末", "月度"),
        ("账本", "台账"),
        ("检查", "核对"),
        ("差额", "差异"),
        ("原始", "来源"),
    )

    def __init__(self, *, dimensions: int = 384) -> None:
        if dimensions < 32:
            raise ValueError("local embedding dimensions must be at least 32")
        self.dimensions = int(dimensions)

    async def embed(self, text: str) -> tuple[float, ...]:
        values = [0.0] * self.dimensions
        for token, weight in self._features(text):
            digest = hashlib.blake2b(
                token.encode("utf-8"),
                digest_size=16,
                person=b"sage-local-v1",
            ).digest()
            index = int.from_bytes(digest[:8], "big") % self.dimensions
            sign = 1.0 if digest[8] & 1 else -1.0
            values[index] += sign * weight
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0:
            return tuple(values)
        return tuple(value / norm for value in values)

    @staticmethod
    def _features(text: str) -> list[tuple[str, float]]:
        normalized = unicodedata.normalize("NFKC", str(text)).casefold()
        # A deliberately small, auditable normalization vocabulary improves
        # common Chinese business paraphrases without pretending that the
        # offline hash baseline is a general-purpose semantic model.
        for source, target in LocalHashEmbeddingProvider._ZH_ALIASES:
            normalized = normalized.replace(source, target)
        features: list[tuple[str, float]] = []
        for word in re.findall(r"[a-z0-9_]+", normalized):
            features.append((f"w:{word}", 1.5))
            for size in (3, 4):
                features.extend(
                    (f"l{size}:{word[index : index + size]}", 0.5)
                    for index in range(max(0, len(word) - size + 1))
                )
        for sequence in re.findall(r"[\u3400-\u9fff]+", normalized):
            features.extend((f"c:{char}", 0.35) for char in sequence)
            for size, weight in ((2, 1.4), (3, 0.8)):
                features.extend(
                    (f"h{size}:{sequence[index : index + size]}", weight)
                    for index in range(max(0, len(sequence) - size + 1))
                )
        return features


class OpenAICompatibleEmbeddingProvider:
    """Minimal bounded adapter for an operator-configured embedding endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        dimensions: int,
        client=None,
    ) -> None:
        if not base_url.strip() or not model.strip():
            raise ValueError("embedding base URL and model are required")
        if dimensions < 1:
            raise ValueError("embedding dimensions must be positive")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.dimensions = int(dimensions)
        self.min_similarity = 0.30
        self._client = client

    async def embed(self, text: str) -> tuple[float, ...]:
        import httpx

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model, "input": text}
        if self._client is not None:
            response = await self._client.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=payload,
            )
        else:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json=payload,
                )
        response.raise_for_status()
        body = response.json()
        return tuple(float(value) for value in body["data"][0]["embedding"])


def build_embedding_service_from_env() -> EmbeddingService | None:
    """Build the configured provider; invalid production configuration fails."""

    provider_name = (
        os.environ.get(
            "MINIONS_SAGE_EMBEDDING_PROVIDER",
            "local-hash",
        )
        .strip()
        .lower()
    )
    if provider_name in {"", "off", "none", "disabled"}:
        return None
    timeout = float(os.environ.get("MINIONS_SAGE_EMBEDDING_TIMEOUT_SECONDS", "1.5"))
    if provider_name == "local-hash":
        dimensions = int(os.environ.get("MINIONS_SAGE_EMBEDDING_DIMENSIONS", "384"))
        return EmbeddingService(
            LocalHashEmbeddingProvider(dimensions=dimensions),
            timeout_seconds=timeout,
        )
    if provider_name == "openai-compatible":
        base_url = os.environ.get("MINIONS_SAGE_EMBEDDING_BASE_URL", "")
        model = os.environ.get("MINIONS_SAGE_EMBEDDING_MODEL", "")
        api_key = os.environ.get("MINIONS_SAGE_EMBEDDING_API_KEY", "")
        dimensions = int(
            os.environ.get("MINIONS_SAGE_EMBEDDING_DIMENSIONS", "1536"),
        )
        return EmbeddingService(
            OpenAICompatibleEmbeddingProvider(
                base_url=base_url,
                api_key=api_key,
                model=model,
                dimensions=dimensions,
            ),
            timeout_seconds=timeout,
        )
    raise ValueError("invalid MINIONS_SAGE_EMBEDDING_PROVIDER")


__all__ = [
    "EmbeddingProvider",
    "EmbeddingResult",
    "EmbeddingService",
    "LocalHashEmbeddingProvider",
    "OpenAICompatibleEmbeddingProvider",
    "build_embedding_service_from_env",
]
