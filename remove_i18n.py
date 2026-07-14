#!/usr/bin/env python3
"""
Remove i18n from Minions console - handles both simple t("key") and t("key", { var }) calls.
"""

import json
import re
from pathlib import Path

CONSOLE_DIR = Path(__file__).parent / "console"
LOCALES_FILE = CONSOLE_DIR / "src" / "locales" / "zh.json"


def load_translations() -> dict[str, str]:
    with open(LOCALES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    flat = {}
    def flatten(obj, prefix=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_key = f"{prefix}.{key}" if prefix else key
                flatten(value, new_key)
        else:
            flat[prefix] = str(obj)
    flatten(data)
    return flat


def find_files_with_i18n() -> list[Path]:
    files = []
    for ext in ["*.tsx", "*.ts"]:
        for path in (CONSOLE_DIR / "src").rglob(ext):
            try:
                content = path.read_text(encoding="utf-8")
                if ("react-i18next" in content or
                    "useTranslation" in content or
                    re.search(r'\bt\(["\']', content)):
                    files.append(path)
            except Exception:
                pass
    return files


def split_args(args_str: str) -> list[str]:
    """Split comma-separated arguments, respecting nested braces and strings."""
    args = []
    current = ""
    in_string = None
    brace_depth = 0
    escape_next = False

    for char in args_str:
        if escape_next:
            current += char
            escape_next = False
            continue
        if char == "\\":
            escape_next = True
            current += char
            continue
        if char == in_string:
            current += char
            in_string = None
            continue
        if char in ('"', "'") and in_string is None:
            in_string = char
            current += char
            continue
        if in_string:
            current += char
            continue
        if char in ("{", "["):
            brace_depth += 1
            current += char
            continue
        if char in ("}", "]"):
            brace_depth -= 1
            current += char
            continue
        if char == "," and brace_depth == 0:
            args.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip():
        args.append(current.strip())
    return args


def parse_object_literal(obj_str: str) -> dict[str, str]:
    """Parse a simple JS object literal like { name: var1, count: var2 } into key->var mappings."""
    result = {}
    obj_str = obj_str.strip()
    if obj_str.startswith("{") and obj_str.endswith("}"):
        obj_str = obj_str[1:-1].strip()
    if not obj_str:
        return result

    args = split_args(obj_str)
    for arg in args:
        if ":" in arg:
            key, _, val = arg.partition(":")
            key = key.strip().strip("'\"")
            val = val.strip()
            # Handle defaultValue in objects (e.g., { name: var, defaultValue: "fallback" })
            if key == "defaultValue":
                continue
            result[key] = val
    return result


def escape_for_template(text: str) -> str:
    """Escape text for use inside a template literal (backtick string)."""
    text = text.replace("\\", "\\\\")
    text = text.replace("`", "\\`")
    text = text.replace("${", "\\${")
    text = text.replace("\n", "\\n")
    text = text.replace("\r", "\\r")
    text = text.replace("\t", "\\t")
    return text


def translation_to_template(translation: str, var_map: dict[str, str]) -> str | None:
    """Convert a translation string with {{var}} placeholders to a template literal."""
    if "{{" not in translation:
        return None

    # Replace {{var}} with ${varValue}
    result = translation
    for var_name, var_value in var_map.items():
        result = result.replace("{{" + var_name + "}}", "${" + var_value + "}")

    # Check if any {{}} remain unresolved
    if "{{" in result:
        return None

    return "`" + escape_for_template(result) + "`"


def find_t_call_args(content: str, start: int) -> tuple[str, int] | None:
    """Find the full argument string of a t(...) call starting at the opening paren.
    Returns (args_str, end_position) or None if parsing fails."""
    if start >= len(content) or content[start] != "(":
        return None
    depth = 0
    in_string = None
    escape_next = False
    i = start
    while i < len(content):
        c = content[i]
        if escape_next:
            escape_next = False
            i += 1
            continue
        if c == "\\":
            escape_next = True
            i += 1
            continue
        if c == in_string:
            in_string = None
            i += 1
            continue
        if c in ('"', "'") and in_string is None:
            in_string = c
            i += 1
            continue
        if in_string:
            i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return (content[start + 1:i], i + 1)
        i += 1
    return None


def replace_t_calls_with_vars(content: str, translations: dict[str, str]) -> str:
    """Replace t("key", { var }) calls where translation has {{var}} placeholders."""
    result = []
    i = 0
    while i < len(content):
        # Check for t( or i18n.t( pattern
        m = None
        if i < len(content) - 2 and content[i:i+2] == "t(" and (i == 0 or content[i-1] in " ,({\n\t"):
            m = ("t(", i)
        elif i < len(content) - 6 and content[i:i+6] == "i18n.t(" and (i == 0 or content[i-1] in " ,({\n\t"):
            m = ("i18n.t(", i)

        if m is None:
            result.append(content[i])
            i += 1
            continue

        prefix, start = m
        paren_pos = start + len(prefix) - 1  # position of '('
        parsed = find_t_call_args(content, paren_pos)
        if parsed is None:
            result.append(content[i])
            i += 1
            continue

        args_str, end_pos = parsed
        args = split_args(args_str)

        if len(args) >= 2:
            key_arg = args[0].strip("'\"")
            obj_arg = args[1].strip()

            if obj_arg.startswith("{"):
                translation = translations.get(key_arg)
                if translation and "{{" in translation:
                    var_map = parse_object_literal(obj_arg)
                    if var_map:
                        template_result = translation_to_template(translation, var_map)
                        if template_result is not None:
                            result.append(template_result)
                            i = end_pos
                            continue

        # No replacement - keep original
        result.append(content[i])
        i += 1

    return "".join(result)


def remove_imports(content: str) -> str:
    content = re.sub(
        r'import\s*\{\s*useTranslation\s*\}\s*from\s*["\']react-i18next["\'];?\n?',
        '', content
    )
    return content


def remove_use_translation_calls(content: str) -> str:
    content = re.sub(
        r'const\s*\{\s*t\s*\}\s*=\s*useTranslation\(\);?\n?',
        '', content
    )
    content = re.sub(
        r'const\s*\{\s*t\s*,\s*i18n\s*\}\s*=\s*useTranslation\(\);?\n?',
        '', content
    )
    content = re.sub(
        r'const\s*\{\s*i18n\s*\}\s*=\s*useTranslation\(\);?\n?',
        '', content
    )
    return content


def process_file(file_path: Path, translations: dict[str, str]) -> bool:
    try:
        original = file_path.read_text(encoding="utf-8")
        content = original

        # Replace t("key", { var }) calls with template literals
        content = replace_t_calls_with_vars(content, translations)

        # Remove imports
        content = remove_imports(content)

        # Remove useTranslation() calls
        content = remove_use_translation_calls(content)

        if content != original:
            file_path.write_text(content, encoding="utf-8")
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    print("Loading translations from zh.json...")
    translations = load_translations()
    print(f"Loaded {len(translations)} translation keys")

    print("\nFinding files with i18n...")
    files = find_files_with_i18n()
    print(f"Found {len(files)} files to process")

    modified = 0
    for i, file_path in enumerate(files, 1):
        rel_path = file_path.relative_to(CONSOLE_DIR)
        print(f"[{i}/{len(files)}] Processing {rel_path}...", end=" ")
        if process_file(file_path, translations):
            print("✓")
            modified += 1
        else:
            print("-")

    print(f"\nDone! Modified {modified} files")


if __name__ == "__main__":
    main()
