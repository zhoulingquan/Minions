# -*- coding: utf-8 -*-
"""Safe CRUD for Markdown documents stored in an agent workspace."""

from datetime import datetime, timezone
from pathlib import Path

from .utils.file_handling import read_text_file_with_encoding_fallback


class WorkspaceMarkdownManager:
    """Read and write top-level Markdown documents in one workspace."""

    def __init__(self, workspace_dir: str | Path) -> None:
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        normalized = name.replace("\\", "/")
        parts = normalized.split("/")
        if any(part == ".." for part in parts):
            raise ValueError(
                f"Invalid Markdown name '{name}': path traversal is not allowed",
            )
        filename = parts[-1]
        if not filename:
            raise ValueError(f"Invalid Markdown name '{name}': filename is empty")
        return filename if filename.endswith(".md") else f"{filename}.md"

    @staticmethod
    def _assert_within_workspace(file_path: Path, workspace_dir: Path) -> None:
        try:
            file_path.resolve().relative_to(workspace_dir.resolve())
        except ValueError:
            raise ValueError(
                f"Resolved path '{file_path}' escapes workspace "
                f"'{workspace_dir}'",
            ) from None

    def list_documents(self) -> list[dict]:
        documents = sorted(
            self.workspace_dir.glob("*.md"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        result: list[dict] = []
        for path in documents:
            if not path.is_file():
                continue
            stat = path.stat()
            result.append(
                {
                    "filename": path.name,
                    "size": stat.st_size,
                    "path": str(path),
                    "created_time": datetime.fromtimestamp(
                        stat.st_ctime,
                        tz=timezone.utc,
                    ).isoformat(),
                    "modified_time": datetime.fromtimestamp(
                        stat.st_mtime,
                        tz=timezone.utc,
                    ).isoformat(),
                },
            )
        return result

    def read_document(self, name: str) -> str:
        filename = self._sanitize_name(name)
        path = self.workspace_dir / filename
        self._assert_within_workspace(path, self.workspace_dir)
        if not path.exists():
            raise FileNotFoundError(f"Workspace Markdown file not found: {filename}")
        return read_text_file_with_encoding_fallback(path).strip()

    def write_document(self, name: str, content: str) -> None:
        filename = self._sanitize_name(name)
        path = self.workspace_dir / filename
        self._assert_within_workspace(path, self.workspace_dir)
        path.write_text(content, encoding="utf-8")


__all__ = ["WorkspaceMarkdownManager"]
