"""콘텐츠 장면 추측 (1단계: 판단만 하고 가중치는 아직 안 바꿈)

매초 이미 계산하는 CLAP 오디오 임베딩을 모아서, '지금 어떤 콘텐츠인지'를 장면 문장과 비교해 추측한다.
추가 모델 실행 없음 (임베딩 재사용 + 내적 몇 번).

판단 시점
  - 첫 판단: 소리가 FIRST_SEC 초 쌓였을 때
  - 이후: EVERY_SEC 초마다 최근 WINDOW_SEC 초로 다시 판단 (자주 바뀌면 흔들리므로 천천히)
  - 확신이 MIN_PROB 미만이거나 1·2위 차이가 MIN_MARGIN 미만이면 '판단 보류' (기본 영상 모드 그대로)
  - 재생이 오래 멈추면(RESET_GAP 초) 처음부터 다시 (다음 영상으로 넘어간 경우)
"""
from __future__ import annotations

from collections import deque

import numpy as np

# 장면 문장: 소리의 '전체 분위기'를 묘사 (개별 소리 이름이 아니라 상황)
SCENES = [
    dict(id="cooking", ko="요리·부엌", prompts=[
        "cooking in a kitchen with chopping and sizzling sounds",
        "sounds of preparing food and washing dishes in a kitchen"]),
    dict(id="game_fps", ko="총싸움 게임", prompts=[
        "first-person shooter video game gameplay with gunfire and explosions",
        "battle royale game sounds with gunshots and footsteps"]),
    dict(id="game_horror", ko="공포 게임·공포 영상", prompts=[
        "a scary horror game with creepy ambience and sudden screams",
        "eerie suspenseful horror atmosphere with dark drones"]),
    # 효과음·배경음악은 요즘 거의 모든 영상에 깔려 있어서 단서가 안 됨 → 웃음·반응 위주로
    dict(id="variety", ko="예능", prompts=[
        "a korean variety show with audience laughter and people reacting loudly",
        "a comedy tv show with several people laughing together"]),
    dict(id="vlog_outdoor", ko="야외 브이로그", prompts=[
        "a person walking outdoors filming a vlog with street ambience",
        "outdoor city sounds with traffic, wind and footsteps"]),
    dict(id="home", ko="실내 일상", prompts=[
        "quiet daily life indoors at home with small household sounds",
        "a person moving around a room at home"]),
    dict(id="talk", ko="토크·뉴스·라이브 방송", prompts=[
        "a news anchor reading the news",
        "people talking on a podcast or a live stream"]),
    # '음악' 장면은 뺌: 배경음악은 어느 영상에나 있어 콘텐츠 구분 단서가 아님 (음악 감상 영상은 대상도 아님)
]

FIRST_SEC = 10          # 첫 판단까지 모을 '음악 아닌' 초 수
EVERY_SEC = 30
WINDOW_SEC = 30
MIN_PROB = 0.40
MIN_MARGIN = 0.15
RESET_GAP = 5.0
# 전환 감지: 최근 SHORT_SEC 초가 지금 판단과 다른 장면으로 확실하면, SWITCH_STREAK 번 연속일 때 바로 바꿈
SHORT_SEC = 8
SHORT_MIN_PROB = 0.50
SWITCH_STREAK = 3


def _unit(v):
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-9)


class SceneGuesser:
    def __init__(self, encode, logit_scale=100.0, temperature=0.5):
        """encode(list[str]) -> (N, D). temperature: CLAP 기본 배율은 너무 뾰족해서 낮춰서 씀"""
        self.T = np.stack([_unit(_unit(np.asarray(encode(s["prompts"]), np.float32)).mean(0)) for s in SCENES])
        self.scale = float(logit_scale) * temperature
        self.buf = deque(maxlen=WINDOW_SEC)
        self.n_total = 0
        self.last_t = None
        self.next_at = FIRST_SEC
        self.current = None          # (id, ko, prob) 또는 None(판단 보류)
        self.streak_id, self.streak = None, 0

    def reset(self):
        self.buf.clear()
        self.n_total = 0
        self.next_at = FIRST_SEC
        self.current = None
        self.streak_id, self.streak = None, 0

    def scores(self, last=None):
        items = list(self.buf)[-last:] if last else list(self.buf)
        m = _unit(np.mean(np.stack(items), axis=0))
        z = self.scale * (self.T @ m)
        p = np.exp(z - z.max())
        p /= p.sum()
        order = np.argsort(p)[::-1]
        return [(SCENES[i]["id"], SCENES[i]["ko"], float(p[i])) for i in order]

    def add(self, emb, t, skip=False):
        """emb: 이번 초의 CLAP 오디오 임베딩, t: 초 단위 시각,
        skip: 이번 초가 음악·노래 위주면 True → 장면 판단에 안 넣음 (배경음악은 어느 영상에나 있어서)
        판단을 갱신했으면 결과 dict 반환, 아니면 None"""
        if self.last_t is not None and t - self.last_t > RESET_GAP:
            self.reset()
        self.last_t = t
        if skip:
            return None
        self.buf.append(_unit(np.asarray(emb, np.float32).reshape(-1)))
        self.n_total += 1

        # 1) 전환 감지: 첫 판단 이후, 최근 SHORT_SEC 초가 다른 장면으로 확실하면 연속 횟수를 셈
        if self.n_total >= FIRST_SEC and len(self.buf) >= SHORT_SEC:
            short = self.scores(last=SHORT_SEC)
            (s1, sk1, sp1), (_, _, sp2) = short[0], short[1]
            cur_id = self.current[0] if self.current else None
            if s1 != cur_id and sp1 >= SHORT_MIN_PROB and (sp1 - sp2) >= MIN_MARGIN:
                self.streak = self.streak + 1 if self.streak_id == s1 else 1
                self.streak_id = s1
            else:
                self.streak_id, self.streak = None, 0
            if self.streak >= SWITCH_STREAK:
                kept = list(self.buf)[-SHORT_SEC:]         # 예전 영상 소리는 버리고 새로 쌓음
                self.buf.clear()
                self.buf.extend(kept)
                self.current = (s1, sk1, sp1)
                self.streak_id, self.streak = None, 0
                self.next_at = self.n_total + EVERY_SEC
                return dict(scene=self.current, ranked=short[:3], sure=True, changed=True,
                            seconds=len(self.buf), switch=True)

        # 2) 정기 판단
        if self.n_total < self.next_at:
            return None
        self.next_at = self.n_total + EVERY_SEC
        ranked = self.scores()
        (i1, k1, p1), (_, k2, p2) = ranked[0], ranked[1]
        sure = p1 >= MIN_PROB and (p1 - p2) >= MIN_MARGIN
        prev = self.current
        self.current = (i1, k1, p1) if sure else None
        return dict(scene=self.current, ranked=ranked[:3], sure=sure,
                    changed=(prev and prev[0]) != (self.current and self.current[0]),
                    seconds=len(self.buf), switch=False)


def fmt_scene(u):
    top = " · ".join(f"{k} {p:.2f}" for _, k, p in u["ranked"])
    head = f"장면: {u['scene'][1]}" if u["scene"] else "장면: 판단 보류 (기본 영상 모드)"
    mark = " ← 전환 감지" if u.get("switch") else (" ← 바뀜" if u["changed"] else "")
    return f"[{head}]{mark}   (음악 뺀 최근 {u['seconds']}초 · {top})"
