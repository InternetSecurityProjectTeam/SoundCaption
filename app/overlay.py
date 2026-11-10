import ctypes
import math
import os
import time
from dataclasses import dataclass, replace

from PySide6.QtCore import QRect, QRectF, Qt, QTimer, QVariantAnimation, Signal, QEasingCurve
from PySide6.QtGui import QGuiApplication, QCursor, QFont, QFontMetricsF, QRegion
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QFrame, QHBoxLayout, QPushButton, QSlider, QWidget

from events import SoundEvent
from settings import default_settings, normalize

try:                                     # 🧸 아동 모드 애니메이션 층 (없거나 실패해도 자막은 그대로 동작)
    from kids_anim import KidsAnimLayer
except Exception as _e:                  # noqa: BLE001
    print(f"[오버레이] 아동 모드 애니메이션을 불러오지 못함: {_e}")
    KidsAnimLayer = None

FADE_MS = 200
CONTINUOUS_HOLD = 1.5
KIDS_CONT_HOLD = {"새 짹짹": 0.5}   # v0.67: 아동 모드 지속음별 짧은 유지 (새 그림이 소리 끝나고 3초 가까이 남음)
KIDS_REPEAT_HOLD = 0.5   # v0.69: 1.0 → 0.5 (사용자: 아동 모드 그림 전체적으로 너무 오래 남음)
KIDS_SHORT = {
    "띠용 효과음": (1.0, 0.5), "휙 지나가는 소리": (1.0, 0.5), "반짝 효과음": (1.0, 0.5),
    "쿵 부딪히는 소리": (1.0, 0.5), "삑삑 효과음": (1.0, 0.5), "콜록 기침": (1.0, 0.5),
    "에취 재채기": (1.0, 0.5), "숨소리": (1.0, 0.5), "딸꾹질 소리": (1.0, 0.5),
    "똑똑 노크 소리": (1.0, 0.5), "딩동 벨소리": (1.0, 0.5), "웃음소리": (1.5, 0.5)
}


def kids_times(label, duration):
    d, r = KIDS_SHORT.get(label, (duration, KIDS_REPEAT_HOLD))
    return min(d, duration), r

MAX_SLOTS = 5
QWIDGETSIZE_MAX = 16777215

STYLE_PRESETS = {
    "순간음": {"padding": "10px 20px", "radius": 14, "border": "none"},
    "지속음": {"padding": "8px 18px", "radius": 14, "border": "none"},
    "일반": {"padding": "8px 16px", "radius": 14, "border": "none"},
}
GROUP_KIND = {"instant": "순간음", "continuous": "지속음"}
WEIGHTS = [400, 600, 800]
MAX_WIDTH = {"instant": 850, "continuous": 900}

INSTANT_LAYOUT = {
    1: [(0.5, 0)],
    2: [(0.0, 0), (1.0, 0)],
    3: [(0.0, 0), (0.5, 0), (1.0, 0)],
    4: [(0.0, 0), (1.0, 0), (0.0, 1), (1.0, 1)],
    5: [(0.0, 0), (0.5, 0), (1.0, 0), (0.0, 1), (1.0, 1)],
}
CONTINUOUS_AX = {
    "상단 가운데": 0.5, 
    "왼쪽 위": 0.0, 
    "오른쪽 위": 1.0,
}
DIRECTION_AX = {"left": 0.0, "center": 0.5, "right": 1.0}
DIR_LABEL_KR = {"left": "왼쪽", "center": "가운데", "right": "오른쪽"}

PREVIEW_CONTINUOUS = ["불타는 소리", "바람 소리", "빗소리", "배경음악", "사이렌"]


def format_caption(label, count, direction, settings):
    text = label.strip()
    if not settings.get("gradient_enabled", True):
        if direction == "left":
            text = f"<  {text}"
        elif direction == "right":
            text = f"{text}  >"
    return text


def _rgb(hex_color):
    h = hex_color.lstrip("#")
    return f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"


@dataclass
class SlotState:
    event: SoundEvent
    shown_at: float
    last_seen: float
    started: float
    pinned: bool = False
    stack_offset: int = 0


class FontSizeSliderPopup(QFrame):
    def __init__(self, parent_overlay, box_index, current_size, default_size, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.parent_overlay = parent_overlay
        self.box_index = box_index
        self.default_size = default_size

        self.setObjectName("fontPopup")
        self.setStyleSheet("""
            QFrame#fontPopup {
                background-color: #FFFFFF;
                border: 2px solid #2563EB;
                border-radius: 12px;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #E2E8F0;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #2563EB;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                border: 2px solid #2563EB;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QPushButton {
                background-color: #F1F5F9;
                color: #0F172A;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563EB;
                color: #FFFFFF;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        effective_val = current_size if current_size is not None else default_size

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(12, 48)
        self.slider.setValue(effective_val)
        self.slider.setFixedWidth(130)
        self.slider.valueChanged.connect(self._on_slider_changed)

        self.btn_reset = QPushButton("초기화")
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.clicked.connect(self._on_reset)

        layout.addWidget(self.slider)
        layout.addWidget(self.btn_reset)

    def _on_slider_changed(self, val):
        self.parent_overlay.set_box_font_size(self.box_index, val)

    def _on_reset(self):
        self.slider.setValue(self.default_size)
        self.parent_overlay.set_box_font_size(self.box_index, None)
        self.close()


class SubtitleLabel(QLabel):
    def __init__(self, parent, group, index):
        super().__init__(parent)
        self.group = group
        self.index = index
        self.shown_text = None
        self._anim = None
        self._drag_start = None
        self._is_dragging = False
        self._press_pos = None

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(False)
        self.hide()

    def set_caption(self, text, settings, strength, direction="center", limit=None):
        p = STYLE_PRESETS[GROUP_KIND[self.group]]
        
        box_font_size = None
        if self.group == "instant":
            box_font_size = settings.get("instant_box_font_sizes", {}).get(str(self.index))
        
        is_interactive = getattr(self.parent(), 'interactive', False)
        _ov = self.parent()
        kids_caption = bool(getattr(_ov, "_kids_on", None) and _ov._kids_on()) and not is_interactive
        size = box_font_size if box_font_size is not None else settings["font_size"]
        if self.group == "continuous":
            size = max(10, int(settings["font_size"] * (0.6 if kids_caption else 0.75)))
        elif kids_caption and box_font_size is None:
            size = max(10, int(size * 0.75))

        opacity_pct = settings.get("opacity", 85)
        effective_pct = max(1, opacity_pct) if is_interactive else opacity_pct
        alpha_val = max(1, min(255, int(effective_pct / 100.0 * 255)))

        use_gradient = settings.get("gradient_enabled", True) and (direction in ["left", "right"])
        bg_rgb = _rgb(settings.get('background_color', '#0F111A'))

        if use_gradient:
            grad_rgb = _rgb(settings.get('gradient_color', '#E11D48'))
            grad_op_pct = settings.get("gradient_opacity", 85)
            effective_grad_pct = max(1, grad_op_pct) if is_interactive else grad_op_pct
            grad_alpha = max(1, min(255, int(effective_grad_pct / 100.0 * 255)))

            if direction == "left":
                bg_style = (
                    f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                    f"stop:0 rgba({grad_rgb}, {grad_alpha}), stop:0.85 rgba({bg_rgb}, {alpha_val}));"
                )
            else:
                bg_style = (
                    f"background: qlineargradient(x1:1, y1:0, x2:0, y2:0, "
                    f"stop:0 rgba({grad_rgb}, {grad_alpha}), stop:0.85 rgba({bg_rgb}, {alpha_val}));"
                )
        else:
            if effective_pct <= 0:
                bg_style = "background-color: transparent;"
            else:
                bg_style = f"background-color: rgba({bg_rgb}, {alpha_val});"

        weight = WEIGHTS[max(0, min(2, strength))]
        padding = (("3px 10px" if self.group == "continuous" else "4px 12px") if kids_caption else p["padding"])
        border_style = "2px dashed rgba(37, 99, 235, 255)" if is_interactive else p['border']
        limit = limit or MAX_WIDTH[self.group]
        padding_x = int(padding.split()[1][:-2])
        font = QFont(settings["font_family"])
        font.setWeight(QFont.Weight(weight))
        while size > 10:
            font.setPixelSize(size)
            if QFontMetricsF(font).horizontalAdvance(text) + padding_x * 2 + 8 <= limit:
                break
            size -= 1

        self.setStyleSheet(f"""
            QLabel {{
                {bg_style}
                color: {settings['text_color']};
                font-family: '{settings['font_family']}', 'Malgun Gothic', sans-serif;
                font-size: {size}px;
                font-weight: {weight};
                padding: {padding};
                border-radius: {p['radius']}px;
                border: {border_style};
            }}
        """)
        self.setText(text)
        self.setMinimumWidth(0)
        self.setMaximumWidth(limit)
        self.adjustSize()

    def mousePressEvent(self, event):
        overlay = self.parent()
        if getattr(overlay, 'interactive', False) and event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._drag_start = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._is_dragging = False
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start is not None:
            dist = (event.globalPosition().toPoint() - self._press_pos).manhattanLength()
            if dist > 4:
                self._is_dragging = True

            if self._is_dragging:
                new_pos = event.globalPosition().toPoint() - self._drag_start
                parent_rect = self.parent().rect()
                x = max(0, min(new_pos.x(), parent_rect.width() - self.width()))
                y = max(0, min(new_pos.y(), parent_rect.height() - self.height()))
                
                if self.group == "instant":
                    self.move(x, y)
                else:
                    self.parent().on_continuous_dragged_step(x, y, self.index)
                    
                self.parent().update_click_mask()
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        overlay = self.parent()
        if getattr(overlay, 'interactive', False):
            if not self._is_dragging and event.button() == Qt.MouseButton.LeftButton:
                if self.group == "instant":
                    self._show_font_slider_popup(event.globalPosition().toPoint())
            elif self._is_dragging:
                if self.group == "instant":
                    self.parent().on_label_dragged(self.index, self.x(), self.y())
                else:
                    self.parent().on_continuous_drag_finished()
            
            self._is_dragging = False
            self._drag_start = None
            self.unsetCursor()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _show_font_slider_popup(self, global_pos):
        overlay = self.parent()
        curr_font = overlay.settings.get("instant_box_font_sizes", {}).get(str(self.index))
        default_font = overlay.settings["font_size"]

        popup = FontSizeSliderPopup(overlay, self.index, curr_font, default_font, self)
        popup.move(global_pos.x() - 100, global_pos.y() + 28)
        popup.show()

    def _fade(self, start, end, on_done=None):
        if self._anim is not None:
            self._anim.stop()

        self._opacity_effect.setOpacity(start)
        anim = QVariantAnimation(self)
        anim.setDuration(FADE_MS)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        anim.setStartValue(float(start))
        anim.setEndValue(float(end))
        anim.valueChanged.connect(lambda value: self._opacity_effect.setOpacity(float(value)))
        anim.finished.connect(lambda: self._on_fade_done(end, on_done))
        self._anim = anim
        anim.start()

    def _on_fade_done(self, final_val, on_done):
        self._opacity_effect.setOpacity(final_val)
        self._anim = None
        if on_done is not None:
            on_done()

    def appear(self, fade=True):
        if self._anim is not None:
            self._anim.stop()
            self._anim = None

        if not self.isVisible():
            self.show()
            if fade:
                self._fade(0.0, 1.0)
            else:
                self._opacity_effect.setOpacity(1.0)
        else:
            if fade and self._opacity_effect.opacity() < 0.95:
                self._fade(self._opacity_effect.opacity(), 1.0)
            else:
                self._opacity_effect.setOpacity(1.0)

    def disappear(self, fade=True):
        if self.isHidden():
            return

        if fade:
            self._fade(self._opacity_effect.opacity(), 0.0, on_done=self.hide)
        else:
            if self._anim is not None:
                self._anim.stop()
                self._anim = None
            self._opacity_effect.setOpacity(0.0)
            self.hide()


class SubtitleOverlay(QWidget):
    slots_changed = Signal()
    custom_pos_changed = Signal()

    def __init__(self):
        super().__init__()
        self.interactive = False
        self.settings = default_settings()
        self._real = {"instant": [None] * MAX_SLOTS, "continuous": [None] * MAX_SLOTS}
        self._preview_states = {"instant": [None] * MAX_SLOTS, "continuous": [None] * MAX_SLOTS}
        self._box = [[] for _ in range(MAX_SLOTS)]
        self.preview = False
        self._suppressed = {}
        self._heights = {"instant": 40, "continuous": 30}
        
        self.setup_window_flags(interactive=False)

        self._labels = {
            "instant": [SubtitleLabel(self, "instant", i) for i in range(MAX_SLOTS)],
            "continuous": [SubtitleLabel(self, "continuous", i) for i in range(MAX_SLOTS)],
        }

        self._kids = KidsAnimLayer(self) if KidsAnimLayer is not None else None
        if self._kids is not None:
            self._kids.locator = self._kids_locate
            self._kids.ranker = self._kids_rank

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self.apply_settings(self.settings)

        if os.name == "nt":
            self._topmost_timer = QTimer(self)
            self._topmost_timer.setInterval(500)
            self._topmost_timer.timeout.connect(self._force_topmost)
            self._topmost_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._kids is not None:
            self._kids.setGeometry(self.rect())

    def _kids_on(self):
        return self._kids is not None and self._kids.active and not self.preview

    def _appear(self, label, fade):
        if (self._kids is not None and not (self.preview or self.interactive)
                and (self._kids.picture_only or getattr(self._kids, "caption_mode", False))):
            label.disappear(fade=False)
        else:
            label.appear(fade)

    def _kids_shown_labels(self):
        return {st.event.label for box in self._box for st in box}

    def _kids_locate(self, label, kind):
        if kind == "instant":
            for i in range(self.slot_limit("instant")):
                if any(st.event.label == label for st in self._box[i]):
                    k = self._kids
                    if k is not None and (k.caption_mode or k.picture_only):
                        return self.kids_box_rect("instant", i)
                    return self._labels["instant"][i].geometry()
            return None
        limit = self.slot_limit("continuous")
        for i, st in enumerate(self._real["continuous"][:limit]):
            if st is not None and st.event.label == label:
                horizontal = self.settings.get("continuous_layout", "가로") == "가로"
                j = 0 if horizontal else i
                return self._kids_anchor("continuous", j, self._labels["continuous"][j])
        return None

    def _kids_anchor(self, group, i, lbl):
        import re as _re
        g = lbl.geometry()
        if not (self._kids is not None and getattr(self._kids, "caption_mode", False)):
            return g
        s = self.settings
        fm = lbl.fontMetrics()
        plain = _re.sub(r"<[^>]+>", "", lbl.text() or "")
        pad = max(0, g.width() - fm.horizontalAdvance(plain))
        if group == "instant":
            d = s.get("instant_box_directions", {}).get(str(i), "center")
            ref = f"박스 {i + 1} ({DIR_LABEL_KR.get(d, '가운데')})"
            custom = (s.get("instant_custom_pos") or {}).get(str(i))
            layout = INSTANT_LAYOUT.get(self.slot_limit("instant"), INSTANT_LAYOUT[1])
            ax = layout[i][0] if i < len(layout) else 0.5
        else:
            ref = PREVIEW_CONTINUOUS[i] if i < len(PREVIEW_CONTINUOUS) else PREVIEW_CONTINUOUS[0]
            custom = s.get("continuous_custom_pos")
            ax = CONTINUOUS_AX.get(s.get("continuous_position", "상단 가운데"), 0.5)
        rw = fm.horizontalAdvance(ref) + pad
        if custom is not None and isinstance(custom, (list, tuple)) and len(custom) == 2:
            x = g.x()
        else:
            x = s["margin"] + (self.width() - 2 * s["margin"] - rw) * ax
        return QRect(int(x), g.y(), int(rw), g.height())

    def _kids_rank(self, label):
        for box in self._box:
            for j, st in enumerate(box):
                if st.event.label == label:
                    return j
        return 99

    def _kids_notify(self, ev):
        if ev.kind == "instant":
            for i in range(self.slot_limit("instant")):
                if any(st.event.label == ev.label for st in self._box[i]):
                    self._kids.trigger(ev, self._kids_locate(ev.label, "instant") or self._labels["instant"][i].geometry(),
                                       self.settings["instant_duration"])
                    break
        else:
            idx = 0
            if self.settings.get("continuous_layout", "가로") == "세로":
                for i, st in enumerate(self._real["continuous"][:self.slot_limit("continuous")]):
                    if st is not None and st.event.label == ev.label:
                        idx = i
                        break
            self._kids.touch(ev, self._labels["continuous"][idx].geometry())
        self._kids.sync_instant(self._kids_shown_labels())
        self._position_kids_captions()

    def _position_kids_captions(self):
        if not self._kids_on() or self.interactive:
            return
        for group in ("continuous", "instant"):
            for i, label in enumerate(self._labels[group][:self.slot_limit(group)]):
                if label.shown_text is not None:
                    self._place(label, group, i)

    def _force_topmost(self):
        if not self.isVisible():
            return
        hwnd = int(self.winId())
        ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0013)

    def setup_window_flags(self, interactive=False):
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        if not interactive:
            flags |= Qt.WindowType.WindowTransparentForInput

        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setGeometry(QGuiApplication.primaryScreen().geometry())

        if os.name == "nt":
            hwnd = int(self.winId())
            GWL_EXSTYLE = -20
            WS_EX_TOPMOST = 0x00000008
            WS_EX_NOACTIVATE = 0x08000000
            
            current_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE, current_style | WS_EX_TOPMOST | WS_EX_NOACTIVATE
            )

    def update_click_mask(self):
        if not self.interactive:
            self.clearMask()
            return

        combined_region = QRegion()
        for i in range(self.slot_limit("instant")):
            lbl = self._labels["instant"][i]
            if lbl.isVisible():
                combined_region = combined_region.united(QRegion(lbl.geometry()))
        for i in range(self.slot_limit("continuous")):
            lbl = self._labels["continuous"][i]
            if lbl.isVisible():
                combined_region = combined_region.united(QRegion(lbl.geometry()))
        
        self.setMask(combined_region)

    def set_interactive(self, on):
        self.interactive = on
        self.hide()
        self.setup_window_flags(interactive=on)
        self.set_preview(self.preview)
        self.show()
        self.raise_()
        self.update_click_mask()

    def set_box_font_size(self, index, size):
        fonts = self.settings.get("instant_box_font_sizes", {})
        fonts[str(index)] = size
        self.settings["instant_box_font_sizes"] = fonts
        self.render_all()
        self.custom_pos_changed.emit()

    def on_label_dragged(self, index, x, y):
        pos_map = self.settings.get("instant_custom_pos", {})
        pos_map[str(index)] = [int(x), int(y)]
        self.settings["instant_custom_pos"] = pos_map
        self.custom_pos_changed.emit()

    def on_continuous_dragged_step(self, x, y, sender_index):
        s = self.settings
        layout_dir = s.get("continuous_layout", "가로")
        
        if layout_dir == "세로":
            base_x = x
            base_y = y - sender_index * (self._heights["continuous"] + 10)
        else:
            base_x = x
            base_y = y

        self.settings["continuous_custom_pos"] = [int(base_x), int(base_y)]
        
        limit = self.slot_limit("continuous")
        for i in range(limit):
            lbl = self._labels["continuous"][i]
            if not lbl.isVisible():
                continue
            if layout_dir == "세로":
                lbl.move(int(base_x), int(base_y + i * (self._heights["continuous"] + 10)))
            else:
                lbl.move(int(base_x), int(base_y))

    def on_continuous_drag_finished(self):
        self.custom_pos_changed.emit()

    def kids_inst_scale(self):
        """아동 모드 순간음 박스(박스 1) 크기 배율 = 박스 글자 크기 ÷ 기본 글자 크기 (안 바꿨으면 1)"""
        f = (self.settings.get("instant_box_font_sizes") or {}).get("0")
        base = self.settings.get("font_size", 24) or 24
        return max(0.4, min(2.5, f / base)) if f else 1.0

    def kids_inst_max(self):
        """아동 모드: 가운데 순간음 박스 하나에 동시에 보이는 소리 수 = 설정의 순간음 개수 (1~5)"""
        return max(1, min(MAX_SLOTS, int(self.settings.get("instant_slots", 3) or 1)))

    def _kids_mode(self):
        """아동 모드 설정인지 (미리보기 중에도 True — 미리보기와 실제 위치를 같게 맞추려고)"""
        return self.settings.get("base_mode") == "아동"

    def slot_limit(self, group):
        # 아동 모드: 순간음은 가운데 박스 하나만 (왼/오 구분 없음). 소리 여러 개는 그 박스 위에 그림으로 나란히
        if group == "instant" and self._kids_mode():
            return 1 if self.settings["instant_slots"] > 0 else 0
        return self.settings["instant_slots" if group == "instant" else "continuous_slots"]

    def group_enabled(self, group):
        if group == "continuous" and self.slot_limit("continuous") == 0:
            return False
        return self.settings[f"{group}_enabled"]

    def follow_margin(self, margin):
        W = self.width()

        def snap(p, label, ax):
            if not (isinstance(p, (list, tuple)) and len(p) == 2):
                return p
            if ax <= 0.0:
                return [int(margin), int(p[1])]
            if ax >= 1.0:
                return [int(W - margin - label.width()), int(p[1])]
            return [int(p[0]), int(p[1])]

        layout = INSTANT_LAYOUT[self.slot_limit("instant")]
        pos = dict(self.settings.get("instant_custom_pos") or {})
        for i in range(MAX_SLOTS):
            if pos.get(str(i)) is not None and i < len(layout):
                pos[str(i)] = snap(pos[str(i)], self._labels["instant"][i], layout[i][0])
        self.settings["instant_custom_pos"] = pos
        c = self.settings.get("continuous_custom_pos")
        if c is not None:
            ax = CONTINUOUS_AX.get(self.settings.get("continuous_position", "상단 가운데"), 0.5)
            self.settings["continuous_custom_pos"] = snap(c, self._labels["continuous"][0], ax)
        self.render_all()

    def apply_settings(self, settings):
        self.settings = normalize(settings)
        if self._kids is not None:
            self._kids.apply_settings(self.settings)
        for group in ("instant", "continuous"):
            for i in range(MAX_SLOTS):
                if i >= self.slot_limit(group) or not self.group_enabled(group):
                    self._real[group][i] = None
                    if group == "instant":
                        self._box[i] = []
        self._trim_boxes()
        self._recompute_metrics()
        
        if self.preview or self.interactive:
            self._build_preview()
            
        self.render_all()
        self.slots_changed.emit()

    def _recompute_metrics(self):
        self._pv_cache = {}
        for group in ("instant", "continuous"):
            probe = SubtitleLabel(self, group, 0)
            probe.set_caption("가", self.settings, 1, "center", 9999)
            self._heights[group] = probe.height()
            probe.deleteLater()

    def slot_name(self, group, i):
        if group == "continuous":
            return f"지속음 {i + 1}"
        
        dirs = self.settings.get("instant_box_directions", {})
        direction_kr = DIR_LABEL_KR.get(dirs.get(str(i), "center"), "가운데")
        pos = self.settings.get("instant_custom_pos", {}).get(str(i))
        
        custom_str = " (위치 직접지정)" if pos is not None else ""
        return f"박스 {i + 1} ({direction_kr}){custom_str}"

    def slot_state(self, group, i):
        if i >= self.slot_limit(group) or not self.group_enabled(group):
            return None
        return self._real[group][i]

    def count(self):
        return sum(1 for group in ("instant", "continuous")
                   for i in range(self.slot_limit(group)) if self.slot_state(group, i) is not None)

    def total_slots(self):
        return self.slot_limit("instant") + self.slot_limit("continuous")

    def _max_width(self, group):
        if group == "continuous":
            if self._kids_on() and not self.interactive:
                return max(1, min(MAX_WIDTH["continuous"], self.width() - 16))
            return MAX_WIDTH["continuous"]
        layout = INSTANT_LAYOUT[self.slot_limit("instant")]
        per_row = max(sum(1 for _, r in layout if r == row) for row in {r for _, r in layout})
        available = self.width() - 2 * self.settings["margin"]
        if self._kids_on() and not self.interactive:
            return max(1, min(MAX_WIDTH["instant"], available // per_row - 16))
        return max(120, min(MAX_WIDTH["instant"], available // per_row - 16))

    def kids_anchor(self, group):
        s = self.settings
        lab = self._labels[group][0]
        w = lab.width()
        if group == "continuous":
            c = s.get("continuous_custom_pos")
            if c is not None and isinstance(c, (list, tuple)) and len(c) == 2:
                return c[0] + w / 2, float(c[1]), True
            ax = CONTINUOUS_AX.get(s.get("continuous_position", "상단 가운데"), 0.5)
            avail = self.width() - 2 * s["margin"]
            return s["margin"] + (avail - w) * ax + w / 2, float(self._continuous_top()), False
        
        lay_ = INSTANT_LAYOUT.get(self.slot_limit("instant"), [(0.5, 0)])
        ci = next((k for k, (ax, row) in enumerate(lay_) if ax == 0.5 and row == 0), 0)
        lab = self._labels["instant"][ci]
        w = lab.width()
        c = (s.get("instant_custom_pos") or {}).get(str(ci))
        if c is not None and isinstance(c, (list, tuple)) and len(c) == 2:
            return c[0] + w / 2, float(c[1]), True
        return self.width() / 2, float(self._instant_y0()), False

    def _continuous_top(self):
        c_pos = self.settings.get("continuous_custom_pos")
        if c_pos is not None and isinstance(c_pos, (list, tuple)) and len(c_pos) == 2:
            return c_pos[1]
        h_ratio = self.settings.get("continuous_height", 3) / 100.0
        return int(self.height() * h_ratio)

    def _instant_y0(self):
        y = int(self.height() * self.settings["instant_height"] / 100)
        if self.group_enabled("continuous"):
            is_vertical = self.settings.get("continuous_layout") == "세로"
            slots = self.slot_limit("continuous") if is_vertical else 1
            bottom = self._continuous_top() + slots * (self._heights["continuous"] + 10)
            y = max(y, bottom + 8)
            # 아동 모드: 지속음 자리에 글 한 줄이 아니라 그림 + 글 칸이 들어가고, 순간음 그림은 순간음 박스 위에 뜸
            #   → 그만큼 비워 둠. 미리보기에서도 똑같이 계산 (미리보기 박스 위치 = 실제 위치)
            if self._kids_mode() and self._kids is not None:
                ct = self._continuous_top()
                if ct <= y:
                    n = self.slot_limit("continuous") if is_vertical else 1
                    y = max(y, int(ct + n * self._kids.cont_unit_h() + self._kids.inst_fig_h() + 8))
        return y

    def _slot_xy(self, group, i, w, h, stack_offset=0):
        """박스 하나의 왼쪽 위 좌표 (미리보기·실제 공통). w, h = 박스 크기"""
        s = self.settings
        if group == "instant":
            custom_pos = (s.get("instant_custom_pos") or {}).get(str(i))
            if custom_pos is not None and isinstance(custom_pos, (list, tuple)) and len(custom_pos) == 2:
                x = custom_pos[0]
                y = custom_pos[1] + stack_offset * (self._heights["instant"] + 8)
            else:
                ax, row = INSTANT_LAYOUT[self.slot_limit("instant")][i]
                y = self._instant_y0() + row * (self._heights["instant"] + 14) + stack_offset * (self._heights["instant"] + 8)
                if abs(ax - 0.5) < 0.05:
                    x = (self.width() - w) / 2.0
                else:
                    x = s["margin"] + (self.width() - 2 * s["margin"] - w) * ax
        else:
            c_custom = s.get("continuous_custom_pos")
            layout_dir = s.get("continuous_layout", "가로")
            # 아동 모드 세로: 박스 사이 간격 = 그림 + 글 한 칸 (미리보기에서도 그 간격으로 보여 줌)
            step = (self._kids.cont_unit_h() if (self._kids_mode() and self._kids is not None)
                    else self._heights["continuous"] + 10)
            if c_custom is not None and isinstance(c_custom, (list, tuple)) and len(c_custom) == 2:
                x = c_custom[0]
                y = c_custom[1] + (i * step if layout_dir == "세로" else 0)
            else:
                ax = CONTINUOUS_AX.get(s.get("continuous_position", "상단 가운데"), 0.5)
                if layout_dir == "세로":
                    y = self._continuous_top() + i * step
                    x = s["margin"] + (self.width() - 2 * s["margin"] - w) * ax
                else:
                    avail = self.width() - 2 * s["margin"]
                    x = s["margin"] + (avail - w) * ax
                    y = self._continuous_top()
        x = max(0, min(int(x), self.width() - int(w)))
        y = max(0, min(int(y), self.height() - int(h)))
        return x, y

    def _preview_text(self, group, i):
        s = self.settings
        if group == "instant":
            d = "center" if self._kids_mode() else s.get("instant_box_directions", {}).get(str(i), "center")
            return f"박스 {i + 1} ({DIR_LABEL_KR.get(d, '가운데')})"
        if s.get("continuous_layout", "가로") == "가로":
            t = "  ·  ".join(PREVIEW_CONTINUOUS[:max(1, self.slot_limit("continuous"))])
        else:
            t = PREVIEW_CONTINUOUS[i % len(PREVIEW_CONTINUOUS)]
        return f"♬  {t}" if s.get("continuous_note_enabled", True) else t

    def _preview_size(self, group, i):
        """설정창 미리보기에서 그 박스가 갖는 크기 (아동 그림 위치 기준)"""
        text = self._preview_text(group, i)
        cache = self.__dict__.setdefault("_pv_cache", {})
        key = (group, i, text, self.width())
        if key not in cache:
            old = self.preview
            self.preview = True          # 미리보기와 같은 글꼴·폭으로 잼
            try:
                probe = SubtitleLabel(self, group, 0)
                probe.set_caption(text, self.settings, 1, "center", MAX_WIDTH[group])
                cache[key] = (probe.width(), probe.height())
                probe.deleteLater()
            finally:
                self.preview = old
        return cache[key]

    def kids_box_rect(self, group, i):
        """미리보기에 보이는 박스 자리 (아동 그림이 따라갈 자리)"""
        w, h = self._preview_size(group, i)
        x, y = self._slot_xy(group, i, w, h)
        return QRect(int(x), int(y), int(w), int(h))

    def kids_cont_anchor(self):
        """지속음 그림 줄의 기준: (첫 박스 자리, 맞춤 'left'|'center'|'right', 세로인지)"""
        s = self.settings
        r = QRectF(self.kids_box_rect("continuous", 0))
        c = s.get("continuous_custom_pos")
        if c is not None and isinstance(c, (list, tuple)) and len(c) == 2:
            align = "center"
        else:
            ax = CONTINUOUS_AX.get(s.get("continuous_position", "상단 가운데"), 0.5)
            align = "left" if ax <= 0.0 else "right" if ax >= 1.0 else "center"
        return r, align, s.get("continuous_layout", "가로") == "세로"

    def kids_cont_order(self, label):
        for i, st in enumerate(self._real["continuous"][:self.slot_limit("continuous")]):
            if st is not None and st.event.label == label:
                return i
        return 99

    def _place(self, label, group, i, stack_offset=0):
        if self._kids_on() and not self.interactive and self._kids is not None and group == "continuous":
            # '글 위주' 등 지속음 글 상자가 보일 때: 그림 바로 아래
            items = self._kids._cont_layout()
            if items:
                if self.settings.get("continuous_layout", "가로") == "세로":
                    st = self._source("continuous")[i]
                    key = st.event.label if st is not None else None
                    item = next((e for e in items if e[0].key == key), None)
                    cx, bottom = (item[0].cap_x, item[0].fig_bottom) if item is not None else (None, None)
                else:
                    cx = (min(b.left() for _, b, _, _ in items) + max(b.right() for _, b, _, _ in items)) / 2
                    bottom = max(e[0].fig_bottom for e in items)
                if cx is not None:
                    x = max(0, min(round(cx - label.width() / 2), self.width() - label.width()))
                    y = max(0, min(round(bottom + 4), self.height() - label.height()))
                    label.move(x, y)
                    return
        x, y = self._slot_xy(group, i, label.width(), label.height(), stack_offset)
        label.move(x, y)

    def _source(self, group):
        return self._preview_states[group] if self.preview else self._real[group]

    def _render_slot(self, group, i, animate=True):
        label = self._labels[group][i]
        s = self.settings
        fade = s.get("fade_enabled", True) and animate
        
        if group == "continuous" and s.get("continuous_layout", "가로") == "가로":
            if i != 0:
                label.disappear(fade)
                label.shown_text = None
                self._render_slot(group, 0, animate=False)
                return
            if i == 0 and self.group_enabled("continuous"):
                active_events = [
                    st.event for st in self._source("continuous")[:self.slot_limit("continuous")] if st is not None
                ]
                if active_events:
                    combined_text = "  ·  ".join(ev.label.replace("지속음: ", "") for ev in active_events)
                    if s.get("continuous_note_enabled", True):
                        combined_text = f"♬  {combined_text}"
                    max_strength = max((ev.strength for ev in active_events), default=1)
                    label.set_caption(combined_text, s, max_strength, "center", self._max_width("continuous"))
                    self._place(label, "continuous", 0)
                    label.shown_text = combined_text
                    self._appear(label, fade)
                    self.update_click_mask()
                    return
            label.disappear(fade)
            label.shown_text = None
            self.update_click_mask()
            return

        entries = []
        if i < self.slot_limit(group) and self.group_enabled(group):
            if group == "instant" and not self.preview:
                entries = sorted(self._box[i], key=lambda st: st.shown_at)
            elif self._source(group)[i] is not None:
                entries = [self._source(group)[i]]

        if not entries:
            label.disappear(fade)
            label.shown_text = None
            self.update_click_mask()
            return

        dir_val = entries[0].event.direction
        lines = [format_caption(st.event.label, 1, dir_val, self.settings) for st in entries]
        text = "\n".join(lines)
        if group == "continuous" and s.get("continuous_note_enabled", True):
            text = f"♬  {text}"
        is_new = label.isHidden() or label.shown_text != text
        label.set_caption(text, self.settings, 1, dir_val, self._max_width(group))

        self._place(label, group, i)
        label.shown_text = text
        if is_new or (self._kids is not None and self._kids.picture_only):
            self._appear(label, fade)
        self.update_click_mask()

    def render_all(self):
        for group in ("instant", "continuous"):
            for i in range(MAX_SLOTS):
                self._render_slot(group, i, animate=False)
        self.update_click_mask()

    def handle_event(self, ev, now=None):
        ok = self._handle_event_core(ev, now)
        if ok and self._kids_on():
            self._kids_notify(ev)
        return ok

    def _handle_event_core(self, ev, now=None):
        s = self.settings
        if self._kids_on() and ev.kind == "continuous" and ev.key == "music" and ev.label != "배경음악":
            ev = replace(ev, label="배경음악")
        if self._kids_mode() and ev.kind == "instant" and ev.direction != "center":
            ev = replace(ev, direction="center")      # 아동 모드: 순간음은 가운데만 (왼/오 구분 없음)
        group = ev.kind
        if not self.group_enabled(group):
            return False

        if ev.key and ev.key in s.get("sounds_off", ()):
            return False

        now = time.monotonic() if now is None else now
        if group == "instant":
            return self._handle_instant(ev, now)
        if group == "continuous" and ev.label in self._suppressed:
            self._suppressed[ev.label] = now
            return False

        states = self._real[group]
        limit = self.slot_limit(group)

        for i in range(limit):
            st = states[i]
            if st is not None and st.event.label == ev.label:
                changed = st.event.direction != ev.direction
                st.event = ev
                st.last_seen = now
                if group == "instant":
                    st.shown_at = now
                if changed:
                    self._render_slot(group, i, animate=True)
                    self.slots_changed.emit()
                return True

        index, stack_offset = self._choose_slot(group, ev)
        if index is None:
            return False
        states[index] = SlotState(ev, shown_at=now, last_seen=now, started=now, stack_offset=stack_offset)
        self._render_slot(group, index, animate=True)
        self.slots_changed.emit()
        return True

    def _sync_box(self, i):
        b = self._box[i]
        self._real["instant"][i] = max(b, key=lambda st: st.event.score) if b else None

    def _trim_boxes(self):
        cap = self.slot_limit("instant")
        per = self.kids_inst_max() if self._kids_mode() else cap
        for i in range(MAX_SLOTS):
            b = sorted(self._box[i], key=lambda st: st.shown_at)
            self._box[i] = b[-per:] if i < cap else []
            self._sync_box(i)

    def _choose_box(self, ev):
        limit = self.slot_limit("instant")
        dirs = self.settings.get("instant_box_directions", {})
        
        # 1. 소리 방향(가운데 등)과 일치하는 박스 목록 추출 (예: [0, 1, 2])
        same_dir_boxes = [i for i in range(limit) if dirs.get(str(i), "center") == ev.direction]
        if not same_dir_boxes:
            same_dir_boxes = list(range(limit))

        # 2. 비어 있는 박스를 1번 -> 2번 -> 3번 순서로 찾음 (내용물이 완전히 없는 박스)
        for idx in same_dir_boxes:
            if not self._box[idx]:
                return idx

        # 3. 박스 1, 2, 3이 모두 꽉 차 있다면 가장 오래된(가장 먼저 떴던) 박스 하나만 교체
        return min(same_dir_boxes, key=lambda i: min((st.shown_at for st in self._box[i]), default=0))

    def _handle_instant(self, ev, now):
        limit = self.slot_limit("instant")

        # 1. 이미 화면에 떠 있는 소리와 '완전히 같은 소리'가 연속으로 들어오면?
        #    새 박스를 먹지 않고, 원래 떠 있던 그 박스의 유지 시간만 연장
        for i in range(limit):
            for st in self._box[i]:
                if st.event.label == ev.label:
                    st.event = ev
                    st.last_seen = now
                    # 아동 모드가 아니면 표시 시간도 최신화
                    if not self._kids_on():
                        st.shown_at = now
                    self._sync_box(i)
                    self._render_slot("instant", i, animate=False)
                    return True

        # 2. '새로운 소리'가 들어왔을 때만 빈 박스로 배정 (1번이 차 있으면 2번, 2번도 차 있으면 3번)
        i = self._choose_box(ev)
        box = self._box[i]

        if self._kids_mode():
            while len(box) >= self.kids_inst_max():   # 오래된 것부터 빠짐
                box.remove(min(box, key=lambda st: st.shown_at))
        else:
            box.clear()
        box.append(SlotState(ev, shown_at=now, last_seen=now, started=now))

        self._sync_box(i)
        self._render_slot("instant", i, animate=True)
        self.slots_changed.emit()
        return True

    def _choose_slot(self, group, ev):
        states = self._real[group]
        limit = self.slot_limit(group)
        if ev.slot is not None:
            return max(0, min(limit - 1, ev.slot)), 0

        free = [i for i in range(limit) if states[i] is None]
        if free:
            return free[0], 0

        candidates = [(i, st) for i, st in enumerate(states[:limit]) if not st.pinned]
        if not candidates:
            return None, 0
        i, weakest = min(candidates, key=lambda c: (c[1].event.score, c[1].shown_at))
        return (i, 0) if ev.score >= weakest.event.score else (None, 0)

    def set_slot(self, group, i, ev, pinned=True):
        now = time.monotonic()
        self._real[group][i] = SlotState(ev, now, now, now, pinned)
        if group == "instant":
            self._box[i] = [self._real[group][i]]
        self._render_slot(group, i, animate=True)
        self.slots_changed.emit()

    def clear_slot(self, group, i):
        self._real[group][i] = None
        if group == "instant":
            self._box[i] = []
        self._render_slot(group, i, animate=True)
        self.slots_changed.emit()

    def clear_all(self):
        if self._kids is not None:
            self._kids.clear()
        for group in ("instant", "continuous"):
            for i in range(MAX_SLOTS):
                self._real[group][i] = None
        self._box = [[] for _ in range(MAX_SLOTS)]
        self.render_all()
        self.slots_changed.emit()

    def clear_events(self):
        if self._kids is not None:
            self._kids.clear()
        for group in ("instant", "continuous"):
            for i in range(MAX_SLOTS):
                st = self._real[group][i]
                if st is not None and not st.pinned:
                    self._real[group][i] = None
        for i in range(MAX_SLOTS):
            self._box[i] = [st for st in self._box[i] if st.pinned]
            self._sync_box(i)
        self._suppressed.clear()
        self.render_all()
        self.slots_changed.emit()

    def _build_preview(self):
        now = time.monotonic()
        dirs = self.settings.get("instant_box_directions", {})
        for group in ("instant", "continuous"):
            self._preview_states[group] = [None] * MAX_SLOTS

        for i in range(MAX_SLOTS):
            direction = "center" if self._kids_mode() else dirs.get(str(i), "center")
            dir_kr = DIR_LABEL_KR.get(direction, "가운데")
            label_text = f"박스 {i + 1} ({dir_kr})"
            ev = SoundEvent(label_text, "instant", count=1, direction=direction, strength=1)
            self._preview_states["instant"][i] = SlotState(ev, now, now, now, True)

        for i, label in enumerate(PREVIEW_CONTINUOUS[:MAX_SLOTS]):
            ev = SoundEvent(f"{label}", "continuous", strength=1)
            self._preview_states["continuous"][i] = SlotState(ev, now, now, now, True)

    def set_preview(self, on):
        self.preview = on
        if self._kids is not None:
            self._kids.clear()
        if on:
            self._build_preview()
        self.render_all()

    def _expire(self, group, i, fade=True):
        self._real[group][i] = None
        if not self.preview:
            self._render_slot(group, i, animate=fade)

    def _tick(self):
        now = time.monotonic()
        s = self.settings
        fade = s.get("fade_enabled", True)
        changed = False

        for i in range(MAX_SLOTS):
            kids = self._kids_on()
            def _t(st):
                return kids_times(st.event.label, s["instant_duration"]) if kids else (s["instant_duration"], KIDS_REPEAT_HOLD)
            keep = [st for st in self._box[i] if st.pinned or now - st.shown_at <= _t(st)[0]
                    or (kids and now - st.last_seen <= _t(st)[1])]
            if len(keep) != len(self._box[i]):
                self._box[i] = keep
                self._sync_box(i)
                if not self.preview:
                    self._render_slot("instant", i, animate=fade)
                changed = True

        for i, st in enumerate(self._real["continuous"]):
            if st is None or st.pinned:
                continue
            hold_ = KIDS_CONT_HOLD.get(st.event.label, CONTINUOUS_HOLD) if self._kids_on() else CONTINUOUS_HOLD
            expired = now - st.last_seen > hold_
            limit = s.get("continuous_duration", 0)
            if not expired and limit > 0 and now - st.started > limit:
                expired = True
                self._suppressed[st.event.label] = now
            if expired:
                self._expire("continuous", i, fade=fade)
                changed = True

        for label, seen in list(self._suppressed.items()):
            if now - seen > CONTINUOUS_HOLD:
                del self._suppressed[label]

        if changed:
            self.slots_changed.emit()
            if self._kids_on():
                self._kids.sync_instant(self._kids_shown_labels())
                self._position_kids_captions()