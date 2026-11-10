"""v2.2 결합: CLAP 메인 + 클래스 모델(PANNs·BEATs) 보조 — sound_live v16.1 규칙을 카테고리 단위로 옮김

v16.1 과 같은 것
  - CLAP 이 메인 (검출 + 이름), 클래스 모델은 보조
  - 말소리가 1위면 말소리 뺀 나머지 안에서 비율로 판단 (SPEECH_REL_MIN 등)
  - 말소리 거부권: 보조의 말소리 ≥ 0.50 이면 목소리 계열 소리는 보조도 0.30 이상 잡아야 살림
  - 이름*  = CLAP 소리를 보조도 잡음 (점수 + 0.5 × 보조)
    이름+  = 보조만 0.50 이상으로 강하게 잡음 (× 0.6, 음악은 제외)
바뀐 것
  - 단위가 라벨 30개 → 서비스 카테고리 56개
  - CLAP 라벨: "fine"  = 세분 클래스 191개, 카테고리 확률은 세분 확률의 합 (이름은 세분 클래스에서)
               "coarse" = 카테고리당 문장 임베딩 1개 (카테고리 안 세분 문장들의 평균)
    라벨이 많아지면 확률이 잘게 나뉘는 문제 → fine 도 카테고리 합으로 비교해서 완화. 실제 차이는 --eval 로 확인
  - 보조 쪽은 AudioSet 527 전수 매핑 (카테고리 안 max)
"""
from __future__ import annotations

import numpy as np

from .audioset_index import build_label_table, load_panns_mids
from .categories import CATEGORIES
from .clap_classes import CLAP_AMBIENT, CLAP_CLASSES, CLAP_NEGATIVES
from .fusion import Fusion, FusionConfig

# ── v16.1 값 그대로 ──────────────────────────────────
ZS_MIN_P = 0.10
MUSIC_MIN_WITH_SPEECH = 0.30
GLASS_MIN_WITH_BLAST = 0.30
SPEECH_REL_MIN = 0.30
SPEECH_RAW_MIN = 0.03
TAG_MIN_P = 0.15
TAG_SPEECH_ON = 0.50
TAG_MUSIC_MIN_WITH_SPEECH = 0.50
SPEECH_VETO_ON = 0.50
VOICE_CONFIRM = 0.30
TAG_CONFIRM_MIN = 0.15
TAG_BONUS = 0.5
TAG_ADD_MIN = 0.50
TAG_ONLY_WEIGHT = 0.6
TOP_K = 3
CAT_MIN_P = {"animal": 0.30}          # v16 의 dog barking 0.30 을 동물 카테고리에
MERGE_REQUIRE_MAIN = {"music"}
# v16 VOICE_LIKE(노래·음악·군중·울음·웃음·한숨·비명) + 새로 생긴 목소리 계열 카테고리
# 외치는 소리·환호: 말소리가 높을 때는 보조 확인 없으면 지움 (2026-10-12 예능 재테스트)
#  - 외침을 거부권에서 뺐더니 일반 대사가 '외치는 소리'로 뜸 → 다시 넣음 (대사·말투는 대사 자막 영역)
#  - 대신 진짜 외침이 '환호'로 새던 문제는 환호도 같이 넣어서 막음 (둘 다 안 뜨는 쪽이 틀리게 뜨는 것보다 나음)
# 재채기·기침: 허스키한 말소리가 재채기 0.54 로 뜸 (2026-10-12 브이로그, 말소리 0.58)
VOICE_LIKE = {"singing", "music", "crowd", "cry", "laugh", "sigh", "scream",
              "groan", "breathing", "gasp", "sneeze", "cough", "shout", "cheer"}
# 알람·종소리·호루라기·신호음: CLAP 혼자 한 번 잡은 건 '효과음'으로 (예능 효과음이 종소리·알람으로 뜸, 2026-10-12)
# 반복되거나(keep_specific, 호출하는 쪽이 최근 이력으로 판단) 보조도 확인(*)하면 원래 이름. 초인종·전화벨은 예외(그대로)
GENERIC_IF_SOLO = {"alarm", "chime", "whistle", "beep"}
# CLAP 혼자 잡았을 때 묶어서 보여줄 이름 (소리만으로 구분 어려운 것끼리)
#  - 신호음류 → 효과음 (반복 확인되면 원래 이름)
#  - 비행기·기차 → 교통 소음 (브이로그에서 걷는 중 차 소리가 비행기로 뜸, 2026-10-12)
SOLO_GROUP = {**{c: "sfx" for c in GENERIC_IF_SOLO}, "aircraft": "traffic", "train": "traffic"}
# 영상 모드에서 보조 확인(*, +) 없이는 안 띄우는 소리. 게임 모드에서는 CLAP 혼자도 허용
#  - 가스 분출: 사실상 게임(연막) 소리. 브이로그 야외 잡음이 0.31~0.80 으로 떠서 점수로는 못 거름
#  - 재채기·기침: 허스키한 대사가 재채기로 뜸 (말소리 점수가 잠깐 0.5 아래로 떨어진 순간엔 거부권도 안 걸림)
#  - 손가락 튕기는 소리: 마이크 딸깍·옷 소리가 끌려옴 (브이로그·집 둘러보기 0.39~0.58)
#  - 지속음 전부 (사람 숨소리·코골이 제외): 설거지·집 둘러보기·브이로그에서 '*' 없이 뜬 사물 지속음
#    (기계·키보드·시계 초침·교통·비행기·심장 박동)은 전부 오판, 숨소리만 맞음 (2026-10-12)
#  아예 지우지 않는 이유: CLAP 선택지에서 빼면 그 소리가 다른 엉뚱한 선택지로 감 → 선택지로는 남기고 화면에만 안 띄움
# 영상 모드에서 '*' 여부와 상관없이 항상 묶어서 보여줄 이름
#  - 비행기 → 교통 소음: 야외의 멀리서 깔리는 웅 소리를 두 모델 다 비행기로 판단(비행기 소리* 0.40, 실제 아님, 2026-10-12)
VIDEO_ALWAYS_GROUP = {"aircraft": "traffic"}
# 영상 모드에서 보조(AudioSet) 점수가 충분히 높을 때만 구체 이름, 아니면 넓은 이름
#  - 재채기: 세 번 떴는데 다 오판 (허스키한 말 ×2, 입으로 낸 '취익' → 재채기* 0.68). 진짜 재채기는 AudioSet 이
#    강하게 잡는 편 → 보조 0.5 이상이면 '재채기', 아니면 '입·코로 내는 소리' (틀린 말이 되지 않게)
VIDEO_STRICT_NAME = {"sneeze": (0.5, "입·코로 내는 소리")}
# ★ 영상 모드 기본 원칙 (v2.2.14): 둘 다 동의('*')가 기본. CLAP 혼자 잡은 건 아래 허용 목록만 표시
#   오늘 영상 모드 오판의 대부분이 CLAP 혼자 낸 것(키보드·기계·시계·전화벨·인터폰·캔·삐걱 …) → 막을 걸 하나씩
#   추가하던 방식 대신, CLAP 혼자도 맞았던 소리만 허용. AudioSet 이 약한 소리(사람 소리·효과음·도어락)가 여기 해당
#   v2.2.15: 도어락(자석 문제)·숨소리(CLAP 혼자 3번 중 1번만 맞음) 제외
#   v2.2.17: AudioSet 에 없는/약한 소리를 CLAP 단독으로 믿으면 오히려 튐 (가짜 0.26~0.80 ↔ 진짜 0.40~0.70 겹침)
#            → CLAP 단독은 사람 소리(말소리 거부권이라는 안전장치가 따로 있음)만, 0.5 이상
VIDEO_SOLO_OK = {"laugh", "cry", "scream"}
VIDEO_SOLO_MIN = 0.5
# 영상 모드 '+'(AudioSet 혼자) 막기: 동물은 '+' 만으로 표시 안 함 (사람 소리를 동물로 착각 — 까마귀·염소·
# 고양이 울부짖음 전부 AudioSet 혼자 낸 오판), 말하는 중에는 목소리 계열도 '+' 만으로 표시 안 함
VIDEO_PLUS_BLOCK = {"animal", "bird_insect"}
# 영상 모드 '*' 기준: 보조 점수 0.15 → 0.30. '*' 인데 틀린 게 5번 (비행기, 재채기 '취익', 심전도 모니터,
# 물 따르는 소리 → 키보드* 0.33 …) — 보조가 약하게 맞장구친 경우를 거름 (2026-10-12)
VIDEO_CONFIRM_MIN = 0.30
VIDEO_SOLO_OK_NAMES = set()
_HUMAN_SUSTAINED_OK = {"breathing", "snore"}
VIDEO_CONFIRM_ONLY = ({"gas", "sneeze", "cough", "snap"}
                      | {c for c, v in CATEGORIES.items()
                         if v["form"] == "sustained" and c not in _HUMAN_SUSTAINED_OK})
# ★ 화면 이름 묶기 (v2.2.19): 소리를 계속 쪼개는 대신 넓은 이름으로. 내부 선택지·규칙은 그대로, 보이는 이름만.
#   세부 이름(칼질·도끼질, 고양이 울부짖는 소리, 버저 …)은 안 씀 → 틀려도 엉뚱한 이름이 되지 않게
DISPLAY_GROUPS = {
    "외침·환호": ["shout", "cheer"],
    "숨소리": ["breathing", "gasp", "sigh", "snore"],
    "사람 소리": ["cough", "sneeze", "groan", "bodily", "whistling", "snap", "heartbeat"],
    "종소리·알림음": ["beep", "chime", "whistle"],
    "탈것·교통 소리": ["vehicle", "traffic", "aircraft", "train", "boat"],
    "기계·공구 소리": ["machine", "tools"],
    "생활 소리": ["household", "tear", "typing", "clock"],
    "물·액체 소리": ["water", "splash"],
    "동물 소리": ["animal", "bird_insect"],
}
CAT_DISPLAY = {c: CATEGORIES[c]["name"] for c in CATEGORIES}
CAT_DISPLAY.update({c: g for g, cs in DISPLAY_GROUPS.items() for c in cs})

N_INSTANT = 3   # 순간음 표시 개수 (설계 문서 영상 모드 기본은 2 — 테스트 중이라 3)
N_SUSTAIN = 2   # 지속음 표시 개수 (설계 문서: 최대 2)
TAG_SPEECH_CLASSES = ["Speech", "Male speech, man speaking", "Female speech, woman speaking",
                      "Child speech, kid speaking", "Conversation", "Narration, monologue"]
FINE_DISPLAY_SHARE = 0.5   # 카테고리 확률 중 1위 세분 클래스 비중이 이 이상이면 세분 이름 사용

CATS = [c for c in CATEGORIES if not CATEGORIES[c]["signal_only"]]


# coarse 에서 카테고리 평균에 섞지 않고 따로 두는 CLAP 클래스 — 실제 테스트로 필요가 확인된 것만
#  - door_lock: 평균에 섞으면 '삑삑' 특징이 묻혀 충격음으로 뜸 → 따로 두니 0.40~0.70 으로 인식 (2026-10-12)
#  처음엔 AudioSet 에 없는 13개를 전부 따로 뒀는데, 각각이 카테고리 전체와 1:1 로 경쟁하면서 비슷한 소리를
#  끌어옴 (욕실 말소리 → 인터폰, 캔 안 땄는데 캔 따는 소리, 심전도 모니터) → 확인된 것만 따로
#  v2.2.15: 도어락도 다시 평균으로 — 혼자 따로 있으니 비슷한 소리를 끌어오는 자석이 됨 (가짜 0.26~0.60, 진짜 0.40~0.70)
#  진짜 도어락은 충격음·문 소리로 뜸 (덜 정확하지만 틀린 말은 아님)
COARSE_SEPARATE = set()


def _unit(v):
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-9)


class ClapSpace:
    """CLAP 텍스트 쪽. encode(list[str]) -> (N, D) 를 받아 한 번만 계산."""

    def __init__(self, encode, mode="fine", logit_scale=100.0, ambient=False):
        assert mode in ("fine", "coarse")
        self.mode, self.scale = mode, float(logit_scale)
        negs = CLAP_NEGATIVES + (CLAP_AMBIENT if ambient else [])
        cls_vec = []
        for c in CLAP_CLASSES:
            cls_vec.append(_unit(_unit(np.asarray(encode(c["prompts"]), np.float32)).mean(0)))
        neg_vec = [_unit(_unit(np.asarray(encode(n["prompts"]), np.float32)).mean(0)) for n in negs]
        if mode == "fine":
            self.rows = [("cls", c) for c in CLAP_CLASSES]
            vecs = cls_vec
        else:
            self.rows, vecs = [], []
            # coarse: 카테고리당 문장 1개로 합치되, AudioSet 에 없는 소리(clap_only: 도어락·휴대폰 진동·매미 등)는
            # 따로 둠. 같이 평균내면 '문 소리' 평균에 도어락의 삑삑 특징이 묻혀서 도어락이 충격음으로 뜸 (2026-10-12)
            for cat in CATS:
                v = [cls_vec[i] for i, c in enumerate(CLAP_CLASSES) if c["cat"] == cat and c["id"] not in COARSE_SEPARATE]
                if v:
                    self.rows.append(("cat", cat))
                    vecs.append(_unit(np.mean(v, axis=0)))
            for i, c in enumerate(CLAP_CLASSES):
                if c["id"] in COARSE_SEPARATE:
                    self.rows.append(("cls", c))
                    vecs.append(cls_vec[i])
        self.rows += [("neg", n) for n in negs]
        self.T = np.stack(vecs + neg_vec)

    def scores(self, audio_emb):
        """-> (카테고리 확률 dict, 카테고리별 표시 이름 dict, 말소리 확률)"""
        a = _unit(np.asarray(audio_emb, np.float32).reshape(-1))
        z = self.scale * (self.T @ a)
        p = np.exp(z - z.max())
        p /= p.sum()
        cat_p, best = {}, {}
        voice = 0.0
        for (kind, obj), pi in zip(self.rows, p):
            pi = float(pi)
            if kind == "neg":
                if obj["role"] == "voice":
                    voice += pi
                continue
            cat = obj["cat"] if kind == "cls" else obj
            cat_p[cat] = cat_p.get(cat, 0.0) + pi
            if kind == "cls" and (cat not in best or pi > best[cat][0]):
                best[cat] = (pi, obj["ko"])
        names = {}
        for cat, cp in cat_p.items():
            if cat in best and best[cat][0] / (cp + 1e-9) >= FINE_DISPLAY_SHARE:
                names[cat] = best[cat][1]
            else:
                names[cat] = CATEGORIES[cat]["name"]
        return cat_p, names, voice


def filter_main(cat_p, voice):
    """v16 filter_zeroshot 를 카테고리 단위로. -> [(cat, score)] 점수순"""
    if not cat_p:
        return []
    speech_first = voice > max(cat_p.values())
    visible = sum(cat_p.values()) + 1e-9
    blast = cat_p.get("gunshot", 0.0) + cat_p.get("explosion", 0.0)
    out = []
    for cat, p in sorted(cat_p.items(), key=lambda kv: -kv[1]):
        if speech_first:
            score = p / visible
            if p < SPEECH_RAW_MIN or score < SPEECH_REL_MIN:
                continue
            if cat == "music" and p < MUSIC_MIN_WITH_SPEECH:
                continue
        else:
            score = p
            if p < ZS_MIN_P:
                continue
        if score < CAT_MIN_P.get(cat, 0.0):
            continue
        if cat == "breaking" and p < GLASS_MIN_WITH_BLAST and blast > p:
            continue
        out.append((cat, score))
    return out


class TagSide:
    """보조: 527 원본(PANNs 순서) 평균 -> 카테고리 점수, 말소리 점수, 카테고리별 구체 이름"""

    def __init__(self):
        self.fusion = Fusion(FusionConfig(th_as_low=0.12))
        names = [t.name for t in build_label_table(load_panns_mids())]
        self.speech_idx = [names.index(n) for n in TAG_SPEECH_CLASSES]

    def scores(self, raw_list):
        p = np.mean(np.stack(raw_list), axis=0)
        _, sc = self.fusion.audioset_scores(p, p)       # 가중치 합 1 → p 그대로
        cat = {k: v[0] for k, v in sc.items()}
        disp = {k: v[1] for k, v in sc.items()}
        speech = float(p[self.speech_idx].max())
        return cat, disp, speech


def filter_tag(cat, speech):
    speaking = speech >= TAG_SPEECH_ON
    out = []
    for c, s in cat.items():
        if s < max(TAG_MIN_P, CAT_MIN_P.get(c, 0.0)):
            continue
        if c == "music" and speaking and s < TAG_MUSIC_MIN_WITH_SPEECH:
            continue
        out.append((c, s))
    out.sort(key=lambda t: -t[1])
    return out[:TOP_K]


def merge(clap_cat_p, clap_names, clap_voice, tag_cat=None, tag_disp=None, tag_speech=0.0, top_k=10,
          solo_min=0.0, keep_specific=frozenset(), confirm_only=frozenset(), always_group=None,
          strict_name=None, solo_ok=None, solo_ok_names=frozenset(), confirm_min=TAG_CONFIRM_MIN,
          solo_min_ok=0.0, plus_block=frozenset(), plus_voice_veto=False):
    """solo_min: 보조 확인(*) 없이 CLAP 혼자 잡은 소리의 최소 점수 (coarse2 = 0.25, 기존 = 0)"""
    """-> dict(items=[(cat, 이름, 표시점수, 표시기호)], vetoed=[(cat, CLAP, 보조)], speech=보조 말소리)"""
    main = filter_main(clap_cat_p, clap_voice)
    vetoed = []
    if tag_cat is not None and tag_speech >= SPEECH_VETO_ON:
        keep = []
        for c, s in main:
            if c in VOICE_LIKE and tag_cat.get(c, 0.0) < VOICE_CONFIRM:
                vetoed.append((c, s, tag_cat.get(c, 0.0)))     # (카테고리, CLAP 점수, 보조 점수)
            else:
                keep.append((c, s))
        main = keep
    main = main[:top_k]
    rows = []
    if tag_cat is None:
        rows = [(s, c, clap_names[c], s, "") for c, s in main]
    else:
        used = set()
        for c, s in main:
            t = tag_cat.get(c, 0.0)
            if t >= confirm_min:
                rows.append((s + TAG_BONUS * t, c, clap_names[c], min(1.0, s + TAG_BONUS * t), "*"))
            elif s >= solo_min:
                rows.append((s, c, clap_names[c], s, ""))
            used.add(c)
        for c, t in filter_tag(tag_cat, tag_speech):
            if c in used or c in MERGE_REQUIRE_MAIN or t < TAG_ADD_MIN:
                continue
            if c in plus_block or (plus_voice_veto and tag_speech >= SPEECH_VETO_ON and c in VOICE_LIKE):
                continue
            rows.append((t * TAG_ONLY_WEIGHT, c, tag_disp.get(c, CATEGORIES[c]["name"]), t, "+"))
    rows.sort(key=lambda r: -r[0])
    signal_seen = {c for _, c, _, _, _ in rows if c in GENERIC_IF_SOLO}
    renamed, best = [], {}
    for r in rows:
        sc, c, n, sh, mk = r
        if mk == "" and c in confirm_only:
            continue
        if mk == "" and c in SOLO_GROUP and c not in keep_specific:
            c = SOLO_GROUP[c]
            n = CATEGORIES[c]["name"]
        if always_group and c in always_group:
            c = always_group[c]
            n = CATEGORIES[c]["name"]
        if mk == "" and solo_ok is not None and c not in keep_specific:
            if (c not in solo_ok and n not in solo_ok_names) or sc < solo_min_ok:
                continue                      # 영상 모드: CLAP 혼자 + (허용 목록 밖 또는 점수 부족) → 표시 안 함
        if c in best:                         # 효과음이 겹치면 점수 높은 것 하나만
            if sc <= best[c][0]:
                continue
            renamed.remove(best[c])
        best[c] = (sc, c, n, sh, mk)
        renamed.append(best[c])
    if strict_name:
        for i, (sc, c, n, sh, mk) in enumerate(renamed):
            if c in strict_name and (tag_cat or {}).get(c, 0.0) < strict_name[c][0]:
                renamed[i] = (sc, c, strict_name[c][1], sh, mk)
    # 화면 이름 묶기 + 같은 이름이 겹치면 점수 높은 것 하나만
    by_name = {}
    for sc, c, n, sh, mk in renamed:
        n = CAT_DISPLAY.get(c, n)
        if n not in by_name or sc > by_name[n][0]:
            by_name[n] = (sc, c, n, sh, mk)
    renamed = list(by_name.values())
    renamed.sort(key=lambda r: -r[0])
    items = [(c, n, sh, mk) for _, c, n, sh, mk in renamed]
    inst, sust = split_display(items)
    return dict(items=inst + sust, instant=inst, sustained=sust, vetoed=vetoed, speech=tag_speech,
                signal_seen=signal_seen, tag_scores=dict(tag_cat or {}))


def split_display(items, n_inst=None, n_sust=None):
    """기본 시간 형태가 '지속'인 카테고리(음악·비·바람·군중 등)는 순간음 칸을 차지하지 않게 따로.
    아직 실제 지속 판정(1.5초 유지, 흐리게, 멈춤)은 없고 종류로만 나눔."""
    n_inst = N_INSTANT if n_inst is None else n_inst
    n_sust = N_SUSTAIN if n_sust is None else n_sust
    inst = [it for it in items if CATEGORIES[it[0]]["form"] != "sustained"][:n_inst]
    sust = [it for it in items if CATEGORIES[it[0]]["form"] == "sustained"][:n_sust]
    return inst, sust
