"""
gun_judge.py — 총게임 모드 판정 (numpy 만 사용, 모델 없이 시험 가능)

라벨 종류마다 검증 장치가 하나씩 (순서가 아니라 라벨별 규칙)
  공통          : 같은 group 의 CLAP softmax 확률을 합쳐서 검출, 표시명은 group 안 1등 (v1.1 부터 group 은 전부 라벨 1개)
  confirm       : CLAP 합 ≥ CLAP_MIN + AudioSet ≥ AS_FLOOR (검증 = AudioSet. AudioSet 이 거의 0 이면 CLAP 찐빠로 버림)
  clap_only     : CLAP 합 ≥ CLAP_SOLO_MIN + 절대 검사 (검증 = CLAP 원래 유사도 최고값 ≥ COS_MIN, 흡수 라벨 제외)
                  AudioSet 이 확인해 줄 수 없는 소리라, CLAP 이 억지로 고른 건지를 유사도로 거름
  AudioSet 강함 : CLAP 이 못 잡아도 AudioSet ≥ AS_STRONG 이면 '+' 로 표시
  sink          : 확률만 흡수. 표시 안 함, 다른 소리를 지우지 않음

표시 기호 (v22 와 동일)
  이름*  = CLAP + AudioSet 둘 다 (AudioSet ≥ STAR_MIN)
  이름+  = AudioSet 혼자 강함
  이름   = CLAP 주도
"""

import numpy as np

import gun_labels as G

VERSION = "gun v1.12"
# v1.12: 분석 간격(hop)을 0.5초로 줄일 수 있게 — 지속음 규칙을 '횟수'가 아니라 '초' 기준으로 (set_hop)
#        시작 = SUS_START_SEC 초 이상 연속 (간격 1초면 2회, 0.5초면 3회) · 끝나기 전 표시 = SUS_GRACE 초
# v1.8: 지속음 유지 시간을 라벨별로 (hold, 예능 v0.8 과 같은 방식). 없으면 HOLD_SEC
# v1.9: 코드 변경 없음 (라벨 파일에 헬기·화염병·수류탄 핀 추가, 버전만 맞춤)
# v1.10: 말소리 가드 — AudioSet 말소리 ≥ SPEECH_GUARD 이면 '말하는 중'. 라벨에 talk_as_min / talk_solo_min 이 있으면
#        (총성) AudioSet 하한·solo 경로 CLAP 기준을 올리고, solo 경로 돌발성 기준도 IMPULSE_TALK_DB 로 올림
# v1.11 (2026-10-21 테스트 반영 — 원칙: 틀린 정보보다 적은 정보. v1.10 보다 조건을 더하기만 함)
#   - 지속음: 시작·유지 분리 (_sustain). 예전 hold(한 번 뜨면 N초 유지)는 없앰
#       시작: 2초 연속 잡히고, 그중 1번 이상 CLAP 이 잡은 것(* 또는 CLAP 주도)
#             예외: 2초 모두 AudioSet ≥ SUS_START_AS (AudioSet 이 아주 확실할 때) / AudioSet 단독(as_only) 라벨은 2초 연속만
#       유지: 이번에도 잡혔고, CLAP 이 잡았거나 AudioSet 이 그 이벤트 최고점의 SUS_KEEP_RATIO 이상
#       종료: 유지 조건이 깨지면 SUS_GRACE 초만 더 보여 주고 끝 (깜빡임 방지)
#   - 총성 solo 경로: CLAP 원래 유사도(총성 문장 cos) ≥ solo_cos 도 필요
#       확률은 '보기 중 1등'이라 어느 보기에도 안 맞는 소리도 높게 나옴 → 실제로 총성과 닮았는지 절대값으로 확인
#       (13:39:09 오표시: 확률 0.59 인데 cos 0.22 / AudioSet 까지 총성이라 한 순간의 cos 는 0.33~0.51)


def impulse_db(stereo, sr):
    """돌발성: 2초 구간에서 가장 센 10ms 순간이 보통 수준(중앙값)보다 몇 dB 튀었는지.
    고음 위주로 보기 위해 샘플 차분(간단한 고역 통과)을 씀 — 총소리의 날카로운 시작은 음악·말소리보다 고음이 확 튐"""
    x = np.asarray(stereo, dtype=np.float32)
    if x.ndim == 2:
        x = x.mean(axis=1)
    if x.size < 2:
        return 0.0
    if np.abs(x).max() > 2.0:                                    # int16 그대로 들어온 경우
        x = x / 32768.0
    d = np.diff(x)
    n = max(1, int(sr * 0.01))
    m = len(d) // n
    if m < 4:
        return 0.0
    e = (d[:m * n].reshape(m, n) ** 2).mean(axis=1) + 1e-12
    return float(10 * np.log10(e.max() / np.median(e)))


def _unit(x):
    x = np.asarray(x, dtype=np.float32)
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-9)


class GunJudge:
    def __init__(self, encode, scale, csv_names, warn=print):
        """encode(list[str]) -> (N, D) 문장 임베딩, scale = CLAP logit scale, csv_names = AudioSet 527 이름(순서)"""
        # as_only(AudioSet 단독) 라벨은 CLAP 선택지에 넣지 않음 — CLAP 확률을 빼앗지 않게
        self.keys = [k for k, v in G.LABELS.items() if v["kind"] != "as_only"]
        self.scale = float(scale)
        self.groups = G.groups()
        self.kind = {g: G.LABELS[m[0]]["kind"] for g, m in self.groups.items()}
        self.form = {g: G.LABELS[m[0]]["form"] for g, m in self.groups.items()}

        # v1.4: 라벨 점수 = 그 라벨 문장들 중 '가장 잘 맞는 문장'의 유사도 (평균 → 최대)
        #   평균이면 문장을 늘릴수록 뜻이 흐려지고(작은 '틱틱' 총소리 문장을 넣으면 큰 총성 쪽이 약해짐),
        #   라벨을 여러 개로 나누면 확률을 여러 칸이 나눠 가져 폭발까지 끌어감(v1.0 문제).
        #   최대값은 라벨 한 칸을 유지하면서 여러 종류의 소리를 받아줌
        self.P = _unit(np.concatenate([encode(G.LABELS[k]["prompts"]) for k in self.keys]))   # (문장 수, D)
        self.owner = np.concatenate([[i] * len(G.LABELS[k]["prompts"]) for i, k in enumerate(self.keys)])
        self.T = np.stack([_unit(self.P[self.owner == i].mean(axis=0)) for i in range(len(self.keys))])  # 시험용
        self.idx = {k: i for i, k in enumerate(self.keys)}
        self.sink = np.array([G.LABELS[k]["kind"] == "sink" for k in self.keys])

        pos = {n: i for i, n in enumerate(csv_names)}
        missing = set()

        def lookup(names):
            out = []
            for n in names:
                if n in pos:
                    out.append(pos[n])
                else:
                    missing.add(n)
            return sorted(set(out))

        self.as_idx = {g: lookup([n for m in mem for n in G.LABELS[m]["audioset"]])
                       for g, mem in self.groups.items()}
        self.speech_idx = lookup(G.SPEECH_AUDIOSET)
        self.sus = {}                                            # v1.11 지속음 상태: group → dict(active, streak, peak, miss, item)
        self.sus_groups = [g for g in self.groups if self.form[g] == "sustained" and self.kind[g] != "sink"]
        self.csv_names = list(csv_names)
        self.set_hop(1.0)
        if missing:
            warn(f"[총게임] AudioSet 에 없는 이름 {len(missing)}개는 무시: {sorted(missing)}")

    # ------------------------------------------------------------------
    @staticmethod
    def combine_audioset(raw):
        """raw: {모델 이름: 527 점수(csv 순서)} → BEATs:PANNs = 0.6:0.4 (하나뿐이면 그대로)"""
        if not raw:
            return None
        beats = [v for n, v in raw.items() if "beat" in n.lower()]
        others = [v for n, v in raw.items() if "beat" not in n.lower()]
        if beats and others:
            return G.BEATS_WEIGHT * np.mean(beats, axis=0) + (1 - G.BEATS_WEIGHT) * np.mean(others, axis=0)
        return np.mean(beats or others, axis=0)

    def set_hop(self, hop):
        """v1.12: 분석 간격(초)에 맞춰 지속음 시작·종료 횟수를 정함 (규칙은 초 기준)"""
        self.hop = float(hop)
        self.n_start = max(2, int(round(G.SUS_START_SEC / self.hop)) + 1)   # 1초 간격 → 2회, 0.5초 → 3회
        self.n_grace = max(1, int(round(G.SUS_GRACE / self.hop)))           # 1초 간격 → 1회, 0.5초 → 2회

    def _sustain(self, cand, rejected):
        """v1.11 지속음 시작·유지 분리 (v1.12: 초 기준). cand: group → (표시, 'clap'/'plus', AudioSet 점수)
        화면에 나오는 순간은 전부 'v1.10 에서도 통과한 순간' 또는 '끝나기 직전 SUS_GRACE 초' 뿐"""
        out = []
        for g in self.sus_groups:
            st = self.sus.setdefault(g, dict(active=False, streak=[], peak=0.0, miss=0, item=None))
            c = cand.get(g)
            name = G.LABELS[self.groups[g][0]]["name"]
            if st["active"]:
                if c is not None and (c[1] == "clap" or c[2] >= G.SUS_KEEP_RATIO * st["peak"]):
                    st.update(peak=max(st["peak"], c[2]), miss=0, item=c[0])      # 유지
                    out.append(c[0])
                    continue
                st["miss"] += 1
                if st["miss"] <= self.n_grace:                                     # 끝나기 전 잠깐 더
                    out.append(st["item"])
                    why = (f"지속음 약해짐 {c[2]:.2f}<최고 {st['peak']:.2f}의 {G.SUS_KEEP_RATIO:.0%}"
                           if c is not None else "지속음 안 잡힘")
                    left = (self.n_grace - st["miss"] + 1) * self.hop
                    rejected.append((name, c[2] if c else 0.0, why + f" → 남은 표시 {left:.1f}초"))
                    continue
                st.update(active=False, peak=0.0, miss=0, item=None, streak=[])    # 종료 (이번 결과는 새 시작 후보로)
            if c is None:
                st["streak"] = []
                continue
            s = st["streak"] = (st["streak"] + [c])[-self.n_start:]
            ok = len(s) >= self.n_start and (self.kind[g] == "as_only" or any(x[1] == "clap" for x in s)
                                             or min(x[2] for x in s) >= G.SUS_START_AS)
            if ok:                                                                 # 시작
                st.update(active=True, peak=max(x[2] for x in s), miss=0, item=c[0], streak=[])
                out.append(c[0])
            else:
                why = (f"지속음 시작 대기 ({len(s)}/{self.n_start}회 — {G.SUS_START_SEC:.0f}초 이상 연속 필요)"
                       if len(s) < self.n_start else
                       f"지속음 시작 안 함 (CLAP 확인 없음, AudioSet {min(x[2] for x in s):.2f}<{G.SUS_START_AS})")
                rejected.append((name, c[2], why))
        return out

    def judge(self, audio_emb, as_raw=None, impulse_db=None):
        """impulse_db: 돌발성(신호 분석). 없으면(None) 돌발성이 필요한 경로는 막힘"""
        a = _unit(audio_emb).reshape(-1)
        pc = self.P @ a                                          # 문장별 유사도
        cos = np.full(len(self.keys), -1.0, dtype=np.float32)
        np.maximum.at(cos, self.owner, pc)                       # 라벨별 최대
        z = self.scale * cos
        p = np.exp(z - z.max())
        p /= p.sum()
        best_cos = float(cos[~self.sink].max())
        clap_ok = best_cos >= G.COS_MIN                          # 절대 검사 (clap_only 전용)

        av = self.combine_audioset(as_raw)
        have_as = av is not None
        speech = float(av[self.speech_idx].max()) if have_as and self.speech_idx else 0.0

        instant, sustained, tag_scores, rejected = [], [], {}, []
        cand = {}                                                # v1.11: 지속음 후보 group → (표시, 'clap'/'plus', AudioSet 점수)
        for g, mem in self.groups.items():
            kind = self.kind[g]
            if kind == "sink":
                continue
            if kind == "as_only":                                # AudioSet 단독: CLAP 은 안 봄
                asg = float(av[self.as_idx[g]].max()) if have_as and self.as_idx[g] else 0.0
                tag_scores[g] = asg
                pmin = G.LABELS[mem[0]].get("plus_min", G.AS_STRONG)
                if asg >= pmin:
                    item = (g, G.LABELS[mem[0]]["name"], asg, "+")
                    if self.form[g] == "sustained":
                        cand[g] = (item, "plus", asg)
                    else:
                        instant.append(item)
                elif asg >= 0.10:
                    rejected.append((G.LABELS[mem[0]]["name"], asg, f"AudioSet 단독 {asg:.2f}<{pmin}"))
                continue
            mi = [self.idx[m] for m in mem]
            pg = float(p[mi].sum())                              # ② 묶음 합
            top = mem[int(np.argmax(p[mi]))]
            asg = float(av[self.as_idx[g]].max()) if have_as and self.as_idx[g] else 0.0
            tag_scores[g] = asg

            L = G.LABELS[mem[0]]
            confirm = kind == "confirm" and have_as
            # 라벨에 'min' 이 있으면 그 라벨만 기준을 따로 (확신도 높을 때만 내보낼 소리)
            cmin = L.get("min", G.CLAP_MIN if confirm else G.CLAP_SOLO_MIN)
            amin = L.get("as_min", G.AS_FLOOR)                   # 라벨별 AudioSet 하한
            pmin = L.get("plus_min", G.AS_STRONG)                # 라벨별 AudioSet 혼자 기준
            talking = speech >= G.SPEECH_GUARD                   # v1.10: 말하는 중이면 talk_* 기준 적용 (AudioSet 이 있을 때만)
            if talking:
                amin = max(amin, L.get("talk_as_min", amin))
            smin = L.get("talk_solo_min", L.get("solo_min", 1.0)) if talking else L.get("solo_min", 1.0)
            imin = G.IMPULSE_TALK_DB if talking else G.IMPULSE_MIN_DB
            gcos = float(cos[mi].max())                          # v1.11: 이 group 문장과의 원래 유사도 (절대값)
            scos = L.get("solo_cos")                             # v1.11: solo 경로 cos 기준 (총성 0.25)
            if confirm:                                          # 검증 = AudioSet 하한 (절대 검사 안 씀)
                passed = pg >= cmin and asg >= amin
            else:                                                # 검증 = 절대 검사 (AudioSet 이 없으면 confirm 도 여기로)
                passed = clap_ok and pg >= cmin
            # 확인형인데 AudioSet 이 음악에 묻혀 못 들을 때: CLAP 높음 + 돌발성(신호 분석)으로 대신 확인
            solo = (not passed and confirm and "solo_min" in L and pg >= smin
                    and (not L.get("need_impulse") or (impulse_db is not None and impulse_db >= imin))
                    and (scos is None or gcos >= scos))

            if passed or solo:
                item = (g, G.LABELS[top]["name"], pg, "*" if have_as and asg >= G.STAR_MIN else "")
            elif kind == "confirm" and have_as and self.as_idx[g] and asg >= pmin:
                # AudioSet 혼자 '+' 는 확인형만. 클랩 전용은 대응 AudioSet 라벨(Clicking·Whoosh 등)이
                # 원래 소리와 다른 넓은 라벨이라, 혼자 뜨게 두면 아무 딸깍·휙 소리마다 장전·총알로 뜸
                item = (g, G.LABELS[mem[0]]["name"], asg, "+")
            else:
                if pg >= G.NEAR_MISS:                            # 디버그: 왜 떨어졌는지
                    if pg < cmin:
                        why = f"CLAP {pg:.2f}<{cmin}"
                    elif confirm:
                        why = f"보조 {asg:.2f}<{amin}" + (" (말하는 중)" if talking else "")
                        if "solo_min" in L and pg >= smin:              # solo 경로 후보였는데 떨어진 이유
                            imp = impulse_db if impulse_db is not None else 0
                            if L.get("need_impulse") and imp < imin:
                                why += f", 돌발 {imp:.0f}dB<{imin:.0f}"
                            if scos is not None and gcos < scos:
                                why += f", solo cos {gcos:.2f}<{scos}"
                    else:
                        why = f"cos {best_cos:.2f}<{G.COS_MIN}"
                    rejected.append((G.LABELS[top]["name"], pg, why))
                continue
            if self.form[g] == "sustained":
                cand[g] = (item, "clap" if (passed or solo) else "plus", asg)
            else:
                instant.append(item)

        sustained = self._sustain(cand, rejected)                # v1.11: 지속음 시작·유지 분리

        instant.sort(key=lambda x: -x[2])
        sustained.sort(key=lambda x: -x[2])
        instant, sustained = instant[:G.MAX_INSTANT], sustained[:G.MAX_SUSTAINED]

        order = np.argsort(-p)[:3]
        rejected.sort(key=lambda x: -x[1])
        dbg = dict(best_cos=best_cos, speech=speech, rejected=rejected, impulse_db=impulse_db,
                   clap_top=[(G.LABELS[self.keys[i]]["name"], float(p[i]), float(cos[i])) for i in order])
        if have_as:
            ai = np.argsort(-av)[:3]
            dbg["as_top"] = [(self.csv_names[i], float(av[i])) for i in ai]
        return dict(instant=instant, sustained=sustained, items=instant + sustained,
                    tag_scores=tag_scores, speech=speech, debug=dbg)
