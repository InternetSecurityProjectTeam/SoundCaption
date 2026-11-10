"""AudioSet 매핑을 모델 출력 인덱스 단위 표로 펼친다.

build_label_table(mids) 에 모델의 인덱스→mid 목록을 넣으면
인덱스마다 (카테고리, 표시명, 계층 깊이, 음성 여부)를 돌려준다.

- PANNs : load_panns_mids()  (class_labels_indices.csv 순서)
- BEATs : 체크포인트 cfg/label_dict 에서 인덱스→mid 목록을 만들어 넣는다
          (예: [checkpoint['label_dict'][i] for i in range(527)])
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .audioset_map import AUDIOSET_MAP, IGNORE, VOICE_CHECK
from .categories import CATEGORIES

DATA = Path(__file__).parent / "data"


@dataclass(frozen=True)
class LabelInfo:
    mid: str
    name: str            # AudioSet 원본 이름
    category: str | None  # None 이면 서비스 대상 아님
    display: str | None   # 구체 표시명 (없으면 카테고리 기본명)
    depth: int           # 온톨로지 깊이 (클수록 구체적)
    ignore_reason: str | None
    is_voice: bool


@lru_cache
def load_csv() -> list[tuple[str, str]]:
    with open(DATA / "class_labels_indices.csv", encoding="utf-8") as f:
        return [(r["mid"], r["display_name"]) for r in csv.DictReader(f)]


def load_panns_mids() -> list[str]:
    return [mid for mid, _ in load_csv()]


@lru_cache
def ontology_depths() -> dict[str, int]:
    """루트에서의 최단 깊이. Dog=2, Bark=3, Bow-wow=4 처럼 구체적일수록 큼."""
    onto = json.load(open(DATA / "ontology.json", encoding="utf-8"))
    by_id = {n["id"]: n for n in onto}
    children = {c for n in onto for c in n.get("child_ids", [])}
    roots = [n["id"] for n in onto if n["id"] not in children]
    depth: dict[str, int] = {}
    frontier = [(r, 0) for r in roots]
    while frontier:
        nid, d = frontier.pop()
        if nid in depth and depth[nid] <= d:
            continue
        depth[nid] = d
        frontier += [(c, d + 1) for c in by_id[nid].get("child_ids", [])]
    return depth


@lru_cache
def name_tables():
    name_to_cat: dict[str, tuple[str, str | None]] = {}
    for cat, items in AUDIOSET_MAP.items():
        for it in items:
            name, disp = (it, None) if isinstance(it, str) else it
            name_to_cat[name] = (cat, disp)
    name_to_ignore = {n: r for r, names in IGNORE.items() for n in names}
    return name_to_cat, name_to_ignore


def build_label_table(mids: list[str]) -> list[LabelInfo]:
    mid_to_name = dict(load_csv())
    depths = ontology_depths()
    name_to_cat, name_to_ignore = name_tables()
    voice = set(VOICE_CHECK)
    table = []
    for mid in mids:
        name = mid_to_name[mid]
        cat, disp = name_to_cat.get(name, (None, None))
        table.append(LabelInfo(
            mid=mid, name=name, category=cat, display=disp,
            depth=depths.get(mid, 0),
            ignore_reason=name_to_ignore.get(name),
            is_voice=name in voice,
        ))
    return table


def display_of(info: LabelInfo) -> str:
    return info.display or CATEGORIES[info.category]["name"]
