"""Shared configuration and source-root primitives for architecture gates."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib
from typing import Any


_IMPORT_PREFIX = re.compile(r"^minions(?:\.[A-Za-z_]\w*)+$")


class ArchitectureError(ValueError):
    """An actionable architecture configuration or ownership error."""


@dataclass(frozen=True)
class PackageRule:
    """Configured import ownership and allowlist for one distribution."""

    imports: tuple[str, ...]
    allows: frozenset[str]


@dataclass(frozen=True)
class SourceRoot:
    """A physical ``src/minions`` directory and its distribution."""

    distribution: str
    path: Path


@dataclass(frozen=True)
class ConfiguredOwnership:
    """A case-equivalent owner match and its canonical-prefix status."""

    prefix: str
    distribution: str
    uses_canonical_prefix: bool


@dataclass(frozen=True)
class ArchitectureConfig:
    """Validated architecture configuration."""

    path: Path
    packages: dict[str, PackageRule]
    active_packages: frozenset[str]
    prefix_owners: tuple[tuple[str, str], ...]

    def configured_owner(self, module: str) -> ConfiguredOwnership | None:
        """Return the longest case-equivalent configured owner and prefix."""
        module_key = namespace_identity_key(module)
        for prefix, distribution in self.prefix_owners:
            prefix_key = namespace_identity_key(prefix)
            if module_key == prefix_key or module_key.startswith(
                f"{prefix_key}."
            ):
                canonical = module == prefix or module.startswith(f"{prefix}.")
                return ConfiguredOwnership(prefix, distribution, canonical)
        return None


def _string_list(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ArchitectureError(
            f"config field {field} must be an array of strings"
        )
    if any(not isinstance(item, str) or not item for item in value):
        raise ArchitectureError(
            f"config field {field} must contain only non-empty strings",
        )
    if len(set(value)) != len(value):
        duplicates = sorted(
            item for item in set(value) if value.count(item) > 1
        )
        raise ArchitectureError(
            f"config field {field} contains duplicate values: {duplicates}",
        )
    return tuple(value)


def _resolve_config_path(root: Path, config_path: Path | None) -> Path:
    if config_path is None:
        return root / "architecture.toml"
    if config_path.is_absolute():
        return config_path
    return root / config_path


def load_architecture_config(
    root: Path,
    config_path: Path | None = None,
) -> ArchitectureConfig:
    """Load and fully validate ``architecture.toml``."""
    path = _resolve_config_path(root, config_path).resolve()
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except FileNotFoundError as exc:
        raise ArchitectureError(f"config file does not exist: {path}") from exc
    except OSError as exc:
        raise ArchitectureError(f"cannot read config {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ArchitectureError(f"malformed config {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ArchitectureError(f"config {path} must contain TOML tables")
    unexpected_tables = sorted(set(data) - {"packages", "workspace"})
    if unexpected_tables:
        raise ArchitectureError(
            f"config {path} has unknown top-level tables: {unexpected_tables}",
        )

    raw_packages = data.get("packages")
    if not isinstance(raw_packages, dict) or not raw_packages:
        raise ArchitectureError(
            f"config {path} requires a non-empty [packages] table"
        )

    packages: dict[str, PackageRule] = {}
    prefix_owners_by_identity: dict[str, tuple[str, str]] = {}
    for distribution, raw_rule in raw_packages.items():
        if not isinstance(distribution, str) or not distribution:
            raise ArchitectureError(
                f"config {path} has an invalid package name"
            )
        if not isinstance(raw_rule, dict):
            raise ArchitectureError(
                f"config package {distribution} must be a table",
            )
        unexpected_fields = sorted(set(raw_rule) - {"imports", "allows"})
        missing_fields = sorted({"imports", "allows"} - set(raw_rule))
        if unexpected_fields or missing_fields:
            raise ArchitectureError(
                f"config package {distribution} must contain exactly imports and "
                f"allows (missing={missing_fields}, unknown={unexpected_fields})",
            )
        imports = _string_list(
            raw_rule["imports"], f"packages.{distribution}.imports"
        )
        allows = _string_list(
            raw_rule["allows"], f"packages.{distribution}.allows"
        )
        if not imports:
            raise ArchitectureError(
                f"config package {distribution} must own at least one import prefix",
            )
        for prefix in imports:
            if _IMPORT_PREFIX.fullmatch(prefix) is None:
                raise ArchitectureError(
                    f"config package {distribution} has invalid minions import prefix "
                    f"{prefix!r}",
                )
            identity = namespace_identity_key(prefix)
            previous = prefix_owners_by_identity.get(identity)
            if previous is not None:
                previous_prefix, previous_distribution = previous
                raise ArchitectureError(
                    f"duplicate import prefixes {previous_prefix!r} "
                    f"({previous_distribution}) and {prefix!r} "
                    f"({distribution}) are case-equivalent",
                )
            for other_identity, owner in prefix_owners_by_identity.items():
                other_prefix, other_distribution = owner
                overlaps = identity.startswith(
                    f"{other_identity}."
                ) or other_identity.startswith(f"{identity}.")
                if overlaps and other_distribution != distribution:
                    raise ArchitectureError(
                        f"overlapping import prefixes {other_prefix!r} "
                        f"({other_distribution}) and {prefix!r} "
                        f"({distribution}) have ambiguous ownership",
                    )
            prefix_owners_by_identity[identity] = (prefix, distribution)
        packages[distribution] = PackageRule(imports, frozenset(allows))

    for distribution, rule in packages.items():
        for target in sorted(rule.allows):
            if target not in packages:
                raise ArchitectureError(
                    f"config package {distribution} allows unknown target {target}",
                )

    workspace = data.get("workspace")
    if not isinstance(workspace, dict):
        raise ArchitectureError(f"config {path} requires a [workspace] table")
    unexpected_workspace = sorted(set(workspace) - {"active_packages"})
    if unexpected_workspace or "active_packages" not in workspace:
        raise ArchitectureError(
            f"config [workspace] must contain exactly active_packages "
            f"(unknown={unexpected_workspace})",
        )
    active = _string_list(
        workspace["active_packages"],
        "workspace.active_packages",
    )
    for distribution in active:
        if distribution not in packages:
            raise ArchitectureError(
                f"workspace active package {distribution} is unknown",
            )

    prefixes = tuple(
        sorted(
            prefix_owners_by_identity.values(),
            key=lambda item: (-len(item[0]), item[0]),
        ),
    )
    return ArchitectureConfig(
        path=path,
        packages=packages,
        active_packages=frozenset(active),
        prefix_owners=prefixes,
    )


def expected_source_root(root: Path, distribution: str) -> Path:
    """Return the conventional source root for a distribution."""
    if distribution == "minions":
        return root / "src" / "minions"
    return root / "packages" / distribution / "src" / "minions"


def discover_source_roots(root: Path) -> dict[str, SourceRoot]:
    """Discover the umbrella root and every ``packages/*`` namespace root."""
    discovered: dict[str, SourceRoot] = {}
    umbrella = expected_source_root(root, "minions")
    if umbrella.is_dir():
        discovered["minions"] = SourceRoot("minions", umbrella.resolve())

    packages_dir = root / "packages"
    if packages_dir.is_dir():
        for member in sorted(
            packages_dir.iterdir(), key=lambda path: path.name
        ):
            if not member.is_dir():
                continue
            source_root = member / "src" / "minions"
            if source_root.is_dir():
                existing = discovered.get(member.name)
                if existing is not None:
                    raise ArchitectureError(
                        f"duplicate source roots for package {member.name}: "
                        f"{existing.path} and {source_root.resolve()}",
                    )
                if member.name == "minions":
                    raise ArchitectureError(
                        f"package minions source root must be "
                        f"{umbrella.resolve()}, not {source_root.resolve()}",
                    )
                discovered[member.name] = SourceRoot(
                    member.name,
                    source_root.resolve(),
                )
    return discovered


def validate_source_roots(
    root: Path,
    config: ArchitectureConfig,
) -> dict[str, SourceRoot]:
    """Require physical source roots to match the active-package set exactly."""
    discovered = discover_source_roots(root)
    for distribution, source_root in discovered.items():
        if distribution not in config.packages:
            raise ArchitectureError(
                f"source root {source_root.path} belongs to unknown package "
                f"{distribution}",
            )
        if distribution not in config.active_packages:
            raise ArchitectureError(
                f"inactive package {distribution} must not have source root "
                f"{source_root.path}",
            )

    for distribution in sorted(config.active_packages):
        if distribution not in discovered:
            expected = expected_source_root(root, distribution).resolve()
            raise ArchitectureError(
                f"active package {distribution} is missing source root {expected}",
            )
    return discovered


def iter_owned_files(source_root: Path):
    """Yield repository-owned files, excluding generated Python caches."""
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source_root)
        if any(
            part.casefold() == "__pycache__" for part in relative.parts
        ) or (path.suffix.casefold() in {".pyc", ".pyo"}):
            continue
        yield path, relative


def is_python_source(path: Path) -> bool:
    """Return whether a path has a Python suffix on any supported filesystem."""
    return path.suffix.casefold() == ".py"


def is_init_module(path: Path) -> bool:
    """Return whether a path is an init module independent of filesystem case."""
    return path.name.casefold() == "__init__.py"


def namespace_identity_key(value: str) -> str:
    """Normalize case without folding one character into several characters."""
    lowered = (character.lower() for character in value)
    return "".join(
        normalized if len(normalized) == 1 else original
        for original, normalized in zip(value, lowered)
    )


def module_name_for_path(source_root: Path, path: Path) -> str:
    """Translate a Python source path below ``src/minions`` to a module name."""
    relative = path.relative_to(source_root)
    parts = list(relative.with_suffix("").parts)
    if parts[-1].casefold() == "__init__":
        parts.pop()
    return ".".join(("minions", *parts))
