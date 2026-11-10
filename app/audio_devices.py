"""audio_devices.py — 사운드 캡처 장치 목록·찾기 (2026-10-25). 모델 없이 가벼움 (UI에서도 import)

  - 출력 장치(스피커·헤드폰 등)의 WASAPI 루프백 장치를 씀 (윈도우 전용, pyaudiowpatch)
  - 화면에 보이는 이름 = 루프백 장치 이름에서 ' [Loopback]' 을 뗀 것 = 설정 'capture_target' 에 저장하는 값
  - 'capture_target' 이 기본값(DEFAULT_CAPTURE)이면 윈도우 기본 출력 장치를 따라감
  - 저장된 장치를 못 찾으면(뽑힘 등) 기본 출력 장치로 대신 캡처 (백엔드 상태 줄에 표시)
"""
from settings import DEFAULT_CAPTURE

_SUFFIX = " [Loopback]"


def display_name(lb_name):
    name = str(lb_name)
    return name[:-len(_SUFFIX)] if name.endswith(_SUFFIX) else name


def list_output_devices():
    """캡처할 수 있는 출력 장치 이름 목록 (2채널 이상 루프백). pyaudiowpatch 없음·윈도우 아님 → []"""
    try:
        import pyaudiowpatch as pyaudio
    except Exception:
        return []
    pa = None
    names = []
    try:
        pa = pyaudio.PyAudio()
        for lb in pa.get_loopback_device_info_generator():
            if int(lb.get("maxInputChannels", 0)) >= 2:
                n = display_name(lb["name"])
                if n not in names:
                    names.append(n)
    except Exception:
        return names
    finally:
        if pa is not None:
            try:
                pa.terminate()
            except Exception:
                pass
    return names


def find_loopback(pa, target):
    """target(화면 이름)에 맞는 루프백 장치 정보. 기본값이거나 못 찾으면 None (→ 기본 출력 장치 사용)"""
    target = str(target or "").strip()
    if not target or target == DEFAULT_CAPTURE:
        return None
    try:
        lbs = [lb for lb in pa.get_loopback_device_info_generator() if int(lb.get("maxInputChannels", 0)) >= 2]
    except Exception:
        return None
    for lb in lbs:                                   # 이름이 정확히 같은 장치
        if display_name(lb["name"]) == target:
            return lb
    for lb in lbs:                                   # 이름 일부가 같은 장치 (드라이버가 이름 끝을 바꾸는 경우)
        if target in lb["name"] or display_name(lb["name"]) in target:
            return lb
    return None
