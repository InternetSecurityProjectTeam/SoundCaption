"""백엔드가 아직 없을 때 UI를 시험하기 위한 가짜 백엔드"""
import random
import threading
import time

from events import SoundEvent

# (표시명, 라벨 키, 분류 코드) — 키가 지금 모드에 있으면 소리 필터 토글로 끌 수 있음
INSTANT = [
    ("발소리", "footsteps", "1-5"), ("노크", "knock", "5-4"), ("박수", "applause", "1-5"),
    ("문 소리", "door", "5-4"), ("총성", "gunshot", "5-8"), ("비명", "scream", "1-1"),
    ("신호음", "beep", "6-3"),
]
CONTINUOUS = [
    ("차량 소리", "vehicle", "5-1"), ("바람 소리", "wind", "4-1"), ("배경음악", "music", "3-13"),
    ("불 타는 소리", "fire", "4-1"), ("심장 박동", "heartbeat", "1-4"),
]


class FakeBackend(threading.Thread):
    def __init__(self, bridge):
        super().__init__(daemon=True)
        self.bridge = bridge
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        active = {}
        next_instant = time.monotonic() + 0.5
        while not self._stop_event.is_set():
            now = time.monotonic()

            if now >= next_instant:
                label, key, category = random.choice(INSTANT)
                self.bridge.sound_received.emit(SoundEvent(
                    label=label, kind="instant", key=key, category=category,
                    direction=random.choice(["left", "right", "center"]),
                    score=random.random(),
                ))
                next_instant = now + random.uniform(0.6, 1.8)

            if len(active) < 3 and random.random() < 0.05:
                label, key, category = random.choice(CONTINUOUS)
                active.setdefault(label, (key, category, now + random.uniform(4, 12)))

            for label, (key, category, until) in list(active.items()):
                if now >= until:
                    del active[label]
                    continue
                self.bridge.sound_received.emit(SoundEvent(
                    label=label, kind="continuous", key=key, category=category,
                    score=0.3,
                ))

            time.sleep(0.2)