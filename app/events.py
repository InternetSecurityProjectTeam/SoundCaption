"""백엔드가 UI로 보내는 소리 이벤트 형식 (Qt 없이 동작)"""
from dataclasses import dataclass
from typing import Optional

_KINDS = {"instant": "instant", "순간음": "instant", "continuous": "continuous", "지속음": "continuous"}
_DIRECTIONS = {
    "left": "left", "왼쪽": "left", "l": "left",
    "right": "right", "오른쪽": "right", "r": "right",
    "center": "center", "가운데": "center", "": "center", "none": "center",
}


@dataclass
class SoundEvent:
    label: str                       # 화면에 보일 이름 (예: "박수")
    kind: str = "instant"            # "instant"(순간음) | "continuous"(지속음)
    key: str = ""                    # 라벨 키 (예: "gunshot"). 소리 필터 sounds_off 와 비교
    category: str = ""               # 분류 코드 (예: "5-8", sound_tree.CATS)
    count: int = 1                   # 폐지 (2026-10-22): 반복 횟수 표시 없음, 항상 1. 예전 코드 호환용으로만 남김
    direction: str = "center"        # "left" | "right" | "center"
    strength: int = 1                # 폐지 (2026-10-22): 굵기 구분 없음, 항상 1. 예전 코드 호환용으로만 남김
    score: float = 0.0               # 우선순위 점수
    confidence: float = 1.0          # 분류 확신도 0~1
    slot: Optional[int] = None       # 백엔드가 칸을 정해 줄 때만 지정

    def __post_init__(self):
        self.kind = _KINDS.get(str(self.kind).strip().lower(), "instant")
        self.direction = _DIRECTIONS.get(str(self.direction).strip().lower(), "center")
        self.count = 1           # 횟수 폐지 — 무엇을 보내도 1
        self.strength = 1        # 굵기 폐지 — 무엇을 보내도 1
        self.label = str(self.label)