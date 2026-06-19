"""Lint the permanent graph: find superseded documents so they can be forgotten."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class DocRef:
    data_id: str
    name: str


def extract_year(name: str) -> int | None:
    years = re.findall(r"(?:19|20)\d{2}", name)
    return max(int(y) for y in years) if years else None


def topic_key(name: str) -> str:
    base = name.rsplit("/", 1)[-1]
    if base.endswith(".md"):
        base = base[:-3]
    base = re.sub(r"_?(?:19|20)\d{2}", "", base)
    return base.strip("_- ").lower()


def pick_stale_doc_ids(docs: list[DocRef]) -> list[str]:
    """Group docs by topic; within any group that has more than one dated
    version, return the data_ids of every version older than the newest."""
    groups: dict[str, list[DocRef]] = {}
    for d in docs:
        groups.setdefault(topic_key(d.name), []).append(d)

    stale: list[str] = []
    for members in groups.values():
        dated = [(extract_year(m.name), m) for m in members]
        dated = [(y, m) for y, m in dated if y is not None]
        if len(dated) > 1:
            newest = max(y for y, _ in dated)
            stale += [m.data_id for y, m in dated if y < newest]
    return stale
