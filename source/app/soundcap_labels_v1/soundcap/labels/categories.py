"""서비스 카테고리 정의 (세 모델 공통 층).

PANNs·BEATs(AudioSet 527)와 CLAP(세분 클래스)은 모두 이 카테고리로 모인다.
우선순위·시간 형태·표시는 전부 이 층에서 결정하므로, 모델이 바뀌어도 이 파일은 그대로 쓴다.

필드
- name     : 카테고리 기본 표시명 (구체 표시명이 없을 때 사용)
- group    : 대분류 5개 (human / signal / event / environment / music_sfx)
- w_inst   : 순간음 기본 가중치 (영상 모드). A=40 B=30 C=20 D=10
- w_sust   : 지속음 기본 가중치 (영상 모드). 사람 25 / 환경 20 / 음악·군중 15
- form     : 기본 시간 형태 (사전 정보일 뿐, 최종 판정은 신호 분석)
             "instant" | "sustained" | "both"
- convert  : 순간 → 지속 전환 허용 (2초 넘게 갱신 시)
- repeat   : 반복 이력 검사 대상 (신호음류)
- icon     : 지속음 상태바 아이콘
- new      : 기존 설계 문서 등급표에 없던 항목 (검토 필요 표시용)

모드별 가중치는 아직 영상 모드만 채워 둔다. 게임 모드는 2번 논의 후 MODE_OVERRIDES에 추가.
"""

GROUPS = {
    "human": "사람 소리",
    "signal": "신호음",
    "event": "사건음",
    "environment": "환경음",
    "music_sfx": "음악·효과음",
}

C = dict  # 가독성용 별칭

CATEGORIES = {
    # ── 사람 소리 (말 제외) ─────────────────────────────
    "scream":     C(name="비명",          group="human", w_inst=40, w_sust=25, form="instant"),
    "cry":        C(name="울음소리",      group="human", w_inst=40, w_sust=25, form="both", convert=True, icon="😢"),
    "shout":      C(name="외치는 소리",   group="human", w_inst=20, w_sust=25, form="instant", new=True),
    "laugh":      C(name="웃음소리",      group="human", w_inst=30, w_sust=25, form="both", convert=True, icon="😆"),
    "applause":   C(name="박수",          group="human", w_inst=30, w_sust=25, form="both", convert=True, icon="👏"),
    "cheer":      C(name="환호",          group="human", w_inst=30, w_sust=25, form="both", convert=True, icon="🙌"),
    "sigh":       C(name="한숨",          group="human", w_inst=20, w_sust=25, form="instant"),
    "cough":      C(name="기침",          group="human", w_inst=20, w_sust=25, form="instant"),
    "sneeze":     C(name="재채기",        group="human", w_inst=20, w_sust=25, form="instant", new=True),
    "gasp":       C(name="숨 들이켜는 소리", group="human", w_inst=20, w_sust=25, form="instant", new=True),
    "breathing":  C(name="거친 숨소리",   group="human", w_inst=20, w_sust=25, form="sustained", icon="😮‍💨", new=True),
    "snore":      C(name="코골이",        group="human", w_inst=20, w_sust=25, form="sustained", icon="💤", new=True),
    "groan":      C(name="신음·힘주는 소리",          group="human", w_inst=20, w_sust=25, form="both", convert=True, new=True),
    "bodily":     C(name="생리음",        group="human", w_inst=20, w_sust=25, form="instant", new=True),
    "whistling":  C(name="휘파람",        group="human", w_inst=20, w_sust=25, form="both", convert=True, icon="🎶", new=True),
    "snap":       C(name="손가락 튕기는 소리", group="human", w_inst=20, w_sust=25, form="instant", new=True),
    "heartbeat":  C(name="심장 박동",     group="human", w_inst=20, w_sust=25, form="sustained", icon="💓", new=True),

    # ── 신호음 ─────────────────────────────────────────
    "doorbell":   C(name="초인종·인터폰",        group="signal", w_inst=40, w_sust=30, form="instant"),
    "knock":      C(name="노크",          group="signal", w_inst=40, w_sust=30, form="instant"),
    "phone":      C(name="전화벨",        group="signal", w_inst=40, w_sust=30, form="instant"),
    "siren":      C(name="사이렌",        group="signal", w_inst=40, w_sust=30, form="both", convert=True, icon="🚨"),
    "alarm":      C(name="경보음·알람",          group="signal", w_inst=30, w_sust=30, form="instant", repeat=True),
    "horn":       C(name="경적",          group="signal", w_inst=30, w_sust=30, form="instant"),
    "whistle":    C(name="호루라기",      group="signal", w_inst=30, w_sust=30, form="instant", new=True),
    # AudioSet 에 라벨이 없는 소리 — CLAP 만 앎. 영상 모드에선 표시 안 됨(흡수 역할), 게임 모드에선 표시
    "phone_vibe": C(name="휴대폰 진동",   group="signal", w_inst=30, w_sust=30, form="instant", new=True, clap_only_cat=True),

    # ── 사건음 ─────────────────────────────────────────
    "gunshot":    C(name="총성",          group="event", w_inst=40, w_sust=20, form="instant"),
    "explosion":  C(name="폭발음",        group="event", w_inst=40, w_sust=20, form="instant"),
    "breaking":   C(name="깨지는 소리",   group="event", w_inst=40, w_sust=20, form="instant"),
    "gun_handling": C(name="총기 장전 소리", group="event", w_inst=20, w_sust=20, form="instant", new=True, clap_only_cat=True),
    "impact":     C(name="충격음",        group="event", w_inst=30, w_sust=20, form="instant", new=True),
    # 가스 분출(연막탄 등): v12·v13의 gas leak 계승. 연막인지 증기인지는 소리만으로 구분 불가 → 생김새 기준 이름
    "gas":        C(name="가스·증기 분출 소리", group="event", w_inst=30, w_sust=20, form="both", convert=True, icon="💨", new=True),
    "door":       C(name="문 소리",       group="event", w_inst=30, w_sust=20, form="instant"),
    "creak":      C(name="삐걱거리는 소리", group="event", w_inst=20, w_sust=20, form="instant", new=True),
    "footsteps":  C(name="발소리",        group="event", w_inst=20, w_sust=20, form="instant"),
    "vehicle":    C(name="차량·탈것 소리",     group="event", w_inst=20, w_sust=20, form="both", convert=True, icon="🚗"),
    "tools":      C(name="공구 소리",     group="event", w_inst=20, w_sust=20, form="both", convert=True, icon="🔨", new=True),
    "machine":    C(name="기계 소리",     group="event", w_inst=20, w_sust=20, form="sustained", icon="⚙️"),
    "household":  C(name="생활 소리",     group="event", w_inst=20, w_sust=20, form="instant", new=True),
    # 2026-10-12: 포장 뜯는 소리가 '깨지는 소리'로 뜸 → 찢기·구기기를 따로
    "tear":       C(name="찢거나 구기는 소리", group="event", w_inst=20, w_sust=20, form="instant", new=True),
    "splash":     C(name="물 튀는 소리",  group="event", w_inst=20, w_sust=20, form="instant", new=True),
    "typing":     C(name="키보드·마우스 소리",   group="event", w_inst=10, w_sust=10, form="sustained", icon="⌨️", new=True),

    # ── 환경음 ─────────────────────────────────────────
    "rain":       C(name="빗소리",        group="environment", w_inst=20, w_sust=20, form="sustained", icon="🌧️"),
    "thunder":    C(name="천둥",          group="environment", w_inst=30, w_sust=20, form="instant", new=True),
    "wind":       C(name="바람 소리",     group="environment", w_inst=20, w_sust=20, form="sustained", icon="🌬️"),
    "water":      C(name="물·액체 소리",        group="environment", w_inst=20, w_sust=20, form="sustained", icon="💧"),
    "fire":       C(name="불",            group="environment", w_inst=20, w_sust=20, form="sustained", icon="🔥"),
    "animal":     C(name="동물 소리",     group="environment", w_inst=20, w_sust=20, form="instant"),
    "bird_insect":C(name="새·벌레 소리",  group="environment", w_inst=20, w_sust=20, form="sustained", icon="🐦"),
    "crowd":      C(name="웅성거림",      group="environment", w_inst=15, w_sust=15, form="sustained", icon="👥"),
    "traffic":    C(name="교통 소음",     group="environment", w_inst=20, w_sust=20, form="sustained", icon="🚦"),
    "aircraft":   C(name="비행기 소리",   group="environment", w_inst=20, w_sust=20, form="sustained", icon="✈️"),
    "train":      C(name="열차 소리",     group="environment", w_inst=20, w_sust=20, form="sustained", icon="🚆"),
    "boat":       C(name="배 소리",       group="environment", w_inst=20, w_sust=20, form="sustained", icon="🚢", new=True),
    "clock":      C(name="시계 초침 소리", group="environment", w_inst=20, w_sust=20, form="sustained", icon="🕰️", new=True),

    # ── 음악·효과음 ────────────────────────────────────
    "music":      C(name="음악",          group="music_sfx", w_inst=15, w_sust=15, form="sustained", icon="🎵"),
    "singing":    C(name="노랫소리",      group="music_sfx", w_inst=15, w_sust=15, form="sustained", icon="🎤"),
    "beep":       C(name="신호음",        group="music_sfx", w_inst=20, w_sust=15, form="instant", repeat=True,
                    repeat_name="반복 신호음", repeat_w_inst=30),
    "chime":      C(name="종소리",        group="music_sfx", w_inst=20, w_sust=15, form="both", convert=True, icon="🔔"),
    "sfx":        C(name="효과음",        group="music_sfx", w_inst=10, w_sust=10, form="instant", new=True),
    # 미확인 효과음은 모델 라벨이 아니라 신호 분석으로만 생긴다 (매핑 대상 아님)
    "unknown":    C(name="미확인 효과음", group="music_sfx", w_inst=10, w_sust=0, form="instant", signal_only=True),
}

# 누락 필드 기본값
for _cid, _c in CATEGORIES.items():
    _c.setdefault("convert", False)
    _c.setdefault("repeat", False)
    _c.setdefault("icon", "")
    _c.setdefault("new", False)
    _c.setdefault("signal_only", False)
    _c.setdefault("clap_only_cat", False)
    assert _c["group"] in GROUPS, _cid
    assert _c["form"] in ("instant", "sustained", "both"), _cid

# 모드별 가중치 덮어쓰기. 영상 모드 = 위 기본값. 게임 모드는 추후 논의.
MODE_OVERRIDES = {
    "video": {},
    # "game": {"footsteps": {"w_inst": 35}, ...},
}


def weight(cat_id: str, sustained: bool, mode: str = "video", repeated: bool = False) -> int:
    c = dict(CATEGORIES[cat_id])
    c.update(MODE_OVERRIDES.get(mode, {}).get(cat_id, {}))
    if repeated and "repeat_w_inst" in c and not sustained:
        return c["repeat_w_inst"]
    return c["w_sust"] if sustained else c["w_inst"]
