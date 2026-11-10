"""
sound_live_all.py — 3모드 통합 터미널 실행 (2026-10-22)
예전 sound_live_gun.py · sound_live_horror.py · sound_live_variety.py 기능 전부를 --mode 하나로
  - 모델은 sound_engine.Engine 이 한 번만 올림 (판정·라벨은 각 모드 파일 그대로)
  - 화면 이름은 표시명 기준 (예: '오답', '물방울'). --onoma 를 주면 의성어도 붙여서 보여 줌 (예: '총성 탕!')
  - 터미널 출력 양식은 v22 와 동일

실행
  python sound_live_all.py --mode gun                               # 실시간 (gun | horror | variety | kids)
  python sound_live_all.py --mode horror --debug                    # + 디버그 정보를 화면에도
  python sound_live_all.py --mode variety --onoma                   # 의성어 붙여서 보기
  python sound_live_all.py --mode gun --file 배그1.wav --csv gun.csv  # 파일
  python sound_live_all.py --mode horror --eval segments.txt        # 정답 구간 평가
  (--save 는 2026-11-07 부터 꺼짐: 녹음·이벤트 표를 저장하지 않음)
  python sound_live_all.py --score                                  # O/X 집계
  python sound_live_all.py --mode gun --latency-test 30             # 지연 시험 (모델 동시 실행)
  python sound_live_all.py --mode gun --latency-test 30 --no-parallel   # 예전처럼 차례로 — 위와 비교
  python sound_live_all.py --mode gun --clap-int8 --check-clap --hop 1   # CLAP int8 경량화 비교
종료: Ctrl + C
"""

import argparse
import csv
import os
import sys
import threading
import time

import numpy as np

import sound_engine as E

ARROW = {"왼쪽": "◀", "오른쪽": "▶", "중앙": " "}
MARK_BACK = 3       # 스페이스바를 누르면 직전 몇 초의 결과를 ★ 파일에 모을지
EVENT_GAP = 1.5     # 같은 소리가 이 시간(초) 안에 다시 뜨면 같은 이벤트
ROUTE = {"*": "둘 다(*)", "+": "AudioSet 혼자(+)", "": "CLAP 주도"}
EV_FIELDS = ["콘텐츠", "파일", "시작(초)", "끝(초)", "표시", "카테고리", "순간/지속", "경로", "최고점수",
             "판정(O/X)", "메모"]
EVAL_NOTE = {"gun": "  · 오표시: 연막·발소리·총성·폭발 중 정답이 아닌 것을 띄운 수 (다른 소리는 안 셈)",
             "horror": "  · 오표시: TRUTH 에 있는 소리 중 정답이 아닌 것을 띄운 수 (배경음악은 안 셈)",
             "variety": "  · 오표시: TRUTH 에 있는 소리 중 정답이 아닌 것을 띄운 수 (배경음악은 안 셈)",
             "kids": "  · 오표시: TRUTH 에 있는 소리 중 정답이 아닌 것을 띄운 수 (배경음악은 안 셈)"}


class Ctx:
    """지금 모드 정보 (출력 함수들이 같이 씀)"""

    def __init__(self, mode, engine, onoma):
        self.mode, self.engine, self.onoma = mode, engine, onoma
        self.G = E.MODES[mode]["G"]
        self.judge = engine.judges[mode] if engine else None
        self.SL = engine.SL if engine else None

    def view(self, o):
        """엔진 결과 → 화면 이름으로 바꾼 판정 결과"""
        disp = E.display(self.mode, self.judge, o["res"], o["emb"], self.onoma)
        return E.renamed_res(o["res"], disp)


# ----------------------------------------------------------------------
# 출력 (v22 와 같은 양식)
# ----------------------------------------------------------------------
def _star(res, c, mk):
    return f"(보조 {res.get('tag_scores', {}).get(c, 0.0):.2f})" if mk == "*" else ""


def fmt22(res):
    s = ", ".join(f"[{n}]{mk} {sh:.2f}{_star(res, c, mk)}" for c, n, sh, mk in res["instant"]) or "-"
    if res["sustained"]:
        s += "   | 지속: " + " · ".join(f"{n}{mk} {sh:.2f}{_star(res, c, mk)}" for c, n, sh, mk in res["sustained"])
    return s


def fmt_debug(ctx, res):
    G, HOP = ctx.G, ctx.SL.HOP_SEC
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
    if m and (m.get("show") or any(c == "music" for c, *_ in res["sustained"])):
        short = lambda v: " / ".join(f"{n.replace(' 있는', '').replace(' 음악', '')} {p:.2f}" for n, p in v)  # noqa: E731
        s += (f"\n         └ 음악 분위기: {short(m['now'])}"
              + (f"  · 보조 무서운·화난 {m.get('scary_as', 0):.2f} · 징글 {m.get('jingle', 0):.2f}"
                 if m.get("as_mood") is not None else "")
              + (f"  · 음악−말소리 {m['gap']:.2f}" if m.get("gap") is not None else "")
              + (f"  → 이번 판단 없음 ({', '.join(m['why'])})" if m.get("why") else "")
              + (f"  · 표시 유지 {m['unsure'] * HOP:.1f}초째 ({G.MOOD_KEEP}초 넘으면 배경음악)" if m.get("unsure") else "")
              + (f"  · 바뀌는 중: {m['pending']}" + (f" (최근 {G.MOOD_WINDOW}초 다수결)" if hasattr(G, "MOOD_WINDOW")
                 else f" ({G.MOOD_CONFIRM}초 연속 또는 {G.MOOD_STRONG} 이상)") if m.get("pending") else ""))
    if d.get("watch"):
        s += "\n         └ 관찰: " + " / ".join(f"{n} {p:.2f}(cos {c:.2f})" for n, p, c in d["watch"])
    if d.get("rejected"):
        s += "\n         └ 탈락: " + ", ".join(f"{n} ({why})" for n, p, why in d["rejected"])
    return s


def line(res, direction):
    arrow = ARROW.get(direction, " ") if res["items"] else " "
    return f"{arrow} " + fmt22(res)


class DebugLog:
    """화면은 깔끔하게, 디버그 정보는 파일에 자동 저장
      <이름>.txt   : 전체 기록 (디버그 포함) + 스페이스바 누른 곳에 ★ 줄
      <이름>_★.txt : 스페이스바 누른 순간의 직전 3초만 (디버그 포함) ← 보통 이것만 첨부"""

    def __init__(self, path, hop):
        from collections import deque
        self.path, self.hop = path, hop
        self.mark_path = os.path.splitext(path)[0] + "_★.txt"
        self.f = open(path, "w", encoding="utf-8")
        self.mf = None
        self.recent = deque(maxlen=max(MARK_BACK, int(round(MARK_BACK / hop))))
        self.marks = 0
        self.typing = False          # 2026-11-07: 스페이스바 뒤 메모 입력 중이면 화면 출력 잠시 멈춤 (파일 기록은 계속)

    def write(self, text):
        self.f.write(text + "\n")
        self.f.flush()

    def block(self, text):
        self.write(text)
        self.recent.append(text)

    def mark(self, stamp):
        self.marks += 1
        self.write(f"★★★ {stamp} 표시 #{self.marks} ★★★")
        if self.mf is None:
            self.mf = open(self.mark_path, "w", encoding="utf-8")
        self.mf.write(f"===== ★ #{self.marks}  {stamp} 에 누름 — 직전 {len(self.recent) * self.hop:.1f}초 =====\n")
        for b in self.recent:
            self.mf.write(b + "\n")
        self.mf.write("\n")
        self.mf.flush()
        print(f"         ★ #{self.marks} 저장 (직전 {len(self.recent) * self.hop:.1f}초)")

    def memo(self, n, text):
        text = (text or "").strip()
        if not text:
            print(f"         ★ #{n} 메모 없이 넘어감")
            return
        line = f"📝 ★ #{n} 메모: {text}"
        self.write(line)
        if self.mf:
            self.mf.write(line + "\n\n")
            self.mf.flush()
        print(f"         {line} (저장)")

    def close(self):
        self.f.close()
        print(f"\n[디버그 기록] 전체: {os.path.abspath(self.path)}")
        if self.mf:
            self.mf.close()
            print(f"[디버그 기록] ★ 표시만: {os.path.abspath(self.mark_path)}  ({self.marks}개) ← 이 파일을 첨부하면 됨")


def poll_marks(dlog):
    """스페이스바(또는 Enter) = ★ 표시. 바로 이어서 메모를 쓰고 Enter (그냥 Enter 면 메모 없이).
    메모를 쓰는 동안 화면 출력만 멈추고, 분석과 파일 기록은 계속됨"""
    try:
        import msvcrt
    except ImportError:
        return
    if dlog.typing:
        return
    while msvcrt.kbhit():
        ch = msvcrt.getwch()
        if ch in (" ", "\r"):
            dlog.mark(time.strftime("%H:%M:%S"))
            n = dlog.marks
            dlog.typing = True

            def ask(n=n):
                try:
                    text = input(f"         📝 ★ #{n} 메모 (무슨 소리였는지, Enter로 저장 · 그냥 Enter면 건너뜀)> ")
                except (EOFError, RuntimeError):
                    text = ""
                dlog.memo(n, text)
                dlog.typing = False

            import threading
            threading.Thread(target=ask, daemon=True).start()
            return


def show(ctx, prefix, o, res, debug, dlog=None, timing=None):
    text = prefix + line(res, o["direction"])
    quiet = bool(dlog and dlog.typing)       # 메모 입력 중엔 화면에 안 찍음 (파일엔 기록)
    if not quiet:
        print(text)
    tl = f"\n         └ {timing}" if timing else ""
    if o.get("check"):
        same, sim, r32 = o["check"]
        tl += "\n         └ 🔬 원래 CLAP 비교: " + (f"같음 (일치 {sim:.4f})" if same
                                                  else f"다름 (일치 {sim:.4f}) → 원래 CLAP 결과: {fmt22(r32)}")
    if debug and not quiet:
        print(fmt_debug(ctx, res) + tl)
    if dlog:
        dlog.block(text + "\n" + fmt_debug(ctx, res) + tl)


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


def run_eval(ctx, seg_path, csv_path, debug):
    SL, G, eng = ctx.SL, ctx.G, ctx.engine
    items = parse_segments(seg_path)
    cache, rows = {}, []
    st = dict(hit=0, total=0, top1=0, wrong=0, n=0)
    targets = set(G.TRUTH.values())
    print(f"\n[평가] {seg_path} · 구간 {len(items)}개 · 구간 중심 {SL.WINDOW_SEC:.0f}초로 분석\n")
    for it in items:
        parts = it["label"].split("+")
        unknown = [p for p in parts if p not in G.TRUTH]
        if unknown:
            print(f"  건너뜀: 모르는 정답 라벨 {unknown} ({G.__name__}.TRUTH 에 추가하세요)")
            continue
        if it["file"] not in cache:
            cache[it["file"]] = SL.load_audio(it["file"])
        data, sr = cache[it["file"]]
        mid = (it["s"] + it["e"]) / 2
        win = int(SL.WINDOW_SEC * sr)
        a = max(0, min(len(data) - win, int(mid * sr) - win // 2))
        o = eng.step(data[a:a + win], sr, ctx.mode)
        eng.timer.drop()
        res = ctx.view(o) if o else None
        got = [c for c, *_ in res["items"]] if res else []
        shown = fmt22(res) if res else "[무음]"
        want = {G.TRUTH[p] for p in parts}
        hits = want & set(got)
        wrong = [g for g in got if g in targets and g not in want and g != "music"]   # 배경음악은 오표시로 안 셈
        st["n"] += 1
        st["total"] += len(want)
        st["hit"] += len(hits)
        st["top1"] += int(bool(got) and got[0] in want)
        st["wrong"] += len(wrong)
        mark = "✅" if hits == want else ("△" if hits else "❌")
        print(f"[{it['s']:5.1f}-{it['e']:5.1f}s] 정답 {it['label']}")
        print(f"    {mark} {shown}")
        if debug and res:
            print(fmt_debug(ctx, res))
        rows.append(dict(file=it["file"], start=it["s"], end=it["e"], truth=it["label"], result=shown, mark=mark))

    print("\n=========== 요약 ===========")
    print(f"  정답 소리 잡음 {st['hit']}/{st['total']} · 1순위 정답 {st['top1']}/{st['n']} · 오표시 {st['wrong']}")
    print(EVAL_NOTE[ctx.mode])
    eng.an.summary()
    if csv_path:
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["file", "start", "end", "truth", "result", "mark"])
            w.writeheader()
            w.writerows(rows)
        print(f"\n[저장] {csv_path}")


# ----------------------------------------------------------------------
# 콘텐츠별 O/X 검토: 이벤트 목록 만들기 / 집계
# ----------------------------------------------------------------------
class EventLog:
    """결과를 '같은 소리가 이어진 구간' 단위로 묶음. 시각은 분석 구간(2초)의 가운데 기준.
    배경음악은 분위기가 바뀌어도 같은 이벤트 — '표시' 칸에는 가장 많이 나온 이름"""

    def __init__(self, ctx, content, source):
        self.ctx, self.content, self.source = ctx, content, source
        self.open, self.done = {}, []
        self.form = {g: ctx.G.LABELS[m[0]]["form"] for g, m in ctx.G.groups().items()}

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
        half = self.ctx.SL.WINDOW_SEC / 2
        rows = []
        for e in evs:
            route = "*" if "*" in e["marks"] else ("+" if "+" in e["marks"] else "")
            rows.append({"콘텐츠": self.content, "파일": self.source,
                         "시작(초)": round(max(0.0, e["first"] - half), 1), "끝(초)": round(e["last"] + half, 1),
                         "표시": max(e["names"], key=e["names"].get), "카테고리": e["cat"],
                         "순간/지속": "지속" if self.form[e["cat"]] == "sustained" else "순간",
                         "경로": ROUTE[route], "최고점수": round(e["best"], 2), "판정(O/X)": "", "메모": ""})
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=EV_FIELDS)
            w.writeheader()
            w.writerows(rows)
        print(f"[저장] {path}  (이벤트 {len(rows)}개 — '판정(O/X)' 칸에 O 또는 X 를 적고 --score)")


def _read_csv_any(path):
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(path, newline="", encoding=enc) as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"{path} 를 읽지 못했습니다 (인코딩)")


def run_score(paths):
    import glob
    files = paths or sorted(glob.glob("*_events.csv") + glob.glob(os.path.join("debug_logs", "*_events.csv")))
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
# 지연 시험 (--latency-test N) — 총게임 v1.12c 와 같은 방식
# ----------------------------------------------------------------------
CLICK_LEVEL = 0.3
LAT_KEYS = [("엔진", "① 재생 요청 → 오디오 엔진 통과"), ("묶음", "② 루프백 묶음 전달"),
            ("대기", "③ 다음 분석까지 대기"), ("처리", "④ 처리 (복사~판정)"), ("출력", "⑤ 터미널 출력"),
            ("전체", "전체 (재생 요청 → 터미널)")]


def _latency_classes():
    FreshCapture, _ = E.capture_classes()

    class LatencyCapture(FreshCapture):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.expect = None
            self.hits, self.hit_lock = [], threading.Lock()

        def _callback(self, in_data, frame_count, time_info, status):
            t_arr = time.perf_counter()
            if self.expect is not None:
                x = np.abs(np.frombuffer(in_data, dtype=np.int16).reshape(-1, self.channels)[:, :2]).max(axis=1) / 32768.0
                idx = np.flatnonzero(x >= CLICK_LEVEL)
                if idx.size:
                    k, t_play = self.expect
                    self.expect = None
                    t_in = t_arr - (len(x) - idx[0]) / self.sr
                    with self.hit_lock:
                        self.hits.append(dict(k=k, t_play=t_play, t_in=t_in, t_arr=t_arr))
            return super()._callback(in_data, frame_count, time_info, status)

    class ClickPlayer(threading.Thread):
        def __init__(self, cap, n, gap=(2.5, 3.5)):
            super().__init__(daemon=True)
            import pyaudiowpatch as pyaudio
            self.pa = pyaudio.PyAudio()
            wasapi = self.pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            dev = self.pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
            self.dev_name = dev["name"]
            sr, ch = int(dev["defaultSampleRate"]), max(1, int(dev["maxOutputChannels"]))
            block = max(64, int(sr * 0.005))
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
                        nxt = time.perf_counter() + self.rng.uniform(*self.gap)
                    else:
                        self.stream.write(self.silence)
                end = time.perf_counter() + 3.0
                while time.perf_counter() < end and not self.stop_flag:
                    self.stream.write(self.silence)
            finally:
                self.stream.stop_stream()
                self.stream.close()
                self.pa.terminate()

    return LatencyCapture, ClickPlayer


def run_latency_test(ctx, n, dlog=None):
    SL, eng = ctx.SL, ctx.engine
    LatencyCapture, ClickPlayer = _latency_classes()
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
            eng.timer.add("캡처 복사", time.perf_counter() - t_copy)
            with cap.hit_lock:
                new = [h for h in cap.hits if h["t_arr"] <= t_copy]
                cap.hits = [h for h in cap.hits if h["t_arr"] > t_copy]
            o = eng.step(buf, cap.sr, ctx.mode)
            t_judged = time.perf_counter()
            now = time.time()
            stamp = time.strftime("%H:%M:%S", time.localtime(now)) + f".{int(now * 10) % 10}"
            if o is None:
                print(f"{stamp} [무음]", end="\r")
            else:
                show(ctx, f"{stamp} ", o, ctx.view(o), False, dlog, eng.timer.commit(eng.models))
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
             f" · 연산 장치 {eng.device} · CLAP {eng.clap_mode}",
             f"  {'단계':<26} {'최소':>7} {'평균':>7} {'최대':>7}  (ms)"]
    for k, label in LAT_KEYS:
        if rows:
            a = np.array([r[k] for r in rows]) * 1000
            lines.append(f"  {label:<26} {a.min():7.1f} {a.mean():7.1f} {a.max():7.1f}")
    lines.append("  ※ ①에는 시험음을 내는 쪽의 출력 버퍼도 포함 (게임도 자기 버퍼가 있음). 모니터에 그려지는 시간은 미포함")
    lines.append("")
    lines.append(eng.timer.summary(eng.models))
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


# ----------------------------------------------------------------------
# 실시간 / 파일
# ----------------------------------------------------------------------
def latency_summary(SL, proc):
    if not proc:
        return
    a = np.array(proc)
    print("\n[소리 → 화면 표시 지연]")
    print(f"  분석·표시 처리       최소 {a.min():.2f}초 · 최대 {a.max():.2f}초 · 평균 {a.mean():.2f}초  ({len(a)}회)")
    print(f"  소리가 난 뒤 화면까지 최소 ≈{a.min():.2f}초 · 최대 ≈{SL.HOP_SEC + a.max():.2f}초 · "
          f"평균 ≈{SL.HOP_SEC / 2 + a.mean():.2f}초  (분석 간격 {SL.HOP_SEC:.1f}초 기준 추정)")


def _tail(ctx):
    eng, SL = ctx.engine, ctx.SL
    s = f"  연산 장치: {eng.device} · 분석 창 {SL.WINDOW_SEC:.1f}초 · 분석 간격 {SL.HOP_SEC:.1f}초 · CLAP {eng.clap_mode}"
    cs = eng.check_summary()
    return s + (f"\n{cs}" if cs else "")


def run_live(ctx, debug, save=None, content="", dlog=None):
    if save:   # 2026-11-07: 사용자 요청 — 녹음(wav)·이벤트 표(csv)는 저장하지 않음. 기록은 debug_logs 의 txt 만
        print(f"[알림] --save {save}: 녹음·이벤트 표 저장은 꺼져 있어요 (기록은 debug_logs 의 txt 만 남아요)")
        save = None
    SL, eng = ctx.SL, ctx.engine
    FreshCapture, RecordingCapture = E.capture_classes()
    proc = []
    cap = (RecordingCapture if save else FreshCapture)(buffer_sec=max(10.0, SL.WINDOW_SEC * 2))
    if save and not os.path.dirname(save):                # 11-06: 이름만 주면 debug_logs 폴더에 저장
        os.makedirs("debug_logs", exist_ok=True)
        save = os.path.join("debug_logs", save)
    log = EventLog(ctx, content, f"{save}.wav") if save else None
    cap.start()
    t_start = time.time()
    if save:
        print(f"[검토용 저장 켬] 끝내면 {save}.wav, {save}_events.csv 저장 · 콘텐츠: {content or '(미지정)'}")
    print("소리를 재생해 보세요. (Ctrl+C 로 종료)")
    print("  표시: 이름* = CLAP + 보조 둘 다 잡음 / 이름+ = 보조만 강하게 잡음")
    if dlog:
        print(f"  ★ 이상한 게 뜨면 스페이스바 → 직전 {MARK_BACK}초 기록이 ★ 파일에 저장됨. 이어서 무슨 소리였는지 쓰고 Enter (그냥 Enter면 건너뜀)")
    print()
    time.sleep(SL.WINDOW_SEC)
    was_stale = False
    try:
        while True:
            t0 = time.time()
            if dlog:
                poll_marks(dlog)
            if cap.stale():
                if not was_stale:                # 영상 전환·일시정지 → 공포·예능은 이전 장면 상태 지움 (총게임은 그대로)
                    eng.pause_reset(ctx.mode)
                    was_stale = True
                if log:
                    log.add(time.time() - t_start - SL.WINDOW_SEC / 2, None)
                print(f"{time.strftime('%H:%M:%S')} [정지 — 재생 중인 소리 없음]", end="\r")
                time.sleep(SL.HOP_SEC)
                continue
            was_stale = False
            tc = time.perf_counter()
            buf = cap.get_last(SL.WINDOW_SEC)
            eng.timer.add("캡처 복사", time.perf_counter() - tc)
            o = eng.step(buf, cap.sr, ctx.mode)
            res = ctx.view(o) if o else None
            if log:
                log.add(time.time() - t_start - SL.WINDOW_SEC / 2, res)
            now = time.time()
            stamp = time.strftime("%H:%M:%S", time.localtime(now)) + (f".{int(now * 10) % 10}" if SL.HOP_SEC < 1 else "")
            if o is None:
                print(f"{stamp} [무음]", end="\r")
            else:
                print(" " * 30, end="\r")
                timing = eng.timer.commit(eng.models)
                to = time.perf_counter()
                show(ctx, f"{stamp} ", o, res, debug, dlog, timing)
                eng.timer.all.setdefault("출력(화면/기록)", []).append(time.perf_counter() - to)
                proc.append(time.time() - t0)
            time.sleep(max(0.0, SL.HOP_SEC - (time.time() - t0)))
    except KeyboardInterrupt:
        print("\n종료합니다.")
        eng.an.summary()
        latency_summary(SL, proc)
        ts = eng.timer.summary(eng.models) + "\n" + _tail(ctx)
        print("\n" + ts)
        if dlog:
            dlog.write("\n" + ts)
    finally:
        cap.stop()
        if save:
            cap.save_wav(f"{save}.wav")
            log.save(f"{save}_events.csv")
        if dlog:
            dlog.close()


def run_file(ctx, path, debug, csv_path, events=False, content="", dlog=None):
    SL, eng = ctx.SL, ctx.engine
    data, sr = SL.load_audio(path)
    log = EventLog(ctx, content, os.path.basename(path)) if events else None
    win, hop = int(SL.WINDOW_SEC * sr), int(SL.HOP_SEC * sr)
    rows = []
    for start in range(0, max(1, len(data) - win + 1), hop):
        t0 = start / sr
        o = eng.step(data[start:start + win], sr, ctx.mode)
        res = ctx.view(o) if o else None
        if log:
            log.add(t0 + SL.WINDOW_SEC / 2, res)
        head = f"[{SL.mmss(t0)}] "
        if o is None:
            print(head + "[무음]")
            rows.append(dict(start=round(t0, 1)))
            continue
        show(ctx, head, o, res, debug, dlog, eng.timer.commit(eng.models))
        rows.append({"start": round(t0, 1), "direction": o["direction"], ctx.mode: fmt22(res)})
    eng.an.summary()
    ts = eng.timer.summary(eng.models) + "\n" + _tail(ctx)
    print("\n" + ts)
    if dlog:
        dlog.write("\n" + ts)
        dlog.close()
    if csv_path:
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["start", "direction", ctx.mode])
            w.writeheader()
            w.writerows(rows)
        print(f"\n[저장] {csv_path}")
    if log:
        log.save(os.path.splitext(path)[0] + "_events.csv")


def main():
    ap = argparse.ArgumentParser(description="3모드 통합 (총게임 · 공포게임 · 예능): CLAP + PANNs·BEATs")
    ap.add_argument("--mode", choices=list(E.MODES), default="gun", help="gun(총게임) / horror(공포게임) / variety(예능) / kids(아동)")
    ap.add_argument("--models", default="clap,panns,beats", help="clap 필수 + panns, beats")
    ap.add_argument("--onoma", action="store_true", help="화면 이름에 의성어도 붙임 (예: 총성 탕!)")
    ap.add_argument("--eval", default=None, help="정답 구간 목록(segments.txt)으로 평가")
    ap.add_argument("--file", default=None, help="분석할 파일 (없으면 실시간)")
    ap.add_argument("--csv", default=None, help="결과 CSV 저장 (--file, --eval)")
    ap.add_argument("--debug", action="store_true", help="디버그 정보를 화면에도 출력 (기본: 파일에만 저장)")
    ap.add_argument("--no-log", action="store_true", help="디버그 기록 파일 저장 안 함")
    ap.add_argument("--normalize", action="store_true", help="구간 음량 맞추기")
    ap.add_argument("--silence", type=float, default=0.003, help="무음 기준. 기본 0.003")
    ap.add_argument("--hop", type=float, default=0.5, help="분석 간격(초). 기본 0.5")
    ap.add_argument("--latency-test", type=int, nargs="?", const=30, default=None,
                    help="지연 시험: 시험음을 N번(기본 30) 재생해 단계별 시간 실측 (다른 소리는 끄고)")
    ap.add_argument("--no-parallel", action="store_true", help="모델 3개를 예전처럼 차례로 실행 (동시 실행과 속도 비교용)")
    ap.add_argument("--clap-int8", action="store_true", help="CLAP int8 경량화 켜기 (총게임 실측에서 효과 없었음)")
    ap.add_argument("--check-clap", action="store_true", help="--clap-int8 과 원래 CLAP 결과 비교 (느려짐 — --hop 1 권장)")
    ap.add_argument("--save", default=None, help="(꺼짐) 예전: 녹음·이벤트 표 저장. 지금은 아무것도 저장하지 않음")
    ap.add_argument("--events", action="store_true", help="--file: <파일명>_events.csv 저장")
    ap.add_argument("--content", default=None, help="콘텐츠 이름 (이벤트 csv 에 기록). 기본: 모드 이름")
    ap.add_argument("--score", nargs="*", default=None, help="O/X 적은 *_events.csv 집계 (파일 생략 시 이 폴더 + debug_logs 전체)")
    args = ap.parse_args()
    if args.score is not None:
        run_score(args.score)
        return

    info = E.MODES[args.mode]
    keys = [k.strip().lower() for k in args.models.split(",") if k.strip()]
    print(f"[sound_live_all {E.VERSION} · models={','.join(keys)} · {info['icon']} {info['title']} 모드]")
    versions = {f"{info['G'].__name__}.py": getattr(info["G"], "VERSION", "옛 버전"),
                f"{info['J'].__name__}.py": getattr(info["J"], "VERSION", "옛 버전")}
    if len(set(versions.values())) > 1:
        print("!" * 60)
        print("[경고] 파일 버전이 서로 다릅니다 — 옛 파일이 섞여 있어요. 같은 버전으로 덮어쓰세요.")
        for f, v in versions.items():
            print(f"   {f:<24} {v}   ({os.path.abspath(getattr(sys.modules.get(f[:-3]), '__file__', f))})")
        print("!" * 60)
    eng = E.Engine(keys, normalize=args.normalize, hop=args.hop, silence=args.silence, modes=(args.mode,),
                   quant=args.clap_int8 or args.check_clap, check=args.check_clap, parallel=not args.no_parallel)
    ctx = Ctx(args.mode, eng, args.onoma)
    content = args.content if args.content is not None else info["content"]
    dlog = None
    if not args.no_log and not args.eval:
        os.makedirs("debug_logs", exist_ok=True)
        dlog = DebugLog(os.path.join("debug_logs", f"{args.mode}_{time.strftime('%m%d_%H%M%S')}.txt"), eng.SL.HOP_SEC)
        dlog.write(f"[sound_live_all {E.VERSION} · {info['title']} · models={','.join(keys)} · "
                   f"분석 간격 {eng.SL.HOP_SEC:.1f}초 · CLAP {eng.clap_mode}]")
        print(f"[디버그 기록] {dlog.path} 에 자동 저장 (화면에는 안 보임)")
    if args.latency_test:
        run_latency_test(ctx, args.latency_test, dlog)
        return
    if args.eval:
        run_eval(ctx, args.eval, args.csv or f"eval_{args.mode}.csv", args.debug)
    elif args.file:
        run_file(ctx, args.file, args.debug, args.csv, args.events, content, dlog)
    else:
        run_live(ctx, args.debug, args.save, content, dlog)


if __name__ == "__main__":
    main()
