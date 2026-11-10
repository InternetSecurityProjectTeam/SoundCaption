"""프리셋 추가 시 베이스 모드 가중치 선택 다이얼로그 (메인 라이트 테마 적용)"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton

from settings import DEFAULT_MODES

BG_LIGHT = "#FFFFFF"
CARD_BG = "#F4F6FB"
BORDER_COLOR = "#CBD5E1"
PRIMARY_BLUE = "#2563EB"
TEXT_COLOR = "#0F172A"


class PresetCreateDialog(QDialog):
    def __init__(self, existing_names, parent=None):
        super().__init__(parent)
        self.existing_names = existing_names
        self.selected_base_mode = "FPS"
        self.created_name = ""

        self.setWindowTitle("새 프리셋 생성")
        self.setFixedSize(380, 260)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_LIGHT};
                color: {TEXT_COLOR};
            }}
            QLabel {{
                color: {TEXT_COLOR};
                font-size: 13px;
                font-weight: 700;
            }}
            QLineEdit {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                color: {TEXT_COLOR};
                padding: 8px 12px;
                font-weight: bold;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 1px solid {PRIMARY_BLUE};
                background-color: #FFFFFF;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title_lbl = QLabel("새 프리셋 생성")
        title_lbl.setStyleSheet(f"color: {PRIMARY_BLUE}; font-size: 16px; font-weight: 800;")
        layout.addWidget(title_lbl)

        layout.addWidget(QLabel("프리셋 이름:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("예: 배틀그라운드, 파스마포비아, 종겜")
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("기준 베이스 모드 (가중치):"))
        mode_box = QHBoxLayout()
        mode_box.setSpacing(8)

        self.mode_buttons = {}
        for mode in DEFAULT_MODES:
            btn = QPushButton(mode)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(36)
            btn.clicked.connect(lambda _, m=mode: self._select_mode(m))
            mode_box.addWidget(btn)
            self.mode_buttons[mode] = btn

        layout.addLayout(mode_box)
        self._select_mode("FPS")

        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        self.btn_cancel = QPushButton("취소")
        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {CARD_BG}; color: {TEXT_COLOR}; border: 1px solid {BORDER_COLOR};
                border-radius: 8px; padding: 8px; font-weight: 700;
            }}
            QPushButton:hover {{ background-color: #E2E8F0; }}
        """)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_create = QPushButton("생성하기")
        self.btn_create.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY_BLUE}; color: #FFFFFF; border: none;
                border-radius: 8px; padding: 8px; font-weight: 800;
            }}
            QPushButton:hover {{ background-color: #1D4ED8; }}
        """)
        self.btn_create.clicked.connect(self._on_create)

        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_create)
        layout.addLayout(btn_box)

    def _select_mode(self, mode_name):
        self.selected_base_mode = mode_name
        for mode, btn in self.mode_buttons.items():
            if mode == mode_name:
                btn.setChecked(True)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {PRIMARY_BLUE}; color: #FFFFFF; border: 1px solid {PRIMARY_BLUE};
                        border-radius: 8px; font-weight: 800;
                    }}
                """)
            else:
                btn.setChecked(False)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {CARD_BG}; color: {TEXT_COLOR}; border: 1px solid {BORDER_COLOR};
                        border-radius: 8px; font-weight: 600;
                    }}
                    QPushButton:hover {{ background-color: #E2E8F0; }}
                """)

    def _on_create(self):
        name = self.name_input.text().strip()
        if not name:
            return
        if name in self.existing_names or name in DEFAULT_MODES:
            self.name_input.setStyleSheet("border: 1px solid #EF4444;")
            return
        self.created_name = name
        self.accept()