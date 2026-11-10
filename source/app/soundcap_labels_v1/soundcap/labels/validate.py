"""라벨 매핑 검증: python -m soundcap.labels.validate

1) AudioSet 527개가 전부 정확히 한 곳에 배정됐는지
2) 매핑에 적힌 이름이 실제 AudioSet 이름인지 (오타 검출)
3) CLAP 클래스의 상위 카테고리가 존재하는지, id 중복이 없는지
"""
from collections import Counter

from .audioset_index import build_label_table, load_csv, load_panns_mids, name_tables
from .audioset_map import AUDIOSET_MAP, IGNORE, VOICE_CHECK
from .categories import CATEGORIES
from .clap_classes import CLAP_CLASSES, CLAP_NEGATIVES


def main() -> int:
    errors = []
    real = {n for _, n in load_csv()}

    assigned = []
    for cat, items in AUDIOSET_MAP.items():
        if cat not in CATEGORIES:
            errors.append(f"없는 카테고리: {cat}")
        if CATEGORIES.get(cat, {}).get("signal_only"):
            errors.append(f"신호 분석 전용 카테고리에 라벨 배정됨: {cat}")
        assigned += [it if isinstance(it, str) else it[0] for it in items]
    for names in IGNORE.values():
        assigned += names

    for n in sorted(set(assigned) - real):
        errors.append(f"AudioSet에 없는 이름(오타?): {n}")
    for n, k in Counter(assigned).items():
        if k > 1:
            errors.append(f"중복 배정: {n} ({k}번)")
    for n in sorted(real - set(assigned)):
        errors.append(f"미배정 라벨: {n}")
    for n in VOICE_CHECK:
        if n not in real:
            errors.append(f"VOICE_CHECK 오타: {n}")

    ids = [c["id"] for c in CLAP_CLASSES] + [c["id"] for c in CLAP_NEGATIVES]
    for i, k in Counter(ids).items():
        if k > 1:
            errors.append(f"CLAP id 중복: {i}")
    for c in CLAP_CLASSES:
        if c["cat"] not in CATEGORIES:
            errors.append(f"CLAP {c['id']}: 없는 카테고리 {c['cat']}")
        if not c["prompts"]:
            errors.append(f"CLAP {c['id']}: 프롬프트 없음")

    table = build_label_table(load_panns_mids())
    mapped = [t for t in table if t.category]
    print(f"AudioSet 라벨 {len(table)}개: 서비스 매핑 {len(mapped)} / 제외 {len(table) - len(mapped)}")
    for reason, names in IGNORE.items():
        print(f"  제외-{reason}: {len(names)}")
    per_cat = Counter(t.category for t in mapped)
    used = [c for c in CATEGORIES if not CATEGORIES[c]["signal_only"]]
    as_used = [c for c in used if not CATEGORIES[c]["clap_only_cat"]]
    print(f"서비스 카테고리 {len(CATEGORIES)}개 (라벨 매핑 대상 {len(used)}개)")
    for c in as_used:
        if per_cat[c] == 0:
            errors.append(f"AudioSet 라벨이 하나도 없는 카테고리: {c}")
    clap_per_cat = Counter(c["cat"] for c in CLAP_CLASSES)
    print(f"CLAP 클래스 {len(CLAP_CLASSES)}개 + 네거티브 {len(CLAP_NEGATIVES)}개, "
          f"CLAP 단독 허용 {sum(c.get('clap_only', False) for c in CLAP_CLASSES)}개")
    for c in used:
        if clap_per_cat[c] == 0:
            errors.append(f"CLAP 클래스가 없는 카테고리: {c}")

    if errors:
        print("\n오류:")
        print("\n".join("  - " + e for e in errors))
        return 1
    print("\n검증 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
