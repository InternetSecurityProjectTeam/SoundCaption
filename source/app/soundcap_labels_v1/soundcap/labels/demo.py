"""결합 로직 동작 확인 (모델 없이 가짜 출력으로): python -m soundcap.labels.demo"""
import numpy as np

from .audioset_index import load_csv, load_panns_mids
from .clap_classes import CLAP_CLASSES, CLAP_NEGATIVES
from .fusion import Fusion, align_to_panns, build_clap_text_matrix

names = [n for _, n in load_csv()]
mids = load_panns_mids()
rng = np.random.default_rng(0)
perm = rng.permutation(527)          # BEATs 라벨 순서가 다르다고 가정
beats_mids = [mids[i] for i in perm]


def probs(d):
    p = np.full(527, 0.01, np.float32)
    for k, v in d.items():
        p[names.index(k)] = v
    return p


D, cache = 64, {}
T = build_clap_text_matrix(lambda ps: np.stack([cache.setdefault(s, rng.normal(size=D)) for s in ps]))
ids = [c["id"] for c in CLAP_CLASSES + CLAP_NEGATIVES]


def clap(cid):
    return T[ids.index(cid)] + 0.3 * rng.normal(size=D) / np.sqrt(D)


F = Fusion()
cases = [
    ("개 짖음 + 말소리 (CLAP 없음)", {"Animal": 0.7, "Dog": 0.65, "Bark": 0.55, "Speech": 0.5}, None),
    ("개 짖음 + CLAP '작은 개'", {"Animal": 0.7, "Dog": 0.65, "Bark": 0.55}, "dog_small"),
    ("약한 전화벨 + CLAP도 전화 → 통과", {"Telephone": 0.30}, "phone_vibrate"),
    ("실측 오판 재현: Caw 0.29 + 말소리, CLAP은 웃음 → 버림", {"Caw": 0.29, "Speech": 0.74}, "laugh_cackle"),
    ("실측 오판 재현: Hiss 0.30, CLAP은 가스 분출 → 가스 분출 소리", {"Hiss": 0.30, "Waves, surf": 0.20}, "gas_smoke"),
    ("AudioSet 없음 + CLAP '매미'", {}, "cicada"),
]
for title, d, c in cases:
    r = F.fuse(probs(d), align_to_panns(probs(d)[perm], beats_mids),
               clap(c) if c else None, T if c else None)
    print(f"\n== {title}")
    for x in r.detections:
        print(f"   [{x.display}]  카테고리={x.category}  확신도={x.conf:.2f}  근거={x.source}")
    for v in r.vetoed:
        print(f"   (CLAP 반대로 버림: {v.display} AS {v.detail['as_score']} / CLAP {v.detail['clap_cat']})")
    print(f"   최고 확신도={r.max_conf:.2f}  음성 가능성={r.voice_prob:.2f}  버린 라벨={r.ignored}")
