#!/usr/bin/env python3
import json
from pathlib import Path


golden_set_path = Path(__file__).resolve().parents[1] / "data" / "golden_set.json"
with golden_set_path.open(encoding="utf-8") as golden_set_file:
    json.load(golden_set_file)

print("0/0 cases")
