import sys
import time
from copy import deepcopy
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFontDatabase, QGuiApplication, QDoubleValidator, QPainter
from PySide6.QtWidgets import (
    QAbstractButton, QApplication, QButtonGroup, QColorDialog, QComboBox, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSlider, QStackedWidget, QTabWidget, QVBoxLayout, QWidget,
    QSizePolicy,
)

from bridge import SoundBridge
from mode_overlay import QuickModeOverlay
from overlay import SubtitleOverlay
from preset_dialog import PresetCreateDialog
from sound_tree import COMMON, build_full_tree, build_tree, mode_keys
from audio_devices import list_output_devices
from settings import (
    DEFAULT_CAPTURE, DEFAULT_MODES, FONT_CANDIDATES, KIDS_VIEWS, POSITIONS, SETTINGS_PATH,
    default_settings, load_state, normalize, save_state,
)

HOTKEY_ID = 101
MOD_ALT = 0x0001
VK_M = 0x4D

BG_LIGHT = "#F4F6FB"
CARD_BG = "#FFFFFF"
FIELD_BG = "#F8FAFC"
BORDER_COLOR = "#E2E8F0"
PRIMARY_BLUE = "#2563EB"
PRIMARY_HOVER = "#1D4ED8"
RED_COLOR = "#EF4444"
GRAY_TEXT = "#64748B"

APP_STYLE = f"""
QWidget {{
    color: #0F172A;
    font-size: 14px;
    font-family: 'Pretendard', 'Segoe UI', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
}}
QMainWindow, #page {{ background-color: {BG_LIGHT}; }}
QScrollArea {{ background: transparent; border: none; }}

QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #CBD5E1; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {PRIMARY_BLUE}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

#title {{ color: #0F172A; font-size: 24px; font-weight: 800; letter-spacing: -0.5px; }}
#subtitle {{ color: {GRAY_TEXT}; font-size: 13px; }}
#section {{ color: #0F172A; font-size: 16px; font-weight: 800; }}
#rowTitle {{ font-size: 13px; font-weight: 700; color: #0F172A; }}
#rowSub {{ color: {GRAY_TEXT}; font-size: 11px; }}
#unit {{ color: {PRIMARY_BLUE}; font-size: 13px; font-weight: 700; }}

#card {{ 
    background-color: {CARD_BG}; 
    border: 1px solid {BORDER_COLOR}; 
    border-radius: 14px; 
}}
#sep {{ 
    background-color: {BORDER_COLOR}; 
    margin-left: 20px; 
    margin-right: 20px; 
}}

#bannerCard {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER_COLOR};
    border-radius: 14px;
}}
#activeBadge {{
    background-color: #EFF6FF;
    border: 1px solid {PRIMARY_BLUE};
    border-radius: 10px;
    color: {PRIMARY_BLUE};
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 800;
}}
#modNotice {{ color: #D97706; font-size: 12px; font-weight: 600; }}

QLineEdit {{
    background-color: #F8FAFC;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    color: #0F172A;
    padding: 6px 12px;
    font-weight: 600;
}}
QLineEdit:focus {{ border: 1.5px solid {PRIMARY_BLUE}; background-color: #FFFFFF; }}

QComboBox {{
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    color: #0F172A;
    padding: 5px 36px 5px 14px;
    min-height: 22px;
    font-weight: 600;
    font-size: 13px;
}}
QComboBox:hover {{
    border: 1.5px solid {PRIMARY_BLUE};
    background-color: #F8FAFC;
}}
QComboBox:focus {{
    border: 1.5px solid {PRIMARY_BLUE};
    background-color: #FFFFFF;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 32px;
    border: none;
    background: transparent;
}}
QComboBox::down-arrow {{
    image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2364748B' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'><path d='m6 9 6 6 6-6'/></svg>");
    width: 14px;
    height: 14px;
    margin-right: 12px;
}}
QComboBox::down-arrow:hover {{
    image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%232563EB' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'><path d='m6 9 6 6 6-6'/></svg>");
}}
QComboBox QAbstractItemView {{
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    selection-background-color: #EFF6FF !important;
    selection-color: {PRIMARY_BLUE} !important;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    padding: 6px;
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    min-height: 32px;
    border-radius: 6px;
    padding-left: 10px;
}}

QSlider::groove:horizontal {{
    height: 6px;
    background: #E2E8F0;
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {PRIMARY_BLUE};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: #FFFFFF;
    border: 2px solid {PRIMARY_BLUE};
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background: {PRIMARY_BLUE};
}}

#seg {{
    background-color: #F1F5F9;
    border: 1px solid #CBD5E1;
    border-radius: 10px;
    padding: 2px;
}}
#seg QPushButton {{
    background-color: transparent;
    color: #0F172A !important;
    border: none;
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 700;
}}
#seg QPushButton:checked {{
    background-color: #2563EB !important;
    color: #FFFFFF !important;
    font-weight: 800;
}}

QTabWidget::pane {{
    border: 1px solid {BORDER_COLOR};
    background-color: {BG_LIGHT};
    border-radius: 14px;
}}
QTabBar::tab {{
    background: {CARD_BG};
    color: #475569;
    padding: 10px 24px;
    font-weight: 700;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    margin-right: 4px;
    border: 1px solid {BORDER_COLOR};
}}
QTabBar::tab:selected {{
    background: #E2E8F0;
    color: {PRIMARY_BLUE};
    border: 1px solid {PRIMARY_BLUE};
    border-bottom: none;
}}
"""

# 소리 필터 목록은 sound_tree.build_tree(base_mode) 가 모드마다 만들어요 (라벨 파일의 실제 라벨)


class NoWheelSlider(QSlider):
    def wheelEvent(self, event):
        event.ignore()


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


def button_style(bg, hover, pressed, color="#FFFFFF", border="none"):
    return f"""
        QPushButton {{
            background-color: {bg}; color: {color}; border: {border};
            border-radius: 8px; padding: 6px 14px; font-size: 13px; font-weight: 800;
            white-space: nowrap;
        }}
        QPushButton:hover {{ background-color: {hover}; }}
        QPushButton:pressed {{ background-color: {pressed}; }}
        QPushButton:disabled {{ background-color: #E2E8F0; color: #94A3B8; border: 1px solid #CBD5E1; }}
    """


BLUE_BUTTON_STYLE = button_style(PRIMARY_BLUE, PRIMARY_HOVER, "#1E40AF", color="#FFFFFF")
GRAY_BUTTON_STYLE = button_style("#F1F5F9", "#E2E8F0", "#CBD5E1", color="#0F172A", border=f"1px solid {BORDER_COLOR}")
DANGER_BUTTON_STYLE = button_style("#FEE2E2", "#FCA5A5", "#F87171", color=RED_COLOR, border=f"1px solid #FECACA")


class ToggleSwitch(QAbstractButton):
    def __init__(self, checked=False):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(44, 24)

        self._pos = 1.0 if checked else 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self.toggled.connect(self._animate)

    def _animate(self, checked):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def _on_anim(self, value):
        self._pos = float(value)
        self.update()

    def set_checked_now(self, checked):
        """애니메이션 없이 바로 그 상태로 (설정 불러오기·모드 전환 때)"""
        self.setChecked(checked)
        self._anim.stop()
        self._pos = 1.0 if checked else 0.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        off, on = QColor("#CBD5E1"), QColor(PRIMARY_BLUE)
        t = self._pos
        color = QColor(
            int(off.red() + (on.red() - off.red()) * t),
            int(off.green() + (on.green() - off.green()) * t),
            int(off.blue() + (on.blue() - off.blue()) * t),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        radius = self.height() / 2
        painter.drawRoundedRect(QRectF(self.rect()), radius, radius)

        margin = 3
        d = self.height() - margin * 2
        x = margin + (self.width() - d - margin * 2) * t
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(x, margin, d, d))


class SegmentedControl(QFrame):
    def __init__(self, items):
        super().__init__()
        self.setObjectName("seg")
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(3, 3, 3, 3)
        self.layout.setSpacing(3)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.set_items(items)

    def set_items(self, items):
        for btn in self.group.buttons():
            self.group.removeButton(btn)
            self.layout.removeWidget(btn)
            btn.deleteLater()

        self.buttons = {}
        for i, name in enumerate(items):
            button = QPushButton(name)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            
            button.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #0F172A;
                    border: none;
                    border-radius: 8px;
                    padding: 6px 14px;
                    font-size: 13px;
                    font-weight: 700;
                }
                QPushButton:checked {
                    background-color: #2563EB;
                    color: #FFFFFF;
                    font-weight: 800;
                }
            """)
            
            self.group.addButton(button, i)
            self.layout.addWidget(button)
            self.buttons[name] = button

        if items:
            self.buttons[items[0]].setChecked(True)

    def currentText(self):
        checked = self.group.checkedButton()
        return checked.text() if checked else ""

    def setCurrentText(self, text):
        if text in self.buttons:
            self.buttons[text].setChecked(True)


def make_section(title):
    label = QLabel(title)
    label.setObjectName("section")
    label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    return label


def make_row(title, control, subtitle=None, expand=False):
    row = QWidget()
    row.setMinimumHeight(64)
    row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(20, 10, 20, 10)
    layout.setSpacing(16)
    layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

    texts = QVBoxLayout()
    texts.setSpacing(2)
    title_label = QLabel(title)
    title_label.setObjectName("rowTitle")
    texts.addWidget(title_label)
    if subtitle:
        sub_label = QLabel(subtitle)
        sub_label.setObjectName("rowSub")
        texts.addWidget(sub_label)
    layout.addLayout(texts)

    control.setSizePolicy(QSizePolicy.Policy.Expanding if expand else QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    if expand:
        layout.addWidget(control, 1)
    else:
        layout.addStretch(1)
        layout.addWidget(control)
    return row


def make_card(rows):
    card = QFrame()
    card.setObjectName("card")
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(0, 6, 0, 12)
    layout.setSpacing(0)
    for i, row in enumerate(rows):
        if i:
            sep = QFrame()
            sep.setObjectName("sep")
            sep.setFixedHeight(1)
            sep.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            layout.addWidget(sep)
        layout.addWidget(row)
    return card


class ColorPickerField(QPushButton):
    colorChanged = Signal(str)

    def __init__(self, color="#2563EB"):
        super().__init__()
        self._color = color
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(100)
        self.setFixedHeight(34)
        self.clicked.connect(self._pick)
        self._refresh()

    def color(self):
        return self._color

    def setColor(self, color):
        if QColor(color).isValid():
            self._color = QColor(color).name().upper()
            self._refresh()

    def _pick(self):
        dialog = QColorDialog(QColor(self._color), self)
        dialog.setWindowTitle("색 선택")
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        
        dialog.setStyleSheet("""
            QColorDialog {
                background-color: #FFFFFF !important;
                color: #0F172A !important;
            }
            QColorDialog QLabel {
                color: #0F172A !important;
                background-color: transparent !important;
                font-size: 12px !important;
                font-weight: bold !important;
            }
            QColorDialog QLineEdit, QColorDialog QSpinBox {
                background-color: #F8FAFC !important;
                color: #0F172A !important;
                border: 1px solid #CBD5E1 !important;
                border-radius: 4px !important;
                padding: 4px !important;
                font-weight: bold !important;
            }
            QColorDialog QPushButton {
                background-color: #F1F5F9 !important;
                color: #0F172A !important;
                border: 1px solid #CBD5E1 !important;
                border-radius: 6px !important;
                padding: 6px 14px !important;
                font-weight: bold !important;
            }
            QColorDialog QPushButton:hover {
                background-color: #2563EB !important;
                color: #FFFFFF !important;
            }
        """)

        if dialog.exec() == QColorDialog.DialogCode.Accepted:
            chosen = dialog.selectedColor()
            if chosen.isValid():
                self.setColor(chosen.name())
                self.colorChanged.emit(self._color)

    def _refresh(self):
        c = QColor(self._color)
        luminance = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
        text_col = "#000000" if luminance > 128 else "#FFFFFF"
        self.setText(self._color)
        self.setStyleSheet(
            f"QPushButton {{ background-color: {self._color}; color: {text_col}; "
            f"border: 1px solid {BORDER_COLOR}; border-radius: 8px; font-size: 12px; "
            f"font-weight: 800; padding: 4px 12px; }}"
        )


def make_slider(minimum, maximum, value, formatter, label_width=44):
    slider = NoWheelSlider(Qt.Orientation.Horizontal)
    slider.setRange(minimum, maximum)
    slider.setValue(value)
    slider.setMinimumWidth(120)
    slider.setFixedHeight(24)
    label = QLabel(formatter(value))
    label.setObjectName("unit")
    label.setFixedWidth(label_width)
    label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    slider.valueChanged.connect(lambda v: label.setText(formatter(v)))
    
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
    layout.addWidget(slider, 1)
    layout.addWidget(label)
    return box, slider


def available_fonts():
    installed = set(QFontDatabase.families())
    fonts = [name for name in FONT_CANDIDATES if name in installed]
    return fonts or ["Malgun Gothic"]


GROUP_LABEL = {"instant": "순간음", "continuous": "지속음"}
DIRECTION_LABELS = {"left": "왼쪽", "center": "가운데", "right": "오른쪽"}
DIRECTION_VALUES = {label: value for value, label in DIRECTION_LABELS.items()}


class BoxDirectionSelector(QWidget):
    directionChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.box_directions = ["left", "center", "right", "center", "left"]
        self.selected_box_idx = 0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        row1_box = QWidget()
        row1_box.setMinimumHeight(60)
        row1_layout = QVBoxLayout(row1_box)          # 제목 아래에 버튼 줄 (좁은 창에서도 안 넘치게)
        row1_layout.setContentsMargins(20, 10, 20, 10)
        row1_layout.setSpacing(8)

        lbl_box_select = QLabel("박스 선택")
        lbl_box_select.setObjectName("rowTitle")
        row1_layout.addWidget(lbl_box_select)

        box_btn_group = QWidget()
        box_btn_layout = QHBoxLayout(box_btn_group)
        box_btn_layout.setContentsMargins(0, 0, 0, 0)
        box_btn_layout.setSpacing(6)
        box_btn_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.box_buttons = []
        for i in range(5):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(34)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _, idx=i: self._select_box(idx))
            box_btn_layout.addWidget(btn)
            self.box_buttons.append(btn)

        row1_layout.addWidget(box_btn_group)
        layout.addWidget(row1_box)

        sep = QFrame()
        sep.setObjectName("sep")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        row2_box = QWidget()
        row2_box.setMinimumHeight(60)
        row2_layout = QHBoxLayout(row2_box)
        row2_layout.setContentsMargins(20, 10, 20, 10)
        row2_layout.setSpacing(12)
        row2_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.lbl_dir_title = QLabel("위치 선택 (박스 1)")
        self.lbl_dir_title.setObjectName("rowTitle")
        row2_layout.addWidget(self.lbl_dir_title)
        row2_layout.addStretch(1)

        self.dir_control = SegmentedControl(["왼쪽", "가운데", "오른쪽"])
        self.dir_control.setMinimumHeight(36)
        self.dir_control.group.buttonClicked.connect(self._on_dir_changed)
        row2_layout.addWidget(self.dir_control)

        layout.addWidget(row2_box)

        self._update_box_button_labels()
        self._select_box(0)

    def _update_box_button_labels(self):
        for i, btn in enumerate(self.box_buttons):
            dir_kr = DIRECTION_LABELS.get(self.box_directions[i], "가운데")
            btn.setText(f"박스 {i + 1} ({dir_kr})")

    def _select_box(self, idx):
        self.selected_box_idx = idx
        dir_kr = DIRECTION_LABELS.get(self.box_directions[idx], "가운데")
        self.lbl_dir_title.setText(f"위치 선택 (박스 {idx + 1})")

        for i, btn in enumerate(self.box_buttons):
            if i == idx:
                btn.setChecked(True)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {PRIMARY_BLUE} !important;
                        color: #FFFFFF !important;
                        font-weight: 800 !important;
                        border-radius: 8px !important;
                        border: none !important;
                        font-size: 13px !important;
                        padding: 0px 6px !important;
                    }}
                """)
            else:
                btn.setChecked(False)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {FIELD_BG} !important;
                        color: #0F172A !important;
                        border: 1px solid {BORDER_COLOR} !important;
                        border-radius: 8px !important;
                        font-weight: 700 !important;
                        font-size: 13px !important;
                        padding: 0px 6px !important;
                    }}
                    QPushButton:hover {{
                        background-color: #CBD5E1 !important;
                        color: #0F172A !important;
                    }}
                """)

        self.dir_control.blockSignals(True)
        self.dir_control.setCurrentText(dir_kr)
        self.dir_control.blockSignals(False)

    def _on_dir_changed(self, button):
        dir_kr = button.text()
        dir_val = DIRECTION_VALUES.get(dir_kr, "center")
        self.box_directions[self.selected_box_idx] = dir_val

        self._update_box_button_labels()
        self._select_box(self.selected_box_idx)
        self.directionChanged.emit()

    def get_directions_dict(self):
        return {str(i): self.box_directions[i] for i in range(5)}

    def set_directions_dict(self, dirs):
        for i in range(5):
            d_val = dirs.get(str(i), "center")
            self.box_directions[i] = d_val if d_val in ["left", "center", "right"] else "center"
        self._update_box_button_labels()
        self._select_box(self.selected_box_idx)


class MainControlWindow(QMainWindow):

    def __init__(self, bridge=None, settings_path=None):
        super().__init__()
        app = QApplication.instance()
        if app is not None:
            app_font = app.font()
            app_font.setFamilies(["Pretendard", "Segoe UI", "Malgun Gothic"])
            app.setFont(app_font)

        self.controls_A = {}
        self.controls_B = {}
        # 소리 필터 (대분류 > 중분류 > 소리, sound_tree.py) — 같은 필터 카드가 두 페이지에 있어 상태는 하나로 공유
        self.sound_views = []              # 필터 카드마다 {host, search, rows}
        self.sound_filter_mode = None      # 지금 그려 둔 트리의 모드
        self.sound_off = set()             # 꺼 둔 라벨 키
        self._sound_syncing = False
        self.sound_leaf_switches = []      # (토글, 라벨 키들)
        self.sound_node_switches = []      # (토글, 아래 소리들 [[키...]...], '일부 꺼짐' 라벨)

        self.preview_switch_corner = ToggleSwitch(False)

        self.bridge = bridge if bridge is not None else SoundBridge()
        self.overlay = SubtitleOverlay()
        
        self.quick_overlay = QuickModeOverlay()
        self.quick_overlay.mode_selected.connect(self.on_quick_mode_selected)
        self.quick_overlay.mode_edit_requested.connect(self.on_quick_mode_edit_requested)
        self.quick_overlay.edit_completed.connect(self.on_quick_mode_edit_completed)

        self.settings_path = settings_path or SETTINGS_PATH
        self.state = load_state(self.settings_path)
        self._real_target = self.state["active_target"]   # '공통' 화면을 보는 동안에도 실제로 쓰는 모드·프리셋
        self._common_baseline = None                        # '공통' 화면을 열 때의 값 (바꾼 것만 골라내는 기준)
        self.is_service_running = False
        self._loading = False
        self._is_modified = False
        self._service_was_running_before_preview = False
        self._is_quick_editing = False
        
        self.expanded_modes = {mode: False for mode in DEFAULT_MODES}
        for preset in self.state.get("presets", {}):
            self.expanded_modes[preset] = False

        self.current_sub_view = "common_all"

        self.init_ui()
        self.register_global_hotkey()

        self.overlay.slots_changed.connect(self.refresh)
        self.overlay.custom_pos_changed.connect(self.on_instant_dragged)
        self.bridge.sound_received.connect(self.on_sound)
        self.bridge.backend_status.connect(self.on_backend_status)
        self.backend = None

        self.apply_active_config_to_ui()
        self.commit_settings()

    def register_global_hotkey(self):
        if sys.platform == "win32":
            hwnd = int(self.winId())
            ctypes.windll.user32.RegisterHotKey(hwnd, HOTKEY_ID, MOD_ALT, VK_M)

    def nativeEvent(self, eventType, message):
        if sys.platform == "win32" and eventType == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam == HOTKEY_ID:
                self.toggle_quick_mode_overlay()
                return True, 0
        return super().nativeEvent(eventType, message)

    def toggle_quick_mode_overlay(self):
        if self.quick_overlay.isVisible():
            self.quick_overlay.hide()
        else:
            self.quick_overlay.set_modes(
                DEFAULT_MODES, 
                self.state["presets"], 
                self.state["active_target"]
            )
            self.quick_overlay.show()
            self.quick_overlay.raise_()
            self.quick_overlay.activateWindow()

    def on_quick_mode_selected(self, target_name):
        self.activate_target(target_name)

    def on_quick_mode_edit_requested(self, target_name):
        self.activate_target(target_name)
        self._is_quick_editing = True
        
        self._service_was_running_before_preview = self.is_service_running
        if self.is_service_running:
            self.bridge.service_toggled.emit(False)
            self.overlay.clear_events()

        self.overlay.set_preview(True)
        self.overlay.set_interactive(True)
        self.update_overlay_visibility()

    def on_quick_mode_edit_completed(self):
        self.commit_settings()
        self._is_quick_editing = False

        self.overlay.set_interactive(False)
        self.overlay.set_preview(False)

        if self._service_was_running_before_preview:
            self.bridge.service_toggled.emit(True)
            self._service_was_running_before_preview = False

        self.update_overlay_visibility()

    def activate_target(self, target_name):
        if target_name not in self.state["modes"] and target_name not in self.state["presets"]:
            return

        if target_name != self.state["active_target"]:
            if self._is_modified:
                self.commit_settings()
            self.state["active_target"] = target_name
            self.apply_active_config_to_ui()
            self.commit_settings()

    def init_ui(self):
        self.setWindowTitle("환경음 자막")
        self.setStyleSheet(APP_STYLE)

        available = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(
            max(940, min(1160, int(available.width() * 0.9))),
            max(660, min(880, int(available.height() * 0.88))),
        )
        self.setMinimumSize(920, 640)

        self.central_box = QWidget()
        c_layout = QVBoxLayout(self.central_box)
        c_layout.setContentsMargins(16, 12, 16, 16)
        c_layout.setSpacing(10)

        self.top_banner = QFrame()
        self.top_banner.setObjectName("bannerCard")
        banner_layout = QHBoxLayout(self.top_banner)
        banner_layout.setContentsMargins(16, 10, 16, 10)
        banner_layout.setSpacing(12)

        self.lbl_active_badge = QLabel("적용 중: FPS(기본)")
        self.lbl_active_badge.setObjectName("activeBadge")

        self.lbl_mod_notice = QLabel("")
        self.lbl_mod_notice.setObjectName("modNotice")

        self.btn_apply_settings = QPushButton("설정 저장")
        self.btn_apply_settings.setStyleSheet(BLUE_BUTTON_STYLE)
        self.btn_apply_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply_settings.clicked.connect(self.commit_settings)

        self.btn_reload_settings = QPushButton("되돌리기")
        self.btn_reload_settings.setStyleSheet(GRAY_BUTTON_STYLE)
        self.btn_reload_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reload_settings.clicked.connect(self.apply_active_config_to_ui)

        banner_layout.addWidget(self.lbl_active_badge)
        banner_layout.addWidget(self.lbl_mod_notice, 1)
        banner_layout.addWidget(self.btn_reload_settings)
        banner_layout.addWidget(self.btn_apply_settings)

        c_layout.addWidget(self.top_banner)

        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)

        corner_widget = QWidget()
        cw_layout = QHBoxLayout(corner_widget)
        cw_layout.setContentsMargins(0, 0, 12, 0)
        cw_layout.setSpacing(8)
        lbl_cw = QLabel("실시간 미리보기")
        lbl_cw.setStyleSheet("font-size: 13px; font-weight: 700; color: #0F172A;")
        self.preview_switch_corner.toggled.connect(self.on_preview_toggled)
        cw_layout.addWidget(lbl_cw)
        cw_layout.addWidget(self.preview_switch_corner)
        self.tabs.setCornerWidget(corner_widget, Qt.Corner.TopRightCorner)

        c_layout.addWidget(self.tabs, 1)
        self.setCentralWidget(self.central_box)

        # ---------------- 탭 1: 메인 ----------------
        tab1_scroll = QScrollArea()
        tab1_scroll.setWidgetResizable(True)
        page1 = QWidget()
        page1.setObjectName("page")
        tab1_scroll.setWidget(page1)
        layout1 = QVBoxLayout(page1)
        layout1.setContentsMargins(24, 18, 24, 20)
        layout1.setSpacing(18)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("환경음 자막")
        title.setObjectName("title")
        heading.addWidget(title)
        header.addLayout(heading, 1)

        hotkey_badge = QFrame()
        hotkey_badge.setStyleSheet(f"background: {CARD_BG}; border: 1px solid {BORDER_COLOR}; border-radius: 10px; padding: 4px 10px;")
        hb_layout = QHBoxLayout(hotkey_badge)
        hb_layout.setContentsMargins(8, 4, 8, 4)
        hb_lbl = QLabel(f"빠른 모드 전환 단축키: <span style='color:{PRIMARY_BLUE}; font-weight:800;'>Alt + M</span>")
        hb_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #1E293B;")
        hb_layout.addWidget(hb_lbl)
        header.addWidget(hotkey_badge, 0, Qt.AlignmentFlag.AlignTop)
        layout1.addLayout(header)

        self.hero_power_card = QFrame()
        self.hero_power_card.setObjectName("card")
        hero_layout = QHBoxLayout(self.hero_power_card)
        hero_layout.setContentsMargins(24, 18, 24, 18)
        hero_layout.setSpacing(20)

        hero_text_box = QVBoxLayout()
        self.hero_status_title = QLabel("자막 오버레이 중지됨")
        self.hero_status_title.setStyleSheet("font-size: 19px; font-weight: 800; color: #0F172A;")
        self.hero_status_sub = QLabel("시작 버튼을 누르면 화면에 소리 자막이 활성화됩니다.")
        self.hero_status_sub.setStyleSheet(f"color: {GRAY_TEXT}; font-size: 12px;")
        hero_text_box.addWidget(self.hero_status_title)
        hero_text_box.addWidget(self.hero_status_sub)
        self.lbl_backend_status = QLabel("백엔드: 초기화 중")
        self.lbl_backend_status.setStyleSheet(f"color: {PRIMARY_BLUE}; font-size: 12px; font-weight: 700;")
        self.lbl_backend_status.setWordWrap(True)
        hero_text_box.addWidget(self.lbl_backend_status)
        hero_layout.addLayout(hero_text_box, 1)

        self.btn_main_power = QPushButton("서비스 시작")
        self.btn_main_power.setMinimumSize(170, 48)
        self.btn_main_power.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_main_power.setStyleSheet(BLUE_BUTTON_STYLE)
        self.btn_main_power.clicked.connect(self.toggle_service)
        hero_layout.addWidget(self.btn_main_power)

        layout1.addWidget(self.hero_power_card)

        layout1.addWidget(make_section("모드 및 프리셋 선택"))
        self.mode_tiles_container = QWidget()
        self.mode_tiles_layout = QVBoxLayout(self.mode_tiles_container)
        self.mode_tiles_layout.setContentsMargins(0, 0, 0, 0)
        self.mode_tiles_layout.setSpacing(14)

        self.base_mode_heading = QLabel("기본 모드")
        self.base_mode_heading.setObjectName("section")
        self.base_modes_container = QWidget()
        self.base_modes_grid = QGridLayout(self.base_modes_container)
        self.base_modes_grid.setContentsMargins(0, 0, 0, 0)
        self.base_modes_grid.setHorizontalSpacing(10)
        self.base_modes_grid.setVerticalSpacing(10)

        preset_header_box = QWidget()
        ph_layout = QHBoxLayout(preset_header_box)
        ph_layout.setContentsMargins(0, 0, 0, 0)
        self.preset_mode_heading = QLabel("프리셋")
        self.preset_mode_heading.setObjectName("section")
        ph_layout.addWidget(self.preset_mode_heading)
        ph_layout.addStretch(1)

        self.preset_modes_container = QWidget()
        self.preset_modes_grid = QGridLayout(self.preset_modes_container)
        self.preset_modes_grid.setContentsMargins(0, 0, 0, 0)
        self.preset_modes_grid.setHorizontalSpacing(10)
        self.preset_modes_grid.setVerticalSpacing(10)
        self.preset_empty_label = QLabel("등록된 프리셋이 없습니다. 설정에서 프리셋을 추가할 수 있어요.")
        self.preset_empty_label.setObjectName("rowSub")

        self.mode_tiles_layout.addWidget(self.base_mode_heading)
        self.mode_tiles_layout.addWidget(self.base_modes_container)
        self.mode_tiles_layout.addWidget(preset_header_box)
        self.mode_tiles_layout.addWidget(self.preset_modes_container)
        self.mode_tiles_layout.addWidget(self.preset_empty_label)
        layout1.addWidget(self.mode_tiles_container)

        layout1.addStretch(1)
        self.tabs.addTab(tab1_scroll, "메인")

        # ---------------- 탭 2: 설정 ----------------
        tab2_widget = QWidget()
        tab2_layout = QHBoxLayout(tab2_widget)
        tab2_layout.setContentsMargins(16, 16, 16, 16)
        tab2_layout.setSpacing(16)

        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setFixedWidth(260)
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 12px;
            }}
        """)
        
        self.sidebar_container = QWidget()
        self.sidebar_layout = QVBoxLayout(self.sidebar_container)
        self.sidebar_layout.setContentsMargins(10, 14, 10, 14)
        self.sidebar_layout.setSpacing(6)
        self.sidebar_scroll.setWidget(self.sidebar_container)
        tab2_layout.addWidget(self.sidebar_scroll)

        self.main_stack = QStackedWidget()
        
        self.page_common_all = self.build_page_common_all()   # idx 0
        self.page_slots = self.build_page_slots()             # idx 1
        self.page_design = self.build_page_design()           # idx 2
        self.page_layout = self.build_page_layout()           # idx 3
        self.page_sound_labels = self.build_page_sound_labels() # idx 4

        self.main_stack.addWidget(self.page_common_all)
        self.main_stack.addWidget(self.page_slots)
        self.main_stack.addWidget(self.page_design)
        self.main_stack.addWidget(self.page_layout)
        self.main_stack.addWidget(self.page_sound_labels)

        tab2_layout.addWidget(self.main_stack, 1)
        self.tabs.addTab(tab2_widget, "설정")

        self._connect_sync_signals()
        self.set_service(False)

    def create_card_audio(self, tag):
        combo = NoWheelComboBox()
        combo.setMinimumHeight(36)
        # 장치 이름이 길어도 칸이 늘어나 화면을 밀지 않게 (펼친 목록은 전체 이름이 보이게 넓게)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(14)
        combo.setMinimumWidth(180)
        combo.setMaximumWidth(320)
        combo.view().setMinimumWidth(320)
        self.controls_A["audio" if tag == "A" else "audio_B"] = combo
        self.refresh_audio_devices(combo)
        combo.currentTextChanged.connect(lambda _t, c=combo: c.setToolTip(c.currentText()))
        combo.currentTextChanged.connect(self.on_capture_changed)

        btn_refresh = QPushButton("새로고침")
        btn_refresh.setFixedHeight(34)
        btn_refresh.setStyleSheet(GRAY_BUTTON_STYLE)
        btn_refresh.setToolTip("헤드폰을 새로 꽂았을 때 장치 목록을 다시 불러와요")
        btn_refresh.clicked.connect(lambda _=False, c=combo: self.refresh_audio_devices(c))

        box = QWidget()
        box_lay = QHBoxLayout(box)
        box_lay.setContentsMargins(0, 0, 0, 0)
        box_lay.setSpacing(8)
        box_lay.addWidget(combo, 1)
        box_lay.addWidget(btn_refresh)
        return make_card([
            make_row("사운드 캡처 장치 선택", box, "소리를 받아올 출력 장치 (바로 적용)"),
        ])

    def refresh_audio_devices(self, combo):
        """실제 출력 장치 목록으로 다시 채움. 저장된 장치가 지금 없으면(뽑힘) '(연결 안 됨)'으로 남겨 둠"""
        current = self.state.get("capture_target", DEFAULT_CAPTURE) if hasattr(self, "state") else DEFAULT_CAPTURE
        devices = list_output_devices()
        combo.blockSignals(True)
        try:
            combo.clear()
            combo.addItem(DEFAULT_CAPTURE, DEFAULT_CAPTURE)
            for name in devices:
                combo.addItem(name, name)
            self._select_capture(combo, current)
        finally:
            combo.blockSignals(False)

    @staticmethod
    def _select_capture(combo, value):
        value = value or DEFAULT_CAPTURE
        idx = combo.findData(value)
        if idx < 0:
            combo.addItem(f"{value} (연결 안 됨)", value)
            idx = combo.count() - 1
        combo.setCurrentIndex(idx)

    def _capture_value(self):
        combo = self.controls_A.get("audio", self.controls_A.get("audio_B"))
        if combo is None or combo.currentData() is None:
            return self.state.get("capture_target", DEFAULT_CAPTURE)
        return combo.currentData()

    def on_capture_changed(self, *_):
        """장치는 고르는 즉시 적용·저장 ([설정 저장] 필요 없음, 모든 모드에 같이 쓰임)"""
        if self._loading:
            return
        self.state["capture_target"] = self._capture_value()
        self._save_state()
        self.bridge.capture_changed.emit(self.state["capture_target"])

    def create_card_slots(self, tag):
        c = self.controls_A if tag == "A" else self.controls_B
        
        i_slots = NoWheelComboBox()
        i_slots.setMinimumHeight(36)
        i_slots.addItems([f"{i}개" for i in range(1, 6)])
        
        c_slots = NoWheelComboBox()
        c_slots.setMinimumHeight(36)
        c_slots.addItems(["없음", "1개", "2개", "3개", "4개", "5개"])

        slot_box = QWidget()
        slot_layout = QHBoxLayout(slot_box)
        slot_layout.setContentsMargins(0, 0, 0, 0)
        slot_layout.setSpacing(10)
        slot_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        slot_layout.addWidget(QLabel("순간음"))
        slot_layout.addWidget(i_slots)
        slot_layout.addWidget(QLabel("지속음"))
        slot_layout.addWidget(c_slots)

        i_enabled = ToggleSwitch(True)
        c_enabled = ToggleSwitch(True)
        onoma_enabled = ToggleSwitch(True)
        continuous_note_enabled = ToggleSwitch(True)

        i_dur = QLineEdit("3.0")
        i_dur.setFixedWidth(70)
        i_dur.setMinimumHeight(36)
        i_dur.setAlignment(Qt.AlignmentFlag.AlignRight)
        i_dur.setValidator(QDoubleValidator(0.1, 10.0, 1, self))

        dur_unit = QLabel("초")
        dur_unit.setObjectName("unit")
        dur_box = QWidget()
        dur_layout = QHBoxLayout(dur_box)
        dur_layout.setContentsMargins(0, 0, 0, 0)
        dur_layout.setSpacing(6)
        dur_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        dur_layout.addWidget(i_dur)
        dur_layout.addWidget(dur_unit)

        c_dur_box, c_dur_slider = make_slider(0, 30, 0, lambda v: "제한 없음" if v == 0 else f"{v}초", label_width=62)

        c["instant_slots"] = i_slots
        c["continuous_slots"] = c_slots
        c["instant_enabled"] = i_enabled
        c["continuous_enabled"] = c_enabled
        c["onoma_enabled"] = onoma_enabled
        c["continuous_note_enabled"] = continuous_note_enabled
        c["instant_duration"] = i_dur
        c["continuous_duration"] = c_dur_slider

        return make_card([
            make_row("순간음 / 지속음 칸 수", slot_box),
            make_row("순간음 자막 활성화", i_enabled),
            make_row("지속음 자막 활성화", c_enabled),
            make_row("의성어 표시", onoma_enabled, "켜면 '총성 탕!', 끄면 '총성'"),
            make_row("지속음 음표 표시", continuous_note_enabled),
            make_row("순간음 표시 시간", dur_box),
            make_row("지속음 최대 표시 시간", c_dur_box, expand=True),
        ])

    def create_card_design(self, tag):
        c = self.controls_A if tag == "A" else self.controls_B
        
        f_size_box, f_size_slider = make_slider(12, 48, 22, lambda v: f"{v}px")
        f_combo = NoWheelComboBox()
        f_combo.setMinimumHeight(36)
        f_combo.addItems(available_fonts())
        t_color = ColorPickerField("#2563EB")
        bg_color = ColorPickerField("#1E293B")
        
        colors = QWidget()
        colors_layout = QHBoxLayout(colors)
        colors_layout.setContentsMargins(0, 0, 0, 0)
        colors_layout.setSpacing(12)
        colors_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        t_box = QHBoxLayout()
        t_box.setSpacing(6)
        t_lbl = QLabel("글자색")
        t_lbl.setStyleSheet("font-weight: 700; color: #0F172A;")
        t_box.addWidget(t_lbl)
        t_box.addWidget(t_color)

        b_box = QHBoxLayout()
        b_box.setSpacing(6)
        b_lbl = QLabel("배경색")
        b_lbl.setStyleSheet("font-weight: 700; color: #0F172A;")
        b_box.addWidget(b_lbl)
        b_box.addWidget(bg_color)

        colors_layout.addLayout(t_box)
        colors_layout.addLayout(b_box)

        # 방향 그라데이션 온/오프 및 색상 선택기
        grad_switch = ToggleSwitch(True)
        grad_color = ColorPickerField("#E11D48")

        grad_wrapper = QWidget()
        grad_layout = QHBoxLayout(grad_wrapper)
        grad_layout.setContentsMargins(0, 0, 0, 0)
        grad_layout.setSpacing(12)
        grad_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        grad_sw_box = QHBoxLayout()
        grad_sw_box.setSpacing(6)
        grad_sw_box.addWidget(QLabel("효과 사용"))
        grad_sw_box.addWidget(grad_switch)

        grad_col_box = QHBoxLayout()
        grad_col_box.setSpacing(6)
        grad_col_box.addWidget(QLabel("그라데이션 색"))
        grad_col_box.addWidget(grad_color)

        grad_layout.addLayout(grad_sw_box)
        grad_layout.addLayout(grad_col_box)

        # 그라데이션 전용 불투명도 조절 슬라이더
        grad_op_box, grad_op_slider = make_slider(0, 100, 85, lambda v: f"{v}%")

        op_box, op_slider = make_slider(0, 100, 85, lambda v: f"{v}%")
        fade_sw = ToggleSwitch(True)

        # 🧸 아동 모드 (2026-11-05): 보기 방식 · 움직임 (아동 모드에서만 쓰임)
        kids_view = NoWheelComboBox()
        kids_view.setMinimumHeight(36)
        kids_view.addItems(KIDS_VIEWS)
        kids_motion = ToggleSwitch(True)
        c["kids_view"] = kids_view
        c["kids_motion"] = kids_motion

        c["font_size"] = f_size_slider
        c["font_family"] = f_combo
        c["text_color"] = t_color
        c["background_color"] = bg_color
        c["gradient_enabled"] = grad_switch
        c["gradient_color"] = grad_color
        c["gradient_opacity"] = grad_op_slider
        c["opacity"] = op_slider
        c["fade_enabled"] = fade_sw

        return make_card([
            make_row("글자 크기", f_size_box, expand=True),
            make_row("글꼴", f_combo),
            make_row("글자색 / 배경색 설정", colors),
            make_row("방향성 그라데이션 설정", grad_wrapper, "끄면 좌우 꺾쇠(<, >) 표기가 적용됩니다."),
            make_row("그라데이션 불투명도", grad_op_box, expand=True),
            make_row("배경 불투명도", op_box, expand=True),
            make_row("페이드 효과 (서서히 나타남/사라짐)", fade_sw),
            make_row("🧸 아동 모드 보기 방식", kids_view, "그림만: 미취학 · 그림 + 짧은 글: 기본 · 글 위주: 초등 고학년"),
            make_row("🧸 아동 모드 움직임", kids_motion, "끄면 애니메이션 줄이기 — 그림은 움직이지 않고 크기·위치로만 보여 줌"),
        ])

    def create_card_layout(self, tag):
        c = self.controls_A if tag == "A" else self.controls_B
        
        layout_ctrl = SegmentedControl(["가로", "세로"])
        layout_ctrl.setMinimumHeight(36)
        m_box, m_slider = make_slider(0, 200, 40, lambda v: f"{v}px")

        box_dir = BoxDirectionSelector()
        box_dir.directionChanged.connect(self.on_setting_changed)

        btn_reset_instant = QPushButton("순간음 드래그 위치 초기화")
        btn_reset_instant.setFixedHeight(34)
        btn_reset_instant.setStyleSheet(GRAY_BUTTON_STYLE)
        btn_reset_instant.clicked.connect(self.reset_instant_positions)

        btn_reset_continuous = QPushButton("지속음 위치 초기화")
        btn_reset_continuous.setFixedHeight(34)
        btn_reset_continuous.setStyleSheet(GRAY_BUTTON_STYLE)
        btn_reset_continuous.clicked.connect(self.reset_continuous_positions)

        btn_box = QHBoxLayout()
        btn_box.setContentsMargins(0, 0, 0, 0)
        btn_box.setSpacing(8)
        btn_box.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        btn_box.addWidget(btn_reset_instant)
        btn_box.addWidget(btn_reset_continuous)
        btn_wrapper = QWidget()
        btn_wrapper.setLayout(btn_box)

        card_pos = make_card([
            make_row("지속음 정렬 방향", layout_ctrl),
            make_row("화면 가장자리 여백", m_box, expand=True),
            make_row("드래그 위치 초기화", btn_wrapper),
        ])

        box_card = QFrame()
        box_card.setObjectName("card")
        box_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        box_card_lay = QVBoxLayout(box_card)
        box_card_lay.setContentsMargins(0, 4, 0, 4)
        box_card_lay.setSpacing(0)
        box_card_lay.addWidget(box_dir)

        c["continuous_layout"] = layout_ctrl
        c["margin"] = m_slider
        c["box_dir_selector"] = box_dir

        wrapper = QWidget()
        wrapper.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        w_lay = QVBoxLayout(wrapper)
        w_lay.setContentsMargins(0, 0, 0, 0)
        w_lay.setSpacing(14)
        w_lay.addWidget(card_pos)
        w_lay.addWidget(box_card)
        return wrapper

    def create_card_sound_labels(self):
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        header_box = QHBoxLayout()
        lbl_title = QLabel("소리 라벨 필터")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #0F172A;")
        header_box.addWidget(lbl_title)
        header_box.addStretch(1)

        btn_all_on = QPushButton("모두 켜기")
        btn_all_on.setFixedHeight(34)
        btn_all_on.setStyleSheet(GRAY_BUTTON_STYLE)
        btn_all_on.clicked.connect(self.turn_on_all_sounds)
        header_box.addWidget(btn_all_on)
        lay.addLayout(header_box)

        note = QLabel("")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {GRAY_TEXT}; font-size: 12px;")
        lay.addWidget(note)

        search_card = QFrame()
        search_card.setObjectName("card")
        search_lay = QHBoxLayout(search_card)
        search_lay.setContentsMargins(16, 10, 16, 10)
        search_lay.setSpacing(10)

        lbl_search_icon = QLabel("🔍")
        lbl_search_icon.setStyleSheet("font-size: 14px; background: transparent;")

        search = QLineEdit()
        search.setPlaceholderText("소리 라벨 검색 (예: 발소리, 총성, gunshot...)")
        search.setClearButtonEnabled(True)
        search.setMinimumHeight(36)

        search_lay.addWidget(lbl_search_icon)
        search_lay.addWidget(search, 1)
        lay.addWidget(search_card)

        host = QWidget()
        host_lay = QVBoxLayout(host)
        host_lay.setContentsMargins(0, 0, 0, 0)
        host_lay.setSpacing(14)
        lay.addWidget(host)

        view = {"host": host_lay, "search": search, "rows": [], "note": note}
        search.textChanged.connect(lambda q, v=view: self.filter_sound_labels(v, q))
        self.sound_views.append(view)
        if self.sound_filter_mode is not None:
            self._render_sound_view(view, self.sound_filter_mode)
            self._sync_sound_switches()
        return container

    @staticmethod
    def _partial_label():
        lbl = QLabel("")
        lbl.setStyleSheet("color: #B45309; font-size: 11px; font-weight: 700; background: transparent; border: none;")
        lbl.hide()
        return lbl

    def _make_node_toggle(self, leaves):
        """대분류·중분류 토글. leaves = [[키...], ...] (아래 소리마다 키 묶음)"""
        toggle = ToggleSwitch(True)
        if not leaves:                               # 소리가 없는 칸 (공통 화면): 토글 없이 표시만
            toggle.setEnabled(False)
            toggle.setVisible(False)                 # 레이아웃에 붙은 뒤에도 숨김 (부모 없이 show 하면 따로 창이 뜸)
            sub = QLabel("소리 없음")
            sub.setStyleSheet(f"color: {GRAY_TEXT}; font-size: 11px; font-weight: 700; background: transparent; border: none;")
            return toggle, sub
        sub = self._partial_label()
        keys = [k for ks in leaves for k in ks]
        toggle.toggled.connect(lambda on, ks=keys: self._on_sound_toggled(ks, on))
        self.sound_node_switches.append((toggle, leaves, sub))
        return toggle, sub

    def _render_sound_view(self, view, base_mode):
        """필터 카드 하나에 base_mode 트리를 그림 (예전 내용은 지움)"""
        host = view["host"]
        while host.count():
            w = host.takeAt(0).widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        view["rows"] = []

        is_common = base_mode == COMMON
        view["note"].setText(
            "모든 모드의 소리를 분류표 전체에 보여줘요. 여기서 켜고 끈 소리만 [설정 저장] 때 그 소리가 있는 모든 모드·프리셋에 적용돼요."
            if is_common else
            "지금 모드에서 뜰 수 있는 소리만 보여요. 대분류·중분류를 끄면 그 아래 소리가 모두 꺼져요. "
            "꺼 둔 소리는 계산은 그대로 하고, 표시 칸에 뽑혔을 때 화면에서만 빠져요 (빈자리를 다른 소리로 채우지 않아요).")
        for top in (build_full_tree() if is_common else build_tree(base_mode)):
            cat_title = f"{top['code']}. {top['name']}"
            cat_card = QFrame()
            cat_card.setObjectName("card")
            cat_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            c_lay = QVBoxLayout(cat_card)
            c_lay.setContentsMargins(16, 12, 16, 14)
            c_lay.setSpacing(10)

            cat_header = QWidget()
            cat_header.setFixedHeight(40)
            ch_lay = QHBoxLayout(cat_header)
            ch_lay.setContentsMargins(0, 0, 0, 0)

            btn_cat = QPushButton(f"  {cat_title}")
            btn_cat.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_cat.setFixedHeight(40)
            btn_cat.setStyleSheet(f"""
                QPushButton {{
                    background-color: {FIELD_BG};
                    color: #0F172A;
                    font-size: 14px;
                    font-weight: 800;
                    text-align: left;
                    border: none;
                    border-radius: 8px;
                    padding-left: 10px;
                }}
                QPushButton:hover {{ background-color: #E2E8F0; }}
            """)
            top_leaves = [lf["keys"] for mid in top["children"] for lf in mid["leaves"]]
            cat_sw, cat_sub = self._make_node_toggle(top_leaves)
            ch_lay.addWidget(btn_cat, 1)
            ch_lay.addWidget(cat_sub)
            ch_lay.addWidget(cat_sw)

            sub_group_container = QWidget()
            sgc_layout = QVBoxLayout(sub_group_container)
            sgc_layout.setContentsMargins(8, 8, 8, 8)
            sgc_layout.setSpacing(12)

            for mid in top["children"]:
                sub_title = f"{mid['code']}. {mid['name']}"
                sub_widget = QWidget()
                sw_lay = QVBoxLayout(sub_widget)
                sw_lay.setContentsMargins(0, 0, 0, 0)
                sw_lay.setSpacing(4)

                sub_header = QFrame()
                sub_header.setFixedHeight(38)
                sub_header.setStyleSheet("""
                    QFrame {
                        background-color: #F1F5F9;
                        border-radius: 8px;
                        border-left: 3.5px solid #2563EB;
                    }
                """)
                sh_lay = QHBoxLayout(sub_header)
                sh_lay.setContentsMargins(10, 4, 10, 4)

                btn_sub = QPushButton(f"▸ {sub_title}")
                btn_sub.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_sub.setFixedHeight(28)
                btn_sub.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        color: {PRIMARY_BLUE};
                        font-size: 13px;
                        font-weight: 800;
                        text-align: left;
                        border: none;
                    }}
                    QPushButton:hover {{ color: #1D4ED8; }}
                """)
                sub_sw, sub_sub = self._make_node_toggle([lf["keys"] for lf in mid["leaves"]])
                sh_lay.addWidget(btn_sub, 1)
                sh_lay.addWidget(sub_sub)
                sh_lay.addWidget(sub_sw)

                item_container = QWidget()
                ic_lay = QVBoxLayout(item_container)
                ic_lay.setContentsMargins(16, 4, 8, 6)
                ic_lay.setSpacing(6)

                if not mid["leaves"]:
                    empty = QLabel("이 분류에 해당하는 소리가 아직 없어요")
                    empty.setStyleSheet(f"color: {GRAY_TEXT}; font-size: 12px; padding: 6px 4px;")
                    ic_lay.addWidget(empty)

                for lf in mid["leaves"]:
                    keys = list(lf["keys"])
                    item_row = QFrame()
                    item_row.setFixedHeight(44)
                    item_row.setStyleSheet("""
                        QFrame {
                            background-color: #FFFFFF;
                            border: 1px solid #E2E8F0;
                            border-radius: 8px;
                        }
                    """)
                    ir_lay = QHBoxLayout(item_row)
                    ir_lay.setContentsMargins(12, 4, 12, 4)

                    name_lbl = QLabel(lf["name"])
                    name_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #0F172A; border: none; background: transparent;")
                    extra = f"   ({' · '.join(lf['modes'])})" if lf.get("modes") else ""
                    key_lbl = QLabel(f"·  {' + '.join(keys)}{extra}")
                    key_lbl.setStyleSheet(f"color: {GRAY_TEXT}; font-size: 12px; border: none; background: transparent;")

                    sw = ToggleSwitch(True)
                    sw.toggled.connect(lambda on, ks=keys: self._on_sound_toggled(ks, on))
                    self.sound_leaf_switches.append((sw, keys))

                    ir_lay.addWidget(name_lbl)
                    ir_lay.addWidget(key_lbl)
                    ir_lay.addStretch(1)
                    ir_lay.addWidget(sw)
                    ic_lay.addWidget(item_row)

                    view["rows"].append({
                        "widget": item_row,
                        "sub_container": item_container,
                        "sub_widget": sub_widget,
                        "sub_button": btn_sub,
                        "sub_title": sub_title,
                        "cat_container": sub_group_container,
                        "cat_card": cat_card,
                        "text": f"{lf['name']} {' '.join(keys)} {sub_title} {cat_title}".lower(),
                    })

                item_container.setVisible(False)
                btn_sub.clicked.connect(lambda _, w=item_container, b=btn_sub, st=sub_title: self.toggle_accordion(w, b, st))

                sw_lay.addWidget(sub_header)
                sw_lay.addWidget(item_container)
                sgc_layout.addWidget(sub_widget)

                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background-color: {BORDER_COLOR};")
                sgc_layout.addWidget(sep)

            sub_group_container.setVisible(False)
            btn_cat.clicked.connect(lambda _, w=sub_group_container: w.setVisible(not w.isVisible()))

            c_lay.addWidget(cat_header)
            c_lay.addWidget(sub_group_container)
            host.addWidget(cat_card)

        if view["search"].text().strip():
            self.filter_sound_labels(view, view["search"].text())

    def rebuild_sound_filter(self, base_mode, off):
        """모드가 바뀌었으면 트리를 다시 그리고, 꺼 둔 키(off)대로 토글을 맞춤"""
        self.sound_off = set(off or [])
        if base_mode != self.sound_filter_mode:
            self.sound_leaf_switches, self.sound_node_switches = [], []
            for view in self.sound_views:
                self._render_sound_view(view, base_mode)
            self.sound_filter_mode = base_mode
        self._sync_sound_switches()

    def _on_sound_toggled(self, keys, on):
        if self._sound_syncing:
            return
        if on:
            self.sound_off.difference_update(keys)
        else:
            self.sound_off.update(keys)
        self._sync_sound_switches()
        self.on_setting_changed()

    def _sync_sound_switches(self):
        """꺼 둔 키 → 토글 상태. 대분류·중분류는 아래 소리가 하나라도 켜져 있으면 켜짐 + '일부 꺼짐 (n/m)'"""
        self._sound_syncing = True
        try:
            leaf_on = lambda ks: not any(k in self.sound_off for k in ks)   # noqa: E731
            for toggle, keys in self.sound_leaf_switches:
                toggle.set_checked_now(leaf_on(keys))
            for toggle, leaves, sub in self.sound_node_switches:
                n_on = sum(leaf_on(ks) for ks in leaves)
                toggle.set_checked_now(n_on > 0)
                partial = 0 < n_on < len(leaves)
                sub.setText(f"일부 꺼짐 ({n_on}/{len(leaves)})" if partial else "")
                sub.setVisible(partial)
        finally:
            self._sound_syncing = False

    def filter_sound_labels(self, view, query):
        q = query.strip().lower()
        rows = view["rows"]
        if not q:
            for item in rows:
                item["widget"].setVisible(True)
                item["sub_widget"].setVisible(True)
                item["cat_card"].setVisible(True)
            return

        hit_sub = {id(r["sub_widget"]) for r in rows if q in r["text"]}
        hit_cat = {id(r["cat_card"]) for r in rows if q in r["text"]}
        for item in rows:
            matched = q in item["text"]
            item["widget"].setVisible(matched)
            item["sub_widget"].setVisible(id(item["sub_widget"]) in hit_sub)
            item["cat_card"].setVisible(id(item["cat_card"]) in hit_cat)
            if matched:                                   # 찾은 소리는 펼쳐서 보여 줌
                item["sub_container"].setVisible(True)
                item["sub_button"].setText(f"▾ {item['sub_title']}")
                item["cat_container"].setVisible(True)

    def toggle_accordion(self, widget, btn, title):
        is_vis = widget.isVisible()
        widget.setVisible(not is_vis)
        btn.setText(f"{'▾' if not is_vis else '▸'} {title}")

    def turn_on_all_sounds(self):
        self.sound_off.clear()
        self._sync_sound_switches()
        self.on_setting_changed()

    def build_page_common_all(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 18, 24)
        lay.setSpacing(18)
        lay.addWidget(make_section("1. 사운드 장치 설정"))
        lay.addWidget(self.create_card_audio("A"))
        lay.addWidget(make_section("2. 자막 칸·표시 시간"))
        lay.addWidget(self.create_card_slots("A"))
        lay.addWidget(make_section("3. 디자인·폰트"))
        lay.addWidget(self.create_card_design("A"))
        lay.addWidget(make_section("4. 레이아웃·위치"))
        lay.addWidget(self.create_card_layout("A"))
        lay.addWidget(make_section("5. 소리 필터"))
        lay.addWidget(self.create_card_sound_labels())
        lay.addStretch(1)
        scroll.setWidget(w)
        return scroll

    def build_page_slots(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 18, 24)
        lay.setSpacing(18)
        lay.addWidget(make_section("자막 칸·표시 시간"))
        lay.addWidget(self.create_card_slots("B"))
        lay.addStretch(1)
        scroll.setWidget(w)
        return scroll

    def build_page_design(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 18, 24)
        lay.setSpacing(18)
        lay.addWidget(make_section("디자인 · 폰트"))
        lay.addWidget(self.create_card_design("B"))
        lay.addStretch(1)
        scroll.setWidget(w)
        return scroll

    def build_page_layout(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 18, 24)
        lay.setSpacing(18)
        lay.addWidget(make_section("레이아웃 · 위치"))
        lay.addWidget(self.create_card_layout("B"))
        lay.addStretch(1)
        scroll.setWidget(w)
        return scroll

    def build_page_sound_labels(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 18, 24)
        lay.setSpacing(18)
        lay.addWidget(self.create_card_sound_labels())
        lay.addStretch(1)
        scroll.setWidget(w)
        return scroll

    def _connect_sync_signals(self):
        keys = ["instant_slots", "continuous_slots", "font_family", "kids_view"]
        for k in keys:
            if k in self.controls_A and k in self.controls_B:
                self.controls_A[k].currentTextChanged.connect(self.controls_B[k].setCurrentText)
                self.controls_B[k].currentTextChanged.connect(self.controls_A[k].setCurrentText)

        toggles = ["instant_enabled", "continuous_enabled", "onoma_enabled", "continuous_note_enabled",
                   "fade_enabled", "gradient_enabled",
                   "kids_motion"]
        for k in toggles:
            if k in self.controls_A and k in self.controls_B:
                self.controls_A[k].toggled.connect(self.controls_B[k].setChecked)
                self.controls_B[k].toggled.connect(self.controls_A[k].setChecked)

        sliders = ["continuous_duration", "font_size", "opacity", "gradient_opacity", "margin"]
        for k in sliders:
            if k in self.controls_A and k in self.controls_B:
                self.controls_A[k].valueChanged.connect(self.controls_B[k].setValue)
                self.controls_B[k].valueChanged.connect(self.controls_A[k].setValue)

        if "instant_duration" in self.controls_A and "instant_duration" in self.controls_B:
            self.controls_A["instant_duration"].textChanged.connect(self.controls_B["instant_duration"].setText)
            self.controls_B["instant_duration"].textChanged.connect(self.controls_A["instant_duration"].setText)

        for picker in ("text_color", "background_color", "gradient_color"):
            if picker in self.controls_A and picker in self.controls_B:
                self.controls_A[picker].colorChanged.connect(self.controls_B[picker].setColor)
                self.controls_B[picker].colorChanged.connect(self.controls_A[picker].setColor)

        for ctrl in (self.controls_A, self.controls_B):
            for k in ("instant_slots", "continuous_slots", "font_family", "kids_view"):
                ctrl[k].currentTextChanged.connect(self.on_setting_changed)
            for k in toggles:
                ctrl[k].toggled.connect(self.on_setting_changed)
            for k in sliders:
                ctrl[k].valueChanged.connect(self.on_setting_changed)
            ctrl["instant_duration"].textChanged.connect(self.on_setting_changed)
            ctrl["text_color"].colorChanged.connect(self.on_setting_changed)
            ctrl["background_color"].colorChanged.connect(self.on_setting_changed)
            ctrl["gradient_color"].colorChanged.connect(self.on_setting_changed)
            ctrl["continuous_layout"].group.buttonClicked.connect(self.on_setting_changed)

    def refresh_mode_sidebar(self):
        while self.sidebar_layout.count():
            child = self.sidebar_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        active_target = self.state["active_target"]

        def add_header(title_text, has_add_btn=False):
            box = QWidget()
            box.setFixedHeight(34)
            layout = QHBoxLayout(box)
            layout.setContentsMargins(8, 10, 6, 4)
            
            lbl = QLabel(title_text)
            lbl.setStyleSheet(f"""
                font-size: 13px;
                font-weight: 800;
                color: {PRIMARY_BLUE};
                letter-spacing: 0.5px;
            """)
            layout.addWidget(lbl)
            layout.addStretch(1)

            if has_add_btn:
                btn_add = QPushButton("＋")
                btn_add.setToolTip("새 프리셋 추가")
                btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_add.setFixedSize(26, 24)
                btn_add.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {PRIMARY_BLUE};
                        border: 1.5px solid {PRIMARY_BLUE};
                        border-radius: 6px;
                        font-weight: 800;
                        font-size: 13px;
                    }}
                    QPushButton:hover {{ background-color: #EFF6FF; }}
                """)
                btn_add.clicked.connect(self.add_preset)
                layout.addWidget(btn_add)

            self.sidebar_layout.addWidget(box)

        def add_common_button():
            is_active = (active_target == "common")
            btn = QPushButton("전체 설정 및 사운드 장치")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(38)
            
            bg = PRIMARY_BLUE if is_active else "transparent"
            color = "#FFFFFF" if is_active else "#1E293B"
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: {color} !important;
                    font-size: 13px;
                    font-weight: 700;
                    text-align: left;
                    border: none;
                    border-radius: 8px;
                    padding-left: 10px;
                }}
                QPushButton:hover {{ background-color: {'#1D4ED8' if is_active else FIELD_BG}; }}
            """)
            btn.clicked.connect(lambda: self.switch_view("common", "common_all"))
            self.sidebar_layout.addWidget(btn)

        def add_mode_button(display_name, target_key, is_preset=False):
            is_active = (target_key == active_target)
            is_expanded = self.expanded_modes.get(target_key, False)

            mode_box = QWidget()
            mode_box.setFixedHeight(38)
            box_layout = QHBoxLayout(mode_box)
            box_layout.setContentsMargins(0, 0, 0, 0)
            box_layout.setSpacing(4)

            btn_main = QPushButton(f"  {display_name}")
            btn_main.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_main.setFixedHeight(38)

            bg = "#EFF6FF" if is_active else "transparent"
            text_color = PRIMARY_BLUE if is_active else "#1E293B"

            btn_main.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: {text_color} !important;
                    font-size: 13px;
                    font-weight: {'800' if is_active else '700'};
                    text-align: left;
                    border: none;
                    border-radius: 8px;
                    padding-left: 10px;
                }}
                QPushButton:hover {{ background-color: #E2E8F0; }}
            """)
            btn_main.clicked.connect(lambda _, k=target_key: self.on_mode_button_clicked(k))
            box_layout.addWidget(btn_main, 1)

            if is_preset:
                btn_del = QPushButton("삭제")
                btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_del.setFixedSize(38, 26)
                btn_del.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: #64748B;
                        border: 1px solid {BORDER_COLOR};
                        border-radius: 6px;
                        font-size: 11px;
                        font-weight: 700;
                    }}
                    QPushButton:hover {{ background-color: #FEE2E2; color: {RED_COLOR}; border: 1px solid #FCA5A5; }}
                """)
                btn_del.clicked.connect(lambda _, k=target_key: self.delete_specific_preset(k))
                box_layout.addWidget(btn_del)

            self.sidebar_layout.addWidget(mode_box)

            if is_expanded and is_active:
                sub_menus = [
                    ("자막 칸·표시 시간", "slots"),
                    ("디자인·폰트", "design"),
                    ("레이아웃·위치", "layout"),
                    ("소리 필터", "sound_label"),
                ]
                for s_label, s_view in sub_menus:
                    is_sub_active = (self.current_sub_view == s_view)
                    sub_btn = QPushButton(f"      {s_label}")
                    sub_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    sub_btn.setFixedHeight(34)
                    
                    sub_bg = PRIMARY_BLUE if is_sub_active else "transparent"
                    sub_color = "#FFFFFF" if is_sub_active else "#64748B"
                    
                    sub_btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {sub_bg};
                            color: {sub_color} !important;
                            font-size: 12px;
                            font-weight: {'800' if is_sub_active else '600'};
                            text-align: left;
                            border: none;
                            border-radius: 6px;
                            padding-left: 8px;
                        }}
                        QPushButton:hover {{ background-color: {'#1D4ED8' if is_sub_active else '#F1F5F9'}; }}
                    """)
                    sub_btn.clicked.connect(lambda _, sv=s_view: self.switch_view(target_key, sv))
                    self.sidebar_layout.addWidget(sub_btn)

        add_header("공통")
        add_common_button()

        add_header("기본 모드")
        for name in DEFAULT_MODES:
            add_mode_button(name, name, is_preset=False)

        add_header("프리셋", has_add_btn=True)
        for name, cfg in self.state["presets"].items():
            base_m = cfg.get("base_mode", "FPS")
            display_str = f"{name} ({base_m})"
            add_mode_button(display_str, name, is_preset=True)

        self.sidebar_layout.addStretch(1)

    def switch_view(self, target_key, sub_view_type):
        if target_key != "common":
            self.activate_target(target_key)
        else:
            self.open_common_view()

        self.current_sub_view = sub_view_type
        self.refresh_mode_sidebar()

        if sub_view_type == "common_all":
            self.main_stack.setCurrentIndex(0)
        elif sub_view_type == "slots":
            self.main_stack.setCurrentIndex(1)
        elif sub_view_type == "design":
            self.main_stack.setCurrentIndex(2)
        elif sub_view_type == "layout":
            self.main_stack.setCurrentIndex(3)
        elif sub_view_type == "sound_label":
            self.main_stack.setCurrentIndex(4)

    def on_mode_button_clicked(self, mode_key):
        is_same = (mode_key == self.state["active_target"])
        self.expanded_modes[mode_key] = not self.expanded_modes.get(mode_key, False) if is_same else True
        self.switch_view(mode_key, "slots")

    def rebuild_mode_tiles(self):
        for grid in (self.base_modes_grid, self.preset_modes_grid):
            while grid.count():
                item = grid.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()

        self.mode_tile_buttons = {}
        cols = 3
        for idx, target in enumerate(DEFAULT_MODES):
            tile_btn = self._make_mode_tile(target)
            tile_btn.clicked.connect(lambda _, name=target: self.select_mode_tile(name))
            self.base_modes_grid.addWidget(tile_btn, idx // cols, idx % cols)
            self.mode_tile_buttons[target] = tile_btn

        preset_names = list(self.state["presets"])
        self.preset_empty_label.setVisible(not preset_names)
        self.preset_modes_container.setVisible(bool(preset_names))
        for idx, target in enumerate(preset_names):
            tile_btn = self._make_mode_tile(target, self.state["presets"][target].get("base_mode", "FPS"))
            tile_btn.clicked.connect(lambda _, name=target: self.select_mode_tile(name))
            self.preset_modes_grid.addWidget(tile_btn, idx // cols, idx % cols)
            self.mode_tile_buttons[target] = tile_btn

        self.update_mode_tiles_ui()

    def _make_mode_tile(self, target, base_mode=None):
        tile_btn = QPushButton()
        tile_btn.setCheckable(True)
        tile_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        tile_btn.setMinimumHeight(62)

        layout = QVBoxLayout(tile_btn)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(1)

        title = QLabel(target)
        title.setObjectName("tileHeader")
        layout.addWidget(title)

        if base_mode is not None:
            subtitle = QLabel(f"{base_mode} 기반 프리셋")
            subtitle.setObjectName("tileSub")
            layout.addWidget(subtitle)
        layout.addStretch(1)
        return tile_btn

    def select_mode_tile(self, target_name):
        self.activate_target(target_name)

    def update_mode_tiles_ui(self):
        active = self.state["active_target"]
        for target, btn in self.mode_tile_buttons.items():
            t_header = btn.findChild(QLabel, "tileHeader")
            t_sub = btn.findChild(QLabel, "tileSub")

            if active == target:
                btn.setChecked(True)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {PRIMARY_BLUE};
                        border: 2px solid {PRIMARY_BLUE};
                        border-radius: 10px;
                        text-align: left;
                    }}
                """)
                if t_header: t_header.setStyleSheet("font-size: 14px; font-weight: 800; color: #FFFFFF; background: transparent;")
                if t_sub: t_sub.setStyleSheet("font-size: 11px; font-weight: 600; color: #DBEAFE; background: transparent;")
            else:
                btn.setChecked(False)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {CARD_BG};
                        border: 1px solid {BORDER_COLOR};
                        border-radius: 10px;
                        text-align: left;
                    }}
                    QPushButton:hover {{
                        background-color: {FIELD_BG};
                        border: 1px solid #94A3B8;
                    }}
                """)
                if t_header: t_header.setStyleSheet("font-size: 14px; font-weight: 800; color: #0F172A; background: transparent;")
                if t_sub: t_sub.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {GRAY_TEXT}; background: transparent;")

    def _save_state(self):
        """'공통' 화면을 보는 중이면 실제 쓰는 모드를 active_target 으로 저장 (다음 실행 때 그 모드로 시작)"""
        if self.state["active_target"] == "common":
            snap = dict(self.state)
            snap["active_target"] = self._real_target
            save_state(snap, self.settings_path)
        else:
            save_state(self.state, self.settings_path)

    def _all_configs(self):
        return list(self.state["modes"].values()) + list(self.state["presets"].values())

    def _common_off(self):
        """'공통' 화면의 꺼짐 표시: 그 소리가 있는 모든 모드·프리셋에서 꺼져 있으면 꺼짐"""
        off = set()
        cfgs = self._all_configs()
        for top in build_full_tree():
            for mid in top["children"]:
                for lf in mid["leaves"]:
                    for k in lf["keys"]:
                        having = [c for c in cfgs if k in mode_keys(c.get("base_mode", "FPS"))]
                        if having and all(k in c.get("sounds_off", ()) for c in having):
                            off.add(k)
        return sorted(off)

    def open_common_view(self):
        """'공통' 화면: 지금 쓰는 모드 값을 보여 주기만 함. 바꾼 것만 [설정 저장] 때 모든 모드·프리셋에 적용"""
        active = self.state["active_target"]
        if active != "common":
            if self._is_modified:
                self.commit_settings()
            self._real_target = active
        self.state["active_target"] = "common"
        cfg = dict(self.get_active_config())
        cfg["sounds_off"] = self._common_off()
        self.apply_settings_dict(cfg)
        self.overlay.apply_settings(cfg)
        self._common_baseline = self.collect_custom_settings()
        self.mark_modified(False)

    def _commit_common(self, cfg):
        """'공통'에서 바꾼 값만 모든 모드·프리셋에 적용"""
        base = self._common_baseline or {}
        skip = ("base_mode", "sounds_off", "capture_target")
        changed = {k: deepcopy(v) for k, v in cfg.items() if k not in skip and base.get(k) != v}
        off_add = set(cfg.get("sounds_off", ())) - set(base.get("sounds_off", ()))
        off_del = set(base.get("sounds_off", ())) - set(cfg.get("sounds_off", ()))
        for group in ("modes", "presets"):
            for name, c in self.state[group].items():
                new = dict(c)
                new.update(deepcopy(changed))
                new["sounds_off"] = sorted((set(c.get("sounds_off", ())) | off_add) - off_del)
                self.state[group][name] = normalize(new)
        self._common_baseline = cfg
        real = self.get_active_config()              # 백엔드는 실제 쓰는 모드 그대로 (바뀐 값만 반영)
        self.overlay.apply_settings(real)
        self.bridge.settings_changed.emit(real)
        self._save_state()
        self.mark_modified(False)

    def get_active_config(self):
        active = self.state["active_target"]
        if active == "common":
            active = self._real_target
        if active in self.state["modes"]:
            return self.state["modes"][active]
        return self.state["presets"].get(active, default_settings("FPS"))

    def set_active_config(self, cfg):
        active = self.state["active_target"]
        if active in self.state["modes"]:
            self.state["modes"][active] = cfg
        elif active in self.state["presets"]:
            self.state["presets"][active] = cfg

    def apply_active_config_to_ui(self):
        cfg = self.get_active_config()
        self.apply_settings_dict(cfg)

        self.rebuild_mode_tiles()
        self.refresh_mode_sidebar()
        self.overlay.apply_settings(cfg)
        self.mark_modified(False)

    def update_banner_ui(self):
        active = self.state["active_target"]
        if active == "common":
            display_str = "공통 설정"
        elif active in DEFAULT_MODES:
            display_str = f"{active}(기본)"
        else:
            base_m = self.state["presets"].get(active, {}).get("base_mode", "FPS")
            display_str = f"{active} ({base_m})"

        self.lbl_active_badge.setText(f"적용 모드: {display_str}")

        if self._is_modified:
            self.lbl_mod_notice.setText("변경된 설정이 있습니다. [설정 저장]을 누르세요.")
            self.btn_apply_settings.setEnabled(True)
            self.btn_reload_settings.setEnabled(True)
        else:
            self.lbl_mod_notice.setText("최신 설정이 백엔드 및 오버레이에 반영되었습니다.")
            self.btn_apply_settings.setEnabled(False)
            self.btn_reload_settings.setEnabled(False)

    def mark_modified(self, modified=True):
        self._is_modified = modified
        self.update_banner_ui()

    def on_tab_changed(self, index):
        is_preview_on = self.preview_switch_corner.isChecked()
        in_settings_tab = (index == 1)

        if not in_settings_tab and not self._is_quick_editing:
            self.overlay.set_interactive(False)
        elif in_settings_tab and is_preview_on:
            self.overlay.set_interactive(True)

        self.update_overlay_visibility()

    def on_instant_dragged(self):
        self.on_setting_changed()

    def reset_instant_positions(self):
        self.overlay.settings["instant_custom_pos"] = {str(i): None for i in range(5)}
        self.on_setting_changed()

    def reset_continuous_positions(self):
        self.overlay.settings["continuous_custom_pos"] = None
        self.on_setting_changed()

    def add_preset(self):
        dlg = PresetCreateDialog(list(self.state["presets"].keys()), self)
        if dlg.exec() == PresetCreateDialog.DialogCode.Accepted and dlg.created_name:
            new_name = dlg.created_name
            base_m = dlg.selected_base_mode

            new_cfg = default_settings(base_m)
            self.state["presets"][new_name] = new_cfg
            self.state["active_target"] = new_name
            self.expanded_modes[new_name] = True

            self.apply_active_config_to_ui()
            self.commit_settings()

    def delete_specific_preset(self, preset_name):
        if preset_name in DEFAULT_MODES:
            QMessageBox.warning(self, "경고", "기본 모드는 삭제할 수 없습니다.")
            return

        reply = QMessageBox.question(
            self,
            "프리셋 삭제 확인",
            f"정말로 '{preset_name}' 프리셋을 삭제하시겠습니까?\n삭제된 데이터는 복구할 수 없습니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if preset_name in self.state["presets"]:
                del self.state["presets"][preset_name]
            if preset_name in self.expanded_modes:
                del self.expanded_modes[preset_name]

            if self.state["active_target"] == preset_name:
                self.state["active_target"] = "FPS"

            self.apply_active_config_to_ui()
            self.commit_settings()

    def collect_custom_settings(self):
        source_ctrl = self.controls_A if self.current_sub_view == "common_all" else self.controls_B
        
        try:
            dur_val = float(source_ctrl["instant_duration"].text())
        except (ValueError, KeyError):
            dur_val = 3.0

        c_slots_str = source_ctrl.get("continuous_slots").currentText() if "continuous_slots" in source_ctrl else "2개"
        c_slots = 0 if c_slots_str == "없음" else int(c_slots_str.replace("개", ""))

        dir_map = source_ctrl["box_dir_selector"].get_directions_dict() if "box_dir_selector" in source_ctrl else {}

        curr_cfg = self.get_active_config()
        base_m = curr_cfg.get("base_mode", self.state["active_target"] if self.state["active_target"] in DEFAULT_MODES else "FPS")

        capture_val = self._capture_value()

        return {
            "base_mode": base_m,
            "capture_target": capture_val,
            "instant_slots": int(source_ctrl["instant_slots"].currentText().replace("개", "")) if "instant_slots" in source_ctrl else 3,
            "continuous_slots": c_slots,
            "instant_enabled": source_ctrl["instant_enabled"].isChecked() if "instant_enabled" in source_ctrl else True,
            "continuous_enabled": source_ctrl["continuous_enabled"].isChecked() if ("continuous_enabled" in source_ctrl and c_slots > 0) else False,
            "arrows_enabled": not source_ctrl["gradient_enabled"].isChecked() if "gradient_enabled" in source_ctrl else False,
            "onoma_enabled": source_ctrl["onoma_enabled"].isChecked() if "onoma_enabled" in source_ctrl else True,
            "continuous_note_enabled": source_ctrl["continuous_note_enabled"].isChecked() if "continuous_note_enabled" in source_ctrl else True,
            "instant_duration": max(0.1, min(10.0, dur_val)),
            "continuous_duration": source_ctrl["continuous_duration"].value() if "continuous_duration" in source_ctrl else 0,
            "font_size": source_ctrl["font_size"].value() if "font_size" in source_ctrl else 22,
            "font_family": source_ctrl["font_family"].currentText() if "font_family" in source_ctrl else "Malgun Gothic",
            "text_color": source_ctrl["text_color"].color() if "text_color" in source_ctrl else "#FFFFFF",
            "background_color": source_ctrl["background_color"].color() if "background_color" in source_ctrl else "#0F111A",
            "gradient_enabled": source_ctrl["gradient_enabled"].isChecked() if "gradient_enabled" in source_ctrl else True,
            "gradient_color": source_ctrl["gradient_color"].color() if "gradient_color" in source_ctrl else "#E11D48",
            "gradient_opacity": source_ctrl["gradient_opacity"].value() if "gradient_opacity" in source_ctrl else 85,
            "opacity": source_ctrl["opacity"].value() if "opacity" in source_ctrl else 85,
            "fade_enabled": source_ctrl["fade_enabled"].isChecked() if "fade_enabled" in source_ctrl else True,
            "continuous_position": self.overlay.settings.get("continuous_position", "상단 가운데"),
            "continuous_layout": source_ctrl["continuous_layout"].currentText() if "continuous_layout" in source_ctrl else "가로",
            "continuous_height": self.overlay.settings.get("continuous_height", 3),
            "continuous_custom_pos": self.overlay.settings.get("continuous_custom_pos"),
            "instant_height": self.overlay.settings.get("instant_height", 8),
            "instant_custom_pos": self.overlay.settings.get("instant_custom_pos", {str(i): None for i in range(5)}),
            "instant_box_directions": dir_map,
            "instant_box_font_sizes": self.overlay.settings.get("instant_box_font_sizes", {str(i): None for i in range(5)}),
            "margin": source_ctrl["margin"].value() if "margin" in source_ctrl else 40,
            "sounds_off": sorted(self.sound_off),
            "kids_view": source_ctrl["kids_view"].currentText() if "kids_view" in source_ctrl else "그림 + 짧은 글",
            "kids_motion": source_ctrl["kids_motion"].isChecked() if "kids_motion" in source_ctrl else True,
        }

    def apply_settings_dict(self, raw):
        s = normalize(raw)
        self._loading = True
        try:
            target_audio = self.controls_A.get("audio", self.controls_A.get("audio_B"))
            if target_audio is not None:      # 캡처 장치는 모드마다가 아니라 앱 전체에 하나
                target_audio.blockSignals(True)
                self._select_capture(target_audio, self.state.get("capture_target", DEFAULT_CAPTURE))
                target_audio.blockSignals(False)

            for c in (self.controls_A, self.controls_B):
                if not c:
                    continue
                c["instant_slots"].setCurrentText(f"{s['instant_slots']}개")
                c_slots_val = s["continuous_slots"]
                c["continuous_slots"].setCurrentText("없음" if c_slots_val == 0 else f"{c_slots_val}개")

                c["instant_enabled"].setChecked(s["instant_enabled"])
                c["continuous_enabled"].setChecked(s["continuous_enabled"])
                c["onoma_enabled"].setChecked(s["onoma_enabled"])
                c["continuous_note_enabled"].setChecked(s["continuous_note_enabled"])
                c["instant_duration"].setText(str(s["instant_duration"]))
                c["continuous_duration"].setValue(s["continuous_duration"])
                c["font_size"].setValue(s["font_size"])
                if c["font_family"].findText(s["font_family"]) < 0:
                    c["font_family"].addItem(s["font_family"])
                c["font_family"].setCurrentText(s["font_family"])
                c["text_color"].setColor(s["text_color"])
                c["background_color"].setColor(s["background_color"])
                if "gradient_enabled" in c:
                    c["gradient_enabled"].setChecked(s.get("gradient_enabled", True))
                if "gradient_color" in c:
                    c["gradient_color"].setColor(s.get("gradient_color", "#E11D48"))
                if "gradient_opacity" in c:
                    c["gradient_opacity"].setValue(s.get("gradient_opacity", 85))
                c["opacity"].setValue(s["opacity"])
                c["fade_enabled"].setChecked(s["fade_enabled"])
                if "kids_view" in c:
                    c["kids_view"].setCurrentText(s.get("kids_view", "그림 + 짧은 글"))
                if "kids_motion" in c:
                    c["kids_motion"].setChecked(s.get("kids_motion", True))
                c["continuous_layout"].setCurrentText(s.get("continuous_layout", "가로"))
                c["margin"].setValue(s["margin"])
                c["box_dir_selector"].set_directions_dict(s.get("instant_box_directions", {}))
            if self.state["active_target"] == "common":     # 공통: 분류표 전체 (normalize 가 지운 키를 원래 값으로)
                self.rebuild_sound_filter(COMMON, raw.get("sounds_off", []))
            else:
                self.rebuild_sound_filter(s["base_mode"], s["sounds_off"])
        finally:
            self._loading = False

    def on_setting_changed(self, *_):
        if self._loading:
            return
        settings = self.collect_custom_settings()
        if settings.get("margin") != self.overlay.settings.get("margin"):   # 여백이 바뀜 → 드래그한 박스도 따라감
            self.overlay.apply_settings(settings)           # 먼저 새 여백으로 자막 칸 너비를 다시 잼
            self.overlay.follow_margin(settings["margin"])
            settings["instant_custom_pos"] = deepcopy(self.overlay.settings.get("instant_custom_pos"))
            settings["continuous_custom_pos"] = deepcopy(self.overlay.settings.get("continuous_custom_pos"))
        self.overlay.apply_settings(settings)
        self.mark_modified(True)

    def commit_settings(self):
        cfg = self.collect_custom_settings()
        if self.state["active_target"] == "common":
            self._commit_common(cfg)
            return
        self.set_active_config(cfg)
        self.bridge.settings_changed.emit(cfg)
        self._save_state()
        self.mark_modified(False)

    def on_backend_status(self, text):
        self.lbl_backend_status.setText(f"백엔드: {text}")

    def set_service(self, running):
        self.is_service_running = running
        if running:
            self.hero_status_title.setText("자막 오버레이 실행 중")
            self.hero_status_title.setStyleSheet(f"font-size: 19px; font-weight: 800; color: {PRIMARY_BLUE};")
            self.hero_status_sub.setText("백엔드가 소리를 실시간 감지하여 오버레이에 표출합니다.")
            self.btn_main_power.setText("서비스 중지")
            self.btn_main_power.setStyleSheet(DANGER_BUTTON_STYLE)
        else:
            self.hero_status_title.setText("자막 오버레이 중지됨")
            self.hero_status_title.setStyleSheet("font-size: 19px; font-weight: 800; color: #0F172A;")
            self.hero_status_sub.setText("시작 버튼을 누르면 화면에 소리 자막이 활성화됩니다.")
            self.btn_main_power.setText("서비스 시작")
            self.btn_main_power.setStyleSheet(BLUE_BUTTON_STYLE)
            self.overlay.clear_events()

        self.update_overlay_visibility()
        self.bridge.service_toggled.emit(running)

    def update_overlay_visibility(self):
        p_on = self.preview_switch_corner.isChecked() or self._is_quick_editing
        self.overlay.setVisible(self.is_service_running or p_on)

    def refresh(self, *_):
        pass

    def toggle_service(self):
        self.set_service(not self.is_service_running)

    def on_sound(self, event):
        t_recv = time.perf_counter()
        is_preview_on = self.preview_switch_corner.isChecked() or self._is_quick_editing
        if self.is_service_running and not is_preview_on:
            self.overlay.handle_event(event)
            n = getattr(event, "_perf_n", None)          # 성능 기록 중일 때만 붙어 있음 (⑥ UI 전달 · ⑦ 오버레이 배치)
            if n is not None and self.backend is not None:
                self.backend.perf_ui(n, t_recv, time.perf_counter())

    def on_preview_toggled(self, on):
        in_settings_tab = (self.tabs.currentIndex() == 1)

        if on:
            self._service_was_running_before_preview = self.is_service_running
            if self.is_service_running:
                self.bridge.service_toggled.emit(False)
                self.overlay.clear_events()

            self.overlay.set_preview(True)

            if in_settings_tab:
                self.overlay.set_interactive(True)
            else:
                self.overlay.set_interactive(False)
        else:
            self.overlay.set_interactive(False)
            self.overlay.set_preview(False)

            if self._service_was_running_before_preview:
                self.bridge.service_toggled.emit(True)
                self._service_was_running_before_preview = False

        self.update_overlay_visibility()

    def closeEvent(self, event):
        if sys.platform == "win32":
            ctypes.windll.user32.UnregisterHotKey(int(self.winId()), HOTKEY_ID)
        if self.backend is not None:
            self.backend.stop()
        self._save_state()
        self.quick_overlay.close()
        self.overlay.close()
        super().closeEvent(event)


class PaintWatch(QObject):
    """성능 기록용: 오버레이 자막 칸이 다시 그려지는 순간을 백엔드 기록에 알림 (⑧ 화면 그리기)"""

    def __init__(self, backend):
        super().__init__()
        self.backend = backend

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Paint:
            text = getattr(obj, "shown_text", None) or obj.text()   # 화면에서 '…'로 줄이기 전의 전체 글자
            self.backend.perf_paint(text, time.perf_counter())
        return False


def parse_perf_args(argv):
    """--perf → 성능 기록, --latency-test [N] → 지연 시험 (시험음 N번, 기본 30). -> (perf, n)"""
    perf, n = None, 30
    if "--perf" in argv:
        perf = "perf"
    if "--latency-test" in argv:
        perf = "latency"
        i = argv.index("--latency-test")
        if i + 1 < len(argv) and argv[i + 1].isdigit():
            n = max(1, int(argv[i + 1]))
    return perf, n


if __name__ == "__main__":
    app = QApplication(sys.argv)
    perf_mode, latency_n = parse_perf_args(sys.argv[1:])
    
    from PySide6.QtGui import QPalette
    light_palette = QPalette()
    light_palette.setColor(QPalette.ColorRole.Window, QColor("#FFFFFF"))
    light_palette.setColor(QPalette.ColorRole.WindowText, QColor("#0F172A"))
    light_palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
    light_palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F1F5F9"))
    light_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#FFFFFF"))
    light_palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#0F172A"))
    light_palette.setColor(QPalette.ColorRole.Text, QColor("#0F172A"))
    light_palette.setColor(QPalette.ColorRole.Button, QColor("#F1F5F9"))
    light_palette.setColor(QPalette.ColorRole.ButtonText, QColor("#0F172A"))
    light_palette.setColor(QPalette.ColorRole.BrightText, QColor("#EF4444"))
    light_palette.setColor(QPalette.ColorRole.Link, QColor("#2563EB"))
    light_palette.setColor(QPalette.ColorRole.Highlight, QColor("#2563EB"))
    light_palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(light_palette)

    bridge = SoundBridge()

    backend = None
    try:
        from real_backend import RealBackend
        backend = RealBackend(bridge, perf=perf_mode, latency_n=latency_n)
        if perf_mode:
            print(f"[성능 기록] {'지연 시험 (시험음 ' + str(latency_n) + '번)' if perf_mode == 'latency' else '분석마다 기록'}"
                  " — [서비스 시작]을 누르면 기록을 시작하고, [서비스 중지]·앱 종료 때 perf_logs 폴더에 저장해요")
        bridge.settings_changed.connect(backend.apply_settings)
        bridge.service_toggled.connect(backend.set_running)
        bridge.capture_changed.connect(backend.set_capture)
    except Exception as e:
        print(f"[백엔드] 불러오지 못함 → 프론트만 실행: {e}")
        backend = None

    window = MainControlWindow(bridge)
    window.backend = backend
    if backend is not None and perf_mode:
        paint_watch = PaintWatch(backend)
        for group in window.overlay._labels.values():
            for lbl in group:
                lbl.installEventFilter(paint_watch)
    if backend is not None:
        backend.start()
    window.show()
    sys.exit(app.exec())