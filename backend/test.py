import os
from pathlib import Path

for line in Path(__file__).with_name(".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    os.environ.setdefault(key.strip(), value.strip().strip("'\""))

from feed_search import search_unified_feed

test = search_unified_feed("Novo Nordisk")
print(test)