"""sound_tree.py — 소리 필터 트리 (2026-10-24). Qt·모델 없이 동작

프론트 소리 필터 = 대분류 > 중분류 > 소리(모드 라벨) 3단 토글
  - 대분류·중분류 이름표: 분류.txt (AudioSet 527 정리) 의 이름을 그대로 씀 (CATS)
  - 맨 아래 '소리'      : 그 모드 라벨 파일의 라벨 (화면에 실제로 뜨는 단위). 라벨마다 cat="5-8" 처럼 중분류 코드
  - 트리는 모드마다 따로 만듦: 그 모드 라벨이 하나라도 있는 칸만 보임 (빈 칸은 안 보임)
  - 같은 모드에서 토글 이름(toggle_name 또는 name)이 같은 라벨은 토글 하나 (공포 '문 소리' = door + knock)
  - 흡수 라벨(kind="sink")은 화면에 안 뜨므로 토글 없음

설정으로 주고받는 것은 꺼 둔 라벨 키 목록 하나뿐: settings['sounds_off'] = ["gunshot", "smoke", ...]
  대분류·중분류 토글은 프론트에서만 계산 (끄면 그 아래 라벨 키를 전부 넣음). 백엔드는 트리를 몰라도 됨
"""
import importlib

# 프론트 base_mode → 라벨 파일
MODE_LABELS = {"FPS": "gun_labels", "공포": "horror_labels", "예능": "variety_labels", "아동": "kids_labels"}

# 분류.txt 대분류·중분류 이름 (코드 → 이름)
CATS = {
    "1": "사람",
    "1-1": "말하기·외침", "1-2": "웃음·울음·신음", "1-3": "노래·허밍·휘파람",
    "1-4": "호흡·소화·심장", "1-5": "움직임·손동작·군중",
    "2": "동물",
    "2-1": "반려동물: 개·고양이", "2-2": "가축", "2-3": "야생 포유류", "2-4": "새",
    "2-5": "곤충·양서·파충·고래",
    "3": "음악",
    "3-1": "음악 총칭", "3-2": "현악기", "3-3": "건반악기", "3-4": "타악기", "3-5": "종·차임",
    "3-6": "관악기", "3-7": "기타 악기·연주 기법", "3-8": "장르: 대중·R&B·힙합·포크",
    "3-9": "장르: 록", "3-10": "장르: 재즈·블루스·클래식", "3-11": "장르: 일렉트로닉",
    "3-12": "장르: 세계 음악·종교·어린이", "3-13": "용도·상황과 분위기",
    "4": "자연",
    "4-1": "날씨·바람·불", "4-2": "물",
    "5": "생활 속 사물과 기계",
    "5-1": "도로 위 차량", "5-2": "배·기차·비행기", "5-3": "엔진", "5-4": "집 안: 문·수납·주방·욕실",
    "5-5": "사무·통신·전자기기", "5-6": "경보·사이렌·호루라기", "5-7": "기계·공구",
    "5-8": "폭발·총기·불꽃놀이", "5-9": "나무·유리·액체", "5-10": "기타 사물·효과",
    "6": "출처를 알 수 없는 소리",
    "6-1": "부딪히는 소리", "6-2": "문지르고 구기는 소리", "6-3": "높고 맑은 소리",
    "6-4": "거칠거나 연속적인 질감", "6-5": "무음·합성 신호",
    "7": "녹음 환경과 배경",
    "7-1": "공간·울림", "7-2": "노이즈·전기적 잡음", "7-3": "재생·녹음 매체",
}


def _code_key(code):
    return tuple(int(x) for x in code.split("-"))


def labels_of(base_mode):
    """base_mode 의 LABELS (라벨 파일은 가벼워서 바로 import)"""
    return importlib.import_module(MODE_LABELS.get(base_mode, "gun_labels")).LABELS


def shown_labels(base_mode):
    """화면에 뜰 수 있는 라벨 키 (흡수 라벨 제외), 라벨 파일 순서"""
    return [k for k, v in labels_of(base_mode).items() if v["kind"] != "sink"]


def build_tree(base_mode):
    """-> [dict(code, name, children=[dict(code, name, leaves=[dict(name, keys=[...])])])]  (코드 순)"""
    L = labels_of(base_mode)
    mids = {}                                     # 중분류 코드 → {토글 이름: [키...]}
    for k in shown_labels(base_mode):
        cat = L[k].get("cat")
        if cat not in CATS:
            raise ValueError(f"{MODE_LABELS.get(base_mode)}: '{k}' 의 cat '{cat}' 이 분류표에 없음")
        name = L[k].get("toggle_name", L[k]["name"])
        mids.setdefault(cat, {}).setdefault(name, []).append(k)
    tops = {}
    for mid in sorted(mids, key=_code_key):
        top = mid.split("-")[0]
        tops.setdefault(top, []).append(dict(
            code=mid, name=CATS[mid],
            leaves=[dict(name=n, keys=ks) for n, ks in mids[mid].items()]))
    return [dict(code=t, name=CATS[t], children=c) for t, c in sorted(tops.items(), key=lambda x: int(x[0]))]


COMMON = "공통"     # 설정 화면 '공통': 분류표 전체 + 모든 모드 라벨을 보여 줌


def build_full_tree():
    """'공통' 화면용: 분류표(CATS)의 대분류·중분류를 전부 (소리가 없는 칸도) + 세 모드 라벨을 모두.
    같은 중분류 안에서 토글 이름이 같으면 하나로 합침. 소리마다 어느 모드에 있는지(modes)도 붙임
    -> build_tree 와 같은 모양 (leaves 에 modes 추가)"""
    mids = {c: {} for c in CATS if "-" in c}            # 중분류 → {이름: {"keys": [...], "modes": [...]}}
    for mode in MODE_LABELS:
        L = labels_of(mode)
        for k in shown_labels(mode):
            cat = L[k].get("cat")
            if cat not in mids:
                raise ValueError(f"{MODE_LABELS[mode]}: '{k}' 의 cat '{cat}' 이 분류표에 없음")
            name = L[k].get("toggle_name", L[k]["name"])
            leaf = mids[cat].setdefault(name, {"keys": [], "modes": []})
            if k not in leaf["keys"]:
                leaf["keys"].append(k)
            if mode not in leaf["modes"]:
                leaf["modes"].append(mode)
    tops = {}
    for mid in sorted(mids, key=_code_key):
        tops.setdefault(mid.split("-")[0], []).append(dict(
            code=mid, name=CATS[mid],
            leaves=[dict(name=n, keys=v["keys"], modes=v["modes"]) for n, v in mids[mid].items()]))
    return [dict(code=t, name=CATS[t], children=c) for t, c in sorted(tops.items(), key=lambda x: int(x[0]))]


def mode_keys(base_mode):
    """그 모드에 있는 라벨 키 집합"""
    return set(shown_labels(base_mode))


def clean_off(base_mode, keys):
    """설정의 sounds_off 정리: 그 모드에 있는 라벨 키만, 중복 제거, 라벨 파일 순서"""
    want = {str(k) for k in (keys or [])}
    return [k for k in shown_labels(base_mode) if k in want]


if __name__ == "__main__":       # python sound_tree.py → 세 모드 트리 출력
    for m in MODE_LABELS:
        print(f"\n===== {m} =====")
        for t in build_tree(m):
            print(f"{t['code']}. {t['name']}")
            for c in t["children"]:
                leaves = " · ".join(f"{lf['name']}" + (f"({'+'.join(lf['keys'])})" if len(lf['keys']) > 1 else "")
                                    for lf in c["leaves"])
                print(f"   {c['code']} {c['name']}: {leaves}")
