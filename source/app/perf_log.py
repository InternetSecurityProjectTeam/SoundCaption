"""perf_log.py — 성능 기록 (2026-10-25). 테스트 실행 때만 켜짐 (성능기록_실행.bat / 지연시험_실행.bat)

  python main.py --perf                 # 평소처럼 쓰면서 분석마다 ④~⑧ 단계 시간·CPU·메모리·표시한 소리 기록
  python main.py --latency-test [N]     # 앱이 '딱' 시험음을 N번(기본 30) 재생해 ①~⑧ 전 단계를 실측

  저장: 앱 폴더의 perf_logs\\
    perf_MMDD_HHMMSS.csv / latency_MMDD_HHMMSS.csv   한 줄 = 분석 1회 / 시험음 1개
    ..._요약.txt                                     단계별 최소·평균·p95·최대, 0.5초 초과, CPU·메모리, 소리별 횟수
  한 번의 기록 = [서비스 시작] ~ [서비스 중지] (앱을 끄면 그때까지 저장)

  단계 (모두 ms)
    ① 오디오 엔진 통과   재생 요청 → 루프백에 그 소리가 들어온 순간 (지연 시험만)
    ② 루프백 전달        그 소리가 든 오디오 묶음이 앱에 도착할 때까지 (지연 시험만)
    ③ 분석 대기          도착 → 다음 분석이 버퍼를 꺼낼 때까지 (지연 시험만)
    ④ 처리               버퍼 꺼내기 ~ 판정 끝 (세부: 캡처 복사, 모델별 리샘플·전처리·추론, 기타, 돌발성, 판정)
    ⑤ 고르기             표시명·의성어, 칸 수 자르기, 소리 필터
    ⑥ UI 전달            백엔드 스레드 → 화면 스레드가 받을 때까지
    ⑦ 오버레이 배치      자막을 칸에 넣는 처리
    ⑧ 화면 그리기        → 오버레이 자막 칸이 다시 그려지기 시작한 순간
  모델 3개는 동시에 돌아서 모델별 시간을 더하면 ④보다 클 수 있음. 모니터 갱신(60Hz 면 최대 약 17ms)은 못 잼
"""
import csv
import os
import threading
import time
from collections import Counter, deque

import numpy as np

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "perf_logs")
PAINT_TIMEOUT = 2.0        # 이 시간 안에 화면이 다시 안 그려지면 ⑧ 은 빈칸으로 저장

UI_KEYS = ["⑥ UI 전달", "⑦ 오버레이 배치", "⑧ 화면 그리기"]
CLICK_KEYS = ["① 오디오 엔진 통과", "② 루프백 전달", "③ 분석 대기"]


def proc_keys(models):
    """④ 처리 세부 단계 이름 (CSV 열 순서)"""
    keys = ["④-1 캡처 복사"]
    for m in models:
        keys.append(f"④ {m}")
        keys.append(f"④ {m}·리샘플")
        if m.upper().startswith("CLAP"):
            keys.append(f"④ {m}·전처리")
        keys.append(f"④ {m}·추론")
    keys += ["④ 기타(방향/무음검사)", "④ 돌발성", "④ 판정", "④ 처리 합계", "⑤ 고르기"]
    return keys


def timer_stages(cur, models, t_copy_sec):
    """sound_engine.Timer 의 이번 분석 값(cur, 초) → 세부 단계 dict (초)"""
    out = {"④-1 캡처 복사": t_copy_sec}
    msum = 0.0
    for m in models:
        if m in cur:
            v = cur[m]
            msum += v
            out[f"④ {m}"] = v
            out[f"④ {m}·리샘플"] = cur.get(f"{m}·리샘플", 0.0)
            if m.upper().startswith("CLAP"):
                out[f"④ {m}·전처리"] = cur.get(f"{m}·전처리", 0.0)
            out[f"④ {m}·추론"] = max(0.0, v - cur.get(f"{m}·리샘플", 0.0) - cur.get(f"{m}·전처리", 0.0)
                                     - cur.get(f"{m}·비교", 0.0))
    if "분석 전체" in cur:
        out["④ 기타(방향/무음검사)"] = max(0.0, cur["분석 전체"] - msum)
    for k in ("돌발성", "판정"):
        if k in cur:
            out[f"④ {k}"] = cur[k]
    return out


class PerfLog:
    """한 번의 기록(서비스 시작~중지). 백엔드 스레드(step)와 화면 스레드(ui, painted)에서 불림 → 잠금 사용"""

    def __init__(self, kind, models, hop, device="", n_clicks=0):
        self.kind = kind                                  # "perf" | "latency"
        self.models, self.hop, self.device, self.n_clicks = list(models), hop, device, n_clicks
        os.makedirs(LOG_DIR, exist_ok=True)
        stamp = time.strftime("%m%d_%H%M%S")
        self.path = os.path.join(LOG_DIR, f"{kind}_{stamp}.csv")
        self.sum_path = os.path.join(LOG_DIR, f"{kind}_{stamp}_요약.txt")
        self.t_start = time.time()
        self.lock = threading.Lock()
        self.pending = {}                                 # 번호 → 아직 화면 쪽 시간이 안 온 줄
        self.rows = []                                    # 저장한 줄 (요약용, ms)
        self.steps = 0
        self.silent = 0
        self.over = 0
        self.modes = Counter()
        self.shown = Counter()
        self.cpu, self.mem = [], []
        self.closed = False
        self._seq = 0
        self._early = {}                                  # 백엔드가 기록하기 전에 화면 쪽이 먼저 받은 시간
        self._paints = deque(maxlen=120)                  # 최근 화면 그리기 (글자, 시각) — 늦게 등록된 줄과 맞춤
        self.stage_keys = proc_keys(self.models)
        self.total_key = "전체 (재생 요청 → 화면)" if kind == "latency" else "④~⑧ 합계 (분석 시작 → 화면)"
        self.over_key = f"처리 {hop:.1f}초 초과"
        head = ["번호", "시각", "모드"]
        if kind == "latency":
            head += [k + " (ms)" for k in CLICK_KEYS]
        head += [k + " (ms)" for k in self.stage_keys + UI_KEYS + [self.total_key]]
        head += [self.over_key, "CPU % (전체 대비)", "메모리 MB"]
        if kind == "latency":
            head += ["시험음 자막", "필터로 빠진 소리", "그 순간 모델 판정 (표시한 소리)"]
        else:
            head += ["표시한 소리", "필터로 빠진 소리"]
        self.f = open(self.path, "w", newline="", encoding="utf-8-sig")
        self.w = csv.writer(self.f)
        self.w.writerow(head)
        self.f.flush()
        try:
            import psutil
            self._proc = psutil.Process()
            self._ncpu = psutil.cpu_count() or 1
            self._proc.cpu_percent(None)
        except Exception:
            self._proc = None

    # ---------------- 자원 ----------------
    def _resources(self):
        if self._proc is None:
            return None, None
        try:
            cpu = self._proc.cpu_percent(None) / self._ncpu
            mem = self._proc.memory_info().rss / (1024 * 1024)
            return cpu, mem
        except Exception:
            return None, None

    # ---------------- 백엔드 스레드 ----------------
    def reserve(self):
        """보내기 전에 기록 번호를 먼저 받음 (이벤트에 붙여서 화면 쪽 시간과 맞춤)"""
        with self.lock:
            self._seq += 1
            return self._seq

    def step(self, mode_title, stages, t_copy, t_judged, t_emit, shown, dropped, clicks=(), silent=False, n=None):
        """분석 1회. stages: 세부 단계(초). t_*: perf_counter (t_emit=None 이면 화면으로 보낸 것 없음).
        shown/dropped: 표시명 목록. clicks: 지연 시험 — 이번 분석에 들어간 시험음 [dict(k, t_play, t_in, t_arr, label)]
        -> 화면 쪽에서 쓸 번호들 (이 번호를 이벤트에 붙여 보냄)"""
        if self.closed:
            return []
        cpu, mem = self._resources()
        with self.lock:
            self.steps += 1
            self.modes[mode_title] += 1
            if silent:
                self.silent += 1
            if cpu is not None:
                self.cpu.append(cpu)
                self.mem.append(mem)
            for s in shown:
                self.shown[s] += 1
            st = dict(stages)
            st["④ 처리 합계"] = t_judged - t_copy
            if t_emit is not None:
                st["⑤ 고르기"] = t_emit - t_judged
            if st["④ 처리 합계"] > self.hop:
                self.over += 1
            now = time.time()
            base = dict(time=time.strftime("%H:%M:%S", time.localtime(now)) + f".{int(now * 10) % 10}",
                        mode=mode_title, st=st, t_copy=t_copy, t_emit=t_emit, cpu=cpu, mem=mem,
                        shown=list(shown), dropped=list(dropped), silent=silent, created=time.perf_counter(),
                        recv=None, handled=None, painted=None)
            ids = []
            if self.kind == "perf":
                if n is None:
                    self._seq += 1
                    n = self._seq
                row = dict(base, n=n, labels=list(shown))
                if t_emit is None or not shown:                  # 화면으로 보낼 게 없음 → 바로 저장
                    self._write(row)
                else:
                    self._register(n, row)
                    ids.append(n)
            else:
                for c in clicks:
                    row = dict(base, n=c["k"], labels=[c["label"]], click=c)
                    self._register(c["k"], row)
                    ids.append(c["k"])
            self._flush_old()
            return ids

    def _register(self, n, row):
        """기다리는 줄로 등록. 화면 쪽이 먼저 받았거나 이미 그렸으면 그 시간을 붙임"""
        e = self._early.pop(n, None)
        if e is not None:
            row["recv"], row["handled"] = e
            for text, t in self._paints:
                if t >= row["handled"] and self._match(row, text):
                    row["painted"] = t
                    break
        if row["painted"] is not None:
            self._write(row)
        else:
            self.pending[n] = row

    @staticmethod
    def _match(row, text):
        return any(lb and lb in text for lb in row["labels"])

    # ---------------- 화면 스레드 ----------------
    def ui(self, n, t_recv, t_handled):
        with self.lock:
            r = self.pending.get(n)
            if r is None:                                 # 백엔드가 아직 기록 전 → 잠시 보관
                if n is not None and not self.closed:
                    e = self._early.get(n)
                    self._early[n] = (t_recv, t_handled) if e is None else (min(e[0], t_recv), max(e[1], t_handled))
                    if len(self._early) > 200:
                        self._early.pop(next(iter(self._early)))
                return
            r["recv"] = t_recv if r["recv"] is None else min(r["recv"], t_recv)
            r["handled"] = t_handled if r["handled"] is None else max(r["handled"], t_handled)

    def painted(self, text, t):
        """오버레이 자막 칸이 다시 그려질 때. 그 칸 글자에 이 줄의 소리 이름이 들어 있으면 ⑧ 끝"""
        with self.lock:
            if self.closed:
                return
            if self._early:
                self._paints.append((text, t))
            done = []
            for n, r in self.pending.items():
                if r["handled"] is not None and r["painted"] is None and t >= r["handled"] and self._match(r, text):
                    r["painted"] = t
                    done.append(n)
            for n in done:
                self._write(self.pending.pop(n))

    def flush(self):
        """오래 기다린 줄 저장 (화면 스레드 타이머가 부름)"""
        with self.lock:
            if not self.closed:
                self._flush_old()

    # ---------------- 저장 ----------------
    def _flush_old(self, force=False):
        now = time.perf_counter()
        for n in [n for n, r in self.pending.items() if force or now - r["created"] > PAINT_TIMEOUT]:
            self._write(self.pending.pop(n))

    def _write(self, r):
        st = dict(r["st"])
        if r["recv"] is not None and r["t_emit"] is not None:
            st["⑥ UI 전달"] = r["recv"] - r["t_emit"]
        if r["handled"] is not None and r["recv"] is not None:
            st["⑦ 오버레이 배치"] = r["handled"] - r["recv"]
        if r["painted"] is not None and r["handled"] is not None:
            st["⑧ 화면 그리기"] = r["painted"] - r["handled"]
        end = r["painted"] or r["handled"] or r["recv"] or r["t_emit"]
        ms = {k: v * 1000 for k, v in st.items()}
        if self.kind == "latency":
            c = r["click"]
            ms["① 오디오 엔진 통과"] = (c["t_in"] - c["t_play"]) * 1000
            ms["② 루프백 전달"] = (c["t_arr"] - c["t_in"]) * 1000
            ms["③ 분석 대기"] = (r["t_copy"] - c["t_arr"]) * 1000
            ms[self.total_key] = (end - c["t_play"]) * 1000 if end else None
        elif end and r["t_emit"] is not None:
            ms[self.total_key] = (end - r["t_copy"]) * 1000
        keys = (CLICK_KEYS if self.kind == "latency" else []) + self.stage_keys + UI_KEYS + [self.total_key]
        line = [r["n"], r["time"], r["mode"]]
        for k in keys:
            v = ms.get(k)
            line.append("" if v is None else round(v, 1))
        line += ["O" if st.get("④ 처리 합계", 0.0) > self.hop else "",
                 "" if r["cpu"] is None else round(r["cpu"], 1),
                 "" if r["mem"] is None else round(r["mem"], 1)]
        if self.kind == "latency":
            line += [r["click"]["label"], " / ".join(r["dropped"]), " / ".join(r["shown"]) or "(없음)"]
        else:
            line += [" / ".join(r["shown"]) or ("(무음)" if r["silent"] else "(없음)"), " / ".join(r["dropped"])]
        self.w.writerow(line)
        self.f.flush()
        self.rows.append({k: ms.get(k) for k in keys})

    def close(self):
        """남은 줄 저장 + 요약 파일. -> (csv 경로, 요약 경로)"""
        with self.lock:
            if self.closed:
                return self.path, self.sum_path
            self._flush_old(force=True)
            self.closed = True
            self.f.close()
            rep = self._summary()
        with open(self.sum_path, "w", encoding="utf-8-sig") as f:
            f.write(rep)
        return self.path, self.sum_path

    def _vals(self, k):
        return np.array([r[k] for r in self.rows if r.get(k) is not None], dtype=float) / 1000.0   # 초

    def _conclusion(self):
        """요약 맨 위 '결론' — 숫자 표를 안 봐도 알 수 있게 (초 단위)"""
        hop = self.hop
        proc = self._vals("④ 처리 합계")
        ui_parts = [self._vals(k) for k in ("⑤ 고르기", "⑥ UI 전달", "⑦ 오버레이 배치", "⑧ 화면 그리기")]
        ui = sum(float(a.mean()) for a in ui_parts if a.size)
        n_ui = int(self._vals("⑧ 화면 그리기").size)
        L = ["[결론]"]
        if proc.size == 0:
            L.append("  분석 기록이 없어요 (서비스를 켜고 소리를 재생해 주세요)")
            return L
        if self.kind == "latency":
            tot = self._vals(self.total_key)
            if tot.size:
                L.append(f"  ▶ 소리가 나서 자막이 뜨기까지: 평균 {tot.mean():.2f}초 "
                         f"(가장 빠를 때 {tot.min():.2f}초 · 가장 느릴 때 {tot.max():.2f}초, 시험음 {tot.size}개)")
            a1, a2, a3 = self._vals("① 오디오 엔진 통과"), self._vals("② 루프백 전달"), self._vals("③ 분석 대기")
            L.append("  그 안에서 걸린 시간 (평균):")
            if a1.size and a2.size:
                L.append(f"    - 윈도우 오디오 (①+②)          {a1.mean() + a2.mean():.2f}초")
            if a3.size:
                L.append(f"    - 다음 분석까지 기다림 (③)      {a3.mean():.2f}초  ← 운에 따라 0~{hop:.1f}초 (분석이 {hop:.1f}초마다 돌아서)")
            L.append(f"    - 분석 (④)                       {proc.mean():.2f}초")
            if ui:
                L.append(f"    - 분석 결과 → 화면 (⑤~⑧)        {ui:.2f}초")
        else:
            L.append(f"  ▶ 분석(④): 평균 {proc.mean():.2f}초 · 가장 느릴 때 {proc.max():.2f}초 "
                     + (f"→ {hop:.1f}초 안에 다 끝남 (밀리지 않음)" if self.over == 0 else
                        f"→ {hop:.1f}초를 {self.over}번 넘김 (그때는 자막이 밀림)"))
            if n_ui:
                L.append(f"  ▶ 분석 결과 → 화면(⑤~⑧): 평균 {ui:.2f}초 (자막이 그려진 {n_ui}번 기준)")
            else:
                L.append("  ▶ 분석 결과 → 화면(⑤~⑧): 이번엔 새로 그려진 자막이 없어 못 잼")
            ui_est = ui if n_ui else 0.03
            base = 0.03 + ui_est                              # 윈도우 오디오(약 0.03초, 지연 시험 기준) + 화면
            avg = base + hop / 2 + proc.mean()
            lo, hi = base + proc.min(), base + hop + proc.max()
            L.append(f"  ▶ 예상 체감 지연 (소리 → 자막): 평균 약 {avg:.2f}초 (운 좋으면 {lo:.2f}초 · 나쁘면 {hi:.2f}초)")
            L.append(f"     = 분석 {proc.mean():.2f} + 다음 분석까지 기다림 평균 {hop / 2:.2f} (0~{hop:.1f}) + 윈도우 오디오·화면 약 {base:.2f}")
            L.append("     정확한 값은 지연시험_실행.bat 으로 재요")
        models = [(m, self._vals(f"④ {m}")) for m in self.models]
        models = [(m, a) for m, a in models if a.size]
        if models:
            slow = max(models, key=lambda x: x[1].mean())
            others = ", ".join(f"{m} {a.mean():.2f}초" for m, a in models if m != slow[0])
            L.append(f"  ▶ 가장 오래 걸린 곳: {slow[0]} 모델 평균 {slow[1].mean():.2f}초"
                     + (f" (다른 모델: {others})" if others else ""))
            L.append("     모델들은 동시에 돌아서, 가장 느린 모델이 분석 시간을 정해요")
        if self.cpu:
            L.append(f"  ▶ 컴퓨터 부담: CPU 평균 {np.mean(self.cpu):.0f}% (최대 {np.max(self.cpu):.0f}%) · "
                     f"메모리 약 {np.mean(self.mem) / 1024:.1f}GB")
        return L

    def _summary(self):
        dur = time.time() - self.t_start
        title = "지연 시험" if self.kind == "latency" else "성능 기록"
        L = [f"[{title}] {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.t_start))} 부터 "
             f"{int(dur // 60)}분 {int(dur % 60)}초", ""]
        L += self._conclusion()
        L += ["", "[자세히]",
             f"  모드: {', '.join(f'{m} {n}회' for m, n in self.modes.items()) or '-'}",
             f"  캡처 장치: {self.device or '-'}",
             f"  모델: {', '.join(self.models)} · 분석 간격 {self.hop:.1f}초",
             f"  분석 횟수: {self.steps}회 (무음 {self.silent}회)"]
        if self.kind == "latency":
            L.append(f"  시험음: {len(self.rows)}/{self.n_clicks}개 기록")
        L.append(f"  처리(④)가 {self.hop:.1f}초를 넘긴 횟수: {self.over}회"
                 + (f" ({self.over / self.steps * 100:.1f}%)" if self.steps else ""))
        if self.cpu:
            L.append(f"  CPU (전체 대비): 평균 {np.mean(self.cpu):.1f}% · 최대 {np.max(self.cpu):.1f}%")
            L.append(f"  메모리: 평균 {np.mean(self.mem):.0f}MB · 최대 {np.max(self.mem):.0f}MB")
        else:
            L.append("  CPU·메모리: psutil 이 없어 기록 안 함")
        L.append("")
        unit = "시험음 1개당" if self.kind == "latency" else "분석 1회당"
        L.append(f"[단계별 시간 — {unit}, ms]")
        L.append(f"  {'단계':<30} {'최소':>8} {'평균':>8} {'p95':>8} {'최대':>8}  횟수")
        keys = list(self.rows[0]) if self.rows else []
        for k in keys:
            a = np.array([r[k] for r in self.rows if r.get(k) is not None], dtype=float)
            if a.size == 0:
                continue
            L.append(f"  {k:<30} {a.min():8.1f} {a.mean():8.1f} {np.percentile(a, 95):8.1f} {a.max():8.1f}  {a.size}")
        sent = [r for r in self.rows if r.get("⑤ 고르기") is not None and (self.kind == "latency" or r.get("⑥ UI 전달") is not None)]
        no_paint = sum(1 for r in sent if r.get("⑧ 화면 그리기") is None)
        if no_paint:
            L.append(f"  ※ 화면으로 보냈는데 ⑧ 이 빈 줄 {no_paint}개: 같은 자막이 이미 떠 있어 다시 안 그려졌거나, "
                     f"미리보기 중이었거나, {PAINT_TIMEOUT:.0f}초 안에 안 그려짐")
        L.append("  ※ 모델 3개는 동시에 돌아서 모델별 시간을 더하면 ④ 처리 합계보다 클 수 있어요")
        if self.kind == "latency":
            L.append("  ※ ①에는 시험음을 내는 쪽의 출력 버퍼도 포함 (게임·영상도 자기 버퍼가 있음). 모니터 갱신 시간은 미포함")
        L.append("")
        L.append("[화면에 표시한 소리 — 횟수]")
        for name, n in self.shown.most_common():
            L.append(f"  {name}: {n}")
        if not self.shown:
            L.append("  (없음)")
        L.append("")
        L.append(f"CSV: {self.path}")
        return "\n".join(L) + "\n"


# ----------------------------------------------------------------------
# 지연 시험: 시험음 재생 + 루프백 도착 시각 (sound_live_gun v1.12c 지연 시험과 같은 방식)
# ----------------------------------------------------------------------
CLICK_LEVEL = 0.3       # 루프백에서 이 크기 이상이면 시험음이 들어온 것으로 봄 (다른 소리는 끄고 시험)


def latency_capture_class(FreshCapture):
    class LatencyCapture(FreshCapture):
        """루프백 묶음마다 도착 시각을 재고, 시험음이 처음 들어온 샘플 위치로 '오디오 엔진 통과 시각'을 계산"""

        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.expect = None                                   # (번호, 재생 요청 시각)
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

        def take_hits(self, t_copy):
            """t_copy(버퍼를 꺼낸 시각) 전에 도착한 시험음들"""
            with self.hit_lock:
                new = [h for h in self.hits if h["t_arr"] <= t_copy]
                self.hits = [h for h in self.hits if h["t_arr"] > t_copy]
            return new
    return LatencyCapture


class ClickPlayer(threading.Thread):
    """캡처 중인 출력 장치로 무음을 계속 흘리다가 2.5~3.5초마다 3ms '딱'을 재생.
    무음을 계속 흘리는 이유: 윈도우 루프백은 재생되는 소리가 없으면 데이터를 안 보냄"""

    def __init__(self, cap, n, gap=(2.5, 3.5)):
        super().__init__(daemon=True)
        import pyaudiowpatch as pyaudio
        self.pa = pyaudio.PyAudio()
        dev = self._output_for(pyaudio, cap.device["name"])
        self.dev_name = dev["name"]
        sr, ch = int(dev["defaultSampleRate"]), max(1, min(2, int(dev["maxOutputChannels"])))
        block = max(64, int(sr * 0.005))                         # 5ms 단위로 씀
        self.stream = self.pa.open(format=pyaudio.paInt16, channels=ch, rate=sr, output=True,
                                   output_device_index=dev["index"], frames_per_buffer=block)
        rng = np.random.default_rng()
        c = np.zeros(block, np.float32)
        m = int(sr * 0.003)
        c[:m] = rng.uniform(-0.8, 0.8, m)
        self.click = (np.repeat(c[:, None], ch, axis=1) * 32767).astype(np.int16).tobytes()
        self.silence = np.zeros((block, ch), np.int16).tobytes()
        self.cap, self.n, self.gap, self.rng = cap, n, gap, rng
        self.stop_flag, self.played = False, 0

    def _output_for(self, pyaudio, loopback_name):
        """캡처 중인 루프백 장치와 같은 출력 장치 (못 찾으면 윈도우 기본 출력 장치)"""
        wasapi = self.pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        want = str(loopback_name).replace(" [Loopback]", "")
        for i in range(self.pa.get_device_count()):
            d = self.pa.get_device_info_by_index(i)
            if d.get("hostApi") == wasapi["index"] and int(d.get("maxOutputChannels", 0)) > 0 \
                    and not d.get("isLoopbackDevice", False) and d["name"] == want:
                return d
        return self.pa.get_device_info_by_index(wasapi["defaultOutputDevice"])

    def run(self):
        try:
            k, nxt = 0, time.perf_counter() + 2.0
            while k < self.n and not self.stop_flag:
                if time.perf_counter() >= nxt:
                    k += 1
                    self.cap.expect = (k, time.perf_counter())
                    self.stream.write(self.click)
                    self.played = k
                    nxt = time.perf_counter() + self.rng.uniform(*self.gap)   # 분석 주기와 안 맞물리게
                else:
                    self.stream.write(self.silence)
            end = time.perf_counter() + 3.0                      # 마지막 시험음이 분석될 때까지 무음 유지
            while time.perf_counter() < end and not self.stop_flag:
                self.stream.write(self.silence)
        finally:
            self.stream.stop_stream()
            self.stream.close()
            self.pa.terminate()
