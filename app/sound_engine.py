"""
sound_engine.py — 3모드 통합 엔진 (2026-10-22)

  - 모델(CLAP + PANNs + BEATs)은 시작할 때 '한 번만' 올림. 판정기 3개(총게임·공포·예능)는 미리 다 만들어 둠
  - 분석 1회 = 지금 모드의 판정기 하나만 돌림 (그 모드 sound_live_*.py 를 따로 켠 것과 같은 계산)
  - 판정 로직·라벨 기준값은 각 모드 *_judge.py · *_labels.py 그대로 (이 파일은 계산을 바꾸지 않음)
  - 표시(display): 표시명 · 의성어 · 소리 필터 그룹 — 계산이 끝난 결과에 이름만 붙임
  - 모델 3개 동시 실행 (parallel=True, 기본): CLAP·BEATs·PANNs 를 차례로 돌리던 것을 동시에 → 처리 시간 단축
    같은 입력을 같은 모델에 넣는 것이라 결과는 차례로 돌릴 때와 같음. 비교하려면 parallel=False (CLI --no-parallel)
  - 프론트용 고르기(select_for_front): 프론트 칸 수만큼 위에서 자르고 → 꺼 둔 그룹은 그 자리에서 탈락 (아래 순위로 채우지 않음)

쓰는 곳
  real_backend.py   : 프론트엔드 앱 (main.py) 백엔드 스레드
  sound_live_all.py : 터미널 실행 (--mode gun|horror|variety|kids). 예전 sound_live_gun/horror/variety.py 기능 전부
"""

import copy
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, "soundcap_labels_v1")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
# 예전 예능 폴더 구조(위 폴더에 sound_live.py) 도 찾음 — 이 폴더 파일이 항상 먼저
_PARENT = os.path.dirname(HERE)
for _p in (_PARENT, os.path.join(_PARENT, "soundcap_labels_v1")):
    if _p not in sys.path:
        sys.path.append(_p)

import gun_judge          # noqa: E402
import gun_labels         # noqa: E402
import horror_judge       # noqa: E402
import horror_labels      # noqa: E402
import variety_judge      # noqa: E402
import variety_labels     # noqa: E402
import kids_judge         # noqa: E402
import kids_labels        # noqa: E402

VERSION = "engine v1.1"   # v1.1: 모델 3개 동시 실행

MODES = {
    "gun": dict(title="총게임", icon="🔫", G=gun_labels, J=gun_judge, cls=gun_judge.GunJudge,
                front="FPS", content="총게임"),
    "horror": dict(title="공포게임", icon="👻", G=horror_labels, J=horror_judge, cls=horror_judge.HorrorJudge,
                   front="공포", content="공포게임"),
    "variety": dict(title="예능", icon="📺", G=variety_labels, J=variety_judge, cls=variety_judge.VarietyJudge,
                    front="예능", content="예능"),
    # 2026-11-05: 🧸 아동 모드 (kids_labels.py · kids_judge.py = 공포 판정 구조)
    "kids": dict(title="아동", icon="🧸", G=kids_labels, J=kids_judge, cls=kids_judge.KidsJudge,
                 front="아동", content="아동"),
}
FRONT_TO_MODE = {v["front"]: k for k, v in MODES.items()}     # 프론트 base_mode → 엔진 모드
DIRECTION = {"왼쪽": "left", "오른쪽": "right"}                  # 그 외(중앙·없음)는 center


# ----------------------------------------------------------------------
# 단계별 처리 시간 (sound_live_gun v1.12 Timer 그대로)
# ----------------------------------------------------------------------
class Timer:
    def __init__(self):
        self.cur, self.all, self.order = {}, {}, []

    def add(self, k, dt):
        self.cur[k] = self.cur.get(k, 0.0) + dt
        if k not in self.order:
            self.order.append(k)

    def drop(self):
        self.cur = {}

    def commit(self, models):
        c = self.cur
        msum = 0.0
        for m in models:
            if m in c:
                msum += c[m]
                c[m + "·추론"] = max(0.0, c[m] - c.get(m + "·리샘플", 0.0) - c.get(m + "·전처리", 0.0)
                                     - c.get(m + "·비교", 0.0))
        if "분석 전체" in c:
            c["기타(방향/무음검사)"] = max(0.0, c["분석 전체"] - msum)
        c["합계"] = sum(c.get(k, 0.0) for k in ("캡처 복사", "분석 전체", "돌발성", "판정"))
        for k, v in c.items():
            self.all.setdefault(k, []).append(v)
            if k not in self.order:
                self.order.append(k)
        ms = lambda k: f"{c.get(k, 0.0) * 1000:.0f}"   # noqa: E731
        parts = [f"캡처 {ms('캡처 복사')}"]
        for m in models:
            sub_ = "·".join(f"{s} {ms(m + '·' + s)}" for s in ("리샘플", "전처리", "추론", "비교") if m + "·" + s in c)
            parts.append(f"{m} {ms(m)}({sub_})")
        parts += [f"기타 {ms('기타(방향/무음검사)')}", f"돌발 {ms('돌발성')}", f"판정 {ms('판정')}",
                  f"합계 {ms('합계')}ms"]
        self.cur = {}
        return "⏱ " + " · ".join(parts)

    def summary(self, models):
        keys = ["캡처 복사"]
        for m in models:
            keys += [m, m + "·리샘플", m + "·전처리", m + "·추론", m + "·비교"]
        keys += ["기타(방향/무음검사)", "돌발성", "판정", "출력(화면/기록)", "합계"]
        out = ["[단계별 처리 시간 — 1회(2초 구간)당, ms]",
               f"  {'단계':<22} {'최소':>7} {'평균':>7} {'p95':>7} {'최대':>7}  횟수"]
        for k in keys:
            v = self.all.get(k)
            if not v:
                continue
            a = np.array(v) * 1000
            name = ("   └ " + k.split("·")[1]) if "·" in k else k
            out.append(f"  {name:<22} {a.min():7.1f} {a.mean():7.1f} {np.percentile(a, 95):7.1f} {a.max():7.1f}  {len(a)}")
        return "\n".join(out)


# ----------------------------------------------------------------------
# 엔진: 모델 1회 로딩 + 판정기 3개
# ----------------------------------------------------------------------
class Engine:
    def __init__(self, keys=("clap", "panns", "beats"), normalize=False, hop=0.5, silence=0.003,
                 modes=tuple(MODES), quant=False, check=False, parallel=True, log=print):
        import sound_live as SL
        import sound_live_plus  # noqa: F401  (BEATs 를 sound_live 모델 목록에 등록)
        from soundcap.labels.audioset_index import load_csv

        keys = [k.strip().lower() for k in keys if k.strip()]
        if "clap" not in keys:
            raise SystemExit("CLAP 이 메인이라 --models 에 clap 이 꼭 있어야 합니다.")
        self.SL, self.log = SL, log
        SL.HOP_SEC = float(hop)                   # 판정기 set_hop · 디버그 기록이 이 값을 씀
        SL.SILENCE_PEAK_RMS = float(silence)
        self.keys = keys
        self.csv_names = [n for _, n in load_csv()]

        log(f"[엔진] 모델 불러오는 중 ({','.join(keys)}) — 한 번만 올리고 3모드가 같이 씀")
        self.an = SL.Analyzer(keys, normalize=normalize, quiet=True)
        self.taggers, self.clap = [], None
        for d in self.an.dets:
            if d.kind == "tag":
                self._hook(d)
                self.taggers.append(d)
            elif d.name == "CLAP":
                self.clap = d
        enc, scale = self._clap_encoder()
        self.judges = {}
        for m in modes:
            info = MODES[m]
            G = info["G"]
            moods = f" · 음악 분위기 {len(G.MUSIC_MOODS)}종" if getattr(G, "MUSIC_MOODS", None) else ""
            log(f"[{info['title']}] CLAP 라벨 문장 임베딩 계산 중... (라벨 {len(G.LABELS)}개{moods})")
            j = info["cls"](enc, scale, self.csv_names, warn=log)
            j.set_hop(SL.HOP_SEC)
            self.judges[m] = j

        # CLAP int8 경량화 (총게임 v1.12 기능, 기본 꺼짐) — 이제 3모드 공통
        self.check = check and quant
        self.judges32 = {m: copy.deepcopy(j) for m, j in self.judges.items()} if self.check else {}
        self.fp32_ae, self.chk = None, []
        self.clap_mode = "원래(fp32)"
        if quant:
            self._quantize_clap()
        self.timer = Timer()
        self.models = [d.name for d in self.an.dets]
        self._instrument()
        self._setup_parallel(parallel)
        try:
            import torch
            self.device = "GPU (" + torch.cuda.get_device_name(0) + ")" if torch.cuda.is_available() else "CPU"
        except Exception:
            self.device = "?"
        log(f"[엔진] 준비 완료 · 연산 장치: {self.device} · 분석 간격 {SL.HOP_SEC:.1f}초 · CLAP {self.clap_mode}"
            f" · 모델 {'동시 실행' if self._pool else '차례로 실행'}")

    # ---------------- sound_live_*.py Runner 와 같은 부분 ----------------
    def _hook(self, d):
        pos = {n: i for i, n in enumerate(d.labels)}
        missing = [n for n in self.csv_names if n not in pos]
        if missing:
            raise SystemExit(f"[{d.name}] 라벨 순서를 맞추지 못함 (없는 이름 {len(missing)}개: {missing[:5]})")
        order = np.array([pos[n] for n in self.csv_names])
        orig = d.summarize

        def summarize(scores, d=d, orig=orig, order=order):
            d._raw = np.asarray(scores, dtype=np.float32)[order]
            return orig(scores)
        d.summarize = summarize

    def _clap_encoder(self):
        d = self.clap
        torch = d.torch

        def enc(prompts):
            with torch.no_grad():
                t = d.processor(text=prompts, return_tensors="pt", padding=True)
                t = {k: v.to(d.device) for k, v in t.items()}
                e = d.model.get_text_features(**t)
                e = e if hasattr(e, "norm") else e.pooler_output
            return e.cpu().numpy()
        return enc, float(d.model.logit_scale_a.exp())

    def _quantize_clap(self):
        import torch
        m = self.clap.model
        if self.check:
            self.fp32_audio = (copy.deepcopy(m.audio_model), copy.deepcopy(m.audio_projection))
        qd = torch.ao.quantization.quantize_dynamic if hasattr(torch, "ao") else torch.quantization.quantize_dynamic
        try:
            m.audio_model = qd(m.audio_model, {torch.nn.Linear}, dtype=torch.qint8)
            m.audio_projection = qd(m.audio_projection, {torch.nn.Linear}, dtype=torch.qint8)
        except Exception as e:
            self.log(f"[엔진] CLAP 경량화 실패 → 원래 CLAP 사용 ({e})")
            self.check = False
            return
        # v0.56: BEATs 도 같은 방식으로 (속도시험 11-10: 분석 0.27 → 0.23초, CPU 39 → 33%, 화면 표시 77판 모두 같음)
        beats = ""
        for d in self.an.dets:
            if d.name == "BEATs":
                try:
                    d.model = qd(d.model, {torch.nn.Linear}, dtype=torch.qint8)
                    beats = "+BEATs"
                except Exception as e:
                    self.log(f"[엔진] BEATs 경량화 실패 → 원래 BEATs 사용 ({e})")
        warm = (np.random.randn(int(48000 * self.SL.WINDOW_SEC)) * 0.01).astype(np.float32)
        self.clap.run(warm, 48000)
        self.clap_mode = f"경량화(int8{beats})" + (" + 원래 CLAP 비교" if self.check else "")

    def _instrument(self):
        SL, T = self.SL, self.timer
        cur = threading.local()                  # 모델마다 다른 스레드에서 돌아도 리샘플 시간이 제 모델에 붙게
        orig_res = SL.resample

        def resample(x, a, b):
            t = time.perf_counter()
            r = orig_res(x, a, b)
            m = getattr(cur, "m", None)
            T.add(f"{m}·리샘플" if m else "리샘플", time.perf_counter() - t)
            return r
        SL.resample = resample
        for d in self.an.dets:
            def run(mono, sr, d=d, orig=d.run):
                cur.m = d.name
                t = time.perf_counter()
                try:
                    return orig(mono, sr)
                finally:
                    T.add(d.name, time.perf_counter() - t)
                    cur.m = None
            d.run = run
        if self.clap is not None:
            proc = self.clap.processor

            def processor(*a, **k):
                t = time.perf_counter()
                r = proc(*a, **k)
                T.add("CLAP·전처리", time.perf_counter() - t)
                return r
            self.clap.processor = processor
        if self.check:
            m, fa_fp = self.clap.model, self.fp32_audio
            orig_gaf = m.get_audio_features

            def get_audio_features(**kw):
                out = orig_gaf(**kw)
                t = time.perf_counter()
                qa, qp = m.audio_model, m.audio_projection
                m.audio_model, m.audio_projection = fa_fp
                try:
                    o = orig_gaf(**kw)
                finally:
                    m.audio_model, m.audio_projection = qa, qp
                o = o if hasattr(o, "norm") else o.pooler_output
                self.fp32_ae = (o / o.norm(dim=-1, keepdim=True))[0].detach().cpu().numpy()
                T.add("CLAP·비교", time.perf_counter() - t)
                return out
            m.get_audio_features = get_audio_features

    # ---------------- 모델 동시 실행 ----------------
    def _setup_parallel(self, on):
        """sound_live.Analyzer.analyze 는 모델을 차례로 부름. 그 전에 같은 입력으로 모델들을 동시에 돌려 두고,
        analyze 가 부를 때는 미리 계산한 결과를 돌려줌 (sound_live.py 는 안 고침)"""
        dets = self.an.dets
        self._pool = ThreadPoolExecutor(max_workers=len(dets), thread_name_prefix="model") if on and len(dets) > 1 else None
        self._ready = {}
        for d in dets:
            d._run_real = d.run

            def run(mono, sr, d=d):
                if d.name in self._ready:
                    return self._ready.pop(d.name)
                return d._run_real(mono, sr)
            d.run = run

    def _analyze(self, stereo, sr):
        """an.analyze 와 같은 결과. 모델 입력(mono)도 analyze 와 똑같이 만듦 (무음 검사·음량 맞추기)"""
        SL = self.SL
        if self._pool is not None:
            mono = stereo.mean(axis=1)
            if SL.peak_rms(mono, sr) >= SL.SILENCE_PEAK_RMS:
                if self.an.normalize:
                    gain = min(SL.NORM_MAX_GAIN, SL.NORM_TARGET_PEAK_RMS / (SL.peak_rms(mono, sr) + 1e-9))
                    mono = np.clip(mono * gain, -1.0, 1.0)
                futs = {d.name: self._pool.submit(d._run_real, mono, sr) for d in self.an.dets}
                self._ready = {k: f.result() for k, f in futs.items()}
        try:
            return self.an.analyze(stereo, sr)
        finally:
            self._ready = {}

    # ---------------- 분석 1회 ----------------
    def step(self, stereo, sr, mode):
        """-> None(무음) 또는 dict(res=판정 결과, emb, direction, db, check, mode)"""
        T, J = self.timer, MODES[mode]["J"]
        t = time.perf_counter()
        text, rec = self._analyze(stereo, sr)
        T.add("분석 전체", time.perf_counter() - t)
        if text is None:
            T.drop()
            return None
        emb = self.clap.last_ae[0].cpu().numpy()
        raw = {d.name: d._raw for d in self.taggers if getattr(d, "_raw", None) is not None}
        t = time.perf_counter()
        imp = J.impulse_db(stereo, sr)
        T.add("돌발성", time.perf_counter() - t)
        t = time.perf_counter()
        kw = {"level": J.level_info(stereo, sr)} if hasattr(J, "level_info") else {}   # 아동 v0.9: 음악 끊김
        res = self.judges[mode].judge(emb, raw or None, imp, **kw)
        T.add("판정", time.perf_counter() - t)
        chk = None
        if self.check and self.fp32_ae is not None:
            q = emb / (np.linalg.norm(emb) + 1e-9)
            sim = float(q @ self.fp32_ae)
            r32 = self.judges32[mode].judge(self.fp32_ae, raw or None, imp, **kw)
            names = lambda r: [(n, mk) for _, n, _, mk in r["items"]]   # noqa: E731
            same = names(res) == names(r32)
            self.chk.append((same, sim))
            chk = (same, sim, r32)
            self.fp32_ae = None
        return dict(res=res, emb=emb, direction=rec.get("direction", ""), db=rec.get("db", 0.0),
                    check=chk, mode=mode)

    def check_summary(self):
        if not self.chk:
            return ""
        same = sum(s for s, _ in self.chk)
        sims = np.array([x for _, x in self.chk])
        return (f"[CLAP 경량화 비교] {len(self.chk)}회 중 표시 결과 같음 {same}회 ({same / len(self.chk):.0%})"
                f" · 임베딩 일치 평균 {sims.mean():.4f} · 최저 {sims.min():.4f}")

    # ---------------- 상태 초기화 ----------------
    def pause_reset(self, mode):
        """재생이 멈췄을 때 — 각 모드 CLI 와 똑같이: 공포·예능은 reset(), 총게임은 아무것도 안 함"""
        j = self.judges[mode]
        if hasattr(j, "reset"):
            j.reset()

    def mode_reset(self, mode):
        """모드를 바꿔 들어올 때 — 예전 장면의 지속음·분위기 상태를 지움 (총게임은 지속음 상태 sus)"""
        reset_judge(self.judges[mode])


def reset_judge(j):
    if hasattr(j, "reset"):
        j.reset()
    if hasattr(j, "sus"):
        j.sus.clear()


# ----------------------------------------------------------------------
# 표시: 표시명 · 의성어 · 필터 그룹 (계산 결과에 이름만 붙임)
# ----------------------------------------------------------------------
def _unit(x):
    x = np.asarray(x, dtype=np.float32).reshape(-1)
    return x / (np.linalg.norm(x) + 1e-9)


def _label_cos(judge, key, a):
    rows = np.where(judge.owner == judge.idx[key])[0]
    return float((judge.P[rows] @ a).max())


def _best_prompt(G, judge, key, a):
    """그 라벨 문장 중 지금 소리와 가장 잘 맞는 문장 (판정기와 같은 계산: 문장별 유사도 최대)"""
    if key not in judge.idx:
        return None
    rows = np.where(judge.owner == judge.idx[key])[0]
    return G.LABELS[key]["prompts"][int(np.argmax(judge.P[rows] @ a))]


def _pick_key(G, judge, g, name, mark, a):
    """표시된 항목이 그룹 안 어느 라벨인지. 판정기와 같은 규칙:
    '+'(AudioSet 혼자)는 그룹 첫 라벨, 아니면 이름이 같은 라벨, 이름이 겹치면 CLAP 1등 라벨"""
    mem = judge.groups[g]
    if len(mem) == 1 or mark == "+":
        return mem[0]
    named = [k for k in mem if G.LABELS[k]["name"] == name]
    if len(named) == 1:
        return named[0]
    cand = [k for k in (named or mem) if k in judge.idx]
    if not cand:
        return mem[0]
    return max(cand, key=lambda k: _label_cos(judge, k, a))


def display(mode, judge, res, emb, onoma_on=True):
    """판정 결과 → 화면 항목. -> dict(instant=[...], sustained=[...])
    항목: dict(group, key, name, onoma, text, score, mark, category)
      key     : 그 라벨 키 (소리 필터 sounds_off 와 비교하는 값)
      category: 분류 코드 (라벨의 cat, 예 "5-8")
      name : 표시명 (공포 쾅·쇠사슬처럼 1등 문장에 따라 바뀌는 이름 포함)
      onoma: 의성어 (1등 문장별 의성어 → 없으면 기본 의성어 → 없으면 None)
      text : 의성어 켜짐이면 '표시명 의성어', 꺼짐이면 '표시명'"""
    G = MODES[mode]["G"]
    a = _unit(emb)
    out = {}
    for part in ("instant", "sustained"):
        items = []
        for g, name, score, mark in res[part]:
            key = _pick_key(G, judge, g, name, mark, a)
            L = G.LABELS[key]
            shown, ono = name, None
            if not L.get("mood"):                       # 배경음악(분위기 이름)은 그대로, 의성어 없음
                bp = _best_prompt(G, judge, key, a) if (L.get("prompt_names") or L.get("prompt_onoma")) else None
                shown = L.get("prompt_names", {}).get(bp, name)
                ono = L.get("prompt_onoma", {}).get(bp) or L.get("onoma")
            text = f"{shown} {ono}" if (onoma_on and ono) else shown
            cat = L.get("cat", "")
            items.append(dict(group=g, key=key, name=shown, onoma=ono, text=text, score=float(score),
                              mark=mark, category=cat))
        out[part] = items
    return out


def renamed_res(res, disp):
    """판정 결과의 이름만 화면 이름(text)으로 바꾼 사본 — 터미널 출력·이벤트 기록이 그대로 씀"""
    inst = [(d["group"], d["text"], d["score"], d["mark"]) for d in disp["instant"]]
    sust = [(d["group"], d["text"], d["score"], d["mark"]) for d in disp["sustained"]]
    return dict(res, instant=inst, sustained=sust, items=inst + sust)


def select_for_front(disp, s):
    """프론트 설정 s(settings.normalize 결과)로 보낼 항목 고르기.
    1) 판정 순위(점수순) 그대로 위에서 프론트 칸 수만큼 자름
    2) 그중 소리 필터로 꺼 둔 라벨(s['sounds_off'] 의 라벨 키)은 탈락 — 빈자리를 아래 순위로 채우지 않음 (오답률 때문)
    -> (순간음, 지속음, 탈락)"""
    inst = disp["instant"][:s["instant_slots"]] if s["instant_enabled"] else []
    sust = (disp["sustained"][:s["continuous_slots"]]
            if (s["continuous_enabled"] and s["continuous_slots"] > 0) else [])
    off = set(s.get("sounds_off", ()))
    on = lambda d: d["key"] not in off   # noqa: E731
    dropped = [d for d in inst + sust if not on(d)]
    return [d for d in inst if on(d)], [d for d in sust if on(d)], dropped


def to_events(inst, sust, direction):
    """화면 항목 → 프론트 SoundEvent. 횟수(count)·굵기(strength)는 폐지 → 항상 1"""
    from events import SoundEvent
    dr = DIRECTION.get(direction, "center")
    evs = [SoundEvent(label=d["text"], kind="instant", key=d["key"], category=d["category"], count=1, direction=dr,
                      strength=1, score=d["score"], confidence=1.0) for d in inst]
    evs += [SoundEvent(label=d["text"], kind="continuous", key=d["key"], category=d["category"], count=1, direction="center",
                       strength=1, score=d["score"], confidence=1.0) for d in sust]
    return evs


# ----------------------------------------------------------------------
# 캡처 (sound_live_*.py 와 같음)
# ----------------------------------------------------------------------
STALE_SEC = 0.5     # 이 시간 동안 새 소리가 안 들어오면 '정지' (재생 멈춤·일시정지)


def capture_classes():
    """sound_live.LoopbackCapture 를 쓰는 캡처 클래스들 (윈도우 전용). -> (FreshCapture, RecordingCapture)"""
    import sound_live as SL

    class FreshCapture(SL.LoopbackCapture):
        """윈도우 루프백은 아무것도 재생 안 하면 데이터를 안 보냄 → 마지막 소리를 반복 분석하지 않게 함"""

        def __init__(self, *a, device_name=None, **k):
            self.device_name = device_name      # 설정 capture_target (화면 이름). 기본값이면 윈도우 기본 출력 장치
            self.used_fallback = False          # 고른 장치를 못 찾아 기본 출력 장치로 대신 잡았는지
            super().__init__(*a, **k)
            self.last_t = 0.0

        def _find_loopback_device(self):
            import audio_devices as AD
            lb = AD.find_loopback(self.pa, self.device_name)
            if lb is not None:
                return lb
            if self.device_name and self.device_name != AD.DEFAULT_CAPTURE:
                self.used_fallback = True
            return super()._find_loopback_device()

        def _callback(self, in_data, frame_count, time_info, status):
            self.last_t = time.time()
            return super()._callback(in_data, frame_count, time_info, status)

        def stale(self):
            return time.time() - self.last_t > STALE_SEC

    class RecordingCapture(FreshCapture):
        """+ 들어온 소리를 모아 두었다가 wav 로 저장 (멈춘 동안은 무음으로 채워 시간 맞춤)"""

        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.chunks = []

        def _callback(self, in_data, frame_count, time_info, status):
            now = time.time()
            if self.last_t and now - self.last_t > STALE_SEC:
                gap = int((now - self.last_t) * self.sr)
                self.chunks.append(np.zeros((gap, 2), dtype=np.int16))
            self.chunks.append(np.frombuffer(in_data, dtype=np.int16).reshape(-1, self.channels)[:, :2].copy())
            return super()._callback(in_data, frame_count, time_info, status)

        def save_wav(self, path):
            import soundfile as sf
            if self.chunks:
                sf.write(path, np.concatenate(self.chunks), self.sr, subtype="PCM_16")
                print(f"[저장] {path}  ({sum(len(c) for c in self.chunks) / self.sr:.0f}초)")

    return FreshCapture, RecordingCapture
