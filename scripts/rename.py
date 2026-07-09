"""Replace qwenpaw -> minions in all tracked file contents, then rename src directory."""
import subprocess, os, sys
from pathlib import Path

REPO = Path(r"D:\MyProject\QwenPaw")
os.chdir(REPO)

# Patterns to replace (longer first to avoid partial matches)
PAIRS = [
    ("QWENPAW", "MINIONS"),
    ("QwenPaw", "Minions"),
    ("qwenpaw", "minions"),
    ("Qwenpaw", "Minions"),
]

BINARY_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2",
               ".ttf", ".eot", ".zip", ".gz", ".whl", ".pyc", ".pyo", ".pyd",
               ".xsd", ".exe", ".dll", ".so", ".o", ".a"}

TOKENIZER_DIR = REPO / "src" / "qwenpaw" / "tokenizer"
TOKENIZER_FILES = {"merges.txt", "tokenizer.json", "vocab.json", "tokenizer_config.json"}

# Get tracked files
result = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
files = [REPO / f for f in result.stdout.strip().splitlines() if f]

count = 0
for fp in files:
    if fp.suffix in BINARY_EXTS:
        continue
    if fp.name in TOKENIZER_FILES:
        continue
    if not fp.is_file():
        continue
    
    try:
        data = fp.read_bytes()
    except Exception:
        continue
    if b"\x00" in data[:4096]:
        continue
    
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        continue
    
    new_text = text
    for old, new in PAIRS:
        new_text = new_text.replace(old, new)
    
    if new_text != text:
        fp.write_bytes(new_text.encode("utf-8"))
        count += 1

print(f"Updated {count} files.")

# Rename src/qwenpaw -> src/minions
src_old = REPO / "src" / "qwenpaw"
src_new = REPO / "src" / "minions"
if src_old.is_dir() and not src_new.exists():
    src_old.rename(src_new)
    print("Renamed src/qwenpaw/ -> src/minions/")
else:
    print(f"SKIP rename: exists={src_old.is_dir()} target_exists={src_new.exists()}")

print("Done. Run 'git status' to verify.")
