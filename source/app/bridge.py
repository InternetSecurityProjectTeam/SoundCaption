"""백엔드(다른 스레드)와 UI(메인 스레드)를 안전하게 잇는 다리.

- 백엔드 → UI : bridge.sound_received.emit(SoundEvent(...))
- UI → 백엔드 : bridge.settings_changed.connect(함수)   (설정이 바뀔 때마다 전체 dict 전달)
                bridge.service_toggled.connect(함수)    (자막 서비스 시작/중지)
                bridge.capture_changed.connect(함수)    (사운드 캡처 장치를 고르면 바로, [설정 저장] 없이)

Qt 화면은 메인 스레드에서만 건드려야 하므로, 백엔드는 emit만 하면 된다.
(받는 쪽 함수는 메인 스레드에서 실행되니 오래 걸리는 일은 큐에 넣고 바로 반환할 것)
"""
from PySide6.QtCore import QObject, Signal


class SoundBridge(QObject):
    sound_received = Signal(object)    # SoundEvent
    settings_changed = Signal(dict)    # 현재 설정 전체 (settings.DEFAULTS와 같은 키)
    service_toggled = Signal(bool)     # True = 시작, False = 중지
    backend_status = Signal(str)       # 백엔드 상태 문구 (모델 불러오는 중 / 준비 완료 / 오류 등)
    capture_changed = Signal(str)      # 사운드 캡처 장치 (settings capture_target 값). 고르는 즉시 전달
