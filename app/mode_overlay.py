"""단축키(Alt+M) 입력 시 화면 우측 하단에 팝업되는 빠른 모드 선택 및 위치 수정 오버레이"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

PRIMARY_BLUE = "#2563EB"
BG_LIGHT = "#FFFFFF"
CARD_BG = "#F8FAFC"
BORDER_COLOR = "#CBD5E1"
TEXT_COLOR = "#0F172A"


class ModeItemWidget(QWidget):
    mode_clicked = Signal(str)
    edit_clicked = Signal(str)

    def __init__(self, target_name, display_text, is_active, parent=None):
        super().__init__(parent)
        self.target_name = target_name
        self.is_active = is_active

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 모드 선택 버튼
        self.btn_select = QPushButton(display_text)
        self.btn_select.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_select.setFixedHeight(38)
        self.btn_select.clicked.connect(lambda: self.mode_clicked.emit(self.target_name))

        # 개별 수정 버튼
        self.btn_edit = QPushButton("수정")
        self.btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_edit.setFixedSize(44, 38)
        self.btn_edit.clicked.connect(lambda: self.edit_clicked.emit(self.target_name))

        self.set_active(is_active)

        layout.addWidget(self.btn_select, 1)
        layout.addWidget(self.btn_edit)

    def set_active(self, is_active):
        self.is_active = is_active
        if is_active:
            sel_bg = PRIMARY_BLUE
            sel_color = "#FFFFFF"
            sel_border = f"1px solid {PRIMARY_BLUE}"
            font_weight = "800"
        else:
            sel_bg = CARD_BG
            sel_color = TEXT_COLOR
            sel_border = f"1px solid {BORDER_COLOR}"
            font_weight = "600"

        self.btn_select.setStyleSheet(f"""
            QPushButton {{
                background-color: {sel_bg};
                color: {sel_color};
                border: {sel_border};
                border-radius: 8px;
                font-size: 13px;
                font-weight: {font_weight};
                padding: 0 10px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {'#1D4ED8' if is_active else '#E2E8F0'};
            }}
        """)

        self.btn_edit.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFFFFF;
                color: {PRIMARY_BLUE};
                border: 1px solid {PRIMARY_BLUE};
                border-radius: 8px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #EFF6FF;
            }}
        """)


class QuickModeOverlay(QWidget):
    mode_selected = Signal(str)
    mode_edit_requested = Signal(str)
    edit_completed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.container = QFrame(self)
        self.container.setStyleSheet(f"""
            QFrame#quickContainer {{
                background-color: {BG_LIGHT};
                border: 2px solid {BORDER_COLOR};
                border-radius: 14px;
            }}
        """)
        self.container.setObjectName("quickContainer")

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title_lbl = QLabel("빠른 모드 전환 (Alt + M)")
        title_lbl.setStyleSheet(f"color: {PRIMARY_BLUE}; font-size: 13px; font-weight: 800; border: none; background: transparent;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)

        # 5~6개 모드가 들어갈 수 있도록 정갈한 전용 스크롤바 세팅
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 6px; margin: 0px; }
            QScrollBar::handle:vertical { background: #CBD5E1; border-radius: 3px; min-height: 24px; }
            QScrollBar::handle:vertical:hover { background: #94A3B8; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        
        self.scroll_widget = QWidget()
        self.scroll_widget.setStyleSheet("background: transparent;")
        self.items_layout = QVBoxLayout(self.scroll_widget)
        self.items_layout.setContentsMargins(0, 0, 6, 0)
        self.items_layout.setSpacing(6)
        self.scroll.setWidget(self.scroll_widget)
        
        layout.addWidget(self.scroll, 1)

        # 하단 수정 완료 버튼 (오직 이 버튼을 눌러야만 창이 닫힘)
        self.btn_finish_edit = QPushButton("수정 완료 (설정 저장)")
        self.btn_finish_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_finish_edit.setFixedHeight(38)
        self.btn_finish_edit.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY_BLUE};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 800;
            }}
            QPushButton:hover {{
                background-color: #1D4ED8;
            }}
        """)
        self.btn_finish_edit.clicked.connect(self._on_finish_edit)
        layout.addWidget(self.btn_finish_edit)

        main_box = QVBoxLayout(self)
        main_box.setContentsMargins(0, 0, 0, 0)
        main_box.addWidget(self.container)

        self.items = []

    def set_modes(self, default_modes, presets, active_target):
        for item in self.items:
            self.items_layout.removeWidget(item)
            item.deleteLater()
        self.items.clear()

        for mode in default_modes:
            is_active = (mode == active_target)
            item = ModeItemWidget(mode, f"[기본] {mode} 모드", is_active)
            item.mode_clicked.connect(self._select_target)
            item.edit_clicked.connect(self._edit_target)
            self.items_layout.addWidget(item)
            self.items.append(item)

        for name, cfg in presets.items():
            is_active = (name == active_target)
            base_m = cfg.get("base_mode", "FPS")
            item = ModeItemWidget(name, f"[프리셋] {name} ({base_m})", is_active)
            item.mode_clicked.connect(self._select_target)
            item.edit_clicked.connect(self._edit_target)
            self.items_layout.addWidget(item)
            self.items.append(item)

        # 모드가 몇 개든 늘어나지 않고 5~6개 노출 높이(330px)로 완전 고정
        fixed_height = 330
        self.setFixedSize(280, fixed_height)
        self.container.setGeometry(0, 0, 280, fixed_height)

        self._position_bottom_right()

    def _position_bottom_right(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = screen.width() - self.width() - 40
        y = screen.height() - self.height() - 40
        self.move(x, y)

    def _select_target(self, target_name):
        # 모드 클릭 시 창을 닫지 않고 해당 모드로 전환 및 UI 뱃지만 갱신
        self.mode_selected.emit(target_name)
        for item in self.items:
            item.set_active(item.target_name == target_name)

    def _edit_target(self, target_name):
        # 수정 클릭 시에도 창을 닫지 않고 즉시 드래그 인터랙션 활성화
        self.mode_edit_requested.emit(target_name)
        for item in self.items:
            item.set_active(item.target_name == target_name)

    def _on_finish_edit(self):
        # 오직 이 버튼을 눌렀을 때만 창이 내려가도록 처리
        self.edit_completed.emit()
        self.hide()