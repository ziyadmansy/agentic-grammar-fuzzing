#!/usr/bin/env python3
"""Explain every input parson rejected in a repeated-experiment arm.

Each rejected input is checked for the constructs parson is known to refuse
although grammar/JSON.g4 permits them (each confirmed with a minimal document,
see docs/parson-replication.md): a duplicate object key, an escaped NUL
(\\u0000) inside an object key, an unpaired UTF-16 surrogate escape, a zero
integer part followed directly by an exponent (0e5), and a number that
overflows a double. Reads committed results.jsonl files only.

    python3 scripts/parson_rejections.py artifacts/repeated/parson-refined-n15
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

NUMBER = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")
HIGH = re.compile(r"\\u[dD][89abAB][0-9a-fA-F]{2}")
LOW = re.compile(r"\\u[dD][c-fC-F][0-9a-fA-F]{2}")


class DuplicateKey(Exception):
    pass


def _no_duplicates(pairs):
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise DuplicateKey
    return dict(pairs)


def _nul_in_key(value) -> bool:
    if isinstance(value, dict):
        return any("\x00" in key or _nul_in_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_nul_in_key(item) for item in value)
    return False


def _lexical_causes(text: str) -> set[str]:
    """Scan strings for unpaired surrogate escapes and numbers for 0e5/overflow."""
    causes: set[str] = set()
    i = 0
    while i < len(text):
        char = text[i]
        if char == '"':
            j = i + 1
            body = []
            while j < len(text) and text[j] != '"':
                if text[j] == "\\":
                    body.append(text[j : j + 2] if text[j + 1 : j + 2] != "u" else text[j : j + 6])
                    j += 2 if text[j + 1 : j + 2] != "u" else 6
                    continue
                body.append(text[j])
                j += 1
            escaped = "".join(body)
            k = 0
            while k < len(escaped):
                high = HIGH.match(escaped, k)
                if high:
                    if LOW.match(escaped, high.end()):
                        k = high.end() + 6
                        continue
                    causes.add("unpaired surrogate escape")
                    k = high.end()
                    continue
                if LOW.match(escaped, k):
                    causes.add("unpaired surrogate escape")
                    k += 6
                    continue
                k += 1
            i = j + 1
            continue
        if char == "-" or char.isdigit():
            number = NUMBER.match(text, i)
            if number:
                token = number.group(0)
                if re.match(r"-?0[eE]", token):
                    causes.add("zero with exponent (0e5)")
                if math.isinf(float(token)):
                    causes.add("number overflows a double")
                i = number.end()
                continue
        i += 1
    return causes


def explain(raw: bytes) -> set[str]:
    text = raw.decode("utf-8", "replace")
    causes: set[str] = set()
    try:
        value, _ = json.JSONDecoder(object_pairs_hook=_no_duplicates).raw_decode(text)
        if _nul_in_key(value):
            causes.add("NUL in an object key")
    except DuplicateKey:
        causes.add("duplicate object key")
    except ValueError:
        causes.add("no grammar-valid prefix")
    return causes | _lexical_causes(text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("arm_dir", type=Path)
    args = parser.parse_args()

    combined: Counter[str] = Counter()
    any_cause: Counter[str] = Counter()
    status: Counter[str] = Counter()
    for results in sorted(args.arm_dir.glob("run-*/iteration-*/results.jsonl")):
        for line in results.read_text().splitlines():
            record = json.loads(line)
            status[record["status"]] += 1
            if record["status"] != "rejected":
                continue
            causes = explain(bytes.fromhex(record["input_hex"]))
            combined[" + ".join(sorted(causes)) or "UNEXPLAINED"] += 1
            for cause in causes or {"UNEXPLAINED"}:
                any_cause[cause] += 1

    print(f"outcomes: {dict(status)}")
    print("rejected inputs by cause (an input can have several):")
    for cause, count in any_cause.most_common():
        print(f"  {count:6}  {cause}")
    print("exact combinations:")
    for causes, count in combined.most_common():
        print(f"  {count:6}  {causes}")


if __name__ == "__main__":
    main()
