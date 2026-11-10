"""
kids_anim.py — 🧸 아동 모드 애니메이션 층 (2026-11-05, PySide6)
"""
import json
import math
import os
import random
import time

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import (QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QPolygonF, QRadialGradient, QTransform)
import threading
from PySide6.QtWidgets import QWidget

try:
    import kids_labels as K
except Exception:
    K = None

HERE = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(HERE, "assets", "kids_anim")

COOLDOWN_SEC = 3.0
DURATION_BY = {
    "띠용 효과음": 1.0, "휙 지나가는 소리": 1.0, "반짝 효과음": 1.0, "쿵 부딪히는 소리": 1.0,
    "삑삑 효과음": 1.0, "콜록 기침": 1.0, "에취 재채기": 1.0, "숨소리": 1.0,
    "딸꾹질 소리": 1.0, "똑똑 노크 소리": 1.0, "딩동 벨소리": 1.0, "웃음소리": 1.5
}
REPEAT_HOLD_BY = {
    "띠용 효과음": 0.5, "휙 지나가는 소리": 0.5, "반짝 효과음": 0.5, "쿵 부딪히는 소리": 0.5,
    "삑삑 효과음": 0.5, "콜록 기침": 0.5, "에취 재채기": 0.5, "숨소리": 0.5,
    "딸꾹질 소리": 0.5, "똑똑 노크 소리": 0.5, "딩동 벨소리": 0.5, "웃음소리": 0.5
}
REPEAT_HOLD = 0.5
REPEAT_HOLD_OLD = 1.0
CONT_HOLD_BY = {"새 짹짹": 0.5}
CONT_HOLD_SEC = 1.5
FRAME_MS = 33
ENTER_SEC = 0.2
GLIDE_RATE = 8.0           # 소리 수가 바뀔 때 그림이 새 자리로 미끄러지는 빠르기 (클수록 빠름. 8 ≈ 0.3초에 거의 도착)
EXIT_SEC = 0.5
MAX_INSTANT = 12

FLIP_FACE = {"dog", "cat", "cow", "pig", "sheep", "horse", "duck", "chicken", "bird", "frog", "lion", "bee", "whoosh"}
EMOJI_CQW = 8.2
CAPTION_UNDER = True
CAPTION_SCALE = 0.6
FIG_SIDE = True
FIG_GAP = 10
FIG_MAX_COLS = 3
FIG_CORE_H = 11.5
PER_BOX = 3
CONT_SPRITE_EXTENT = 7.5
CONT_ICON_SCALE = 0.9
INSTANT_ICON_SCALE = 0.9    # 2026-11-11: 0.75 → 0.9 (사용자: 조금 더 크게)
CONT_SCALE = 0.75
EMOJI_FONTS = ["Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji"]
NOTE_COLORS = ["#5db0ff", "#ff8fc7", "#ffd35c", "#8ef0b0", "#b79cff"]
VIEWS = ("그림 + 짧은 글", "그림만", "글 위주")


def _clamp(v, a, b):
    return a if v < a else b if v > b else v


def _ease_out_back(t):
    c1, c3 = 1.70158, 2.70158
    t -= 1
    return 1 + c3 * t * t * t + c1 * t * t


def _lerp_keys(keys, t):
    if t <= keys[0][0]:
        return keys[0][1:]
    for (t0, *v0), (t1, *v1) in zip(keys, keys[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0) if t1 > t0 else 1
            return tuple(a + (b - a) * u for a, b in zip(v0, v1))
    return keys[-1][1:]


JPOP_SEC = 0.55
JPOP = [(0, 0.0, 0.0), (0.28, 1.4, 0.62), (0.46, 0.78, 1.3), (0.62, 1.15, 0.88), (0.78, 0.95, 1.06), (1, 1, 1)]

LEAD_SEC = {
    "boing": 0.15, "zing": 0.2, "bell": 0.25, "clap": 0.3,
    "toilet": 0.35, "snore": 0.4, "door": 0.5,
    "dog": 0.2, "cat": 0.25, "cow": 0.25, "pig": 0.15, "sheep": 0.3, "horse": 0.25, "duck": 0.2,
    "chicken": 0.25, "bird": 0.15, "frog": 0.2, "owl": 0.25, "lion": 0.25,
}
FRAME_CACHE = 6
ONCE_SPEED = 1.25
LOOP_SPEED = 1.0


class Sprite:
    def __init__(self, name, meta):
        self.name = name
        self.path = os.path.join(ASSET_DIR, f"{name}.png")
        self._img = None
        self._data = None
        self._frames = {}
        self.last_used = 0.0
        self.m = meta
        self.n, self.fps, self.loop = meta["n"], meta["fps"], meta["loop"]
        self.dur = self.n / self.fps
        self.lead = float(meta.get("lead", LEAD_SEC.get(name, 0.0)))
        self.speed = LOOP_SPEED if self.loop else ONCE_SPEED

    def prefetch(self):
        if self._data is None:
            try:
                with open(self.path, "rb") as f:
                    self._data = f.read()
            except OSError:
                pass

    @property
    def img(self):
        self.last_used = time.monotonic()
        if self._img is None:
            img = QImage()
            if not (self._data and img.loadFromData(self._data)):
                img = QImage(self.path)
            self._img = img
        return self._img

    def frame(self, i):
        i = int(_clamp(i, 0, self.n - 1))
        pm = self._frames.get(i)
        if pm is None:
            if len(self._frames) >= FRAME_CACHE:
                self._frames.pop(next(iter(self._frames)))
            pm = self._frames[i] = QPixmap.fromImage(self.img.copy(self.src(i)))
        else:
            self.last_used = time.monotonic()
        return pm

    def loaded(self):
        return self._img is not None

    def unload(self):
        self._img = None
        self._frames.clear()

    def ok(self):
        return os.path.exists(self.path)

    def src(self, i):
        m = self.m
        i = int(_clamp(i, 0, self.n - 1))
        return QRect((i % m["cols"]) * m["fw"], (i // m["cols"]) * m["fh"], m["fw"], m["fh"])

    def frame_at(self, t):
        i = int((t * self.speed + self.lead) * self.fps)
        return i % self.n if self.loop else min(i, self.n - 1)


def load_sprites():
    try:
        index = json.load(open(os.path.join(ASSET_DIR, "index.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for name, meta in index.items():
        s = Sprite(name, meta)
        if s.ok():
            out[name] = s
    return out


MOTIONS = {"jump", "bounce", "slide", "wobble", "sparkle", "shake", "pop", "breathe", "rain", "wind", "fire", "music", "sweep"}
SWEEP_SEC = 2.4

MOOD_MOTION = {
    "노래": dict(motion="bounce", period=0.5, every=0.5, n=2, up=-1, speed=1.0, colors=NOTE_COLORS, alpha=1.0, sway=0.12),
    "밝은 음악": dict(motion="bounce_spin", period=0.45, every=0.45, n=2, up=-1, speed=0.9, colors=NOTE_COLORS, alpha=1.0, sway=0.12),
    "잔잔한 음악": dict(motion="rock", period=3.0, every=1.4, n=1, up=-1, speed=1.5, colors=["#c9d8ff", "#e6d6ff", "#ffe9b0"], alpha=0.65, sway=0.2),
    "슬픈 음악": dict(motion="droop", period=4.0, every=1.6, n=1, up=1, speed=1.3, colors=["#6f9bd8", "#8aa8d8"], alpha=0.8, sway=0.08),
    "무서운 음악": dict(motion="tremble", period=0.05, every=2.5, n=1, up=-1, speed=1.0, colors=["#b79cff"], alpha=0.7, sway=0.04),
    "배경음악": dict(motion="breathe", period=2.4, every=2.0, n=1, up=-1, speed=1.2, colors=NOTE_COLORS, alpha=0.85, sway=0.12),
}
MOOD_MOTION["동요"], MOOD_MOTION["자장가"], MOOD_MOTION["조마조마한 음악"] = (
    MOOD_MOTION["노래"], MOOD_MOTION["잔잔한 음악"], MOOD_MOTION["무서운 음악"]
)
MUSIC_MOTION = MOOD_MOTION["배경음악"]
UNLOAD_SEC = 60.0


def check_names(sprites):
    clash = MOTIONS & set(sprites)
    if clash:
        print(f"[아동 애니메이션] 움직임 이름이 그림 이름과 겹침: {sorted(clash)}")
    if K is None:
        return
    for k, v in K.LABELS.items():
        a = v.get("anim")
        if v.get("kind") != "sink" and a and a not in sprites and a not in MOTIONS:
            print(f"[아동 애니메이션] {k}: anim '{a}' 그림 파일 없음 → 기본 움직임으로 표시")


class _Inst:
    def __init__(self, key, label, anim, emoji, direction, rect, now, until):
        self.key, self.label, self.anim, self.emoji, self.direction = key, label, anim, emoji, direction
        self.rect = QRect(rect)
        self.t0 = now
        self.ta = now
        self.until = until
        self.leaving = None
        self.seed = random.random() * 10


class _Cont:
    def __init__(self, key, label, anim, emoji, rect, now):
        self.key, self.label, self.anim, self.emoji = key, label, anim, emoji
        self.rect = QRect(rect)
        self.t0, self.last = now, now
        self.leaving = None
        self.ps, self.ps2, self.acc = [], [], 0.0
        self.ax = self.av = 0.0
        self.at = 0.0
        self.anext = now


class KidsAnimLayer(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.sprites = load_sprites()
        check_names(self.sprites)
        self._next_gc = 0.0
        self.active = False
        self.view = VIEWS[0]
        self.motion = True
        self.font_size = 24
        self.locator = None
        self.ranker = None
        self.inst = {}
        self.cont = {}
        self._emoji_cache = {}
        self._dirty = QRect()
        self._last = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)
        self.hide()

    @property
    def caption_mode(self):
        return self.active and CAPTION_UNDER and self.view == "그림 + 짧은 글"

    @property
    def picture_only(self):
        return self.active and self.view == "그림만"

    def ppc(self):
        k = 0.42 * self.font_size
        return k * (0.6 if self.view == "글 위주" else 1.15 if self.view == "그림만" else 1.0)

    def apply_settings(self, s):
        was = self.active
        self.active = s.get("base_mode") == "아동"
        self.view = s.get("kids_view", VIEWS[0]) if s.get("kids_view") in VIEWS else VIEWS[0]
        self.motion = bool(s.get("kids_motion", True))
        self.font_size = int(s.get("font_size", 24))
        self.font_family = s.get("font_family") or "Malgun Gothic"
        if self.parent() is not None:
            self.setGeometry(self.parent().rect())
        if not self.active:
            self.clear()
            self.hide()
        else:
            if not was:
                sps = list(self.sprites.values())
                threading.Thread(target=lambda: [sp.prefetch() for sp in sps], daemon=True).start()
            self.show()
            self.raise_()
            if not was:
                self.update()

    def clear(self):
        self.inst.clear()
        self.cont.clear()
        self._timer.stop()
        self.update()

    def _meta(self, ev):
        anim, emoji = ("pop", "💫")
        if K is not None:
            anim, emoji = K.anim_of(ev.key)
            if ev.key == "music":
                emoji = "🎵"
        return anim, emoji

    def trigger(self, ev, rect, duration):
        if not self.active:
            return
        now = time.monotonic()
        anim, emoji = self._meta(ev)
        key = ev.label or ev.key
        it = self.inst.get(key)
        if it is not None and it.leaving is None:
            it.until = max(it.until, now + REPEAT_HOLD_BY.get(ev.label, REPEAT_HOLD))
            it.rect, it.label, it.direction = QRect(rect), ev.label, ev.direction
            if now - it.ta >= COOLDOWN_SEC:
                it.ta = now
        else:
            if len(self.inst) >= MAX_INSTANT:
                oldest = min(self.inst.values(), key=lambda x: x.t0)
                self.inst.pop(oldest.key, None)
            self.inst[key] = _Inst(key, ev.label, anim, emoji, ev.direction, rect, now, now + min(duration, DURATION_BY.get(ev.label, duration)))
        self._start()

    def touch(self, ev, rect):
        if not self.active:
            return
        now = time.monotonic()
        anim, emoji = self._meta(ev)
        if anim not in ("rain", "wind", "fire", "music", "sweep") and anim not in self.sprites:
            anim = "breathe"
        key = ev.label or ev.key
        c = self.cont.get(key)
        if c is None or c.leaving is not None:
            c = self.cont[key] = _Cont(key, ev.label, anim, emoji, rect, now)
        c.last, c.label, c.emoji = now, ev.label, emoji
        c.rect = QRect(rect)
        self._start()

    def sync_instant(self, shown_labels):
        now = time.monotonic()
        for it in self.inst.values():
            if it.leaving is None and it.label not in shown_labels and now - it.t0 > 0.6:
                it.leaving = now

    def _start(self):
        if not self._timer.isActive():
            self._last = time.monotonic()
            self._timer.start()

    def _tick(self):
        now = time.monotonic()
        dt = min(0.05, now - self._last)
        self._last = now
        for k, it in list(self.inst.items()):
            if it.leaving is None and now >= it.until:
                it.leaving = now
            if it.leaving is not None and now - it.leaving > EXIT_SEC:
                del self.inst[k]
        for k, c in list(self.cont.items()):
            if c.leaving is None and now - c.last > CONT_HOLD_BY.get(c.label, CONT_HOLD_SEC):
                c.leaving = now
            if c.leaving is not None and now - c.leaving > EXIT_SEC:
                del self.cont[k]
            elif self.motion:
                self._step_cont(c, dt, now)
        if now >= self._next_gc:
            self._next_gc = now + 5.0
            self._unload_idle(now)
        if not self.inst and not self.cont:
            self._timer.stop()
            QTimer.singleShot(int(UNLOAD_SEC * 1000) + 500, lambda: self._unload_idle(time.monotonic()))

        self._glide(dt)
        area = QRect(self._dirty)
        cur = QRect()
        pos = self._inst_positions()
        for it in self.inst.values():
            cur = cur.united(self._inst_box(it, pos).toAlignedRect())
            if self.caption_mode and it.key in pos:
                cx, cy, w, h = pos[it.key]
                cur = cur.united(QRectF(cx - 200, cy + h / 2, 400, self.font_size * 1.6).toAlignedRect())
        if self.caption_mode:
            for c in self._cont_layout():
                cur = cur.united(c[1].adjusted(-200, 0, 200, self.font_size * 1.8).toAlignedRect())
        else:
            for c in self._cont_layout():
                cur = cur.united(c[1].toAlignedRect())
        self._dirty = cur.adjusted(-8, -8, 8, 8)
        area = area.united(self._dirty)
        if not area.isEmpty():
            self.update(area)

    def _unload_idle(self, now):
        using = {it.anim for it in self.inst.values()} | {c.anim for c in self.cont.values()}
        for name, sp in self.sprites.items():
            if sp.loaded() and name not in using and now - sp.last_used > UNLOAD_SEC:
                sp.unload()

    def _fig_size(self, it):
        extent = 7.0 * self.ppc() * 0.8 * INSTANT_ICON_SCALE * 1.35 * self.inst_scale()
        sp = self.sprites.get(it.anim)
        if sp is not None:
            scale = extent / max(sp.m["w"], sp.m["h"])
            return sp.m["w"] * scale, sp.m["h"] * scale
        return extent, extent

    def _caption_height(self, group):
        if self.picture_only:
            return 0
        heights = getattr(self.parent(), "_heights", {})
        return heights.get(group, 0)

    def _locate(self, label, kind, fallback):
        if self.locator is not None:
            r = self.locator(label, kind)
            if r is not None and r.width() > 0:
                return QRect(r)
        return QRect(fallback)

    def _locate_ok(self, label):
        if self.locator is None:
            return True
        r = self.locator(label, "instant")
        return r is not None and r.width() > 0

    def _cont_shown(self, c):
        if self.locator is None:
            return True
        r = self.locator(c.label, "continuous")
        return r is not None and r.width() > 0

    def _inst_positions(self, cont_layout=None):
        """지금 그릴 자리 = 목표 자리(_inst_targets)로 미끄러져 가는 중인 자리.
        소리가 늘거나 줄어 목표가 바뀌면 남은 그림이 툭 튀지 않고 부드럽게 옮겨 감 (_glide)
        사라지는 중인 그림은 마지막 자리에서 흐려짐"""
        t = self._inst_targets()
        out = {}
        for it in self.inst.values():
            if it.key in t:
                tx, ty, w, h = t[it.key]
                if not hasattr(it, "_px"):
                    it._px, it._py = tx, ty           # 처음 나타날 때는 바로 제자리
                it._wh = (w, h)
                out[it.key] = (it._px, it._py, w, h)
            elif hasattr(it, "_px"):
                out[it.key] = (it._px, it._py) + tuple(getattr(it, "_wh", self._fig_size(it)))
        return out

    def _glide(self, dt):
        t = self._inst_targets()
        k = 1.0 if not self.motion else min(1.0, dt * GLIDE_RATE)
        for it in self.inst.values():
            if it.key in t and hasattr(it, "_px"):
                tx, ty = t[it.key][0], t[it.key][1]
                it._px += (tx - it._px) * k
                it._py += (ty - it._py) * k
                if abs(tx - it._px) < 0.5 and abs(ty - it._py) < 0.5:
                    it._px, it._py = tx, ty

    def snap_positions(self):
        """미끄러지는 중인 그림을 바로 목표 자리로 (시험·설정 바꿀 때)"""
        for it in self.inst.values():
            for a in ("_px", "_py"):
                if hasattr(it, a):
                    delattr(it, a)
        self._inst_positions()

    def _inst_targets(self, cont_layout=None):
        """소리가 배정된 자막 박스(rect) 바로 위에 그림을 놓음.
        같은 박스에 소리가 여럿이면 겹치지 않게 옆으로 나란히 (최대 PER_BOX개, 오래된 것부터 빠짐)
        '그림 + 짧은 글'이면 그림 아래 글 폭까지 칸으로 잡아 글끼리도 안 겹치게"""
        if not self.inst:
            return {}
        # 같은 자막 박스 = 박스 가운데가 가까운 것끼리 (사라지는 중인 소리는 박스에서 빠져 좌표가 조금 달라도 같은 묶음)
        groups = []
        for it in sorted(self.inst.values(), key=lambda x: x.t0):
            if it.leaving is not None and hasattr(it, "_px"):
                continue
            it.rect = self._locate(it.label, "instant", it.rect)
            r = it.rect
            for gi, g in enumerate(groups):
                gr = g[0]
                if r.width() > 0 and gr[2] > 0 and abs((r.x() + r.width() / 2) - (gr[0] + gr[2] / 2)) < max(80, gr[2] / 2) \
                        and abs(r.y() - gr[1]) < max(20, gr[3]):
                    g[1].append(it)
                    if self._locate_ok(it.label):          # 박스에 아직 있는 소리의 박스 자리를 기준으로
                        groups[gi] = ((r.x(), r.y(), r.width(), r.height()), g[1])
                    break
            else:
                groups.append(((r.x(), r.y(), r.width(), r.height()), [it]))
        fm = None
        if self.caption_mode:
            from PySide6.QtGui import QFontMetricsF
            fm = QFontMetricsF(self._cap_font(instant=True))
        W, H = self.width(), self.height()
        gap0 = max(10.0, self.ppc() * 0.6)
        out = {}
        for (x, y, rw, rh), its in groups:
            gap = gap0
            per = getattr(self.parent(), "kids_inst_max", lambda: PER_BOX)()   # 설정의 순간음 개수만큼
            its = its[-per:]
            sizes = [self._fig_size(it) for it in its]
            slots = [max(w, fm.horizontalAdvance(self._cap_text(it)) + 6) if fm is not None else w
                     for it, (w, _) in zip(its, sizes)]
            total = sum(slots) + gap * (len(its) - 1)
            if total > W - 16 > 0:                      # 화면보다 넓으면 그림·칸을 같이 줄임
                g = (W - 16) / total
                sizes = [(w * g, h * g) for w, h in sizes]
                slots = [sw * g for sw in slots]
                gap *= g
                total = W - 16
            max_h = max(h for _, h in sizes)
            if rw > 0:
                mid = x + rw / 2
                top = max(0.0, y - max_h - 4)
            else:
                mid = W / 2
                top = max(0.0, H / 2 - max_h / 2)
            left = _clamp(mid - total / 2, 0.0, max(0.0, W - total))
            cy = top + max_h / 2
            for it, (w, h), sw in zip(its, sizes, slots):
                out[it.key] = (left + sw / 2, top + max_h - h / 2, w, h)   # 밑선 맞춤 → 아래 글자가 한 줄로
                left += sw + gap
        return out

    def inst_fig_h(self):
        """순간음 그림 한 장의 최대 높이 (자리 예약용)"""
        return 7.0 * self.ppc() * 0.8 * INSTANT_ICON_SCALE * 1.35 * self.inst_scale()

    def inst_scale(self):
        """순간음 박스 크기(설정창 미리보기에서 박스를 눌러 바꾸는 글자 크기) ÷ 기본 글자 크기.
        박스를 키우면 순간음 그림·글도 같은 비율로 커짐"""
        f = getattr(self.parent(), "kids_inst_scale", None)
        return f() if f is not None else 1.0

    def cont_fig_nom(self):
        """지속음 그림 한 칸의 높이 상한 (= 🎵 그림 높이). 더 큰 그림(비·불 등)은 이 높이에 맞춰 줄임
        세로로 여러 칸 쌓으면 화면 높이의 45% 안에 다 들어가도록 줄임 (안 그러면 아래 칸이 화면 끝에 몰려 겹침)"""
        base = 2.0 * 7.0 * self.ppc() * 0.8 * CONT_ICON_SCALE
        par = self.parent()
        st = getattr(par, "settings", None) or {}
        n = 1
        if st.get("continuous_layout", "가로") == "세로" and hasattr(par, "slot_limit"):
            n = max(1, par.slot_limit("continuous"))
        budget = self.height() * 0.45 / n - self._cont_cap_h() - 8
        return max(12.0, min(base, budget))

    def _cont_cap_h(self):
        if self.picture_only:
            return 0.0
        if self.caption_mode:
            from PySide6.QtGui import QFontMetricsF
            return QFontMetricsF(self._cap_font()).height() + 4
        return self._caption_height("continuous") + 4

    def cont_unit_h(self):
        """지속음 한 칸 = 그림 + 그 아래 글 (세로 배치 간격, 순간음 자리 예약에 씀)"""
        return self.cont_fig_nom() + self._cont_cap_h() + 8

    def _cap_font(self, instant=False):
        f = QFont(self.font_family)
        k = self.inst_scale() if instant else 1.0
        f.setPixelSize(max(11, int(round(self.font_size * CAPTION_SCALE * k))))
        f.setBold(True)
        return f

    def _cap_text(self, it):
        d = getattr(it, "direction", "center")
        return ("◀ " + it.label) if d == "left" else (it.label + " ▶") if d == "right" else it.label

    def _paint_caption(self, p, it, now, pos):
        c = pos.get(it.key)
        if c is None:
            return
        cx, cy, w, h = c
        alpha = self._fade(it.t0, it.leaving, now)
        if alpha <= 0:
            return
        f = self._cap_font(instant=True)
        text = self._cap_text(it)
        from PySide6.QtGui import QFontMetricsF
        fm = QFontMetricsF(f)
        tw = fm.horizontalAdvance(text)
        x = cx - tw / 2
        y = cy + h / 2 + 2 + fm.ascent()
        self._draw_caption_text(p, f, text, x, y, alpha)

    def _inst_center(self, it, pos=None):
        pos = pos if pos is not None else self._inst_positions()
        return pos.get(it.key)

    def _inst_box(self, it, pos=None):
        c = self._inst_center(it, pos)
        if c is None:
            return QRectF()
        cx, cy, w, h = c
        pad = 1.3 if it.anim == "slide" else 0.6
        return QRectF(cx - w * (0.5 + pad), cy - h * (0.5 + pad), w * (1 + 2 * pad), h * (1 + 2 * pad))

    def _cont_zone(self, c, ic):
        sp = self.sprites.get(c.anim)
        if sp is not None:
            sw_, sh_ = sp.m["w"] * self.ppc() * CONT_SCALE, sp.m["h"] * self.ppc() * CONT_SCALE
            return QRectF(-sw_ / 2, -sh_ / 2, sw_, sh_), sw_
        a = c.anim
        zw = ic * (2.6 if a == "wind" else 1.7 if a == "music" else 2.3 if a == "sweep" else 1.5)
        if a == "rain":
            return QRectF(-ic * 1.0, -ic * 0.7, ic * 2.0, ic * 3.6), zw
        if a == "wind":
            return QRectF(-ic * 1.9, -ic * 0.9, ic * 3.8, ic * 1.8), zw
        if a == "music":
            return QRectF(-ic * 2.6, -ic * 2.3, ic * 4.1, ic * 4.4), zw
        if a == "sweep":
            return QRectF(-ic * 1.4, -ic * 0.9, ic * 2.8, ic * 1.6), zw
        if a == "fire":
            return QRectF(-ic, -ic * 2.0, ic * 2, ic * 2.7), zw
        return QRectF(-ic * 0.75, -ic * 0.75, ic * 1.5, ic * 1.5), zw

    def _paint_cont_caption(self, p, c, box, now):
        alpha = self._fade(c.t0, c.leaving, now)
        if alpha <= 0:
            return
        f = self._cap_font()
        from PySide6.QtGui import QFontMetricsF
        fm = QFontMetricsF(f)
        text = c.label
        st_ = getattr(self.parent(), "settings", None) or {}
        if st_.get("continuous_note_enabled", True):
            text = "♬ " + text
        tw = fm.horizontalAdvance(text)
        self._draw_caption_text(p, f, text, getattr(c, "cap_x", box.center().x()) - tw / 2, getattr(c, "cap_y", box.bottom() + 2) + fm.ascent(), alpha)

    def _draw_caption_text(self, p, f, text, x, y, alpha):
        path = QPainterPath()
        path.addText(QPointF(x, y), f, text)
        p.setOpacity(alpha)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.strokePath(path, QPen(QColor(0, 0, 0, 230), max(3.0, f.pixelSize() / 5), Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.fillPath(path, QColor(255, 255, 255))

    def _cont_layout(self):
        """지속음 그림 자리. 설정창 미리보기의 지속음 박스 자리에서 시작
        (가로: 한 줄로 나란히 / 세로: 박스마다 한 칸씩 아래로). 박스가 왼쪽이면 왼쪽 맞춤, 오른쪽이면 오른쪽 맞춤
        각 칸 = 그림(높이 cont_fig_nom 이하) + 아래 글"""
        raw = []
        ic_base = 7.0 * self.ppc() * 0.8 * CONT_ICON_SCALE
        for c in self.cont.values():
            if not self._cont_shown(c):
                continue
            c.rect = self._locate(c.label, "continuous", c.rect)
            sp = self.sprites.get(c.anim)
            if sp is not None:
                size = CONT_SPRITE_EXTENT * self.ppc()
                scale = size / max(sp.m["w"], sp.m["h"])
                w = sp.m["w"] * scale
                h = sp.m["h"] * scale
                top_offset = bottom_offset = h / 2
            else:
                w = ic_base * (2.0 if c.anim == "rain" else
                               3.8 if c.anim == "wind" else
                               4.1 if c.anim == "music" else
                               2.8 if c.anim == "sweep" else
                               2.0 if c.anim == "fire" else 1.5)
                top_offset, bottom_offset = (
                    (0.7 * ic_base, 2.9 * ic_base) if c.anim == "rain" else
                    (0.9 * ic_base, 0.9 * ic_base) if c.anim == "wind" else
                    (0.26 * ic_base, 1.74 * ic_base) if c.anim == "music" else
                    (0.9 * ic_base, 0.7 * ic_base) if c.anim == "sweep" else
                    (2.0 * ic_base, 1.35 * ic_base) if c.anim == "fire" else
                    (0.75 * ic_base, 0.75 * ic_base)
                )
            raw.append((c, sp, w, top_offset, bottom_offset))
        if not raw:
            return []

        par = self.parent()
        order = getattr(par, "kids_cont_order", None)
        if order is not None:
            raw.sort(key=lambda t: order(t[0].label))
        nom = self.cont_fig_nom()
        W = self.width()
        fm = None
        if self.caption_mode:
            from PySide6.QtGui import QFontMetricsF
            fm = QFontMetricsF(self._cap_font())
        note = (getattr(par, "settings", None) or {}).get("continuous_note_enabled", True)
        units = []
        for c, sp, w, to, bo in raw:
            sc = min(1.0, nom / (to + bo)) if to + bo > 0 else 1.0
            capw = fm.horizontalAdvance(("♬ " if note else "") + c.label) + 6 if fm is not None else 0.0
            units.append([c, sp, w * sc, to * sc, bo * sc, sc, capw])

        anc = getattr(par, "kids_cont_anchor", None)
        if anc is not None:
            A, align, vertical = anc()
        else:
            A, align, vertical = QRectF(W / 2 - 50, 8, 100, 30), "center", False

        def x_left(width):
            if align == "left":
                x = A.left()
            elif align == "right":
                x = A.right() - width
            else:
                x = A.center().x() - width / 2
            return _clamp(x, 0.0, max(0.0, W - width))

        gap = max(10.0, self.ppc() * 0.6)
        placed = []
        if vertical:
            step = self.cont_unit_h()
            for k, u in enumerate(units):
                sw = max(u[2], u[6])
                placed.append((u, x_left(sw), A.top() + k * step, sw))
        else:
            total = sum(max(u[2], u[6]) for u in units) + gap * (len(units) - 1)
            if total > W - 16 > 0:                     # 화면보다 넓으면 그림만 줄임
                g = max(0.3, (W - 16 - gap * (len(units) - 1)) / max(1.0, sum(max(u[2], u[6]) for u in units)))
                for u in units:
                    u[2], u[3], u[4], u[5] = u[2] * g, u[3] * g, u[4] * g, u[5] * g
                total = sum(max(u[2], u[6]) for u in units) + gap * (len(units) - 1)
            left = x_left(total)
            for u in units:
                sw = max(u[2], u[6])
                placed.append((u, left, A.top(), sw))
                left += sw + gap

        out = []
        for (c, sp, w, to, bo, sc, capw), x0, top, sw in placed:
            top = _clamp(top, 0.0, max(0.0, self.height() - self.cont_unit_h()))
            cx = x0 + sw / 2
            cy = top + to
            center = QPointF(cx, cy)
            ic = ic_base * sc
            if sp is not None:
                h = to + bo
                box = QRectF(cx - w / 2, cy - h / 2, w, h)
            elif c.anim == "rain":
                box = QRectF(cx - ic * 1.0, cy - ic * 0.7, ic * 2.0, ic * 3.6)
            elif c.anim == "wind":
                box = QRectF(cx - ic * 1.9, cy - ic * 0.9, ic * 3.8, ic * 1.8)
            elif c.anim == "music":
                box = QRectF(cx - ic * 2.05, cy - ic * 0.26, ic * 4.1, ic * 2.0)
            elif c.anim == "sweep":
                box = QRectF(cx - ic * 1.4, cy - ic * 0.9, ic * 2.8, ic * 1.6)
            elif c.anim == "fire":
                box = QRectF(cx - ic, cy - ic * 2.0, ic * 2, ic * 3.35)
            else:
                box = QRectF(cx - ic * 0.75, cy - ic * 0.75, ic * 1.5, ic * 1.5)
            c.cap_x = cx
            if sp is not None or c.anim in ("rain", "wind", "sweep", "fire"):
                c.cap_y = box.bottom() + 2
            elif c.anim == "music":
                c.cap_y = cy + ic * 1.24 + 2
            else:
                c.cap_y = cy + ic * 0.75 + 2
            c.fig_bottom = box.bottom()
            out.append((c, box, center, ic))
        return out

    def _step_cont(self, c, dt, now):
        ic = 7.0 * self.ppc() * 0.8 * CONT_ICON_SCALE
        if c.anim == "rain":
            W, H = ic * 2.0, ic * 2.9
            u = W / 100
            c.acc += 70 * dt
            while c.acc > 1:
                c.acc -= 1
                x = W * (0.5 + (random.random() + random.random() + random.random() - 1.5) * 0.55)
                c.ps.append([x, -random.uniform(0, 0.08) * H, H * random.uniform(0.95, 1.3),
                             H * random.uniform(0.06, 0.1), random.uniform(0.5, 0.8) * u])
            G = H * 0.97
            keep = []
            for d in c.ps:
                d[1] += d[2] * dt
                d[0] -= d[2] * 0.07 * dt
                if d[1] >= G:
                    c.ps2.append(["r", d[0], 0.4 * u, 0.8])
                    for _ in range(1 if random.random() < 0.5 else 2):
                        c.ps2.append(["b", d[0], G, random.uniform(-14, 14) * u, -random.uniform(18, 34) * u])
                else:
                    keep.append(d)
            c.ps = keep
            keep = []
            for s in c.ps2:
                if s[0] == "r":
                    s[2] += 13 * u * dt
                    s[3] -= 1.8 * dt
                    if s[3] > 0:
                        keep.append(s)
                else:
                    s[4] += 260 * u * dt
                    s[1] += s[3] * dt
                    s[2] += s[4] * dt
                    if s[2] <= G:
                        keep.append(s)
            c.ps2 = keep
        elif c.anim == "wind":
            W, H = ic * 3.8, ic * 1.8
            u = W / 100
            c.at += dt
            T = c.at
            gust = _clamp((0.5 + 0.5 * math.sin(T * 1.25)) * (0.65 + 0.35 * math.sin(T * 0.41 + 1)) + 0.12, 0, 1)
            c.gust = gust
            c.acc += 6 * (0.25 + gust * 1.3) * dt
            while c.acc > 1:
                c.acc -= 1
                c.ps.append(dict(x=random.uniform(-4, 10) * u, y=random.uniform(0.15, 0.85) * H,
                                 a=random.uniform(-0.12, 0.12), sp=random.uniform(30, 46) * u * (0.7 + gust * 0.6),
                                 life=0.0, mx=random.uniform(1.4, 2.2),
                                 curl_at=random.uniform(0.35, 1.1) if random.random() < 0.55 else 99,
                                 ct=0.0, cd=random.choice((-1, 1)), tr=[], seed=random.uniform(0, 9),
                                 leaf=random.choice("🍃🍂🍃") if random.random() < 0.16 else None,
                                 rot=random.uniform(0, 6), spin=random.uniform(4, 9)))
            keep = []
            for q in c.ps:
                q["life"] += dt
                if q["life"] > q["mx"] or q["x"] > W * 1.05:
                    continue
                if q["life"] > q["curl_at"] and q["ct"] < 0.6:
                    q["ct"] += dt
                    q["a"] += q["cd"] * (2 * math.pi / 0.6) * dt
                    if q["ct"] >= 0.6:
                        q["a"] -= q["cd"] * 2 * math.pi
                else:
                    q["a"] += (-q["a"] * 2.2 + math.sin(T * 2.5 + q["seed"]) * 0.9) * dt
                sp = q["sp"] * (0.75 + gust * 0.4)
                q["x"] += math.cos(q["a"]) * sp * dt
                q["y"] += math.sin(q["a"]) * sp * dt
                q["tr"].append((q["x"], q["y"]))
                if len(q["tr"]) > 26:
                    q["tr"].pop(0)
                q["rot"] += q["spin"] * dt
                keep.append(q)
            c.ps = keep
        elif c.anim == "music":
            mm = MUSIC_MOTION
            if now >= c.anext:
                c.anext = now + mm["every"]
                room_up = c.rect.center().y() > ic * 1.8
                for i in range(mm["n"]):
                    if mm["up"] < 0 and not room_up:
                        ddx, ddy = -random.uniform(1.2, 2.0), random.uniform(-0.25, 0.25)
                    else:
                        ddx, ddy = random.uniform(-0.9, 0.9), mm["up"] * random.uniform(0.9, 1.6)
                    c.ps.append(dict(t=-i * 0.12, dx=ddx, dy=ddy,
                                     ch=random.choice("♪♫♩♬"), col=random.choice(mm["colors"]), a=mm["alpha"],
                                     dur=random.uniform(2.0, 2.8) * mm["speed"], rot=random.uniform(-30, 30),
                                     sd=random.uniform(0.4, 0.8), sw=mm["sway"]))
            for q in c.ps:
                q["t"] += dt
            c.ps = [q for q in c.ps if q["t"] < q["dur"]]
        elif c.anim == "sweep":
            ph = (now - c.t0) % SWEEP_SEC
            k = int(ph // 0.5)
            u = (ph % 0.5) / 0.5
            if k < 3 and u < 0.7:
                c.acc += 16 * dt
                bx = -0.65 + 1.3 * (u / 0.7)
                while c.acc > 1:
                    c.acc -= 1
                    c.ps.append(dict(t=0.0, x=bx - 0.1, vx=random.uniform(0.4, 0.9), vy=-random.uniform(0.15, 0.45),
                                     r=random.uniform(0.035, 0.07), dur=random.uniform(0.45, 0.7)))
            for q in c.ps:
                q["t"] += dt
            c.ps = [q for q in c.ps if q["t"] < q["dur"]]
        elif c.anim == "fire":
            c.acc += 3.5 * dt
            while c.acc > 1:
                c.acc -= 1
                c.ps.append(dict(t=0.0, dx=random.uniform(-0.5, 0.5), dy=-random.uniform(0.8, 1.5),
                                 ch=random.choice(["✨", "🔥", "🧡"]), dur=random.uniform(2.2, 3.4),
                                 rot=random.uniform(-40, 40)))
            for q in c.ps:
                q["t"] += dt
            c.ps = [q for q in c.ps if q["t"] < q["dur"]]

    def _emoji_pix(self, ch, px):
        px = max(8, int(px))
        key = (ch, px)
        pm = self._emoji_cache.get(key)
        if pm is None:
            if len(self._emoji_cache) > 300:
                self._emoji_cache.pop(next(iter(self._emoji_cache)))
            dpr = self.devicePixelRatioF() or 1.0
            size = int(px * 1.35 * dpr)
            pm = QPixmap(size, size)
            pm.setDevicePixelRatio(dpr)
            pm.fill(Qt.GlobalColor.transparent)
            q = QPainter(pm)
            q.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            f = QFont()
            f.setFamilies(EMOJI_FONTS)
            f.setPixelSize(px)
            q.setFont(f)
            q.drawText(QRectF(0, 0, px * 1.35, px * 1.35), Qt.AlignmentFlag.AlignCenter, ch)
            q.end()
            self._emoji_cache[key] = pm
        return pm

    def _draw_emoji(self, p, ch, cx, cy, px, sx=1.0, sy=1.0, rot=0.0, alpha=1.0, anchor_bottom=False):
        pm = self._emoji_pix(ch, px)
        s = px * 1.35
        p.save()
        p.setOpacity(p.opacity() * alpha)
        p.translate(cx, cy + (s / 2 if anchor_bottom else 0))
        if rot:
            p.rotate(rot)
        p.scale(sx, sy)
        p.drawPixmap(QRectF(-s / 2, -s if anchor_bottom else -s / 2, s, s), pm, QRectF(pm.rect()))
        p.restore()

    def paintEvent(self, e):
        if not self.active or (not self.inst and not self.cont):
            return
        now = time.monotonic()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        cont_layout = self._cont_layout()
        for c, box, center, ic in cont_layout:
            if not box.toAlignedRect().intersects(e.rect()):
                continue
            p.save()
            p.setOpacity(self._fade(c.t0, c.leaving, now))
            self._paint_cont(p, c, box, center, ic, now)
            p.restore()
            if self.caption_mode:
                p.save()
                self._paint_cont_caption(p, c, box, now)
                p.restore()
        pos = self._inst_positions(cont_layout)
        for it in sorted(self.inst.values(), key=lambda x: x.t0):
            p.save()
            self._paint_inst(p, it, now, pos)
            p.restore()
            if self.caption_mode:
                p.save()
                self._paint_caption(p, it, now, pos)
                p.restore()
        p.end()

    def _fade(self, t0, leaving, now):
        a = _clamp((now - t0) / 0.12, 0, 1)
        if leaving is not None:
            a *= 1 - _clamp((now - leaving) / EXIT_SEC, 0, 1)
        return a

    def _paint_inst(self, p, it, now, pos=None):
        c = self._inst_center(it, pos)
        if c is None:
            return
        cx, cy, w, h = c
        te = now - it.t0
        ta = now - it.ta
        alpha = 1.0
        lift = 0.0
        if it.leaving is not None:
            u = _clamp((now - it.leaving) / EXIT_SEC, 0, 1)
            alpha, lift = 1 - u, -0.4 * h * u
        sp = self.sprites.get(it.anim)
        p.setOpacity(alpha)
        if sp is not None:
            if self.motion:
                k = _ease_out_back(_clamp(te / ENTER_SEC, 0, 1)) if te < ENTER_SEC else 1.0
                k = max(0.05, 0.4 + 0.6 * k)
                fi = sp.frame_at(ta)
            else:
                k, fi = 1.0, sp.m["still"]
                p.setOpacity(alpha * _clamp(te / 0.2, 0, 1))
            p.translate(cx, cy + h / 2 + lift)
            p.scale(k, k)
            if it.anim in FLIP_FACE and it.direction == "right":
                p.scale(-1, 1)
            pm = sp.frame(fi)
            p.drawPixmap(QRectF(-w / 2, -h, w, h), pm, QRectF(pm.rect()))
            return

        px = max(w, h) / 1.35
        if not self.motion:
            p.setOpacity(alpha * _clamp(te / 0.2, 0, 1))
            self._draw_emoji(p, it.emoji, cx, cy + lift, px)
            return
        sx = sy = 1.0
        dx = dy = rot = 0.0
        if te < JPOP_SEC:
            sx, sy = _lerp_keys(JPOP, te / JPOP_SEC)
        a = it.anim
        dsign = -1 if it.direction == "right" else 1
        if a == "jump":
            t = ta - 0.15
            if 0 <= t < 1.2:
                u = (t % 0.4) / 0.4
                dy = -0.35 * px * math.sin(math.pi * u)
                if u < 0.15 or u > 0.85:
                    sx, sy = sx * 1.12, sy * 0.88
        elif a == "bounce":
            t = ta - 0.1
            if 0 <= t < 1.6:
                dy = -0.42 * px * abs(math.sin(t * 7.0)) * math.exp(-2.2 * t)
                sq = math.exp(-2.2 * t) * max(0.0, math.cos(t * 7.0) ** 8)
                sx, sy = sx * (1 + 0.25 * sq), sy * (1 - 0.25 * sq)
        elif a == "slide":
            u = _clamp(ta / 0.45, 0, 1)
            off = (1 - _ease_out_back(u)) * 1.6 * px * dsign
            for g, ga in ((0.09, 0.22), (0.18, 0.12), (0.27, 0.06)):
                ug = _clamp((ta - g) / 0.45, 0, 1)
                if ug < 1:
                    self._draw_emoji(p, it.emoji, cx - (1 - _ease_out_back(ug)) * 1.6 * px * dsign, cy + lift,
                                     px, alpha=ga * alpha)
            dx = -off
        elif a == "wobble":
            t = ta - 0.05
            if t >= 0:
                o = math.sin(2 * math.pi * 3 * t) * math.exp(-2.0 * t) * 0.16
                sx, sy = sx * (1 + o), sy * (1 - o)
        elif a == "shake":
            if ta < 1.0:
                dx = 0.08 * px * math.sin(2 * math.pi * 9 * ta) * math.exp(-4 * ta)
                rot = 6 * math.sin(2 * math.pi * 9 * ta) * math.exp(-4 * ta)
            if ta < 0.55:
                u = ta / 0.55
                pen = QPen(QColor(255, 255, 255, int(230 * (1 - u) * alpha)), max(2.0, px * 0.05))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                for ang in (-150, -120, -60, -30, 180, 0):
                    r = math.radians(ang)
                    r1, r2 = px * (0.62 + 0.25 * u), px * (0.8 + 0.3 * u)
                    p.drawLine(QPointF(cx + r1 * math.cos(r), cy + r1 * math.sin(r) + lift),
                               QPointF(cx + r2 * math.cos(r), cy + r2 * math.sin(r) + lift))
        elif a == "sparkle":
            for i in range(6):
                ang = it.seed + i * math.pi / 3 + ta * 0.6
                ph = (ta * 0.9 + i / 6) % 1.0
                s = math.sin(math.pi * ph)
                rr = px * (0.72 + 0.18 * ph)
                self._draw_emoji(p, "✨", cx + rr * math.cos(ang), cy + rr * math.sin(ang) + lift,
                                 px * 0.32, sx=s, sy=s, alpha=alpha * s)
        self._draw_emoji(p, it.emoji, cx + dx, cy + dy + lift, px, sx, sy, rot, anchor_bottom=True)

    def _paint_cont(self, p, c, box, center, ic, now):
        cx, cy = center.x(), center.y()
        t = now - c.t0
        sp = self.sprites.get(c.anim)
        if sp is not None:
            fi = sp.frame_at(t) if self.motion else sp.m["still"]
            pm = sp.frame(fi)
            p.drawPixmap(box, pm, QRectF(pm.rect()))
            return
        if c.anim == "rain":
            if self.motion:
                p.save()
                p.translate(cx - ic, cy + ic * 0.35)
                W = ic * 2.0
                H = ic * 2.9
                u = W / 100
                G = H * 0.97
                for d in c.ps:
                    edge = math.pow(_clamp(math.sin(math.pi * d[0] / W), 0, 1), 0.7)
                    top = _clamp(d[1] / (H * 0.1), 0, 1)
                    a = 0.8 * edge * top
                    tx, ty = d[0] + d[3] * 0.07, d[1] - d[3]
                    g = QLinearGradient(tx, ty, d[0], d[1])
                    g.setColorAt(0, QColor(170, 210, 255, 0))
                    g.setColorAt(1, QColor(205, 230, 255, int(255 * a)))
                    pen = QPen(g, d[4])
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    p.setPen(pen)
                    p.drawLine(QPointF(tx, ty), QPointF(d[0], min(d[1], G)))
                for s in c.ps2:
                    if s[0] == "r":
                        p.setPen(QPen(QColor(205, 230, 255, int(255 * max(0, s[3]))), 0.4 * u))
                        p.setBrush(Qt.BrushStyle.NoBrush)
                        p.drawEllipse(QPointF(s[1], G), s[2], s[2] * 0.28)
                    else:
                        p.setPen(Qt.PenStyle.NoPen)
                        p.setBrush(QColor(215, 235, 255, 210))
                        p.drawEllipse(QPointF(s[1], s[2]), 0.5 * u, 0.5 * u)
                p.restore()
            self._draw_emoji(p, "☁️", cx, cy, ic)
        elif c.anim == "wind":
            gust = getattr(c, "gust", 0.4) if self.motion else 0.3
            if self.motion:
                p.save()
                p.translate(box.left(), box.top())
                W, H = box.width(), box.height()
                u = W / 100
                for q in c.ps:
                    al = math.sin(math.pi * _clamp(q["life"] / q["mx"], 0, 1)) * \
                        math.pow(_clamp(math.sin(math.pi * _clamp(q["x"] / W, 0, 1)), 0, 1), 0.5)
                    if q["leaf"]:
                        self._draw_emoji(p, q["leaf"], q["x"], q["y"], 3.6 * u, rot=math.degrees(q["rot"]),
                                         alpha=_clamp(al * 1.3, 0, 1))
                        continue
                    tr = q["tr"]
                    n = len(tr)
                    for i in range(1, n):
                        f = i / n
                        pen = QPen(QColor(225, 240, 255, int(255 * al * f * 0.8)), (0.25 + 0.6 * f) * u)
                        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                        p.setPen(pen)
                        p.drawLine(QPointF(*tr[i - 1]), QPointF(*tr[i]))
                p.restore()
            bend = 4 + gust * 24 + (math.sin(t * 11) * gust * 3 if self.motion else 0)
            self._draw_grass(p, cx, cy, ic, bend)
        elif c.anim == "fire":
            if self.motion:
                for q in c.ps:
                    u = q["t"] / q["dur"]
                    a = _clamp(u / 0.15, 0, 1) * (1 - _clamp((u - 0.75) / 0.25, 0, 1))
                    self._draw_emoji(p, q["ch"], cx + q["dx"] * ic * u, cy - ic * 0.3 + q["dy"] * ic * u,
                                     ic * 0.4, rot=q["rot"] * u, alpha=a)
            g = QRadialGradient(QPointF(cx, cy), ic * 0.9)
            pul = 0.45 + 0.1 * math.sin(t * 5.3) if self.motion else 0.45
            g.setColorAt(0, QColor(255, 140, 40, int(255 * pul)))
            g.setColorAt(1, QColor(255, 140, 40, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawEllipse(QPointF(cx, cy), ic * 0.9, ic * 0.9)
            p.save()
            p.translate(cx, cy + ic * 0.45)
            if self.motion:
                ph = (t % 1.7) / 1.7
                keys = [(0, 0, 1, 1), (0.14, 4, 1.04, 1.09), (0.29, -3, 0.97, 0.93), (0.43, 2.5, 1.07, 1.13),
                        (0.58, -4, 0.95, 0.96), (0.73, 3, 1.03, 1.07), (0.87, -1.5, 0.98, 0.97), (1, 0, 1, 1)]
                sk, sx, sy = _lerp_keys(keys, ph)
                tr = QTransform()
                tr.shear(math.tan(math.radians(sk)), 0)
                p.setTransform(tr, True)
                p.scale(sx, sy)
            p.translate(-cx, -(cy + ic * 0.45))
            self._draw_emoji(p, c.emoji or "🔥", cx, cy, ic)
            p.restore()
        elif c.anim == "music":
            mm = MUSIC_MOTION
            if self.motion:
                for q in c.ps:
                    if q["t"] < 0:
                        continue
                    u = q["t"] / q["dur"]
                    a = q["a"] * _clamp(u / 0.15, 0, 1) * (1 - _clamp((u - 0.75) / 0.25, 0, 1))
                    sw = math.sin(q["t"] / q["sd"] * math.pi) * ic * q["sw"]
                    x = cx + q["dx"] * ic * u + sw
                    y = cy - ic * 0.15 + q["dy"] * ic * u
                    f = QFont()
                    f.setPixelSize(int(ic * 0.42))
                    p.save()
                    p.setFont(f)
                    p.setOpacity(p.opacity() * a)
                    p.translate(x, y)
                    p.rotate(q["rot"] * u)
                    p.setPen(QColor(q["col"]))
                    p.drawText(QRectF(-ic * 0.3, -ic * 0.3, ic * 0.6, ic * 0.6), Qt.AlignmentFlag.AlignCenter, q["ch"])
                    p.restore()
            sx = sy = 1.0
            dx = dy = rot = 0.0
            if self.motion:
                ph = (t % mm["period"]) / mm["period"]
                mo = mm["motion"]
                if mo in ("bounce", "bounce_spin"):
                    hop = abs(math.sin(math.pi * ph))
                    dy = -0.22 * ic * hop
                    if hop < 0.2:
                        sx, sy = 1.1, 0.9
                    if mo == "bounce_spin":
                        rot = 10 * math.sin(2 * math.pi * ph)
                elif mo == "tilt":
                    rot = 18 * math.sin(2 * math.pi * ph)
                    dx = 0.06 * ic * math.sin(2 * math.pi * ph)
                elif mo == "rock":
                    rot = 10 * math.sin(2 * math.pi * ph)
                    dy = -0.05 * ic * math.cos(2 * math.pi * ph)
                elif mo == "droop":
                    d = 0.5 - 0.5 * math.cos(2 * math.pi * ph)
                    dy, rot, sy = 0.14 * ic * d, -12 * d, 1 - 0.06 * d
                elif mo == "tremble":
                    dx = random.uniform(-0.03, 0.03) * ic
                    dy = random.uniform(-0.02, 0.02) * ic
                else:
                    k = 1 + 0.06 * math.sin(2 * math.pi * ph)
                    sx = sy = k
            self._draw_emoji(p, "🎵", cx + dx, cy + dy + ic * 0.5, ic * 1.1, sx, sy, rot, anchor_bottom=True)
        elif c.anim == "sweep":
            floor = cy + ic * 0.55
            pen = QPen(QColor(200, 210, 230, 90), max(1.5, ic * 0.04))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(cx - ic * 1.2, floor), QPointF(cx + ic * 1.2, floor))
            bx, rot, sx, lift = 0.0, 4.0, 1.0, 0.0
            if self.motion:
                ph = t % SWEEP_SEC
                k = int(ph // 0.5)
                u = (ph % 0.5) / 0.5
                if k < 3:
                    if u < 0.7:
                        e = u / 0.7
                        e = e * e * (3 - 2 * e)
                        bx, rot, sx = -0.65 + 1.3 * e, 14 - 20 * e, 1.0 + 0.08 * math.sin(math.pi * e)
                    else:
                        e = (u - 0.7) / 0.3
                        bx, rot, lift = 0.65 - 1.3 * e, -6 + 20 * e, -0.12 * math.sin(math.pi * e)
                else:
                    bx, rot = -0.65, 14
                p.setPen(Qt.PenStyle.NoPen)
                for q in c.ps:
                    a = 1 - q["t"] / q["dur"]
                    p.setBrush(QColor(235, 228, 215, int(150 * a)))
                    rr = ic * q["r"] * (1 + q["t"] * 1.5)
                    p.drawEllipse(QPointF(cx + ic * (q["x"] - q["vx"] * q["t"]), floor - ic * 0.05 + ic * q["vy"] * q["t"]), rr, rr)
            bsz = ic * 1.05
            self._draw_emoji(p, c.emoji or "🧹", cx + ic * bx, floor - bsz * 0.6 + ic * lift, bsz, sx, 1.0, rot,
                             anchor_bottom=True)
        else:
            k = 1 + (0.06 * math.sin(2 * math.pi * t / 2.2) if self.motion else 0)
            self._draw_emoji(p, c.emoji, cx, cy, ic, k, k)

    def _draw_grass(self, p, cx, cy, ic, bend):
        s = ic / 60.0
        p.save()
        p.translate(cx - 30 * s, cy - 32 * s)
        p.scale(s, s)
        for x, (qx, qy, ex, ey), col, f in (
                (22, (20, 38, 14, 20), "#5fc46b", 1.0), (30, (31, 32, 30, 8), "#7ed67a", 1.25),
                (38, (40, 38, 46, 22), "#4fae5f", 0.9), (26, (24, 44, 20, 34), "#8fe08a", 0.6),
                (34, (37, 44, 40, 36), "#69c971", 0.7)):
            p.save()
            p.translate(x, 58)
            p.rotate(bend * f)
            p.translate(-x, -58)
            path = QPainterPath(QPointF(x, 58))
            path.quadTo(qx, qy, ex, ey)
            pen = QPen(QColor(col), 4.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
            p.restore()
        p.restore()