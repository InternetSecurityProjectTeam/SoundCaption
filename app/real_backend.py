"""실제 백엔드 (2026-10-22) — 프론트엔드 앱(main.py)과 3모드 엔진(sound_engine.py)을 잇는 스레드

  - 앱이 켜지면 모델을 한 번만 올림 (CLAP + PANNs + BEATs, 판정기 3개)
  - 프론트에서 고른 모드(FPS·공포·예능, 프리셋은 base_mode)의 판정기로 계산
    모드가 바뀌면(모드 타일·Alt+M·프리셋) 그 판정기의 이전 상태(지속음·분위기)를 지우고 시작
  - 서비스 시작/중지에 맞춰 루프백 캡처를 켜고 끔
  - 보내는 것: 프론트 칸 수만큼 위에서 자른 뒤, 소리 필터로 꺼 둔 그룹은 탈락 (빈자리는 채우지 않음)
  - 의성어: 설정 'onoma_enabled' 켜짐이면 "표시명 의성어", 꺼짐이면 표시명만
  - 횟수(count)·굵기(strength) 폐지 → 항상 1
  - 성능 기록 (테스트 실행 때만, perf_log.py): perf="perf" 면 분석마다 ④~⑧ 단계 시간을,
    perf="latency" 면 시험음을 재생해 ①~⑧ 단계 시간을 perf_logs\ 에 저장
"""
import threading
import time
import traceback

import sound_engine as E
from events import SoundEvent
from settings import normalize


# v0.56 (2026-11-10): 갑자기 난 소리는 0.5초 차례를 기다리지 않고 바로 분석
#   분석 사이 쉬는 동안 40ms 마다 마지막 1초 소리를 봄 (10ms 조각 에너지, 고음 위주 = 돌발성 계산과 같은 방식).
#   지난 분석 이후에 '보통 수준(중앙값)보다 ONSET_DB 이상 튄' 조각이 생기면 → 그 순간 + ONSET_DELAY 에 분석.
#   그 분석이 다음 차례를 대신함 (다음은 거기서 0.5초 뒤) → 분석 횟수는 그대로, CPU 도 그대로.
#   너무 잦으면(총소리 연사) 1초에 한 번만 당김 → 최악 +15% 정도. 끄려면 ONSET_EARLY = False
ONSET_EARLY = True
# v0.56: CLAP·BEATs 경량화(int8) 켬 — 속도시험 11-10 (22코어 노트북): 분석 0.27 → 0.23초 · CPU 39 → 33% · 표시 77판 100% 같음
#   (CLAP 임베딩 일치 평균 0.991, 최저 0.980). 판정이 이상하면 False 로 (원래 모델)
QUANT = True
# v0.58: 앱(run_app)도 터미널 실행과 같은 디버그 기록을 남김 → debug_logs/<모드>_<시각>.txt (tools/kids_score.py 로 바로 채점 가능)
#   서비스 시작~중지 · 모드가 바뀌면 새 파일. ⚡ = 갑자기 난 소리라 차례보다 당겨서 분석한 판
APP_DEBUG_LOG = True
# v0.59: 윈도우 절전 제한 끄기 + 우선순위 '보통 이상'
#   앱 디버그 기록(11-10 01:37): 분석 평균 0.60초 (처음 몇 번만 0.25~0.30초) ↔ 속도시험(창 맨 앞 콘솔) 0.23초.
#   인텔 코어 울트라(22스레드)는 앞에 안 띄운 프로그램을 절전용 저전력 코어로 보내 느려짐 (Windows 11 '전원 제한')
#   → 이 프로세스만 제한 끔. CPU 를 더 쓰는 게 아니라 같은 일을 빠른 코어에서 함. 끄려면 NO_THROTTLE = False
NO_THROTTLE = True


def _no_throttle():
    """-> 결과 문자열 (디버그 기록 첫 줄에 남김)"""
    import sys
    if sys.platform != "win32":
        return "해당 없음"
    try:
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.GetCurrentProcess.restype = wintypes.HANDLE
        # v0.60: 인자 형식 지정 (안 하면 핸들 -1 을 32비트 int 로 넘기다 OverflowError → 11-10 09:51 로그 '실패')
        k.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k.SetProcessInformation.restype = wintypes.BOOL
        k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k.SetPriorityClass.restype = wintypes.BOOL

        class PPT(ctypes.Structure):
            _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]
        st = PPT(1, 0x1 | 0x4, 0)            # EXECUTION_SPEED · IGNORE_TIMER_RESOLUTION 를 '제한 안 함'으로
        h = k.GetCurrentProcess()
        ok1 = k.SetProcessInformation(h, 4, ctypes.byref(st), ctypes.sizeof(st))   # 4 = ProcessPowerThrottling
        ok2 = k.SetPriorityClass(h, 0x8000)                                        # ABOVE_NORMAL_PRIORITY_CLASS
        try:
            ctypes.WinDLL("winmm").timeBeginPeriod(1)                              # sleep 오차 15ms → 1ms
        except Exception:
            pass
        return f"절전 제한 {'끔' if ok1 else '실패'} · 우선순위 {'보통 이상' if ok2 else '실패'}"
    except Exception as e:
        return f"실패 ({e})"
ONSET_DB = 12.0            # 보통 수준보다 이만큼 튀면 '갑자기 난 소리'
ONSET_LEVEL = 0.003        # 이 소리 크기(RMS)보다 작으면 무시 (무음 기준과 같음)
ONSET_DELAY = 0.2          # 소리 시작 뒤 이만큼 소리를 담고 분석 (너무 빠르면 모델이 소리를 덜 들음)
ONSET_MIN_GAP = 0.3        # 지난 분석과 최소 간격
ONSET_EVERY = 1.0          # 당기는 건 이 초에 한 번까지
ONSET_POLL = 0.04


def _onset_time(cap, since, now):
    """마지막 1초에서 since 이후 처음 튄 순간(시각) 또는 None"""
    import numpy as np
    x = cap.get_last(1.0)
    if x.size == 0:
        return None
    m = x.mean(axis=1) if x.ndim == 2 else x
    sr = cap.sr
    n = max(1, int(sr * 0.01))
    k = (len(m) - 1) // n
    if k < 20:
        return None
    d = np.diff(m)[-k * n:].reshape(k, n)
    e = (d ** 2).mean(axis=1) + 1e-12
    lvl = np.sqrt((m[-k * n:].reshape(k, n) ** 2).mean(axis=1))
    base = np.median(e)
    hot = np.nonzero((10 * np.log10(e / base) >= ONSET_DB) & (lvl >= ONSET_LEVEL))[0]
    for i in hot:
        t = now - (k - i) * 0.01
        if t > since:
            return t
    return None


class RealBackend(threading.Thread):
    def __init__(self, bridge, models="clap,panns,beats", hop=0.5, silence=0.003, perf=None, latency_n=30):
        super().__init__(daemon=True)
        self.bridge = bridge
        self.models = [m for m in models.split(",") if m.strip()]
        self.hop, self.silence = hop, silence
        self._settings = normalize({})
        self._running = threading.Event()
        self._stop_event = threading.Event()
        self._suppressed = False          # 선택적 테스트 이벤트와 실제 이벤트가 섞이지 않게 제어
        self.engine = None
        self.mode = None
        self.status = "모델 준비 전"
        self._capture = self._settings["capture_target"]   # 써야 할 캡처 장치 (UI에서 고르면 바로 바뀜)
        self._cap_target = None           # 지금 캡처 중인 장치 설정값 (바뀌면 캡처를 다시 엶)
        self._dev_label = ""
        self.perf = perf                  # None | "perf" | "latency"  (성능기록_실행.bat / 지연시험_실행.bat)
        self.latency_n = latency_n
        self._log = None                  # 지금 기록 중인 perf_log.PerfLog (서비스 시작~중지)
        self._player = None               # 지연 시험 시험음 재생기

    # ---------- UI(메인) 스레드에서 불림 — 바로 반환 ----------
    def apply_settings(self, settings):
        self._settings = normalize(settings)
        self._capture = self._settings["capture_target"]

    def set_capture(self, name):
        """사운드 캡처 장치를 고르면 바로 불림 → 다음 분석 때 그 장치로 다시 엶"""
        self._capture = normalize({"capture_target": name})["capture_target"]

    def set_running(self, on):
        (self._running.set if on else self._running.clear)()

    def set_suppressed(self, on):
        self._suppressed = bool(on)

    def stop(self):
        self._stop_event.set()
        self._running.clear()
        self._close_log()                 # 앱을 끄면 그때까지 기록 저장

    # ---------- 성능 기록: 화면 스레드에서 불림 ----------
    def perf_ui(self, n, t_recv, t_handled):
        log = self._log
        if log is not None:
            log.ui(n, t_recv, t_handled)

    def perf_paint(self, text, t):
        log = self._log
        if log is not None:
            log.painted(text, t)

    # ---------- 성능 기록: 열기·닫기 ----------
    def _open_log(self, cap):
        if not self.perf:
            return
        import perf_log as P
        self._close_log()
        self._log = P.PerfLog(self.perf, self.engine.models, self.engine.SL.HOP_SEC,
                              device=cap.device.get("name", ""), n_clicks=self.latency_n)
        if self.perf == "latency":
            try:
                self._player = P.ClickPlayer(cap, self.latency_n)
                self._player.start()
                sec = self.latency_n * 3
                self._status(f"지연 시험 중 — 시험음 {self.latency_n}번 (약 {sec // 60}분 {sec % 60}초). "
                             f"다른 소리는 꺼 주세요 · 재생 장치: {self._player.dev_name}")
            except Exception as e:
                traceback.print_exc()
                self._status(f"지연 시험 시험음을 재생하지 못함: {e}")
                self._player = None
        else:
            self._status("소리 듣는 중 · 성능 기록 중" + self._dev_label)

    def _close_log(self):
        if self._player is not None:
            self._player.stop_flag = True
            self._player = None
        log, self._log = self._log, None
        if log is not None:
            try:
                path, sum_path = log.close()
                self._status(f"성능 기록 저장: {sum_path}")
            except Exception as e:
                traceback.print_exc()
                self._status(f"성능 기록 저장 실패: {e}")

    def _latency_finished(self, cap):
        """시험음을 다 재생했고 마지막 시험음까지 분석했으면 끝"""
        p = self._player
        if self.perf != "latency" or self._log is None or p is None or p.is_alive():
            return False
        with cap.hit_lock:
            waiting = bool(cap.hits)
        return not waiting

    # ---------- 백엔드 스레드 ----------
    def _status(self, text):
        self.status = text
        print(f"[백엔드] {text}")
        sig = getattr(self.bridge, "backend_status", None)
        if sig is not None:
            sig.emit(text)

    def run(self):
        self._throttle = _no_throttle() if NO_THROTTLE else "그대로"
        print(f"[백엔드] {self._throttle}")
        self._status("모델 불러오는 중… (처음 한 번만, 수십 초 걸릴 수 있어요)")
        try:
            self.engine = E.Engine(self.models, hop=self.hop, silence=self.silence, quant=QUANT)
        except BaseException as e:            # SystemExit 포함 (모델·패키지 없음 등)
            traceback.print_exc()
            self._status(f"백엔드 준비 실패: {e}")
            return
        # 프론트 칸 수(최대 5)로 자르기 위해 판정기의 개수 제한을 5로 — 자르는 위치만 바뀌고 계산은 같음
        for info in E.MODES.values():
            info["G"].MAX_INSTANT = info["G"].MAX_SUSTAINED = 5
        self.engine.timer.drop()
        self._status("준비 완료 — 서비스 시작을 누르면 소리를 듣기 시작해요")
        try:
            self._loop()
        except Exception as e:
            traceback.print_exc()
            self._status(f"백엔드 오류로 멈춤: {e}")

    def _loop(self):
        SL, eng = self.engine.SL, self.engine
        FreshCapture, _ = E.capture_classes()
        if self.perf == "latency":
            import perf_log as P
            FreshCapture = P.latency_capture_class(FreshCapture)
        cap, was_stale = None, False
        try:
            while not self._stop_event.is_set():
                target = self._capture
                if cap is not None and target != self._cap_target:     # 캡처 장치가 바뀜 → 다시 엶
                    self._close_log()
                    cap.stop()
                    cap = None
                    self.mode = None                                     # 새 장치로 판정 상태도 새로 시작
                if not self._running.is_set():
                    if cap is not None:
                        cap.stop()
                        cap = None
                        self._status("준비 완료 — 서비스 중지됨")
                        self._close_log()
                    self._close_dlog()
                    time.sleep(0.1)
                    continue
                if cap is None:
                    try:
                        self._cap_target = target
                        cap = FreshCapture(buffer_sec=max(10.0, SL.WINDOW_SEC * 2), device_name=target)
                        cap.start()
                    except Exception as e:
                        traceback.print_exc()
                        self._status(f"소리 캡처를 시작하지 못함: {e}")
                        cap = None
                        self._stop_event.wait(3.0)               # 3초 뒤 다시 시도
                        continue
                    self._dev_label = f" · 장치: {cap.device['name']}"
                    if cap.used_fallback:
                        self._dev_label += f" (선택한 '{target}'을(를) 찾지 못해 기본 출력 장치로 듣는 중)"
                    self._status("소리 듣는 중" + self._dev_label)
                    self._open_log(cap)
                    self._stop_event.wait(SL.WINDOW_SEC)      # 2초 버퍼가 찰 때까지 (CLI 와 같음)
                    was_stale = False

                t0 = time.time()
                s = self._settings
                mode = E.FRONT_TO_MODE.get(s["base_mode"], "gun")
                if mode != self.mode:
                    eng.mode_reset(mode)
                    self.mode = mode
                    was_stale = False
                    self._status(f"소리 듣는 중 · {E.MODES[mode]['title']} 모드{self._dev_label}")

                if cap.stale():
                    if not was_stale:
                        eng.pause_reset(mode)                    # 각 모드 CLI 와 같은 규칙
                        was_stale = True
                    time.sleep(SL.HOP_SEC)
                    continue
                was_stale = False

                log = self._log
                t_copy = time.perf_counter()
                buf = cap.get_last(SL.WINDOW_SEC)
                t_copied = time.perf_counter()
                clicks = cap.take_hits(t_copy) if (log is not None and self.perf == "latency") else []
                o = eng.step(buf, cap.sr, mode)
                t_judged = time.perf_counter()
                cur = dict(eng.timer.cur) if log is not None else None
                if APP_DEBUG_LOG and o is not None:
                    self._write_dlog(mode, o, t0)
                eng.timer.drop()                                 # 앱에서는 처리 시간을 쌓지 않음
                evs, dropped = [], []
                if o is not None and not self._suppressed:
                    disp = E.display(mode, eng.judges[mode], o["res"], o["emb"], s["onoma_enabled"])
                    inst, sust, dropped = E.select_for_front(disp, s)
                    evs = E.to_events(inst, sust, "center" if mode == "kids" else o["direction"])   # v0.49: 아동 모드는 좌우 판단 안 함
                if log is None:
                    for ev in evs:
                        self.bridge.sound_received.emit(ev)
                else:
                    self._emit_logged(log, mode, evs, dropped, clicks, cur, t_copy, t_copied, t_judged, o is None)
                    if self._latency_finished(cap):
                        self._close_log()
                self._early = self._wait_next(cap, t0, SL.HOP_SEC)
        finally:
            self._close_dlog()
            self._close_log()
            if cap is not None:
                cap.stop()

    def _write_dlog(self, mode, o, t0):
        """v0.58: 터미널 실행(sound_live_all)과 같은 양식의 디버그 기록"""
        try:
            import sound_live_all as SA
            eng = self.engine
            if getattr(self, "_dlog", None) is None or self._dlog_mode != mode:
                import os
                self._close_dlog()
                os.makedirs("debug_logs", exist_ok=True)
                self._dlog = SA.DebugLog(os.path.join("debug_logs", f"{mode}_{time.strftime('%m%d_%H%M%S')}.txt"), eng.SL.HOP_SEC)
                self._dlog.write(f"[run_app {E.VERSION} · {E.MODES[mode]['title']} · models={','.join(eng.models)} · "
                                 f"분석 간격 {eng.SL.HOP_SEC:.1f}초 · CLAP {eng.clap_mode} · 당겨 분석 {'켬' if ONSET_EARLY else '끔'} · {getattr(self, '_throttle', '')}]")
                self._dlog_mode, self._dctx = mode, SA.Ctx(mode, eng, True)
            res = self._dctx.view(o)
            stamp = time.strftime("%H:%M:%S", time.localtime(t0)) + f".{int(t0 * 10) % 10}"
            text = f"{stamp} " + ("⚡ " if getattr(self, "_early", False) else "") + SA.line(res, o["direction"])
            timing = eng.timer.commit(eng.models)
            self._dlog.block(text + "\n" + SA.fmt_debug(self._dctx, res) + (f"\n         └ {timing}" if timing else ""))
        except Exception:
            traceback.print_exc()

    def _close_dlog(self):
        d, self._dlog = getattr(self, "_dlog", None), None
        if d is not None:
            try:
                d.close()
                print(f"[디버그 기록] {d.path} 저장")
            except Exception:
                pass

    def _wait_next(self, cap, t0, hop):
        """다음 분석까지 기다림. 갑자기 난 소리가 있으면 일찍 깸 (v0.56). -> 당겼으면 True"""
        due = t0 + hop
        if not ONSET_EARLY or getattr(self, "_t_early", 0.0) > time.time() - ONSET_EVERY:
            time.sleep(max(0.0, due - time.time()))
            return False
        while not self._stop_event.is_set():
            now = time.time()
            if now >= due:
                return False
            try:
                on = _onset_time(cap, t0, now)
            except Exception:
                on = None
            if on is not None:
                at = max(on + ONSET_DELAY, t0 + ONSET_MIN_GAP)
                if at < due - 0.05:                      # 차례보다 확실히 빠를 때만
                    self._t_early = at
                    time.sleep(max(0.0, at - time.time()))
                    return True
                time.sleep(max(0.0, due - time.time()))
                return False
            time.sleep(min(ONSET_POLL, max(0.0, due - now)))
        return False

    def _emit_logged(self, log, mode, evs, dropped, clicks, cur, t_copy, t_copied, t_judged, silent):
        """성능 기록 중: 이벤트에 기록 번호를 붙여 보내고, 이번 분석의 단계 시간을 기록.
        지연 시험이면 시험음마다 '⏱ 시험음 #번호' 자막을 같은 경로로 보내 ⑤~⑧ 을 실제로 잼"""
        import perf_log as P
        shown = [ev.label for ev in evs]
        markers = []
        for c in clicks:
            c["label"] = f"⏱ 시험음 #{c['k']}"
            markers.append((c["k"], SoundEvent(label=c["label"], kind="instant", key="", category="",
                                               direction="center", score=99.0)))
        out = list(evs) + [m for _, m in markers]
        if self.perf == "perf":
            n = log.reserve() if out else None
            for ev in out:
                ev._perf_n = n
        else:
            for k, m in markers:
                m._perf_n = k
        t_emit = time.perf_counter() if out else None
        for ev in out:
            self.bridge.sound_received.emit(ev)
        stages = P.timer_stages(cur or {}, self.engine.models, t_copied - t_copy)
        log.step(E.MODES[mode]["title"], stages, t_copy, t_judged, t_emit, shown,
                 [d["text"] for d in dropped], clicks=clicks, silent=silent,
                 n=(out[0]._perf_n if (out and self.perf == "perf") else None))
