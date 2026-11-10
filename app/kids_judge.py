"""
kids_judge.py — 🧸 아동 모드 판정 (numpy 만 사용, 모델 없이 시험 가능)
공포게임 horror_judge.py v0.11 구조 그대로 (라벨만 kids_labels.py)

라벨 종류마다 검증 장치 (horror_judge 와 같음)
  confirm   : CLAP 합 ≥ CLAP_MIN + AudioSet ≥ as_min  (+ solo_min/solo_cos 대체 경로, impulse_min, veto)
  clap_only : CLAP 합 ≥ CLAP_SOLO_MIN + 절대 검사
  as_only   : AudioSet ≥ plus_min 이면 '+'
  sink      : 확률만 흡수
  음악 분위기 : CLAP 분위기 문장 + AudioSet 분위기 칸이 같을 때만 → 밝은·슬픈·잔잔한·무서운 (+ 노래). 애매하면 배경음악 (v0.13)

v0.38 (2026-11-08) 평탄화 — kids_labels.BASELINE_V38 이 켜져 있으면 실제로 쓰는 길은 셋뿐
  ① 확인형 : 최근 1.5초 CLAP 최고 ≥ min  그리고  AudioSet 칸(합 또는 최고) ≥ as_min  (지금 판도 하나는 넘어야)
  ② '+'    : AudioSet ≥ plus_min (놀람은 Screaming 0.30) — 동물은 CLAP cos ≥ plus_cos 또는 CLAP ≥ plus_clap 도 필요
  ③ 유리   : AudioSet 단독 (Shatter+Breaking+Glass 합 ≥ 0.40)
  공통 거름: veto(그 칸 들리면 거부) · impulse_min(쿵·폭발음 돌발) · 목소리 흡수 · 배경음악 전용 판단
  아래 코드의 solo·as_alt·weak·비명 바꾸기 부분은 라벨에 그 옵션이 없어서 안 탐 (BASELINE_V38 = False 면 예전 그대로)
"""

import collections
import time
import numpy as np

import kids_labels as G

VERSION = "kids v0.70"
# v0.1 (2026-11-05): 공포게임 horror_judge v0.11 복제. 판정 계산은 그대로
#   - 순서: 점수 × 등급 가중치(GRADE_WEIGHT, 1등급 사건 소리를 앞에). 화면에 보내는 점수는 원래 점수 그대로
#   - 같은 소리 3초 쿨다운은 화면 쪽(kids_anim.COOLDOWN_SEC)에서 — 판정은 0.5초마다 그대로 보냄


def impulse_db(stereo, sr):
    """돌발성: 2초 구간에서 가장 센 10ms 순간이 보통 수준(중앙값)보다 몇 dB 튀었는지.
    고음 위주로 보기 위해 샘플 차분(간단한 고역 통과)을 씀"""
    x = np.asarray(stereo, dtype=np.float32)
    if x.ndim == 2:
        x = x.mean(axis=1)
    if x.size < 2:
        return 0.0
    if np.abs(x).max() > 2.0:                                    # int16 그대로 들어온 경우
        x = x / 32768.0
    d = np.diff(x)
    n = max(1, int(sr * 0.01))
    m = len(d) // n
    if m < 4:
        return 0.0
    e = (d[:m * n].reshape(m, n) ** 2).mean(axis=1) + 1e-12
    return float(10 * np.log10(e.max() / np.median(e)))


def level_info(stereo, sr):
    """v0.9: 2초 구간의 (앞 1.5초 소리 크기 dBFS, 마지막 0.5초 소리 크기 dBFS).
    음악이 뚝 끊긴 순간을 잡으려고 (2초 묶음이라 AudioSet 은 끊긴 뒤에도 앞 음악을 계속 들음)"""
    x = np.asarray(stereo, dtype=np.float32)
    if x.ndim == 2:
        x = x.mean(axis=1)
    if np.abs(x).max() > 2.0 if x.size else False:
        x = x / 32768.0
    n = int(sr * 0.5)
    if x.size < n * 2:
        return None
    db = lambda v: float(10 * np.log10(np.mean(v ** 2) + 1e-12))   # noqa: E731
    return db(x[:-n]), db(x[-n:])


def short_name(n):
    return (n or "-").replace(" 음악", "")


def _unit(x):
    x = np.asarray(x, dtype=np.float32)
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-9)


class KidsJudge:
    def __init__(self, encode, scale, csv_names, warn=print):
        """encode(list[str]) -> (N, D) 문장 임베딩, scale = CLAP logit scale, csv_names = AudioSet 527 이름(순서)"""
        # as_only(AudioSet 단독) 라벨은 CLAP 선택지에 넣지 않음 — CLAP 확률을 빼앗지 않게
        self.keys = [k for k, v in G.LABELS.items() if v["kind"] != "as_only"]
        self.scale = float(scale)
        self.groups = G.groups()
        self.kind = {g: G.LABELS[m[0]]["kind"] for g, m in self.groups.items()}
        self.form = {g: G.LABELS[m[0]]["form"] for g, m in self.groups.items()}

        # 라벨 점수 = 그 라벨 문장들 중 '가장 잘 맞는 문장'의 유사도
        self.P = _unit(np.concatenate([encode(G.LABELS[k]["prompts"]) for k in self.keys]))   # (문장 수, D)
        self.owner = np.concatenate([[i] * len(G.LABELS[k]["prompts"]) for i, k in enumerate(self.keys)])
        self.idx = {k: i for i, k in enumerate(self.keys)}
        self.sink = np.array([G.LABELS[k]["kind"] == "sink" for k in self.keys])

        # 음악 분위기 = 배경음악(mood=True) 라벨 문장 중 가장 잘 맞은 문장의 분위기
        #   칸 0 = 일반('배경음악'), 칸 1.. = MUSIC_MOODS 순서
        self.mood_key = next((k for k in self.keys if G.LABELS[k].get("mood")), None)
        self.mood_names = list(getattr(G, "MUSIC_MOODS", {}) or {})
        if self.mood_key and self.mood_names:
            cls_of = {p: 0 for p in getattr(G, "MUSIC_GENERIC", [])}
            for j, n in enumerate(self.mood_names, 1):
                for p_ in G.MUSIC_MOODS[n]:
                    cls_of[p_] = j
            self.mood_rows = np.where(self.owner == self.idx[self.mood_key])[0]
            self.mood_cls = np.array([cls_of.get(p_, 0) for p_ in G.LABELS[self.mood_key]["prompts"]])
        else:
            self.mood_rows = None
        self.mood_shown, self.mood_cand, self.mood_cnt, self.mood_unsure = None, None, 0, 0
        self.mood_diff = 0                                       # v0.6: 표시와 다른 판단 연속 횟수
        self.mood_win = collections.deque(maxlen=64)             # v0.8: 최근 분위기 판단 (다수결)
        self.voice_idx = [i for i, n in enumerate(csv_names) if n in set(getattr(G, "VOICE_AS", []))]
        self.quiet_n, self.quiet_ref = 0, None                   # v0.9: 음악 끊김 (남은 판정 횟수, 끊기기 전 크기)
        self.music_streak = 0                                    # v0.12: 배경음악 연속으로 들린 횟수

        pos = {n: i for i, n in enumerate(csv_names)}
        missing = set()

        def lookup(names):
            out = []
            for n in names:
                if n in pos:
                    out.append(pos[n])
                else:
                    missing.add(n)
            return sorted(set(out))

        self.as_idx = {g: lookup([n for m in mem for n in G.LABELS[m]["audioset"]])
                       for g, mem in self.groups.items()}
        self.speech_idx = lookup(G.SPEECH_AUDIOSET)
        self.veto_idx = {g: lookup([n for m in mem for n in G.LABELS[m].get("veto", [])])
                         for g, mem in self.groups.items()}
        self.held = {}                                           # 지속음 유지: group → [남은 횟수, 마지막 표시]
        self.music_as = [i for g, mem in self.groups.items() if G.LABELS[mem[0]].get("mood")
                         for i in self.as_idx[g]]                # 음악 세기를 볼 AudioSet 칸
        self.csv_names = list(csv_names)
        # v0.13: 음악 전용 판단 — 분위기 칸·노래·징글 AudioSet 칸
        self.mood_as_idx = {m: lookup(n) for m, n in getattr(G, "MOOD_AS", {}).items()}
        self.scary_idx = lookup(getattr(G, "SCARY_AS", []))
        # v0.15: '다른 소리'를 볼 AudioSet 칸 = 음악 칸(Music~Scary music)·말소리·목소리·노래·일반 칸을 뺀 나머지
        skip = set(self.speech_idx) | set(self.voice_idx) | set(lookup(getattr(G, "SING_AS", [])))
        skip |= set(lookup(getattr(G, "MOOD_BUSY_IGNORE", [])))
        if "Music" in pos and "Scary music" in pos:
            skip |= set(range(pos["Music"], pos["Scary music"] + 1))
        self.busy_idx = [i for i in range(len(csv_names)) if i not in skip]
        self.sing_idx = lookup(getattr(G, "SING_AS", []))
        self.jingle_idx = lookup(getattr(G, "JINGLE_AS", []))
        self.m_on, self.m_run, self.m_gap, self.m_off = False, 0.0, 0.0, 1e9
        self.m_vals, self.mood_contra = [], 0
        self.set_hop(1.0)
        if missing:
            warn(f"[아동] AudioSet 에 없는 이름 {len(missing)}개는 무시: {sorted(missing)}")

    # ------------------------------------------------------------------
    @staticmethod
    def combine_audioset(raw):
        """raw: {모델 이름: 527 점수(csv 순서)} → BEATs:PANNs = 0.6:0.4 (하나뿐이면 그대로)"""
        if not raw:
            return None
        beats = [v for n, v in raw.items() if "beat" in n.lower()]
        others = [v for n, v in raw.items() if "beat" not in n.lower()]
        if beats and others:
            return G.BEATS_WEIGHT * np.mean(beats, axis=0) + (1 - G.BEATS_WEIGHT) * np.mean(others, axis=0)
        return np.mean(beats or others, axis=0)

    def set_hop(self, hop):
        """분석 간격(초)에 맞춰 횟수 기준을 초 기준으로 바꿈 (간격 1초면 예전과 똑같음)"""
        self.hop = float(hop)
        self.n_confirm = max(1, int(round(G.MOOD_CONFIRM / self.hop)))   # 1초 → 3회, 0.5초 → 6회 (= 3초)
        self.n_keep = max(1, int(round(G.MOOD_KEEP / self.hop)))
        self.n_first = max(1, int(round(G.MOOD_FIRST / self.hop)))       # 0.5초 → 4회 (= 2초)
        self.n_win = max(1, int(round(G.MOOD_WINDOW / self.hop)))        # 0.5초 → 6회 (= 3초)
        self.n_major = max(1, int(np.ceil(self.n_win * G.MOOD_MAJOR)))   # 6회 중 4회
        self.n_music_start = max(1, int(round(getattr(G, "MUSIC_START_SEC", 0.0) / self.hop)))   # 0.5초 → 3회
        self.n_scary_win = max(1, int(round(getattr(G, "SCARY_WINDOW", 6) / self.hop)))        # 0.5초 → 12회
        self.n_scary = max(1, int(np.ceil(self.n_scary_win * getattr(G, "SCARY_MAJOR", 0.8))))  # 12회 중 10회

    def _hold_n(self, h):
        """라벨 hold(1초 간격 기준 횟수) → 지금 간격의 횟수. 마지막으로 잡힌 뒤 (h-1)초 더 표시"""
        return max(1, int(round((h - 1) / self.hop)) + 1)

    def reset(self):
        """재생이 멈췄을 때(영상 전환·일시정지) 이전 장면 상태를 지움 — 지속음 유지(HOLD)·분위기 표시"""
        self.held.clear()
        self.ev_hist = []                                        # v0.24: 최근 근거
        self.av_hist = []                                        # v0.45: 거부용 최근 5초 AudioSet
        self.last_scream = -1e9                                  # v0.28
        self.quiet_n, self.quiet_ref = 0, None
        self.music_streak = 0
        self.m_on, self.m_run, self.m_gap, self.m_off = False, 0.0, 0.0, 1e9
        self.m_vals, self.mood_contra = [], 0
        self.mood_shown, self.mood_cand, self.mood_cnt, self.mood_unsure = None, None, 0, 0
        self.mood_diff = 0
        self.mood_win = collections.deque(maxlen=64)

    def mood(self, pc, av=None, music_on=True, busy=None):
        """v0.15 -> (분위기 이름 또는 None, 디버그 dict). busy = (다른 소리 이름, 점수) 또는 None
        0.5초마다 한 표 (아래를 다 만족하면 그 분위기, 아니면 None):
          ① 음악이 있음  ② 다른 소리가 크게 안 겹침  ③ CLAP 분위기 1등 ≥ MOOD_CLAP_MIN, 2등보다 MOOD_CLAP_LEAD 앞섬
          ④ '무서운 음악'이면 CLAP ≥ SCARY_CLAP_MIN 이고 AudioSet 무서운·화난 음악 ≥ SCARY_AS_MIN 도
        표시: 최근 MOOD_WINDOW 초(표 없는 칸 포함) 중 MOOD_MAJOR 이상 같은 분위기 → 그 분위기
              ('무서운 음악'은 최근 SCARY_WINDOW 초 중 SCARY_MAJOR 이상)
              표가 MOOD_KEEP 초 넘게 계속 없으면 '배경음악'"""
        if self.mood_rows is None:
            return None, {}
        labels = ["배경음악"] + self.mood_names
        mc = np.full(len(labels), -1.0, dtype=np.float32)
        np.maximum.at(mc, self.mood_cls, pc[self.mood_rows])
        z = self.scale * mc
        mp = np.exp(z - z.max())
        mp /= mp.sum()
        order = np.argsort(-mp)
        p1, p2 = float(mp[order[0]]), float(mp[order[1]])
        clap_mood = labels[order[0]]
        am = {m: (float(av[ix].max()) if av is not None and ix else 0.0) for m, ix in self.mood_as_idx.items()}
        a_ord = sorted(am.items(), key=lambda kv: -kv[1])
        scary_as = float(av[self.scary_idx].max()) if av is not None and self.scary_idx else 0.0
        why = []
        if not music_on:
            why.append("배경음악 없음")
        if busy:
            why.append(f"다른 소리 겹침: {busy[0]} {busy[1]:.2f}")
        if order[0] == 0:
            why.append("CLAP 일반 문장이 1등")
        if p1 < G.MOOD_CLAP_MIN:
            why.append(f"CLAP {p1:.2f}<{G.MOOD_CLAP_MIN}")
        if p1 - p2 < G.MOOD_CLAP_LEAD:
            why.append(f"CLAP 1·2등 차 {p1 - p2:.2f}<{G.MOOD_CLAP_LEAD}")
        if not why and clap_mood == G.SCARY_NAME:
            if p1 < G.SCARY_CLAP_MIN:
                why.append(f"무서운: CLAP {p1:.2f}<{G.SCARY_CLAP_MIN}")
            if scary_as < G.SCARY_AS_MIN:
                why.append(f"무서운: 보조 {scary_as:.2f}<{G.SCARY_AS_MIN}")
        now = None if why else clap_mood

        # v0.16: 떠 있는 분위기와 다른 분위기를 CLAP 이 강하게 말하면 (다른 소리 겹침이 아닐 때) 연속 횟수를 셈
        if (self.mood_shown and music_on and not busy and order[0] != 0 and clap_mood != self.mood_shown
                and p1 >= G.MOOD_CLAP_MIN):
            self.mood_contra += 1
            if self.mood_contra >= getattr(G, "MOOD_CONTRA", 99):
                why.append(f"지금 분위기와 반대 {self.mood_contra}번 → 배경음악")
                self.mood_shown = None
                self.mood_contra = 0
                now = None                                       # v0.18 버그 고침: 바로 새 분위기로 바꾸지 않고 '배경음악'
                self.mood_win.clear()
        else:
            self.mood_contra = 0
        self.mood_win.append(now)                                # 표 없는 칸도 넣음 (최근 N초 중 몇 %)
        if now is None:
            self.mood_unsure += 1
            if self.mood_unsure > self.n_keep:
                self.mood_shown = None
        else:
            self.mood_unsure = 0
            if now != self.mood_shown:
                n_w, need = ((self.n_scary_win, self.n_scary) if now == G.SCARY_NAME
                             else (self.n_win, self.n_major))
                if list(self.mood_win)[-n_w:].count(now) >= need:
                    self.mood_shown = now
        self.mood_cand = now
        top = [(labels[i], float(mp[i])) for i in order[:3]]
        pending = None
        if now and now != self.mood_shown:
            n_w, need = ((self.n_scary_win, self.n_scary) if now == G.SCARY_NAME else (self.n_win, self.n_major))
            pending = f"{now} {list(self.mood_win)[-n_w:].count(now)}/{need}"
        return self.mood_shown, dict(now=top, why=why, pending=pending, unsure=self.mood_unsure,
                                     as_mood=a_ord, scary_as=scary_as)

    def _music_cut(self, level):
        """v0.9: 마지막 0.5초가 앞보다 MUSIC_CUT_DB 이상 작아지면 음악 끊김 → MUSIC_CUT_SEC 동안 배경음악 내림.
        그 사이 마지막 0.5초가 끊기기 전 크기 근처(MUSIC_BACK_DB 이내)로 돌아오면 바로 풀림"""
        if level is None:
            return False
        head, tail = level
        if head - tail >= G.MUSIC_CUT_DB:
            self.quiet_n = max(1, int(round(G.MUSIC_CUT_SEC / self.hop)))
            self.quiet_ref = head
            return True
        if self.quiet_n > 0:
            if tail >= self.quiet_ref - G.MUSIC_BACK_DB:
                self.quiet_n = 0
                return False
            self.quiet_n -= 1
            return True
        return False

    def judge(self, audio_emb, as_raw=None, impulse_db=None, level=None):
        # v0.20: 음악 시작·끊김 시간은 실제 시간으로 셈 (분석이 0.5초가 아니라 0.6~1초마다 돌아 6초가 8초 넘게 걸림)
        _t = time.monotonic()
        _real = _t - self._last_t if getattr(self, "_last_t", None) else self.hop
        self._last_t = _t
        self.dt = max(self.hop, min(_real, 2.0))
        """impulse_db: 돌발성(신호 분석). 없으면(None) 돌발성이 필요한 경로는 막힘"""
        a = _unit(audio_emb).reshape(-1)
        pc = self.P @ a                                          # 문장별 유사도
        cos = np.full(len(self.keys), -1.0, dtype=np.float32)
        np.maximum.at(cos, self.owner, pc)                       # 라벨별 최대
        z = self.scale * cos
        p = np.exp(z - z.max())
        p /= p.sum()
        best_cos = float(cos[~self.sink].max())
        # v0.8: 배경음악을 뺀 확률 — 음악이 크게 깔려 CLAP 이 음악에 쏠릴 때 첨벙 같은 소리를 따로 봄 (ex_music)
        if self.mood_key:
            zx = z.copy()
            zx[[self.idx[m] for m in self.groups[G.LABELS[self.mood_key]["group"]]]] = -np.inf
            px = np.exp(zx - zx.max())
            px /= px.sum()
        else:
            px = p
        clap_ok = best_cos >= G.COS_MIN                          # 절대 검사

        av = self.combine_audioset(as_raw)
        have_as = av is not None
        # v0.24: 최근 EVIDENCE_SEC 초 근거 모으기 — 2초 창이 소리의 어디에 걸리느냐에 따라 점수가 흔들려
        #   CLAP 은 이 판, AudioSet 은 다음 판에서 넘는 일이 잦음 (가스: 기계 0.36 판 ≠ cos 0.24 판). 라벨마다 최근 판들의 최고값으로 판단,
        #   단 지금 판에도 둘 중 하나는 기준을 넘어야 함 (소리가 끝난 뒤 늦게 뜨지 않게)
        if not hasattr(self, "ev_hist"):
            self.ev_hist = []
        self.ev_hist.append((getattr(self, "_last_t", 0.0), p, px, cos, av))
        _ev_sec = getattr(G, "EVIDENCE_SEC", 0.0)
        self.ev_hist = [h for h in self.ev_hist if self.ev_hist[-1][0] - h[0] <= _ev_sec + 1e-6][-4:]
        H = self.ev_hist
        # v0.45: 거부용 긴 기록 (veto_sec — 기침: 3초 안에 물·증기 소리)
        if not hasattr(self, "av_hist"):
            self.av_hist = []
        self.av_hist.append((getattr(self, "_last_t", 0.0), av))
        self.av_hist = [h for h in self.av_hist if self.av_hist[-1][0] - h[0] <= 5.0 + 1e-6]
        speech = float(av[self.speech_idx].max()) if have_as and self.speech_idx else 0.0
        music = float(av[self.music_as].max()) if have_as and self.music_as else None
        voice = max(speech, float(av[self.voice_idx].max()) if have_as and self.voice_idx else 0.0)   # v0.10
        # v0.13: 배경음악 있는지 = AudioSet 음악 점수의 길이 (목소리·CLAP 과 비교 안 함)
        music_cut = self._music_cut(level)
        mstate = None
        asm, jg = 0.0, 0.0
        if self.mood_key and have_as:
            gm = G.LABELS[self.mood_key]["group"]
            asm = float(av[self.as_idx[gm]].max()) if self.as_idx[gm] else 0.0
            jg = float(av[self.jingle_idx].max()) if self.jingle_idx else 0.0
            n_start = G.MUSIC_START_SEC
            if music_cut:
                if self.m_on:
                    self.m_off = 0.0
                self.m_on, self.m_run, self.m_gap = False, 0.0, 0.0
                mstate = "음악 끊김"
            elif self.m_on:
                if asm < getattr(G, "MUSIC_DROP", 0.0):                  # v0.16: 확 떨어지면 바로 내림
                    self.m_on, self.m_run, self.m_gap, self.m_off = False, 0.0, 0.0, 0.0
                    mstate = f"음악 {asm:.2f}<{G.MUSIC_DROP} → 바로 내림"
                elif asm >= G.MUSIC_KEEP:
                    self.m_gap = 0.0
                else:
                    self.m_gap += self.dt
                    if self.m_gap > G.MUSIC_GAP_SEC:
                        self.m_on, self.m_run, self.m_gap, self.m_off = False, 0.0, 0.0, 0.0
                        mstate = f"음악 {asm:.2f}<{G.MUSIC_KEEP} {G.MUSIC_GAP_SEC}초 넘음 → 내림"
                    else:
                        mstate = f"음악 {asm:.2f}<{G.MUSIC_KEEP} ({self.m_gap:.1f}/{G.MUSIC_GAP_SEC}초)"
            else:
                self.m_off += self.dt
                if asm >= G.MUSIC_ON and jg < G.JINGLE_MAX:
                    if self.m_run == 0:
                        self.m_vals = []
                    self.m_run += self.dt + self.m_gap
                    self.m_gap = 0.0
                    self.m_vals.append(asm)
                    nf = max(1, int(round(getattr(G, "MUSIC_FAST_SEC", 99) / self.dt)))
                    recent = self.m_vals[-nf:]
                    fast = (self.m_run >= getattr(G, "MUSIC_FAST_SEC", 99) and len(recent) >= nf
                            and sum(recent) / len(recent) >= G.MUSIC_FAST_AVG and min(recent) >= G.MUSIC_FAST_MIN)
                    if self.m_off <= G.MUSIC_RESUME_SEC or self.m_run >= n_start or fast:
                        self.m_on, self.m_gap = True, 0.0
                    else:
                        mstate = f"시작 확인 {self.m_run:.1f}/{n_start:.0f}초"
                elif self.m_run > 0:
                    self.m_gap += self.dt
                    if self.m_gap > G.MUSIC_GAP_SEC:
                        self.m_run, self.m_gap = 0.0, 0.0
                    why = f"징글·효과음 {jg:.2f}≥{G.JINGLE_MAX}" if jg >= G.JINGLE_MAX else f"음악 {asm:.2f}<{G.MUSIC_ON}"
                    mstate = f"시작 확인 {self.m_run:.1f}/{n_start:.0f}초 ({why})"
        music_on = self.m_on
        mood_name, mood_dbg = None, None                         # v0.15: 분위기는 아래(순간음 판단 뒤)에서

        def name(key):
            L = G.LABELS[key]
            return mood_name if (L.get("mood") and mood_name) else L["name"]

        instant, sustained, tag_scores, rejected = [], [], {}, []
        for g, mem in self.groups.items():
            kind = self.kind[g]
            if kind == "sink":
                continue
            if kind == "as_only":                                # AudioSet 단독: CLAP 은 안 봄
                asg = float(av[self.as_idx[g]].max()) if have_as and self.as_idx[g] else 0.0
                if have_as and self.as_idx[g] and G.LABELS[mem[0]].get("as_sum"):   # v0.23: 유리 Shatter+Breaking
                    asg = min(1.0, float(av[self.as_idx[g]].sum()))
                tag_scores[g] = asg
                pmin = G.LABELS[mem[0]].get("plus_min", G.AS_STRONG)
                # v0.43: 칸 하나만으로 따로 띄우는 기준 (유리: 와장창 Smash, crash 혼자 0.30)
                if have_as and G.LABELS[mem[0]].get("as_or"):
                    if not hasattr(self, "_ci"):
                        self._ci = {n: i for i, n in enumerate(self.csv_names)}
                    for _n, _v in G.LABELS[mem[0]]["as_or"].items():
                        if _n in self._ci and float(av[self._ci[_n]]) >= _v:
                            asg = max(asg, float(av[self._ci[_n]]))
                            pmin = min(pmin, _v)
                if asg >= pmin:
                    item = (g, name(mem[0]), asg, "+")
                    (sustained if self.form[g] == "sustained" else instant).append(item)
                elif asg >= 0.10:
                    rejected.append((G.LABELS[mem[0]]["name"], asg, f"AudioSet 단독 {asg:.2f}<{pmin}"))
                continue
            if G.LABELS[mem[0]].get("mood"):                     # v0.13: 배경음악은 아래 전용 판단으로
                continue
            mi = [self.idx[m] for m in mem]
            pg = float(p[mi].sum())                              # 묶음 합
            def _as_of(avx, g=g, mem=mem):
                if avx is None or not self.as_idx[g]:
                    return 0.0
                if G.LABELS[mem[0]].get("as_sum"):
                    return min(1.0, float(avx[self.as_idx[g]].sum()))
                return float(avx[self.as_idx[g]].max())
            ev = not G.LABELS[mem[0]].get("no_evidence")
            # v0.39: 지금 판 CLAP 1등이 다른 순간 소리(숨김·목소리 포함, 배경음악 제외)면 최근 1.5초 근거를 안 씀
            #   (1초 전 '우는 소리' 점수가 남아, 지금은 환호·웃음·목소리인데 우는 소리가 뜸). 지속음엔 적용 안 함
            if ev and getattr(G, "EVIDENCE_TOP1", False) and self.form[g] != "sustained":
                _tk = self.keys[int(np.argmax(p))]
                _tg = G.LABELS[_tk]["group"]
                if _tg != g and not G.LABELS[_tk].get("mood"):
                    ev = False
            Hx = H if ev else H[-1:]
            pg_h = max(float(h[1][mi].sum()) for h in Hx)
            asg_h = max(_as_of(h[4]) for h in Hx)
            cos_h = max(max(float(h[3][self.idx[k]]) for k in mem) for h in Hx)
            pgs_h = (max(float(h[2][mi].sum()) for h in Hx) if G.LABELS[mem[0]].get("ex_music") else pg_h)
            top = mem[int(np.argmax(p[mi]))]
            asg = float(av[self.as_idx[g]].max()) if have_as and self.as_idx[g] else 0.0
            if have_as and self.as_idx[g] and G.LABELS[mem[0]].get("as_sum"):   # v0.20: 약한 칸 여러 개를 합침 (쉬익: 증기 0.12 + 쉬익 0.10)
                asg = min(1.0, float(av[self.as_idx[g]].sum()))
            tag_scores[g] = asg
            # v0.22: 다른 AudioSet 칸으로 들릴 때 (소화기 → 기계 장치·래칫) — 그 칸 ≥ as_alt_min + CLAP 이 이 소리 쪽(cos)
            alt_ok, alt_v = False, 0.0
            La = G.LABELS[mem[0]]
            if have_as and La.get("as_alt"):
                if not hasattr(self, "_ci"):
                    self._ci = {n: i for i, n in enumerate(self.csv_names)}
                ai_ = [self._ci[n] for n in La["as_alt"] if n in self._ci]
                alt_v = float(av[ai_].max()) if ai_ else 0.0
                alt_cos = max(float(cos[self.idx[k]]) for k in mem)
                alt_vh = max(float(h[4][ai_].max()) if (ai_ and h[4] is not None) else 0.0 for h in Hx)
                a_min, a_cos = La.get("as_alt_min", 1.0), La.get("as_alt_cos", 1.0)
                alt_ok = (alt_vh >= a_min and cos_h >= a_cos) and (alt_v >= a_min or alt_cos >= a_cos)   # v0.24: 최근 판 합침
                alt_v = max(alt_v, alt_vh)

            L = G.LABELS[mem[0]]
            confirm = kind == "confirm" and have_as
            cmin = L.get("min", G.CLAP_MIN if confirm else G.CLAP_SOLO_MIN)
            amin = L.get("as_min", G.AS_FLOOR)
            pmin = L.get("plus_min", G.AS_STRONG)
            # v0.30: 칸별 '+' 기준 (비명 Screaming 0.30 — Gasp 0.30~0.33 은 한숨·대사라 0.40 그대로)
            if have_as and L.get("plus_by"):
                if not hasattr(self, "_ci"):
                    self._ci = {n: i for i, n in enumerate(self.csv_names)}
                for _n, _v in L["plus_by"].items():
                    if _n in self._ci and float(av[self._ci[_n]]) >= _v:
                        pmin = min(pmin, asg)
            # v0.61: CLAP 1등이 배경음악(분위기)이면 CLAP 이 음악에 묻혀 못 들음 → AudioSet 혼자 기준을 plus_mood_min 으로 낮춤 (문)
            if have_as and "plus_mood_min" in L and G.LABELS[self.keys[int(np.argmax(p))]].get("mood"):
                pmin = min(pmin, L["plus_mood_min"])
            # v0.67: CLAP 1등이 배경음악 + 대사 큼 + CLAP 이 이 소리를 못 들음 → AudioSet 혼자 기준을 plus_busy_min 으로 올림 (기침: 대사 속 기침 칸 0.13~0.18 찐빠)
            if have_as and "plus_busy_min" in L and G.LABELS[self.keys[int(np.argmax(p))]].get("mood") \
                    and speech >= L.get("plus_busy_speech", 1.0) and pg < cmin:
                pmin = max(pmin, L["plus_busy_min"])
            if confirm:                                          # 검증 = AudioSet 하한
                # v0.24: 최근 판 최고값끼리 + 지금 판도 하나는 넘음
                passed = pg_h >= cmin and asg_h >= amin and (pg >= cmin or asg >= amin)
                # v0.51: 지금 판 하나만으로 — CLAP 조금 낮아도(alt_min) AudioSet 이 지금 강하게(alt_as) 들으면
                if "alt_min" in L and have_as:
                    passed = passed or (pg >= L["alt_min"] and asg >= L["alt_as"])
                if "alt2_min" in L and have_as:                  # v0.53: CLAP 이 아주 확실하면 AudioSet 은 약해도
                    passed = passed or (pg >= L["alt2_min"] and asg >= L["alt2_as"])
                # v0.65: AudioSet 한 칸(seq_as)이 seq_n 판 연속 seq_min 이상 + 막는 칸(seq_block) 모두 seq_block_max 미만 (우는 소리: Wail · 대사)
                if "seq_as" in L and have_as and not passed:
                    if not hasattr(self, "_ci"):
                        self._ci = {n: i for i, n in enumerate(self.csv_names)}
                    _ia = self._ci.get(L["seq_as"]); _ib = [self._ci[n] for n in L.get("seq_block", []) if n in self._ci]
                    _n = int(L.get("seq_n", 2)); _hs = self.av_hist[-_n:]
                    if _ia is not None and len(_hs) == _n and _hs[-1][0] - _hs[0][0] <= 0.6 * _n + 1e-6 \
                            and all(h_[1] is not None and float(h_[1][_ia]) >= L["seq_min"]
                                    and all(float(h_[1][j]) < L.get("seq_block_max", 1.0) for j in _ib) for h_ in _hs):
                        passed = True
            else:                                                # 검증 = 절대 검사
                passed = clap_ok and pg >= cmin
            # impulse_min — '툭 튀는' 소리여야 하는 라벨 (쾅·점프 스케어)
            imin = L.get("impulse_min")
            imp_fail = passed and imin is not None and (impulse_db is None or impulse_db < imin)
            passed = passed and not imp_fail
            # 확인형인데 AudioSet 이 음악에 묻혀 못 들을 때: CLAP 높음 + 돌발성 + 절대 검사로 대신 확인 (노크)
            # v0.2: solo_cos 가 있으면 전체 최고 cos 대신 '이 라벨 자신의' cos 로 절대 검사
            own_cos = float(cos[self.idx[top]])
            cos_ok = own_cos >= L["solo_cos"] if "solo_cos" in L else clap_ok
            pgs = float(px[mi].sum()) if L.get("ex_music") else pg   # v0.8: 음악 뺀 확률로 대신 확인
            solo = (not passed and confirm and cos_ok and "solo_min" in L and pgs >= L["solo_min"]
                    and pg >= L.get("ex_raw_min", 0.0)                   # v0.11: 음악 뺀 확률이 부풀지 않게 원래 점수도
                    and (not L.get("need_impulse") or (impulse_db is not None
                                                        and impulse_db >= L.get("solo_impulse", G.IMPULSE_MIN_DB)))
                    and (impulse_db is None or impulse_db <= L.get("solo_impulse_max", 1e9))   # v0.18: 장면 전환급 돌발 제외
                    and not (L.get("solo_no_cut") and music_cut)                               # v0.18: 음악 끊김 순간 제외
                    and self.keys[int(np.argmax(p))] not in L.get("weak_block_top", ()))      # v0.27: CLAP 1등이 목소리면 (쉬익 대사)

            # v0.2: 거부 — 키보드 타자처럼 헷갈리는 소리를 AudioSet 이 들으면 표시 안 함
            vg = float(av[self.veto_idx[g]].max()) if have_as and self.veto_idx[g] else 0.0
            if L.get("veto_recent") and have_as and self.veto_idx[g]:   # v0.40: 최근 1.5초 안에 들렸어도 거부 (고양이 뒤 우는 소리)
                vg = max([vg] + [float(h[4][self.veto_idx[g]].max()) for h in H if h[4] is not None])
                if L.get("veto_sec"):
                    _t0 = self.av_hist[-1][0] if self.av_hist else 0.0
                    vg = max([vg] + [float(a_[self.veto_idx[g]].max()) for t_, a_ in self.av_hist
                                     if a_ is not None and _t0 - t_ <= L["veto_sec"] + 1e-6])
            if (passed or solo or (kind == "confirm" and have_as and self.as_idx[g] and asg >= pmin)) and vg >= L.get("veto_min", 1.0) \
                    and not (pg >= L.get("veto_skip_clap", 9.0)):   # v0.45: '+' 길에도 거부 적용 · v0.52: 지금 판 CLAP 이 아주 확실하면 거부 안 함
                rejected.append((G.LABELS[top]["name"], pg, f"거부 AudioSet {vg:.2f}≥{L['veto_min']}"))
                continue
            # v0.2: 분위기 판단이 없으면 표시 안 함 (배경음악)
            if L.get("need_mood") and not mood_name:
                if passed or solo or (kind == "confirm" and have_as and self.as_idx[g] and asg >= pmin):
                    rejected.append((L["name"], max(pg, asg), "분위기 판단 없음"))
                continue

            # v0.8: 말소리가 음악보다 크면 배경음악 표시 안 함
            # v0.10: 말소리 + 끙·웃음 같은 목소리. 걸리면 지속음 유지(1초)도 바로 끊음
            v_low = (g not in self.held and voice >= 0.2 and asg < L.get("voice_music_min", 0.0))
            if L.get("speech_block") and have_as and (voice > asg or v_low):
                self.held.pop(g, None)
                if passed or asg >= pmin or solo:
                    why = (f"목소리 {voice:.2f}>음악 {asg:.2f}" if voice > asg
                           else f"목소리 {voice:.2f} 있는데 음악 {asg:.2f}<{L['voice_music_min']:.2f} (처음 띄울 때)")
                    rejected.append((L["name"], max(pg, asg), why))
                continue
            if passed or solo:
                shown = name(top)
                pn = G.LABELS[top].get("prompt_names")           # v0.7: 1등 문장에 따라 이름만 바꿈
                if pn:
                    rows = np.where(self.owner == self.idx[top])[0]
                    bp = G.LABELS[top]["prompts"][int(np.argmax(pc[rows]))]
                    shown = pn.get(bp, shown)
                item = (g, shown, pg, "*" if have_as and asg >= G.STAR_MIN else "")
            elif alt_ok:
                item = (g, name(mem[0]), alt_v, "+")
            elif (kind == "confirm" and have_as and "weak_as" in L and asg_h >= L["weak_as"] and cos_h >= L["weak_cos"]
                  and self.keys[int(np.argmax(p))] not in L.get("weak_block_top", ())   # v0.26: CLAP 1등이 목소리면 안 씀
                  and (asg >= L["weak_as"] or max(float(cos[self.idx[k]]) for k in mem) >= L["weak_cos"])):
                item = (g, name(mem[0]), asg_h, "+")            # v0.25: 약하지만 두 모델이 같이 가리킴
            elif (kind == "confirm" and have_as and self.as_idx[g] and asg >= pmin
                  and (pgs_h >= L.get("plus_clap", 0.0)              # 동물은 plus_clap 0.10 (v0.13), v0.24 최근 판
                       or ("plus_cos" in L and cos_h >= L["plus_cos"])   # v0.19, v0.24 최근 판
                       or asg >= L.get("plus_strong", 9.0))):   # v0.21: AudioSet 이 아주 확실하면 CLAP 확인 없이
                # AudioSet 혼자 '+' 는 확인형만. v0.9: plus_clap 이 있으면 CLAP(음악 뺀 확률)도 그 소리 쪽이어야
                item = (g, name(mem[0]), asg, "+")
            else:
                if pg >= G.NEAR_MISS:                            # 디버그: 왜 떨어졌는지
                    if pg < cmin:
                        why = f"CLAP {pg:.2f}<{cmin}"
                    elif imp_fail:
                        why = f"돌발 {impulse_db if impulse_db is not None else 0:.0f}dB<{L['impulse_min']:.0f}"
                    elif confirm:
                        why = f"보조 {asg:.2f}<{amin}"
                        if "solo_min" in L and pgs >= L["solo_min"]:
                            why += f", 돌발 {impulse_db if impulse_db is not None else 0:.0f}dB<{L.get('solo_impulse', G.IMPULSE_MIN_DB):.0f}"
                    else:
                        why = f"cos {best_cos:.2f}<{G.COS_MIN}"
                    rejected.append((G.LABELS[top]["name"], pg, why))
                continue
            (sustained if self.form[g] == "sustained" else instant).append(item)

        # 지속음 유지: 한 번 잡힌 지속음은 hold 번 동안 안 잡혀도 계속 표시 (깜빡임 방지)
        seen = {it[0] for it in sustained}
        for it in sustained:
            self.held[it[0]] = [self._hold_n(G.LABELS[self.groups[it[0]][0]].get("hold", G.HOLD_SEC)), it]
        for g in list(self.held):
            if g in seen:
                continue
            self.held[g][0] -= 1
            if self.held[g][0] > 0:
                sustained.append(self.held[g][1])
            else:
                del self.held[g]

        # v0.15: 분위기 — 다른 소리가 크게 겹치면 그 0.5초는 쉼 (순간음 자막이 떴거나, AudioSet 음악 아닌 칸이 큼)
        busy = None
        if instant:
            busy = (instant[0][1], float(instant[0][2]))
        elif have_as and self.busy_idx:
            bi = self.busy_idx[int(np.argmax(av[self.busy_idx]))]
            if av[bi] >= G.MOOD_BUSY_MIN:
                busy = (self.csv_names[bi], float(av[bi]))
        mood_name, mood_dbg = self.mood(pc, av, self.m_on or self.m_run > 0, busy)   # 시작 확인 중에도 미리 봄

        # v0.13: 배경음악 표시 (전용 판단)
        if self.mood_key:
            gm = G.LABELS[self.mood_key]["group"]
            sustained = [it for it in sustained if it[0] != gm]
            self.held.pop(gm, None)
            if self.m_on:
                shown_mood = None if mood_name in getattr(G, "MOOD_HIDDEN", ()) else mood_name   # v0.20: 밝은 음악은 '배경음악'으로
                sustained.append((gm, shown_mood or G.LABELS[self.mood_key]["name"], asm, "*"))
            elif mstate:
                rejected.append(("배경음악", asm, mstate))
            if mood_dbg is not None:
                mood_dbg["show"] = self.m_on or self.m_run > 0
                mood_dbg["jingle"] = jg

        # v0.9: 음악이 뚝 끊기면 🎵 바로 내림 (지속음 유지도 지움, 분위기 기억은 그대로 → 다시 나오면 같은 분위기)
        if music_cut and self.mood_key:
            gm = G.LABELS[self.mood_key]["group"]
            sustained = [it for it in sustained if it[0] != gm]
            self.held.pop(gm, None)
            d = level[0] - level[1] if level else 0.0
            rejected.append(("배경음악", 0.0, f"음악 끊김 {d:.0f}dB" if d >= G.MUSIC_CUT_DB else "음악 끊김 (이어지는 중)"))

        # v0.28: 비명 뒤 '우는 소리' → '깜짝 놀라는 소리'로 이어 띄움 (비명이 멀어졌다 가까워지면 AudioSet 이 아기 울음 0.44 로 들음)
        if have_as and getattr(G, "SCREAM_TO", None):
            if not hasattr(self, "_ci"):
                self._ci = {n: i for i, n in enumerate(self.csv_names)}
            si = [self._ci[n] for n in G.SCREAM_AS if n in self._ci]
            sc = float(av[si].max()) if si else 0.0
            tnow = getattr(self, "_last_t", 0.0)
            if sc >= G.SCREAM_MIN:
                self.last_scream = tnow
            if tnow - getattr(self, "last_scream", -1e9) <= G.SCREAM_SEC:
                sg = G.LABELS[G.SCREAM_TO]["group"]
                changed = False
                for lst in (instant, sustained):
                    for i, it in enumerate(lst):
                        if it[0] in G.SCREAM_FROM:
                            lst[i] = (sg, G.LABELS[G.SCREAM_TO]["name"], it[2], it[3]) if not changed else None
                            changed = True
                    lst[:] = [x for x in lst if x is not None]
                if changed:
                    rejected.append(("엉엉 우는 소리", 0.0, f"비명 뒤 {G.SCREAM_SEC:.0f}초 안 → 깜짝 놀라는 소리로"))
                    seen, inst2 = set(), []
                    for it in instant:                           # 놀람이 이미 있으면 하나만
                        if it[0] == sg and sg in seen:
                            continue
                        seen.add(it[0]); inst2.append(it)
                    instant[:] = inst2

        # v0.8: 양보 — 첨벙·비·파도·변기가 떠 있으면 '물소리'는 빼기 (같은 물을 두 번 안 띄움)
        present = {it[0] for it in instant + sustained}
        def _keep(it):
            yl = G.LABELS[self.groups[it[0]][0]].get("yield_to")
            return not (yl and present.intersection(yl))
        instant = [it for it in instant if _keep(it)]
        sustained = [it for it in sustained if _keep(it)]

        # v0.1: 등급 가중치 순서 (점수 값은 그대로)
        gw = lambda it: it[2] * G.GRADE_WEIGHT.get(G.LABELS[self.groups[it[0]][0]].get("grade", 2), 1.0)   # noqa: E731
        instant.sort(key=lambda x: -gw(x))
        sustained.sort(key=lambda x: -gw(x))
        instant, sustained = instant[:G.MAX_INSTANT], sustained[:G.MAX_SUSTAINED]

        order = np.argsort(-p)[:3]
        rejected.sort(key=lambda x: -x[1])
        # CLAP 1등 라벨에서 가장 잘 맞은 문장 (어느 문장이 소리를 끌어오는지 보려고)
        i0 = int(order[0])
        sidx = np.where(self.owner == i0)[0]
        best_prompt = G.LABELS[self.keys[i0]]["prompts"][int(np.argmax(pc[sidx]))] if len(sidx) > 1 else None
        dbg = dict(best_cos=best_cos, music_cut=music_cut, speech=speech, rejected=rejected, impulse_db=impulse_db, mood=mood_dbg,
                   best_prompt=best_prompt,
                   clap_top=[(G.LABELS[self.keys[i]]["name"], float(p[i]), float(cos[i])) for i in order])
        dbg["watch"] = [(G.LABELS[k]["name"], float(p[self.idx[k]]), float(cos[self.idx[k]]))
                        for k in getattr(G, "WATCH", []) if k in self.idx]
        if have_as:
            ai = np.argsort(-av)[:8]                             # v0.19: 3 → 8등 (못 잡은 소리가 4등 밑에 있었는지 보려고)
            dbg["as_top"] = [(self.csv_names[i], float(av[i])) for i in ai]
        return dict(instant=instant, sustained=sustained, items=instant + sustained,
                    tag_scores=tag_scores, speech=speech, debug=dbg)
