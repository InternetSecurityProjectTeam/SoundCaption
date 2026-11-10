"""
sound_live_variety.py — 📺 예능 모드 (CLAP + PANNs + BEATs)

2026-10-14 방향 수정: 범용 → 총게임 / 공포게임 / 예능 3모드 특화. 이 파일은 예능 모드.
  - 총게임 모드(sound_live_gun.py gun v1.7) 구조를 그대로 복제
  - v22 의 말소리 거부권, 영상 모드 규칙, 장면 추측, 범용 카테고리 56개 전부 없음
  - 라벨: variety_labels.py (예능 라벨 + 흡수 라벨 + 음악 분위기), 판정: variety_judge.py
  - 터미널 출력 양식은 v22 와 동일

※ sound_live.py, sound_live_plus.py, soundcap_labels_v1 폴더와 같은 폴더에 둘 것
  (모델 로딩·루프백 캡처는 sound_live 그대로)

실행
  python sound_live_variety.py                                     # 실시간
  python sound_live_variety.py --debug                             # + 디버그 정보를 화면에도
  python sound_live_variety.py --file 런닝맨1.wav --csv var.csv    # 파일
  python sound_live_variety.py --eval segments.txt                 # 정답 구간 평가
  python sound_live_variety.py --save 런닝맨1 --content 예능        # 실시간 + wav·이벤트 csv 저장 (O/X 검토)
  python sound_live_variety.py --score                             # O/X 집계
  python sound_live_variety.py --latency-test                      # 지연 시험 (다른 소리는 끄고)
종료: Ctrl + C
"""

import argparse
import csv
import os
import sys
import threading
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "soundcap_labels_v1")):
    if p not in sys.path:
        sys.path.insert(0, p)
# 위 폴더(sound)의 sound_live.py·soundcap_labels_v1 은 맨 뒤에서 찾음 (예능 폴더 파일이 항상 먼저)
PARENT = os.path.dirname(HERE)
for p in (PARENT, os.path.join(PARENT, "soundcap_labels_v1")):
    if p not in sys.path:
        sys.path.append(p)

import sound_live as SL                      # noqa: E402
import sound_live_plus  # noqa: E402,F401   (BEATs 를 sound_live 모델 목록에 등록)
from soundcap.labels.audioset_index import load_csv                    # noqa: E402

import variety_labels as G                   # noqa: E402
import variety_judge                         # noqa: E402
from variety_judge import VarietyJudge       # noqa: E402

VERSION = "variety v0.15"
# v0.15 (A판 v0.14 + B판 v0.14 의 속도 개선 합침)
#   - 음악 분위기에 AudioSet 분위기 라벨 가산점 (A판 v0.14 그대로, 디버그 'AudioSet 분위기' 줄)
#   - 분석 간격 1초 → 0.5초 (--hop, 기본 0.5). 기다리는 시간이 평균 0.5초 → 0.25초
#     지속음 유지·분위기 바꿈 규칙은 초 기준으로 맞춤 (variety_judge.set_hop). 시각 표시에 0.1초 단위
#   - 단계별 처리 시간: 디버그 기록 매 줄 아래 '⏱' 줄, 끝낼 때(Ctrl+C) 최소·평균·p95·최대 표
#   - --latency-test N: 시험음('딱')을 N번(기본 30) 재생해 소리 → 터미널 전 단계를 실측 (csv 저장)
#   - 위 폴더(sound)의 sound_live.py·soundcap_labels_v1 도 찾음
#   - 표시 이름 '땡 부저' → '오답' ('쾅 치는 소리'는 그대로)
# v0.14 (A판): 음악 분위기에 AudioSet 분위기 라벨(Scary/Happy/Funny/Sad/Tender music) 가산점
# v0.12 (10차 테스트 반영)
#   - 쾅 치는 소리: 클랩 전용 → 확인형 (AudioSet 둔탁음 0.10 이상 필요). 돌발성 15dB 조건은 유지
# v0.11 (9차 테스트 반영)
#   - '딩동 소리' 삭제 → 문장은 효과음으로 (예능 효과음이 계속 딩동으로 뜸), 초인종은 AudioSet 단독 '초인종'
# v0.10 (8차 테스트 반영)
#   - 땡 부저·딩동: CLAP + 돌발성만으로 뜨는 경로 삭제, AudioSet 확인 필요 (쨍그랑·띠링 효과음이 땡·딩동으로)
#   - 효과음에 '반짝이는 띠링' 문장 추가
# v0.9 (7차 테스트 반영)
#   - 배경음악: AudioSet 혼자 0.45, CLAP 이 잡아도 Music 0.20 이상 (음악 없는 대화에 배경음악)
#   - 박수·환호: AudioSet 하한 0.20 (관객 웃음·외침에 박수·환호)
#   - 문 소리: Slam 삭제·0.35 / 새 라벨 '쾅 치는 소리'(책상 내리침)
#   - 땡 부저 등 돌발성 대체 경로도 절대 검사 필요 (잡음에 땡 부저)
# v0.8 (6차 테스트 반영)
#   - 코믹 + 신나는 → '경쾌한 음악'
#   - 배경음악은 끝나면 바로 내림 (3초 유지 없음)
#   - 발소리: AudioSet 'Run' 삭제, CLAP 0.35 (대화 중 발소리 오표시)
# v0.7 (5차 테스트 반영)
#   - 'dun dun dun sting' 을 분위기 투표에서 뺌 (같은 코믹 곡의 드럼 한 방에 긴장으로 바뀜)
#   - 전화벨: AudioSet 혼자 기준 0.50 (예능 '띠리링' 효과음이 전화벨로 뜸)
# v0.6 (4차 테스트 반영)
#   - 코믹 문장 'silly bouncy cartoon' 삭제 (거의 모든 배경음악을 코믹으로 끌어감), 긴장에 'sneaky suspenseful' 추가
#   - 분위기 바꿈: 연속 3번 또는 0.85 이상 (코믹 중 신나는 깜빡임)
#   - 환호: CLAP 0.25 + AudioSet 0.10 이상 (관객 반응에 웃음/환호 번갈아 뜸)
# v0.5 (3차 테스트 반영)
#   - 분위기 '판단 없음'(말소리·웃음이 클 때)은 표시를 그대로 둠 — 배경음악 ↔ 코믹 깜빡임 해결. 5초 넘게 모르면 배경음악
#   - 확률 0.70 이상인 분위기 판단은 바로 교체 (코믹이 늦게 뜨던 문제)
# v0.4 (2차 테스트 반영)
#   - 분위기: 따로 둔 분위기 문장 비교 → 배경음악 라벨 안에서 가장 잘 맞은 문장의 분위기로 (같은 코믹 음악에 코믹·신남·긴장 오가던 문제)
#   - 표시 이름은 같은 판단이 연속 2번이어야 바뀜 (배경음악·코믹·신남 깜빡임). 재생 멈추면 초기화
# v0.3
#   - 음악 분위기 누적 삭제 → 이번 2초만 (영상 전환·앞으로 넘기기 대응). 음악이 말소리보다 0.15 이상 크고
#     1등이 2등보다 0.10 이상 앞설 때만 분위기 이름, 아니면 '배경음악'
#   - 재생이 멈추면(영상 전환·일시정지) 지속음 유지(3초)를 초기화
# v0.2 (첫 예능 테스트 반영)
#   - 효과음: 긴장 배경음악에 13초 연속으로 뜸 → 'dun dun dun' 문장을 배경음악으로 옮김, 기준 0.35, 돌발성 ≥ 12dB 필요
#   - 배경음악에 긴장·극적·코믹 배경음악 문장 추가
#   - 음악 분위기: 말소리가 크면 거의 항상 '코믹한' → 음악이 말소리보다 클 때만 누적 (v0.3에서 누적 삭제)
#   - 디버그: CLAP 1등 라벨의 가장 잘 맞은 문장「…」, 분위기는 이번/누적/신뢰도
# v0.1 (2026-10-14): 총게임 gun v1.7 구조 복제
#   - 라벨: 웃음·박수·환호·비명·울음·딩동·부저·효과음·노크·문·전화벨·발소리·폭죽(AudioSet 단독)
#     지속음: 배경음악(분위기 이름)·노래 / 흡수: 목소리·방송 배경 소음·기타
#   - 배경음악 분위기: 메인 선택지와 별도로 분위기 문장끼리 비교 → '긴장감 있는 음악' 등. 애매하면 '배경음악'
#   - 디버그 기록에 음악 분위기 상위 3개
CSV_NAMES = [n for _, n in load_csv()]


# ----------------------------------------------------------------------
# sound_live 의 모델을 그대로 돌리고, 원본 점수만 옆에서 받아옴
# ----------------------------------------------------------------------
class Timer:
    """v1.11c: 단계별 처리 시간. cur = 이번 1회, all = 누적 (ms 로 보여 줌)"""

    def __init__(self):
        self.cur, self.all, self.order = {}, {}, []

    def add(self, k, dt):
        self.cur[k] = self.cur.get(k, 0.0) + dt
        if k not in self.order:
            self.order.append(k)

    def drop(self):
        self.cur = {}

    def commit(self, models):
        """이번 1회를 누적에 넣고 '⏱' 한 줄을 돌려줌. models: 모델 이름 순서"""
        c = self.cur
        msum = 0.0
        for m in models:
            if m in c:
                msum += c[m]
                c[m + "·추론"] = max(0.0, c[m] - c.get(m + "·리샘플", 0.0) - c.get(m + "·전처리", 0.0))
        if "분석 전체" in c:
            c["기타(방향/무음검사)"] = max(0.0, c["분석 전체"] - msum)
        c["합계"] = sum(c.get(k, 0.0) for k in ("캡처 복사", "분석 전체", "돌발성", "판정"))
        for k, v in c.items():
            self.all.setdefault(k, []).append(v)
            if k not in self.order:
                self.order.append(k)
        ms = lambda k: f"{c.get(k, 0.0) * 1000:.0f}"  # noqa: E731
        parts = [f"캡처 {ms('캡처 복사')}"]
        for m in models:
            sub_ = "·".join(f"{s} {ms(m + '·' + s)}" for s in ("리샘플", "전처리", "추론") if m + "·" + s in c)
            parts.append(f"{m} {ms(m)}({sub_})")
        parts += [f"기타 {ms('기타(방향/무음검사)')}", f"돌발 {ms('돌발성')}", f"판정 {ms('판정')}",
                  f"합계 {ms('합계')}ms"]
        self.cur = {}
        return "⏱ " + " · ".join(parts)

    def summary(self, models):
        keys = ["캡처 복사"]
        for m in models:
            keys += [m, m + "·리샘플", m + "·전처리", m + "·추론"]
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


class Runner:
    def __init__(self, keys, normalize):
        if "clap" not in keys:
            raise SystemExit("예능 모드는 CLAP 이 메인이라 --models 에 clap 이 꼭 있어야 합니다.")
        self.an = SL.Analyzer(keys, normalize=normalize, quiet=True)
        self.taggers, self.clap = [], None
        for d in self.an.dets:
            if d.kind == "tag":
                self._hook(d)
                self.taggers.append(d)
            elif d.name == "CLAP":
                self.clap = d
        n = len(G.LABELS)
        print(f"[예능] CLAP 라벨 문장 임베딩 계산 중... (라벨 {n}개 · 음악 분위기 {len(G.MUSIC_MOODS)}종)")
        enc, scale = self._clap_encoder()
        self.judge = VarietyJudge(enc, scale, CSV_NAMES)
        self.judge.set_hop(SL.HOP_SEC)                           # 규칙을 초 기준으로
        self.clap_mode = "원래(fp32)"
        self.timer = Timer()
        self.models = [d.name for d in self.an.dets]
        self._instrument()
        try:
            import torch
            self.device = "GPU (" + torch.cuda.get_device_name(0) + ")" if torch.cuda.is_available() else "CPU"
        except Exception:
            self.device = "?"
        print(f"[예능] 준비 완료 · 연산 장치: {self.device} · 분석 간격 {SL.HOP_SEC:.1f}초")

    @staticmethod
    def _hook(d):
        pos = {n: i for i, n in enumerate(d.labels)}
        missing = [n for n in CSV_NAMES if n not in pos]
        if missing:
            raise SystemExit(f"[{d.name}] 라벨 순서를 맞추지 못함 (없는 이름 {len(missing)}개: {missing[:5]})")
        order = np.array([pos[n] for n in CSV_NAMES])
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

    def _instrument(self):
        """v1.11c: sound_live 는 안 고치고, 모델 실행·리샘플·CLAP 전처리를 감싸서 시간만 잼"""
        T, cur = self.timer, {"m": None}
        orig_res = SL.resample

        def resample(x, a, b):
            t = time.perf_counter()
            r = orig_res(x, a, b)
            T.add(f"{cur['m']}·리샘플" if cur["m"] else "리샘플", time.perf_counter() - t)
            return r
        SL.resample = resample
        for d in self.an.dets:
            def run(mono, sr, d=d, orig=d.run):
                cur["m"] = d.name
                t = time.perf_counter()
                try:
                    return orig(mono, sr)
                finally:
                    T.add(d.name, time.perf_counter() - t)
                    cur["m"] = None
            d.run = run
        if self.clap is not None:
            proc = self.clap.processor

            def processor(*a, **k):
                t = time.perf_counter()
                r = proc(*a, **k)
                T.add("CLAP·전처리", time.perf_counter() - t)
                return r
            self.clap.processor = processor

    def step(self, stereo, sr):
        """-> None(무음) 또는 dict(var=판정 결과, direction, db)"""
        T = self.timer
        t = time.perf_counter()
        text, rec = self.an.analyze(stereo, sr)
        T.add("분석 전체", time.perf_counter() - t)
        if text is None:
            T.drop()
            return None
        emb = self.clap.last_ae[0].cpu().numpy()
        raw = {d.name: d._raw for d in self.taggers if getattr(d, "_raw", None) is not None}
        t = time.perf_counter()
        imp = variety_judge.impulse_db(stereo, sr)
        T.add("돌발성", time.perf_counter() - t)
        t = time.perf_counter()
        res = self.judge.judge(emb, raw or None, imp)
        T.add("판정", time.perf_counter() - t)
        return dict(var=res, direction=rec.get("direction", ""), db=rec.get("db", 0.0))


# ----------------------------------------------------------------------
# 출력 (v22 와 같은 양식)
# ----------------------------------------------------------------------
ARROW = {"왼쪽": "◀", "오른쪽": "▶", "중앙": " "}


def _star(res, c, mk):
    """'*' 옆에 보조(AudioSet) 점수 — 두 모델이 같이 틀린 경우 원인 확인용"""
    return f"(보조 {res.get('tag_scores', {}).get(c, 0.0):.2f})" if mk == "*" else ""


def fmt22(res):
    s = ", ".join(f"[{n}]{mk} {sh:.2f}{_star(res, c, mk)}" for c, n, sh, mk in res["instant"]) or "-"
    if res["sustained"]:
        s += "   | 지속: " + " · ".join(f"{n}{mk} {sh:.2f}{_star(res, c, mk)}" for c, n, sh, mk in res["sustained"])
    return s


def fmt_debug(res):
    d = res["debug"]
    top = [f"{n} {p:.2f}" for n, p, c in d["clap_top"]]
    if d.get("best_prompt"):
        top[0] += f"「{d['best_prompt']}」"
    s = (f"         └ CLAP: " + " / ".join(top)
         + f"  · 최고 cos {d['best_cos']:.2f}" + ("" if d["best_cos"] >= G.COS_MIN else " (기준 미달)"))
    if "as_top" in d:
        s += ("\n         └ AudioSet: " + " / ".join(f"{n} {v:.2f}" for n, v in d["as_top"])
              + f"  · 말소리 {d['speech']:.2f}")
    if d.get("impulse_db") is not None:
        s += f"  · 돌발 {d['impulse_db']:.0f}dB"
    m = d.get("mood")
    if m and any(c == "music" for c, *_ in res["sustained"]):
        short = lambda v: " / ".join(f"{n.replace(' 있는', '').replace(' 음악', '')} {p:.2f}" for n, p in v)  # noqa: E731
        s += (f"\n         └ 음악 분위기: {short(m['now'])}"
              + (f"  · 음악−말소리 {m['gap']:.2f}" if m.get("gap") is not None else "")
              + (f"  → 이번 판단 없음 ({', '.join(m['why'])})" if m.get("why") else "")
              + (f"  · 표시 유지 {m['unsure'] * SL.HOP_SEC:.1f}초째 ({G.MOOD_KEEP}초 넘으면 배경음악)" if m.get("unsure") else "")
              + (f"  · 바뀌는 중: {m['pending']} ({G.MOOD_CONFIRM}초 연속 또는 {G.MOOD_STRONG} 이상)" if m.get("pending") else ""))
        if m.get("as_mood"):                                  # v0.14: AudioSet 분위기 점수 (MOOD_AS_W 조정용)
            s += f"\n         └ AudioSet 분위기: {short(m['as_mood'])}  (가산 ×{G.MOOD_AS_W})"
    if d.get("rejected"):
        s += "\n         └ 탈락: " + ", ".join(f"{n} ({why})" for n, p, why in d["rejected"])
    return s


def line(o):
    """화살표는 표시할 소리가 있을 때만"""
    res = o["var"]
    arrow = ARROW.get(o["direction"], " ") if res["items"] else " "
    return f"{arrow} " + fmt22(res)


MARK_BACK = 3       # 스페이스바를 누르면 직전 몇 초의 결과를 ★ 파일에 모을지


class DebugLog:
    """화면은 깔끔하게, 디버그 정보는 파일에 자동 저장
      <이름>.txt       : 전체 기록 (디버그 포함) + 스페이스바 누른 곳에 ★ 줄
      <이름>_★.txt     : 스페이스바 누른 순간의 직전 3초만 (디버그 포함) ← 보통 이것만 첨부"""

    def __init__(self, path):
        from collections import deque
        self.path = path
        self.mark_path = os.path.splitext(path)[0] + "_★.txt"
        self.f = open(path, "w", encoding="utf-8")
        self.mf = None
        self.recent = deque(maxlen=max(MARK_BACK, int(round(MARK_BACK / SL.HOP_SEC))))   # 초 기준
        self.marks = 0

    def write(self, text):
        self.f.write(text + "\n")
        self.f.flush()

    def block(self, text):
        """한 번의 분석 결과(결과 줄 + 디버그 줄)"""
        self.write(text)
        self.recent.append(text)

    def mark(self, stamp):
        self.marks += 1
        self.write(f"★★★ {stamp} 표시 #{self.marks} ★★★")
        if self.mf is None:
            self.mf = open(self.mark_path, "w", encoding="utf-8")
        self.mf.write(f"===== ★ #{self.marks}  {stamp} 에 누름 — 직전 {len(self.recent) * SL.HOP_SEC:.1f}초 =====\n")
        for b in self.recent:
            self.mf.write(b + "\n")
        self.mf.write("\n")
        self.mf.flush()
        print(f"         ★ #{self.marks} 저장 (직전 {len(self.recent) * SL.HOP_SEC:.1f}초)")

    def close(self):
        self.f.close()
        print(f"\n[디버그 기록] 전체: {os.path.abspath(self.path)}")
        if self.mf:
            self.mf.close()
            print(f"[디버그 기록] ★ 표시만: {os.path.abspath(self.mark_path)}  ({self.marks}개) ← 이 파일을 첨부하면 됨")


def poll_marks(dlog):
    """윈도우 콘솔에서 스페이스바(또는 Enter)를 누르면 그 순간을 표시. 다른 OS 에서는 그냥 넘어감"""
    try:
        import msvcrt
    except ImportError:
        return
    while msvcrt.kbhit():
        ch = msvcrt.getwch()
        if ch in (" ", "\r"):
            dlog.mark(time.strftime("%H:%M:%S"))


def show(prefix, o, debug, dlog=None, timing=None):
    text = prefix + line(o)
    print(text)
    tl = f"\n         └ {timing}" if timing else ""
    if debug:
        print(fmt_debug(o["var"]) + tl)
    if dlog:
        dlog.block(text + "\n" + fmt_debug(o["var"]) + tl)


# ----------------------------------------------------------------------
# 정답 구간 평가 (--eval segments.txt)
# ----------------------------------------------------------------------
def parse_segments(path):
    items = []
    with open(path, encoding="utf-8-sig") as f:
        for ln, raw in enumerate(f, 1):
            s = raw.split("#")[0].strip()
            if not s:
                continue
            parts = s.split()
            if len(parts) < 3 or parts[-1].count("-") != 1:
                print(f"  건너뜀({ln}번째 줄): {s}")
                continue
            a, b = parts[-1].split("-")
            items.append(dict(label=parts[0], file=" ".join(parts[1:-1]), s=float(a), e=float(b)))
    return items


def run_eval(runner, seg_path, csv_path, debug):
    items = parse_segments(seg_path)
    cache, rows = {}, []
    st = dict(hit=0, total=0, top1=0, wrong=0, n=0)
    targets = set(G.TRUTH.values())
    print(f"\n[평가] {seg_path} · 구간 {len(items)}개 · 구간 중심 {SL.WINDOW_SEC:.0f}초로 분석\n")
    for it in items:
        parts = it["label"].split("+")
        unknown = [p for p in parts if p not in G.TRUTH]
        if unknown:
            print(f"  건너뜀: 모르는 정답 라벨 {unknown} (variety_labels.TRUTH 에 추가하세요)")
            continue
        if it["file"] not in cache:
            cache[it["file"]] = SL.load_audio(it["file"])
        data, sr = cache[it["file"]]
        mid = (it["s"] + it["e"]) / 2
        win = int(SL.WINDOW_SEC * sr)
        a = max(0, min(len(data) - win, int(mid * sr) - win // 2))
        o = runner.step(data[a:a + win], sr)
        got = [c for c, *_ in o["var"]["items"]] if o else []
        shown = fmt22(o["var"]) if o else "[무음]"
        want = {G.TRUTH[p] for p in parts}
        hits = want & set(got)
        wrong = [g for g in got if g in targets and g not in want and g != "music"]   # 배경음악은 거의 항상이라 오표시로 안 셈
        st["n"] += 1
        st["total"] += len(want)
        st["hit"] += len(hits)
        st["top1"] += int(bool(got) and got[0] in want)
        st["wrong"] += len(wrong)
        mark = "✅" if hits == want else ("△" if hits else "❌")
        print(f"[{it['s']:5.1f}-{it['e']:5.1f}s] 정답 {it['label']}")
        print(f"    {mark} {shown}")
        if debug and o:
            print(fmt_debug(o["var"]))
        rows.append(dict(file=it["file"], start=it["s"], end=it["e"], truth=it["label"], result=shown, mark=mark))

    print("\n=========== 요약 ===========")
    print(f"  정답 소리 잡음 {st['hit']}/{st['total']} · 1순위 정답 {st['top1']}/{st['n']} · 오표시 {st['wrong']}")
    print("  · 오표시: TRUTH 에 있는 소리 중 정답이 아닌 것을 띄운 수 (배경음악은 안 셈)")
    runner.an.summary()
    if csv_path:
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["file", "start", "end", "truth", "result", "mark"])
            w.writeheader()
            w.writerows(rows)
        print(f"\n[저장] {csv_path}")


# ----------------------------------------------------------------------
# 콘텐츠별 O/X 검토: 이벤트 목록 만들기 / 집계
# ----------------------------------------------------------------------
EVENT_GAP = 1.5          # 같은 소리가 이 시간(초) 안에 다시 뜨면 같은 이벤트
ROUTE = {"*": "둘 다(*)", "+": "AudioSet 혼자(+)", "": "CLAP 주도"}
EV_FIELDS = ["콘텐츠", "파일", "시작(초)", "끝(초)", "표시", "카테고리", "순간/지속", "경로", "최고점수",
             "판정(O/X)", "메모"]
GROUP_FORM = {G.LABELS[m[0]]["group"]: G.LABELS[m[0]]["form"] for m in G.groups().values()}


class EventLog:
    """분석마다 뜬 결과를 '같은 소리가 이어진 구간' 단위로 묶음. 시각은 분석 구간(2초)의 가운데 기준.
    배경음악은 분위기가 바뀌어도 같은 이벤트 — '표시' 칸에는 가장 많이 나온 분위기 이름"""

    def __init__(self, content, source):
        self.content, self.source = content, source
        self.open, self.done = {}, []

    def add(self, t, res):
        for cat, name, score, mark in (res["items"] if res else []):
            ev = self.open.get(cat)
            if ev and t - ev["last"] <= EVENT_GAP:
                ev["last"], ev["best"] = t, max(ev["best"], score)
                ev["marks"].add(mark)
                ev["names"][name] = ev["names"].get(name, 0) + 1
            else:
                if ev:
                    self.done.append(ev)
                self.open[cat] = dict(cat=cat, first=t, last=t, best=score, marks={mark}, names={name: 1})
        for cat in [c for c, ev in self.open.items() if t - ev["last"] > EVENT_GAP]:
            self.done.append(self.open.pop(cat))

    def save(self, path):
        evs = sorted(self.done + list(self.open.values()), key=lambda e: e["first"])
        half = SL.WINDOW_SEC / 2
        rows = []
        for e in evs:
            route = "*" if "*" in e["marks"] else ("+" if "+" in e["marks"] else "")
            rows.append({"콘텐츠": self.content, "파일": self.source,
                         "시작(초)": round(max(0.0, e["first"] - half), 1), "끝(초)": round(e["last"] + half, 1),
                         "표시": max(e["names"], key=e["names"].get), "카테고리": e["cat"],
                         "순간/지속": "지속" if GROUP_FORM[e["cat"]] == "sustained" else "순간",
                         "경로": ROUTE[route], "최고점수": round(e["best"], 2), "판정(O/X)": "", "메모": ""})
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=EV_FIELDS)
            w.writeheader()
            w.writerows(rows)
        print(f"[저장] {path}  (이벤트 {len(rows)}개 — '판정(O/X)' 칸에 O 또는 X 를 적고 --score)")


def _read_csv_any(path):
    for enc in ("utf-8-sig", "cp949"):          # 엑셀에서 저장하면 cp949 로 바뀌는 경우가 있음
        try:
            with open(path, newline="", encoding=enc) as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"{path} 를 읽지 못했습니다 (인코딩)")


def run_score(paths):
    import glob
    files = paths or sorted(glob.glob("*_events.csv"))
    if not files:
        raise SystemExit("집계할 *_events.csv 가 없습니다.")
    rows, blank = [], 0
    for p in files:
        for r in _read_csv_any(p):
            v = (r.get("판정(O/X)") or "").strip().upper()
            if v in ("O", "0", "ㅇ", "1", "Y"):
                v = "O" if v != "0" else "X"
            if v not in ("O", "X"):
                blank += 1
                continue
            r["_ok"] = v == "O"
            rows.append(r)
    print(f"[집계] 파일 {len(files)}개 · 판정한 이벤트 {len(rows)}개 · 판정 안 한 것 {blank}개\n")
    if not rows:
        return

    def table(title, key):
        groups = {}
        for r in rows:
            groups.setdefault(key(r), []).append(r["_ok"])
        print(f"== {title} ==")
        for k in sorted(groups, key=lambda k: (-len(groups[k]), str(k))):
            v = groups[k]
            print(f"  {str(k):<24} {sum(v):>3}/{len(v):<3} 맞음  {sum(v) / len(v):>4.0%}")
        print()

    table("콘텐츠별", lambda r: r["콘텐츠"])
    table("경로별 (전체)", lambda r: r["경로"])
    table("표시별", lambda r: r["표시"])
    table("순간/지속", lambda r: r["순간/지속"])
    wrong = {}
    for r in rows:
        if not r["_ok"]:
            wrong.setdefault(r["표시"], []).append(r)
    if wrong:
        print("== 자주 틀린 표시 ==")
        for name, rs in sorted(wrong.items(), key=lambda kv: -len(kv[1]))[:12]:
            ex = ", ".join(f"{r['콘텐츠']} {r['시작(초)']}s" for r in rs[:3])
            print(f"  {name:<20} {len(rs)}번  ({ex})")


# ----------------------------------------------------------------------
# 실시간 / 파일
# ----------------------------------------------------------------------
STALE_SEC = 0.5     # 이 시간 동안 새 소리가 안 들어오면 '정지' (재생 멈춤·일시정지)


class FreshCapture(SL.LoopbackCapture):
    """윈도우 루프백은 아무것도 재생 안 하면 데이터를 안 보냄 → 마지막 소리를 반복 분석하지 않게 함"""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.last_t = 0.0

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


# ----------------------------------------------------------------------
# 지연 시험 (총게임 gun v1.12c 와 같은 방식) (--latency-test N)
#   프로그램이 직접 '딱' 소리를 기본 출력 장치로 재생하고, 그 소리가 각 단계를 지나는 시각을 잼
#   ① 재생 요청 → 오디오 엔진 통과(루프백 스트림에 그 샘플이 들어간 시각)
#   ② 루프백 묶음 전달 (그 샘플이 들어 있는 1024샘플 묶음이 프로그램에 도착할 때까지)
#   ③ 다음 분석까지 대기 (도착 → 분석이 버퍼를 꺼내는 순간)
#   ④ 처리 (버퍼 복사 ~ 판정 끝)    ⑤ 터미널 출력 (print·로그 기록)
#   전체 = 재생 요청 → 터미널에 결과 줄이 찍힌 순간. 모니터에 그려지는 시간(60Hz 면 최대 약 17ms)은 못 잼
# ----------------------------------------------------------------------
CLICK_LEVEL = 0.3       # 루프백에서 이 크기 이상이면 시험음이 들어온 것으로 봄 (다른 소리는 끄고 시험)


class LatencyCapture(FreshCapture):
    """루프백 묶음마다 도착 시각을 재고, 시험음이 처음 들어온 샘플 위치로 '오디오 엔진 통과 시각'을 계산"""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.expect = None                                       # (번호, 재생 요청 시각)
        self.hits, self.hit_lock = [], threading.Lock()

    def _callback(self, in_data, frame_count, time_info, status):
        t_arr = time.perf_counter()
        if self.expect is not None:
            x = np.abs(np.frombuffer(in_data, dtype=np.int16).reshape(-1, self.channels)[:, :2]).max(axis=1) / 32768.0
            idx = np.flatnonzero(x >= CLICK_LEVEL)
            if idx.size:
                k, t_play = self.expect
                self.expect = None
                t_in = t_arr - (len(x) - idx[0]) / self.sr       # 묶음 안에서 시험음이 시작된 샘플의 시각
                with self.hit_lock:
                    self.hits.append(dict(k=k, t_play=t_play, t_in=t_in, t_arr=t_arr))
        return super()._callback(in_data, frame_count, time_info, status)


class ClickPlayer(threading.Thread):
    """기본 출력 장치(WASAPI)로 무음을 계속 흘리다가 2.5~3.5초마다 3ms '딱'을 재생.
    무음을 계속 흘리는 이유: 윈도우 루프백은 재생되는 소리가 없으면 데이터를 안 보냄"""

    def __init__(self, cap, n, gap=(2.5, 3.5)):
        super().__init__(daemon=True)
        import pyaudiowpatch as pyaudio
        self.pa = pyaudio.PyAudio()
        wasapi = self.pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        dev = self.pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
        self.dev_name = dev["name"]
        sr, ch = int(dev["defaultSampleRate"]), max(1, int(dev["maxOutputChannels"]))
        block = max(64, int(sr * 0.005))                         # 5ms 단위로 씀
        self.stream = self.pa.open(format=pyaudio.paInt16, channels=ch, rate=sr, output=True,
                                   output_device_index=dev["index"], frames_per_buffer=block)
        rng = np.random.default_rng()
        c = np.zeros(block, np.float32)
        m = int(sr * 0.003)
        c[:m] = rng.uniform(-0.8, 0.8, m)
        self.click = (np.repeat(c[:, None], ch, axis=1) * 32767).astype(np.int16).tobytes()
        self.silence = np.zeros((block, ch), np.int16).tobytes()
        self.cap, self.n, self.gap, self.rng, self.stop_flag = cap, n, gap, rng, False

    def run(self):
        try:
            k, nxt = 0, time.perf_counter() + 2.0
            while k < self.n and not self.stop_flag:
                if time.perf_counter() >= nxt:
                    k += 1
                    self.cap.expect = (k, time.perf_counter())
                    self.stream.write(self.click)
                    nxt = time.perf_counter() + self.rng.uniform(*self.gap)   # 간격을 흔들어 분석 주기와 안 맞물리게
                else:
                    self.stream.write(self.silence)
            end = time.perf_counter() + 3.0                      # 마지막 시험음이 분석될 때까지 무음 유지
            while time.perf_counter() < end and not self.stop_flag:
                self.stream.write(self.silence)
        finally:
            self.stream.stop_stream()
            self.stream.close()
            self.pa.terminate()


LAT_KEYS = [("엔진", "① 재생 요청 → 오디오 엔진 통과"), ("묶음", "② 루프백 묶음 전달"),
            ("대기", "③ 다음 분석까지 대기"), ("처리", "④ 처리 (복사~판정)"), ("출력", "⑤ 터미널 출력"),
            ("전체", "전체 (재생 요청 → 터미널)")]


def run_latency_test(runner, n, dlog=None):
    cap = LatencyCapture(buffer_sec=max(10.0, SL.WINDOW_SEC * 2))
    cap.start()
    player = ClickPlayer(cap, n)
    print(f"\n[지연 시험] 시험음 {n}번 (약 {n * 3 // 60}분 {n * 3 % 60}초) · 출력 장치: {player.dev_name}")
    print("  ※ 다른 소리(영상·음악·게임)는 모두 끄고, 음소거만 안 하면 됩니다. 중간에 Ctrl+C 로 멈춰도 그때까지 결과는 나옴\n")
    player.start()
    rows = []
    try:
        while len(rows) < n:
            t0 = time.time()
            with cap.hit_lock:
                waiting = bool(cap.hits)
            if not player.is_alive() and not waiting:
                break
            t_copy = time.perf_counter()
            buf = cap.get_last(SL.WINDOW_SEC)
            runner.timer.add("캡처 복사", time.perf_counter() - t_copy)
            with cap.hit_lock:
                new = [h for h in cap.hits if h["t_arr"] <= t_copy]
                cap.hits = [h for h in cap.hits if h["t_arr"] > t_copy]
            o = runner.step(buf, cap.sr)
            t_judged = time.perf_counter()
            now = time.time()
            stamp = time.strftime("%H:%M:%S", time.localtime(now)) + f".{int(now * 10) % 10}"
            if o is None:
                print(f"{stamp} [무음]", end="\r")
            else:
                show(f"{stamp} ", o, False, dlog, runner.timer.commit(runner.models))
            t_printed = time.perf_counter()
            for h in new:
                r = dict(번호=h["k"], 엔진=h["t_in"] - h["t_play"], 묶음=h["t_arr"] - h["t_in"],
                         대기=t_copy - h["t_arr"], 처리=t_judged - t_copy, 출력=t_printed - t_judged,
                         전체=t_printed - h["t_play"])
                rows.append(r)
                s = " · ".join(f"{k} {r[k] * 1000:.0f}" for k, _ in LAT_KEYS[:-1])
                msg = f"         ⏱ 시험음 #{h['k']:>2}: 전체 {r['전체'] * 1000:.0f}ms  ({s})"
                print(msg)
                if dlog:
                    dlog.write(msg)
            time.sleep(max(0.0, SL.HOP_SEC - (time.time() - t0)))
    except KeyboardInterrupt:
        print("\n중간에 멈춤")
    finally:
        player.stop_flag = True
        cap.stop()

    lines = [f"\n[지연 시험 결과] 시험음 {len(rows)}/{n}개 · 분석 간격 {SL.HOP_SEC:.1f}초 · 분석 창 {SL.WINDOW_SEC:.1f}초"
             f" · 연산 장치 {runner.device} · CLAP {runner.clap_mode}",
             f"  {'단계':<26} {'최소':>7} {'평균':>7} {'최대':>7}  (ms)"]
    for k, label in LAT_KEYS:
        if rows:
            a = np.array([r[k] for r in rows]) * 1000
            lines.append(f"  {label:<26} {a.min():7.1f} {a.mean():7.1f} {a.max():7.1f}")
    lines.append("  ※ ①에는 시험음을 내는 쪽의 출력 버퍼도 포함 (게임도 자기 버퍼가 있음). 모니터에 그려지는 시간은 미포함")
    lines.append("")
    lines.append(runner.timer.summary(runner.models))
    rep = "\n".join(lines)
    print(rep)
    if dlog:
        dlog.write(rep)
    if rows:
        path = f"latency_test_{time.strftime('%m%d_%H%M%S')}.csv"
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["번호"] + [label + " (ms)" for _, label in LAT_KEYS])
            for r in rows:
                w.writerow([r["번호"]] + [round(r[k] * 1000, 1) for k, _ in LAT_KEYS])
        print(f"\n[저장] {os.path.abspath(path)}  (시험음마다 단계별 시간)")
    if dlog:
        dlog.close()


def latency_summary(proc):
    if not proc:
        return
    a = np.array(proc)
    print("\n[소리 → 화면 표시 지연]")
    print(f"  분석·표시 처리       최소 {a.min():.2f}초 · 최대 {a.max():.2f}초 · 평균 {a.mean():.2f}초  ({len(a)}회)")
    print(f"  소리가 난 뒤 화면까지 최소 ≈{a.min():.2f}초 · 최대 ≈{SL.HOP_SEC + a.max():.2f}초 · "
          f"평균 ≈{SL.HOP_SEC / 2 + a.mean():.2f}초  (분석 간격 {SL.HOP_SEC:.1f}초 기준 추정)")


def run_live(runner, debug, save=None, content="", dlog=None):
    proc = []
    cap = (RecordingCapture if save else FreshCapture)(buffer_sec=max(10.0, SL.WINDOW_SEC * 2))
    log = EventLog(content, f"{save}.wav") if save else None
    cap.start()
    t_start = time.time()
    if save:
        print(f"[검토용 저장 켬] 끝내면 {save}.wav, {save}_events.csv 저장 · 콘텐츠: {content or '(미지정)'}")
    print("소리를 재생해 보세요. (Ctrl+C 로 종료)")
    print("  표시: 이름* = CLAP + 보조 둘 다 잡음 / 이름+ = 보조만 강하게 잡음")
    if dlog:
        print(f"  ★ 이상한 게 뜨면 스페이스바 → 직전 {MARK_BACK}초 기록이 디버그 정보와 함께 ★ 파일에 따로 저장됨")
    print()
    time.sleep(SL.WINDOW_SEC)
    was_stale = False
    try:
        while True:
            t0 = time.time()
            if dlog:
                poll_marks(dlog)
            if cap.stale():
                if not was_stale:                    # 영상 전환·일시정지 → 이전 장면의 지속음 유지 지움
                    runner.judge.reset()
                    was_stale = True
                if log:
                    log.add(time.time() - t_start - SL.WINDOW_SEC / 2, None)
                print(f"{time.strftime('%H:%M:%S')} [정지 — 재생 중인 소리 없음]", end="\r")
                time.sleep(SL.HOP_SEC)
                continue
            was_stale = False
            tc = time.perf_counter()
            buf = cap.get_last(SL.WINDOW_SEC)
            runner.timer.add("캡처 복사", time.perf_counter() - tc)
            o = runner.step(buf, cap.sr)
            if log:
                log.add(time.time() - t_start - SL.WINDOW_SEC / 2, o["var"] if o else None)
            now = time.time()
            stamp = time.strftime("%H:%M:%S", time.localtime(now)) + (f".{int(now * 10) % 10}" if SL.HOP_SEC < 1 else "")
            if o is None:
                print(f"{stamp} [무음]", end="\r")
            else:
                print(" " * 30, end="\r")
                timing = runner.timer.commit(runner.models)
                to = time.perf_counter()
                show(f"{stamp} ", o, debug, dlog, timing)
                runner.timer.all.setdefault("출력(화면/기록)", []).append(time.perf_counter() - to)
                proc.append(time.time() - t0)
            time.sleep(max(0.0, SL.HOP_SEC - (time.time() - t0)))
    except KeyboardInterrupt:
        print("\n종료합니다.")
        runner.an.summary()
        latency_summary(proc)
        ts = runner.timer.summary(runner.models)
        tail = f"  연산 장치: {runner.device} · 분석 창 {SL.WINDOW_SEC:.1f}초 · 분석 간격 {SL.HOP_SEC:.1f}초"
        print("\n" + ts + "\n" + tail)
        if dlog:
            dlog.write("\n" + ts + "\n" + tail)
    finally:
        cap.stop()
        if save:
            cap.save_wav(f"{save}.wav")
            log.save(f"{save}_events.csv")
        if dlog:
            dlog.close()


def run_file(runner, path, debug, csv_path, events=False, content="", dlog=None):
    data, sr = SL.load_audio(path)
    log = EventLog(content, os.path.basename(path)) if events else None
    win, hop = int(SL.WINDOW_SEC * sr), int(SL.HOP_SEC * sr)
    rows = []
    for start in range(0, max(1, len(data) - win + 1), hop):
        t0 = start / sr
        o = runner.step(data[start:start + win], sr)
        if log:
            log.add(t0 + SL.WINDOW_SEC / 2, o["var"] if o else None)
        head = f"[{SL.mmss(t0)}] "
        if o is None:
            print(head + "[무음]")
            rows.append(dict(start=round(t0, 1)))
            continue
        show(head, o, debug, dlog, runner.timer.commit(runner.models))
        rows.append(dict(start=round(t0, 1), direction=o["direction"], variety=fmt22(o["var"])))
    runner.an.summary()
    ts = runner.timer.summary(runner.models) + f"\n  연산 장치: {runner.device}"
    print("\n" + ts)
    if dlog:
        dlog.write("\n" + ts)
        dlog.close()
    if csv_path:
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["start", "direction", "variety"])
            w.writeheader()
            w.writerows(rows)
        print(f"\n[저장] {csv_path}")
    if log:
        log.save(os.path.splitext(path)[0] + "_events.csv")


def main():
    ap = argparse.ArgumentParser(description="예능 모드: CLAP + PANNs·BEATs")
    ap.add_argument("--models", default="clap,panns,beats", help="clap 필수 + panns, beats")
    ap.add_argument("--eval", default=None, help="정답 구간 목록(segments.txt)으로 평가")
    ap.add_argument("--file", default=None, help="분석할 파일 (없으면 실시간)")
    ap.add_argument("--csv", default=None, help="결과 CSV 저장 (--file, --eval)")
    ap.add_argument("--debug", action="store_true", help="디버그 정보를 화면에도 출력 (기본: 파일에만 저장)")
    ap.add_argument("--no-log", action="store_true", help="디버그 기록 파일 저장 안 함")
    ap.add_argument("--normalize", action="store_true", help="구간 음량 맞추기")
    ap.add_argument("--silence", type=float, default=0.003, help="무음 기준. 기본 0.003")
    ap.add_argument("--hop", type=float, default=0.5, help="분석 간격(초). 기본 0.5 (v0.15, 예전 1.0)")
    ap.add_argument("--latency-test", type=int, nargs="?", const=30, default=None,
                    help="지연 시험: 시험음을 N번(기본 30) 재생해 단계별 시간 실측 (다른 소리는 끄고)")
    ap.add_argument("--save", default=None, help="실시간: 끝낼 때 <이름>.wav + <이름>_events.csv 저장")
    ap.add_argument("--events", action="store_true", help="--file: <파일명>_events.csv 저장")
    ap.add_argument("--content", default="예능", help="콘텐츠 이름 (이벤트 csv 에 기록)")
    ap.add_argument("--score", nargs="*", default=None, help="O/X 적은 *_events.csv 집계 (파일 생략 시 폴더 전체)")
    args = ap.parse_args()
    if args.score is not None:
        run_score(args.score)
        return

    keys = [k.strip().lower() for k in args.models.split(",") if k.strip()]
    SL.SILENCE_PEAK_RMS = args.silence
    SL.HOP_SEC = args.hop
    print(f"[sound_live_variety {VERSION} · models={','.join(keys)} · 📺 예능 모드]")
    versions = {"sound_live_variety.py": VERSION,
                "variety_labels.py": getattr(G, "VERSION", "옛 버전"),
                "variety_judge.py": getattr(variety_judge, "VERSION", "옛 버전")}
    if len(set(versions.values())) > 1:
        print("!" * 60)
        print("[경고] 파일 버전이 서로 다릅니다 — 옛 파일이 섞여 있어요. 같은 버전으로 덮어쓰세요.")
        for f, v in versions.items():
            print(f"   {f:<24} {v}   ({os.path.abspath(getattr(sys.modules.get(f[:-3]), '__file__', f))})")
        print("!" * 60)
    runner = Runner(keys, args.normalize)
    dlog = None
    if not args.no_log and not args.eval:
        os.makedirs("debug_logs", exist_ok=True)
        dlog = DebugLog(os.path.join("debug_logs", f"variety_{time.strftime('%m%d_%H%M%S')}.txt"))
        dlog.write(f"[sound_live_variety {VERSION} · models={','.join(keys)} · 분석 간격 {SL.HOP_SEC:.1f}초]")
        print(f"[디버그 기록] {dlog.path} 에 자동 저장 (화면에는 안 보임)")
    if args.latency_test:
        run_latency_test(runner, args.latency_test, dlog)
        return
    if args.eval:
        run_eval(runner, args.eval, args.csv or "eval_variety.csv", args.debug)
    elif args.file:
        run_file(runner, args.file, args.debug, args.csv, args.events, args.content, dlog)
    else:
        run_live(runner, args.debug, args.save, args.content, dlog)


if __name__ == "__main__":
    main()
