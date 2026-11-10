"""설정 기본값 / 모드·프리셋 / 검증 / 저장·불러오기"""
import json
import re
from copy import deepcopy
from pathlib import Path

from sound_tree import clean_off

SETTINGS_PATH = Path.home() / ".sound-caption" / "settings.json"

DEFAULT_MODES = ["FPS", "공포", "예능", "아동"]
KIDS_VIEWS = ["그림 + 짧은 글", "그림만", "글 위주"]   # 아동 모드 보기 방식 (문서 v0.1)
POSITIONS = ["상단 가운데", "왼쪽 위", "오른쪽 위"]
FONT_CANDIDATES = ["Malgun Gothic", "Pretendard", "Noto Sans KR", "NanumGothic"]

# 소리 필터 (2026-10-24): 10개 그룹 → 대분류 > 중분류 > 소리(모드 라벨) 3단 토글 (sound_tree.py)
#   설정에는 꺼 둔 라벨 키 목록만 저장: "sounds_off": ["gunshot", "smoke", ...]  (모드·프리셋마다 따로)
#   꺼 둔 소리: 백엔드는 계산을 그대로 다 하고, 프론트 칸 수 안에 뽑힌 경우 화면에서만 탈락 (빈자리는 안 채움)

DEFAULT_BOX_DIRECTIONS = {
    "0": "left",
    "1": "center",
    "2": "right",
    "3": "center",
    "4": "left",
}

# 사운드 캡처 장치: 이 값이면 윈도우 기본 출력 장치를 따라감 (audio_devices.py). 장치 설정은 앱 전체에 하나
DEFAULT_CAPTURE = "기본 시스템 출력 (Loopback)"
_OLD_CAPTURE_NAMES = {"시스템 출력(Loopback)", ""}

DEFAULTS = {
    "base_mode": "FPS",
    "capture_target": DEFAULT_CAPTURE,
    "instant_slots": 3,
    "continuous_slots": 3,
    "instant_enabled": True,
    "continuous_enabled": True,
    "arrows_enabled": True,
    "onoma_enabled": True,
    "continuous_note_enabled": True,     # 2026-11-10 (팀원 zip): 지속음 자막 앞 ♬ 표시
    "instant_duration": 3.0,
    "continuous_duration": 0,
    "font_size": 22,
    "font_family": "Malgun Gothic",
    "text_color": "#FFFFFF",
    "background_color": "#0F111A",
    "opacity": 85,
    "fade_enabled": True,
    "gradient_enabled": True,
    "gradient_color": "#E11D48",
    "gradient_opacity": 85,           # 그라데이션 전용 불투명도 (%)
    "continuous_position": "상단 가운데",
    "continuous_layout": "가로",
    "continuous_height": 3,
    "continuous_custom_pos": None,
    "instant_height": 8,
    "instant_custom_pos": {str(i): None for i in range(5)},
    "instant_box_directions": deepcopy(DEFAULT_BOX_DIRECTIONS),
    "instant_box_font_sizes": {str(i): None for i in range(5)},
    "margin": 40,
    "sounds_off": [],           # 소리 필터에서 꺼 둔 라벨 키 (sound_tree.py)
    # 🧸 아동 모드 (2026-11-05) — 다른 모드에서는 안 씀
    "kids_view": "그림 + 짧은 글",   # 그림만(미취학) / 그림 + 짧은 글(기본) / 글 위주(초등 고학년)
    "kids_motion": True,             # 끄면 애니메이션 줄이기: 움직임 없이 그림만 (크기·위치)
}

BOOL_KEYS = (
    "instant_enabled", "continuous_enabled", "arrows_enabled", 
    "onoma_enabled", "continuous_note_enabled", "fade_enabled", "gradient_enabled", "kids_motion"
)
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def default_settings(base_mode="FPS"):
    s = deepcopy(DEFAULTS)
    s["base_mode"] = base_mode if base_mode in DEFAULT_MODES else "FPS"
    
    if base_mode == "FPS":
        s.update(font_size=24, instant_duration=2.0, continuous_slots=2, opacity=85, text_color="#FFFFFF")
    elif base_mode == "공포":
        s.update(font_size=26, instant_duration=4.0, continuous_slots=3, opacity=90, text_color="#FFFFFF")
    elif base_mode == "예능":
        s.update(font_size=22, instant_duration=3.0, continuous_slots=3, opacity=80, text_color="#FFFFFF")
    elif base_mode == "아동":
        # 문서 v0.1: 최소 표시 시간을 성인 모드보다 길게 (글자를 읽을 시간), 글자는 조금 크게
        # 그림이 자막 위에 뜨므로 순간음 자막을 조금 아래(화면 높이 24%)에서 시작
        # 2026-11-10: 순간음 표시 4.0 → 2.0초 (사용자: 아이 만화는 컷이 빨라 다음 컷까지 그림이 남음. 2초 묶음 분석이라 소리 끝난 뒤 1.5~2초는 계속 판정됨)
        s.update(font_size=24, instant_duration=1.5, continuous_slots=3, opacity=85, text_color="#FFFFFF",   # v0.69: 2.0 → 1.5 (사용자) · v0.64 (팀원): 지속음 3칸
                 instant_height=24)

    return normalize(s)


def _clamp(value, low, high, default):
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _clamp_float(value, low, high, default):
    try:
        number = round(float(value), 1)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _color(value, default):
    return value.upper() if isinstance(value, str) and _HEX.match(value) else default


def normalize(raw):
    raw = raw if isinstance(raw, dict) else {}
    s = deepcopy(DEFAULTS)

    base = str(raw.get("base_mode") or "FPS")
    s["base_mode"] = base if base in DEFAULT_MODES else "FPS"

    cap = str(raw.get("capture_target") or "").strip()
    s["capture_target"] = DEFAULT_CAPTURE if cap in _OLD_CAPTURE_NAMES else cap
    s["instant_slots"] = _clamp(raw.get("instant_slots"), 1, 5, s["instant_slots"])
    s["continuous_slots"] = _clamp(raw.get("continuous_slots"), 0, 5, s["continuous_slots"])
    for key in BOOL_KEYS:
        s[key] = bool(raw.get(key, s[key]))

    s["instant_duration"] = _clamp_float(raw.get("instant_duration"), 0.1, 10.0, s["instant_duration"])
    s["continuous_duration"] = _clamp(raw.get("continuous_duration"), 0, 30, s["continuous_duration"])
    s["font_size"] = _clamp(raw.get("font_size"), 12, 48, s["font_size"])
    s["font_family"] = str(raw.get("font_family") or s["font_family"])
    s["text_color"] = _color(raw.get("text_color"), s["text_color"])
    s["background_color"] = _color(raw.get("background_color"), s["background_color"])
    s["gradient_color"] = _color(raw.get("gradient_color"), s["gradient_color"])
    s["gradient_opacity"] = _clamp(raw.get("gradient_opacity"), 0, 100, s["gradient_opacity"])

    if "opacity" in raw and raw["opacity"] is not None:
        s["opacity"] = _clamp(raw["opacity"], 0, 100, s["opacity"])
    else:
        s["opacity"] = _clamp(raw.get("opacity"), 0, 100, s["opacity"])

    s["continuous_height"] = _clamp(raw.get("continuous_height"), 0, 100, s["continuous_height"])
    s["instant_height"] = _clamp(raw.get("instant_height"), 1, 80, s["instant_height"])
    s["margin"] = _clamp(raw.get("margin"), 0, 200, s["margin"])

    position = raw.get("continuous_position")
    s["continuous_position"] = position if position in POSITIONS else s["continuous_position"]

    c_layout = raw.get("continuous_layout")
    s["continuous_layout"] = c_layout if c_layout in ["가로", "세로"] else s["continuous_layout"]

    raw_c_pos = raw.get("continuous_custom_pos")
    if isinstance(raw_c_pos, (list, tuple)) and len(raw_c_pos) == 2:
        try:
            s["continuous_custom_pos"] = [int(raw_c_pos[0]), int(raw_c_pos[1])]
        except (ValueError, TypeError):
            s["continuous_custom_pos"] = None
    else:
        s["continuous_custom_pos"] = None

    raw_custom_pos = raw.get("instant_custom_pos")
    if isinstance(raw_custom_pos, dict):
        s["instant_custom_pos"] = {}
        for k in range(5):
            val = raw_custom_pos.get(str(k)) or raw_custom_pos.get(k)
            if isinstance(val, (list, tuple)) and len(val) == 2:
                s["instant_custom_pos"][str(k)] = [int(val[0]), int(val[1])]
            else:
                s["instant_custom_pos"][str(k)] = None

    raw_dirs = raw.get("instant_box_directions")
    if isinstance(raw_dirs, dict):
        for k in range(5):
            d = str(raw_dirs.get(str(k)) or raw_dirs.get(k) or DEFAULT_BOX_DIRECTIONS[str(k)])
            s["instant_box_directions"][str(k)] = d if d in ["left", "center", "right"] else DEFAULT_BOX_DIRECTIONS[str(k)]

    raw_fonts = raw.get("instant_box_font_sizes")
    if isinstance(raw_fonts, dict):
        for k in range(5):
            val = raw_fonts.get(str(k)) or raw_fonts.get(k)
            s["instant_box_font_sizes"][str(k)] = _clamp(val, 12, 48, None) if val is not None else None

    # 예전 10개 그룹 설정("sounds")은 버림 → 전부 켜짐으로 시작
    s["sounds_off"] = clean_off(s["base_mode"], raw.get("sounds_off"))
    view = raw.get("kids_view")
    s["kids_view"] = view if view in KIDS_VIEWS else s["kids_view"]
    return s


def load_state(path=None):
    path = Path(path) if path else SETTINGS_PATH
    state = {
        "active_target": "FPS",
        "modes": {
            "FPS": default_settings("FPS"),
            "공포": default_settings("공포"),
            "예능": default_settings("예능"),
            "아동": default_settings("아동"),
        },
        "presets": {},
        "capture_target": DEFAULT_CAPTURE,     # 사운드 캡처 장치 (모드와 상관없이 하나)
    }

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return state

    if isinstance(data, dict):
        if isinstance(data.get("modes"), dict):
            for m in DEFAULT_MODES:
                if m in data["modes"]:
                    state["modes"][m] = normalize(data["modes"][m])
                    if m == "아동" and state["modes"][m]["continuous_slots"] == 2:   # v0.64 (팀원 kids.zip): 지속음 그림 3개까지
                        state["modes"][m]["continuous_slots"] = 3
        if isinstance(data.get("presets"), dict):
            state["presets"] = {str(k): normalize(v) for k, v in data["presets"].items()}
        
        active = str(data.get("active_target") or "")
        if active in state["modes"] or active in state["presets"]:
            state["active_target"] = active

        if "capture_target" in data:
            state["capture_target"] = normalize({"capture_target": data.get("capture_target")})["capture_target"]
        else:                                   # 예전 설정 파일: 지금 고른 모드에 저장돼 있던 장치를 씀
            cfg = state["modes"].get(state["active_target"]) or state["presets"].get(state["active_target"]) or {}
            state["capture_target"] = cfg.get("capture_target", DEFAULT_CAPTURE)

    return state


def save_state(state, path=None):
    path = Path(path) if path else SETTINGS_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except OSError:
        return False