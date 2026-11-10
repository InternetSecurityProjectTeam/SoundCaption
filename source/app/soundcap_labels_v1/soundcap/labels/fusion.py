"""세 모델 결과를 서비스 카테고리 층에서 합치는 참조 구현.

입력 (한 분석 프레임 = 약 1초 창)
- PANNs : 527 시그모이드 확률 (class_labels_indices.csv 순서)
- BEATs : 527 시그모이드 확률 (체크포인트 label_dict 순서 → align_to_panns 로 재정렬)
- CLAP  : 오디오 임베딩 1개 (텍스트 임베딩 행렬은 시작할 때 한 번만 계산)

출력
- detections : 확신도 기준을 넘은 카테고리 목록 (카테고리, 확신도, 표시명, 근거)
- max_conf   : 모든 카테고리 중 최고 확신도 → 기준 미달이면 미확인 효과음 판정으로
- voice_prob : 음성 가능성 → 미확인 효과음 판정에서 사용
- ignored    : 확신도 기준 이상인데 서비스 대상이 아닌 라벨 (디버그용)

규칙 요약 (기존 "dog + bark" 류 결합 규칙을 대체)
1. 같은 카테고리 안의 라벨은 합산하지 않고 max 를 쓴다.
   AudioSet은 Animal→Dog→Bark 가 동시에 켜지는 계층 구조라 합산하면 중복 계산된다.
2. 표시명은 우선순위대로 고른다.
   a. CLAP 세분 클래스가 같은 카테고리이고 카테고리 내 비중이 충분하면 → CLAP 표시명
   b. 아니면 기준을 넘은 AudioSet 라벨 중 가장 깊은(구체적인) 라벨 → 그 표시명
   c. 아니면 카테고리 기본 표시명
3. 검출은 PANNs·BEATs가 하고, CLAP은 "반대"만 한다 (v1.1: 거드는 규칙 삭제)
   - AudioSet 점수 ≥ th_strong                          → 검출 (CLAP 상관없음)
   - th_as ≤ AudioSet 점수 < th_strong                  → CLAP 카테고리 ≥ th_clap_veto 일 때만 검출
                                                          (CLAP 반대 시 버림 → vetoed 에 기록)
   - clap_only 클래스이고 CLAP 확률 ≥ th_clap_only       → 검출 (AudioSet에 없는 소리)
   실측 근거: 낄낄 웃음 → Caw 0.29/Bleat 0.31, 게임 효과음 → Basketball bounce 0.28 로 오판,
   셋 다 CLAP 0.00~0.10. 거드는 규칙은 수류탄을 폭죽으로 띄운 것 외에 효과가 없었음.

모든 기준값은 초기값. 실제 영상으로 모델별 확신도 분포를 본 뒤 재설정한다.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from .audioset_index import LabelInfo, build_label_table, display_of, load_panns_mids
from .categories import CATEGORIES
from .clap_classes import CLAP_CLASSES, CLAP_NEGATIVES


@dataclass
class FusionConfig:
    w_beats: float = 0.6         # BEATs가 AudioSet 성능이 더 높아 비중을 조금 더 줌 (검증 후 조정)
    w_panns: float = 0.4
    th_as: float = 0.25          # 검출 하한 (AudioSet 결합 점수)
    th_strong: float = 0.45      # 이 이상이면 CLAP 확인 없이 통과
    th_clap_veto: float = 0.15   # 약한 구간에서 CLAP 카테고리 확률이 이 미만이면 버림
    th_as_low: float = 0.12      # 구체 표시명 채택 하한 (검출과는 무관)
    clap_logit_scale: float = 100.0  # CLAP 유사도 → softmax 온도 (모델 체크포인트 값 사용 권장)
    th_clap_agree: float = 0.30  # CLAP 표시명 채택에 필요한 CLAP 카테고리 확률
    th_clap_only: float = 0.60   # CLAP 단독 검출 기준 (높게)
    th_clap_display: float = 0.50  # CLAP 표시명 채택: 해당 카테고리 확률 중 이 클래스 비중
    voice_labels_weight: float = 1.0


@dataclass
class Detection:
    category: str
    conf: float
    display: str
    source: str               # "audioset" | "audioset+clap" | "clap_only"
    detail: dict = field(default_factory=dict)


@dataclass
class FusionResult:
    detections: list[Detection]
    max_conf: float
    voice_prob: float
    ignored: list[tuple[str, float]]
    vetoed: list[Detection] = field(default_factory=list)   # CLAP 반대로 버린 것 (디버그용)


def align_to_panns(probs: np.ndarray, model_mids: list[str]) -> np.ndarray:
    """BEATs처럼 인덱스 순서가 다른 모델 출력을 PANNs(csv) 순서로 재정렬."""
    pos = {m: i for i, m in enumerate(model_mids)}
    return np.array([probs[pos[m]] for m in load_panns_mids()], dtype=np.float32)


def build_clap_text_matrix(encode_text) -> np.ndarray:
    """encode_text(list[str]) -> (N, D) 임베딩. 클래스별 프롬프트 평균 후 L2 정규화.
    순서: CLAP_CLASSES 다음 CLAP_NEGATIVES. 시작 시 한 번만 호출."""
    rows = []
    for c in CLAP_CLASSES + CLAP_NEGATIVES:
        e = np.asarray(encode_text(c["prompts"]), dtype=np.float32)
        e = e / np.linalg.norm(e, axis=1, keepdims=True)
        m = e.mean(axis=0)
        rows.append(m / np.linalg.norm(m))
    return np.stack(rows)


class Fusion:
    def __init__(self, cfg: FusionConfig | None = None):
        self.cfg = cfg or FusionConfig()
        self.table: list[LabelInfo] = build_label_table(load_panns_mids())
        self.cat_idx: dict[str, np.ndarray] = defaultdict(list)
        for i, t in enumerate(self.table):
            if t.category:
                self.cat_idx[t.category].append(i)
        self.cat_idx = {k: np.array(v) for k, v in self.cat_idx.items()}
        self.voice_idx = np.array([i for i, t in enumerate(self.table) if t.is_voice])
        self.ignore_idx = np.array([i for i, t in enumerate(self.table) if t.category is None])
        self.n_clap = len(CLAP_CLASSES)

    # ── AudioSet (PANNs + BEATs) ───────────────────────
    def audioset_scores(self, p_panns, p_beats_aligned):
        c = self.cfg
        p = c.w_panns * np.asarray(p_panns) + c.w_beats * np.asarray(p_beats_aligned)
        out = {}
        for cat, idx in self.cat_idx.items():
            sub = p[idx]
            score = float(sub.max())
            # 표시명: 하한을 넘은 라벨 중 가장 깊은 것, 동률이면 확률 높은 것
            ok = idx[sub >= c.th_as_low]
            if len(ok):
                best = max(ok, key=lambda i: (self.table[i].depth, p[i]))
            else:
                best = idx[int(sub.argmax())]
            out[cat] = (score, display_of(self.table[best]), self.table[best].name)
        return p, out

    # ── CLAP ───────────────────────────────────────────
    def clap_scores(self, audio_emb, text_matrix):
        a = np.asarray(audio_emb, dtype=np.float32)
        a = a / np.linalg.norm(a)
        logits = self.cfg.clap_logit_scale * (text_matrix @ a)
        prob = np.exp(logits - logits.max())
        prob /= prob.sum()
        per_cat = defaultdict(float)
        top_in_cat: dict[str, tuple[float, dict]] = {}
        for i, cls in enumerate(CLAP_CLASSES):
            per_cat[cls["cat"]] += float(prob[i])  # softmax라 합산 가능 (AudioSet과 다른 점)
            if cls["cat"] not in top_in_cat or prob[i] > top_in_cat[cls["cat"]][0]:
                top_in_cat[cls["cat"]] = (float(prob[i]), cls)
        neg = {CLAP_NEGATIVES[j]["role"]: 0.0 for j in range(len(CLAP_NEGATIVES))}
        for j, n in enumerate(CLAP_NEGATIVES):
            neg[n["role"]] += float(prob[self.n_clap + j])
        return dict(per_cat), top_in_cat, neg

    # ── 결합 ───────────────────────────────────────────
    def fuse(self, p_panns, p_beats_aligned, audio_emb=None, text_matrix=None) -> FusionResult:
        c = self.cfg
        p, as_scores = self.audioset_scores(p_panns, p_beats_aligned)
        clap_cat, clap_top, clap_neg = ({}, {}, {})
        if audio_emb is not None and text_matrix is not None:
            clap_cat, clap_top, clap_neg = self.clap_scores(audio_emb, text_matrix)

        dets: list[Detection] = []
        vetoed: list[Detection] = []
        max_conf = 0.0
        for cat in CATEGORIES:
            if CATEGORIES[cat]["signal_only"]:
                continue
            s_as, as_disp, as_label = as_scores.get(cat, (0.0, CATEGORIES[cat]["name"], None))
            s_clap = clap_cat.get(cat, 0.0)
            top_p, top_cls = clap_top.get(cat, (0.0, None))

            source = None
            conf = s_as
            have_clap = bool(clap_cat)
            if s_as >= c.th_strong or (s_as >= c.th_as and not have_clap):
                source = "audioset"
            elif s_as >= c.th_as:
                if s_clap >= c.th_clap_veto:
                    source = "audioset+clap"        # 약한 구간, CLAP이 반대하지 않음
                else:
                    vetoed.append(Detection(cat, float(s_as), as_disp, "vetoed",
                                            dict(as_score=round(s_as, 3), as_label=as_label,
                                                 clap_cat=round(s_clap, 3),
                                                 clap_top=top_cls["id"] if top_cls else None)))
            elif top_cls and top_cls["clap_only"] and top_p >= c.th_clap_only:
                source = "clap_only"
                conf = top_p
            max_conf = max(max_conf, conf if source else s_as)
            if not source:
                continue

            # 표시명 선택 a → b → c
            if top_cls and s_clap > 0 and top_p / s_clap >= c.th_clap_display and s_clap >= c.th_clap_agree:
                display = top_cls["ko"]
            elif source == "clap_only":
                display = top_cls["ko"]
            else:
                display = as_disp
            dets.append(Detection(cat, float(conf), display, source,
                                  dict(as_score=round(s_as, 3), as_label=as_label,
                                       clap_cat=round(s_clap, 3),
                                       clap_top=top_cls["id"] if top_cls else None)))

        voice_as = float(p[self.voice_idx].max()) if len(self.voice_idx) else 0.0
        voice_prob = max(voice_as, clap_neg.get("voice", 0.0))
        ignored = [(self.table[i].name, float(p[i])) for i in self.ignore_idx if p[i] >= c.th_as]
        dets.sort(key=lambda d: d.conf, reverse=True)
        return FusionResult(dets, max_conf, voice_prob, ignored, vetoed)
