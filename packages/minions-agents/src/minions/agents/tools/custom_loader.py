# -*- coding: utf-8 -*-
"""Dynamic loader for user-defined custom tools.

Custom tools are plain ``.py`` files placed in
``~/.minions/custom_tools/``.  Each file uses ``@tool_descriptor`` exactly
like a built-in tool.  At startup (and on demand via the API) we import
these files with :mod:`importlib`, which triggers the decorator and
auto-collects the functions into the global registry.

Because the module name is set to ``minions.agents.tools._custom.<name>``,
the functions pass the ``minions.agents.tools.`` prefix filter in
:func:`get_registered_tool_funcs` and are returned alongside built-in tools.

Adding a new tool is therefore as simple as dropping a ``.py`` file into
the directory - no core code changes required.
"""

from __future__ import annotations

import importlib.util
import logging
import re
import sys
from pathlib import Path
from typing import Any

from ...constant import WORKING_DIR

logger = logging.getLogger(__name__)

CUSTOM_TOOLS_DIR: Path = WORKING_DIR / "custom_tools"

# Only allow safe filenames: letters, digits, underscore.  Prevents path
# traversal and weird module names.
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Cap file size to avoid accidentally loading huge files.
_MAX_FILE_BYTES = 256 * 1024  # 256 KB

_LOADED_MODULES: dict[str, Any] = {}


def _ensure_dir() -> None:
    """Create the custom tools directory if it does not exist."""
    CUSTOM_TOOLS_DIR.mkdir(parents=True, exist_ok=True)


def _module_name(stem: str) -> str:
    """Return the fully-qualified module name for a custom tool file."""
    return f"minions.agents.tools._custom.{stem}"


def _validate_name(name: str) -> str:
    """Validate a tool file name (without extension).

    Returns the safe stem.  Raises ``ValueError`` on invalid input.
    """
    if not name or not _SAFE_NAME_RE.match(name):
        raise ValueError(
            f"Invalid tool name {name!r}: use only letters, digits and "
            "underscore, starting with a letter or underscore.",
        )
    return name


def load_custom_tools() -> list[str]:
    """Import every ``.py`` file in the custom tools directory.

    Returns the list of successfully loaded file stems.  Errors in a
    single file are logged and skipped so that one bad tool does not
    break the whole set.
    """
    _ensure_dir()
    loaded: list[str] = []
    for py_file in sorted(CUSTOM_TOOLS_DIR.glob("*.py")):
        stem = py_file.stem
        if not _SAFE_NAME_RE.match(stem):
            logger.warning(
                "Skipping custom tool file with invalid name: %s",
                py_file.name,
            )
            continue
        if _load_one(stem, py_file):
            loaded.append(stem)

    # Register discovered custom tools into agent configs so they show up
    # in the /tools API list and can be toggled in the UI.
    _register_custom_tools_to_config(loaded)

    return loaded


def _register_custom_tools_to_config(loaded_stems: list[str]) -> None:
    """Ensure each loaded custom tool has a BuiltinToolConfig entry.

    Iterates all agent profiles and adds missing custom tool entries
    (default disabled) so the tools appear in the /tools API and UI.
    """
    if not loaded_stems:
        return
    try:
        from ...config.config import BuiltinToolConfig
        from ...config.utils import load_config, load_agent_config, save_agent_config
    except Exception:
        logger.debug("Config modules unavailable, skipping custom tool registration", exc_info=True)
        return

    # Collect tool function names from loaded modules.
    tool_names: list[str] = []
    for stem in loaded_stems:
        mod = _LOADED_MODULES.get(stem)
        if mod is None:
            continue
        for attr in dir(mod):
            fn = getattr(mod, attr, None)
            if callable(fn) and hasattr(fn, "_tool_descriptor"):
                desc = fn._tool_descriptor
                tool_names.append(desc.name)

    if not tool_names:
        return

    try:
        config = load_config()
    except Exception:
        logger.debug("Failed to load config for custom tool registration", exc_info=True)
        return

    changed = False
    for agent_id, ref in config.agents.profiles.items():
        try:
            agent_config = load_agent_config(agent_id)
        except Exception:
            continue

        if agent_config.tools is None:
            continue

        for tname in tool_names:
            if tname not in agent_config.tools.builtin_tools:
                agent_config.tools.builtin_tools[tname] = BuiltinToolConfig(
                    name=tname,
                    enabled=False,
                    description="Custom tool",
                    icon="🔧",
                )
                changed = True

        if changed:
            try:
                save_agent_config(agent_id, agent_config)
            except Exception:
                logger.debug("Failed to save agent config for %s", agent_id, exc_info=True)

    if changed:
        logger.info("Registered custom tools: %s", tool_names)


def _load_one(stem: str, file_path: Path) -> bool:
    """Import a single custom tool file.

    Returns ``True`` on success.  On failure the error is logged and
    ``False`` is returned.  If a module with the same name was previously
    loaded it is removed from ``sys.modules`` first so that re-imports
    pick up the latest file content (hot reload).
    """
    mod_name = _module_name(stem)
    # Remove stale module so reload picks up file changes.
    sys.modules.pop(mod_name, None)
    try:
        spec = importlib.util.spec_from_file_location(mod_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {file_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)
        _LOADED_MODULES[stem] = module
        logger.info("Loaded custom tool: %s", stem)
        return True
    except Exception:
        # Clean up partial import so it doesn't shadow a retry.
        sys.modules.pop(mod_name, None)
        _LOADED_MODULES.pop(stem, None)
        logger.exception("Failed to load custom tool: %s", stem)
        return False


def reload_custom_tool(name: str) -> bool:
    """Re-import a single custom tool file by name (without ``.py``).

    Returns ``True`` on success.  Raises ``FileNotFoundError`` if the
    file does not exist, ``ValueError`` if the name is invalid.
    """
    stem = _validate_name(name)
    file_path = CUSTOM_TOOLS_DIR / f"{stem}.py"
    if not file_path.exists():
        raise FileNotFoundError(f"Custom tool file not found: {stem}.py")
    return _load_one(stem, file_path)


def list_custom_tool_files() -> list[dict[str, Any]]:
    """Return metadata for every custom tool file on disk.

    Each entry has: ``name`` (stem), ``filename``, ``size`` (bytes),
    ``modified_time`` (epoch float).  Does **not** import the files.
    """
    _ensure_dir()
    result: list[dict[str, Any]] = []
    for py_file in sorted(CUSTOM_TOOLS_DIR.glob("*.py")):
        stem = py_file.stem
        if not _SAFE_NAME_RE.match(stem):
            continue
        stat = py_file.stat()
        result.append(
            {
                "name": stem,
                "filename": py_file.name,
                "size": stat.st_size,
                "modified_time": stat.st_mtime,
            },
        )
    return result


def read_custom_tool_file(name: str) -> str:
    """Return the source content of a custom tool file.

    Raises ``FileNotFoundError`` / ``ValueError``.
    """
    stem = _validate_name(name)
    file_path = CUSTOM_TOOLS_DIR / f"{stem}.py"
    if not file_path.exists():
        raise FileNotFoundError(f"Custom tool file not found: {stem}.py")
    return file_path.read_text(encoding="utf-8")


def save_custom_tool_file(name: str, content: str) -> Path:
    """Create or overwrite a custom tool file.

    Returns the path written.  Raises ``ValueError`` for invalid names
    or content exceeding the size limit.
    """
    stem = _validate_name(name)
    if len(content.encode("utf-8")) > _MAX_FILE_BYTES:
        raise ValueError(
            f"Tool file too large: limit is {_MAX_FILE_BYTES} bytes.",
        )
    _ensure_dir()
    file_path = CUSTOM_TOOLS_DIR / f"{stem}.py"
    file_path.write_text(content, encoding="utf-8")
    logger.info("Saved custom tool: %s", stem)
    return file_path


def delete_custom_tool_file(name: str) -> None:
    """Delete a custom tool file and unload its module.

    Raises ``FileNotFoundError`` / ``ValueError``.
    """
    stem = _validate_name(name)
    file_path = CUSTOM_TOOLS_DIR / f"{stem}.py"
    if not file_path.exists():
        raise FileNotFoundError(f"Custom tool file not found: {stem}.py")
    file_path.unlink()
    # Unload the module so the tool function is no longer discovered.
    mod_name = _module_name(stem)
    sys.modules.pop(mod_name, None)
    _LOADED_MODULES.pop(stem, None)
    logger.info("Deleted custom tool: %s", stem)


def is_custom_tool(func: Any) -> bool:
    """Return ``True`` if *func* was loaded from the custom tools dir."""
    mod = getattr(func, "__module__", "")
    return mod.startswith("minions.agents.tools._custom.")
