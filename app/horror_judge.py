"""
horror_judge.py — 👻 공포게임 모드 판정 (numpy 만 사용, 모델 없이 시험 가능)
예능 variety_judge.py v0.12 구조 그대로 (라벨만 horror_labels.py)

라벨 종류마다 검증 장치가 하나씩 (순서가 아니라 라벨별 규칙)
  공통          : 같은 group 의 CLAP softmax 확률을 합쳐서 검출, 표시명은 group 안 1등
  confirm       : CLAP 합 ≥ CLAP_MIN + AudioSet ≥ AS_FLOOR (검증 = AudioSet)
  clap_only     : CLAP 합 ≥ CLAP_SOLO_MIN + 절대 검사 (검증 = CLAP 원래 유사도 최고값 ≥ COS_MIN, 흡수 라벨 제외)
  as_only       : CLAP 선택지에 없음. AudioSet ≥ plus_min 이면 '+'
  AudioSet 강함 : CLAP 이 못 잡아도 AudioSet ≥ AS_STRONG 이면 '+' (확인형만)
  sink          : 확률만 흡수. 표시 안 함, 다른 소리를 지우지 않음
  impulse_min   : 돌발성 ≥ 이 값(dB)이어야 통과 (확인형·클랩 전용 모두)
  음악 분위기   : 배경음악 라벨 문장(일반 + 분위기별) 중 가장 잘 맞은 칸 → 분위기 이름

표시 기호 (v22 와 동일)
  이름*  = CLAP + AudioSet 둘 다 (AudioSet ≥ STAR_MIN)
  이름+  = AudioSet 혼자 강함
  이름   = CLAP 주도
"""

import numpy as np

import horror_labels as G

VERSION = "horror v0.11"
# v0.11: 분석 간격(hop)을 0.5초로 줄일 수 있게 — '횟수'로 세던 규칙을 '초' 기준으로 (set_hop, 총게임 gun v1.12 와 같은 방식)
#        지속음 유지(hold) · 분위기 바꿈(MOOD_CONFIRM) · '배경음악'으로 돌아가기(MOOD_KEEP) 가 간격과 상관없이 같은 시간
# v0.8: 코드 변경 없음 (라벨만 변경, 버전 맞춤)
# v0.7: prompt_names — 라벨 안에서 가장 잘 맞은 문장에 따라 표시 이름만 바꿈 (판정은 그대로). 문 끼익 소리
# v0.6: 분위기 바꿈 — 지금 표시와 '다른' 판단이 연속 MOOD_CONFIRM 번이면 (서로 달라도) 가장 최근 판단으로 바꿈
#       4차 21:11:11~16: 표시는 '추격'인데 판단이 불길한↔긴장감 번갈아 나와 '같은 판단 3번'을 못 채워 6초간 안 바뀜
# v0.5: 분위기 판단은 배경음악이 실제로 잡힌 초에만 반영 — 음악이 없을 때(말소리·드론 구간)의 판단이
#       쌓였다가 나중에 음악이 나오면 엉뚱한 분위기로 뜨던 문제 (3차 21:05:24 '추격 음악')
# v0.4: 코드 변경 없음 (라벨만 변경, 버전 맞춤)
# v0.3: 디버그에 WATCH 라벨(발소리·문·노크·괴물·비명)의 CLAP 확률·자기 cos 를 항상 기록
# v0.2 (1차 테스트 반영 — 게임 방송: 말소리가 거의 항상 0.6 이상이라 AudioSet 이 발소리·노크를 0.00 으로 들음)
#   - solo_cos: 대체 경로를 '그 라벨 자신의' CLAP 원래 유사도 ≥ solo_cos 로 확인 (발소리·노크)
#   - veto / veto_min: 이 AudioSet 라벨이 veto_min 이상이면 표시 안 함 (키보드 타자 → 노크·발소리 방지)
#   - need_mood: 분위기 판단이 있을 때만 표시 (배경음악 — 그냥 '배경음악'은 안 띄움)
# v0.1 (2026-10-14): 예능 variety_judge v0.12 복제. 판정 코드 변경 없음


def impulse_db(stereo, sr):
    """돌발성: 2초 구간에서 가장 센 10ms 순간이 보통 수준(중앙값)보다 몇 dB 튀었는지.
    고음 위주로 보기 위해 샘플 차분(간단한 고역 통과)을 씀"""
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


class HorrorJudge:
    def __init__(self, encode, scale, csv_names, warn=print):
        """encode(list[str]) -> (N, D) 문장 임베딩, scale = CLAP logit scale, csv_names = AudioSet 527 이름(순서)"""
        # as_only(AudioSet 단독) 라벨은 CLAP 선택지에 넣지 않음 — CLAP 확률을 빼앗지 않게
        self.keys = [k for k, v in G.LABELS.items() if v["kind"] != "as_only"]
        self.scale = float(scale)
        self.groups = G.groups()
        self.kind = {g: G.LABELS[m[0]]["kind"] for g, m in self.groups.items()}
        self.form = {g: G.LABELS[m[0]]["form"] for g, m in self.groups.items()}

        # 라벨 점수 = 그 라벨 문장들 중 '가장 잘 맞는 문장'의 유사도
        self.P = _unit(np.concatenate([encode(G.LABELS[k]["prompts"]) for k in self.keys]))   # (문장 수, D)
        self.owner = np.concatenate([[i] * len(G.LABELS[k]["prompts"]) for i, k in enumerate(self.keys)])
        self.idx = {k: i for i, k in enumerate(self.keys)}
        self.sink = np.array([G.LABELS[k]["kind"] == "sink" for k in self.keys])

        # 음악 분위기 = 배경음악(mood=True) 라벨 문장 중 가장 잘 맞은 문장의 분위기
        #   칸 0 = 일반('배경음악'), 칸 1.. = MUSIC_MOODS 순서
        self.mood_key = next((k for k in self.keys if G.LABELS[k].get("mood")), None)
        self.mood_names = list(getattr(G, "MUSIC_MOODS", {}) or {})
        if self.mood_key and self.mood_names:
            cls_of = {p: 0 for p in getattr(G, "MUSIC_GENERIC", [])}
            for j, n in enumerate(self.mood_names, 1):
                for p_ in G.MUSIC_MOODS[n]:
                    cls_of[p_] = j
            self.mood_rows = np.where(self.owner == self.idx[self.mood_key])[0]
            self.mood_cls = np.array([cls_of.get(p_, 0) for p_ in G.LABELS[self.mood_key]["prompts"]])
        else:
            self.mood_rows = None
        self.mood_shown, self.mood_cand, self.mood_cnt, self.mood_unsure = None, None, 0, 0
        self.mood_diff = 0                                       # v0.6: 표시와 다른 판단 연속 횟수

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
        self.veto_idx = {g: lookup([n for m in mem for n in G.LABELS[m].get("veto", [])])
                         for g, mem in self.groups.items()}
        self.held = {}                                           # 지속음 유지: group → [남은 횟수, 마지막 표시]
        self.music_as = [i for g, mem in self.groups.items() if G.LABELS[mem[0]].get("mood")
                         for i in self.as_idx[g]]                # 음악 세기를 볼 AudioSet 칸
        self.csv_names = list(csv_names)
        self.set_hop(1.0)
        if missing:
            warn(f"[공포] AudioSet 에 없는 이름 {len(missing)}개는 무시: {sorted(missing)}")

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
        """분석 간격(초)에 맞춰 횟수 기준을 초 기준으로 바꿈 (간격 1초면 예전과 똑같음)"""
        self.hop = float(hop)
        self.n_confirm = max(1, int(round(G.MOOD_CONFIRM / self.hop)))   # 1초 → 3회, 0.5초 → 6회 (= 3초)
        self.n_keep = max(1, int(round(G.MOOD_KEEP / self.hop)))         # 1초 → 5회, 0.5초 → 10회 (= 5초)

    def _hold_n(self, h):
        """라벨 hold(1초 간격 기준 횟수) → 지금 간격의 횟수. 마지막으로 잡힌 뒤 (h-1)초 더 표시"""
        return max(1, int(round((h - 1) / self.hop)) + 1)

    def reset(self):
        """재생이 멈췄을 때(영상 전환·일시정지) 이전 장면 상태를 지움 — 지속음 유지(HOLD)·분위기 표시"""
        self.held.clear()
        self.mood_shown, self.mood_cand, self.mood_cnt, self.mood_unsure = None, None, 0, 0
        self.mood_diff = 0

    def mood(self, pc, music=None, speech=0.0, music_on=True):
        """-> (분위기 이름 또는 None, 디버그 dict)
        배경음악 라벨 문장들(일반 + 분위기별)의 유사도를 칸별 최대 → softmax. 이번 2초만 봄 (누적 없음)
        이번 판단 = 분위기 이름 (아래 조건을 다 만족) 또는 None('판단 없음')
          ① 음악 − 말소리 ≥ MOOD_GAP  ② 1등이 분위기 칸이고 ≥ MOOD_MIN  ③ 1등 − 2등 ≥ MOOD_LEAD
        표시 규칙
          - 판단 없음: 표시 유지. 단 MOOD_KEEP 초 넘게 계속 판단 없음이면 '배경음악'
          - 지금 '배경음악'이면: 분위기 판단이 나오는 즉시 그 분위기
          - 다른 분위기로 바꾸기: 같은 분위기 판단이 MOOD_CONFIRM 번 연속(판단 없음은 건너뜀), 또는 확률 ≥ MOOD_STRONG 한 번"""
        if self.mood_rows is None:
            return None, {}
        labels = ["배경음악"] + self.mood_names
        mc = np.full(len(labels), -1.0, dtype=np.float32)
        np.maximum.at(mc, self.mood_cls, pc[self.mood_rows])
        z = self.scale * mc
        mp = np.exp(z - z.max())
        mp /= mp.sum()
        order = np.argsort(-mp)
        p1, p2 = float(mp[order[0]]), float(mp[order[1]])
        gap = None if music is None else music - speech
        why = []
        if order[0] == 0:
            why.append("일반 문장이 1등")
        if gap is not None and gap < G.MOOD_GAP:
            why.append(f"음악−말소리 {gap:.2f}<{G.MOOD_GAP}")
        if p1 < G.MOOD_MIN:
            why.append(f"1등 {p1:.2f}<{G.MOOD_MIN}")
        if p1 - p2 < G.MOOD_LEAD:
            why.append(f"1·2등 차 {p1 - p2:.2f}<{G.MOOD_LEAD}")
        now = None if why else labels[order[0]]
        if not music_on:                                         # v0.5: 배경음악이 안 잡힌 초는 판단에 안 씀
            why.append("배경음악 없음")
            now = None

        if now is None:
            self.mood_unsure += 1
            if self.mood_unsure > self.n_keep:
                self.mood_shown = None
        else:
            self.mood_unsure = 0
            if self.mood_shown is None or now == self.mood_shown:
                self.mood_shown, self.mood_cnt, self.mood_diff = now, 0, 0
            else:
                self.mood_cnt = self.mood_cnt + 1 if now == self.mood_cand else 1
                self.mood_cand = now
                self.mood_diff += 1
                if self.mood_cnt >= self.n_confirm or p1 >= G.MOOD_STRONG or self.mood_diff >= self.n_confirm:
                    self.mood_shown, self.mood_cnt, self.mood_diff = now, 0, 0
        top = [(labels[i], float(mp[i])) for i in order[:3]]
        pending = self.mood_cand if (self.mood_cnt > 0 and self.mood_cand != self.mood_shown) else None
        return self.mood_shown, dict(now=top, gap=gap, why=why, pending=pending, unsure=self.mood_unsure)

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
        clap_ok = best_cos >= G.COS_MIN                          # 절대 검사

        av = self.combine_audioset(as_raw)
        have_as = av is not None
        speech = float(av[self.speech_idx].max()) if have_as and self.speech_idx else 0.0
        music = float(av[self.music_as].max()) if have_as and self.music_as else None
        # v0.5: 배경음악 라벨이 이번 초에 잡히는지 먼저 봄 (분위기 조건은 빼고)
        music_on = False
        if self.mood_key and have_as:
            Lm = G.LABELS[self.mood_key]
            gm = Lm["group"]
            pgm = float(sum(p[self.idx[m]] for m in self.groups[gm]))
            asm = float(av[self.as_idx[gm]].max()) if self.as_idx[gm] else 0.0
            music_on = ((pgm >= Lm.get("min", G.CLAP_MIN) and asm >= Lm.get("as_min", G.AS_FLOOR))
                        or asm >= Lm.get("plus_min", G.AS_STRONG))
        mood_name, mood_dbg = self.mood(pc, music, speech, music_on)

        def name(key):
            L = G.LABELS[key]
            return mood_name if (L.get("mood") and mood_name) else L["name"]

        instant, sustained, tag_scores, rejected = [], [], {}, []
        for g, mem in self.groups.items():
            kind = self.kind[g]
            if kind == "sink":
                continue
            if kind == "as_only":                                # AudioSet 단독: CLAP 은 안 봄
                asg = float(av[self.as_idx[g]].max()) if have_as and self.as_idx[g] else 0.0
                tag_scores[g] = asg
                pmin = G.LABELS[mem[0]].get("plus_min", G.AS_STRONG)
                if asg >= pmin:
                    item = (g, name(mem[0]), asg, "+")
                    (sustained if self.form[g] == "sustained" else instant).append(item)
                elif asg >= 0.10:
                    rejected.append((G.LABELS[mem[0]]["name"], asg, f"AudioSet 단독 {asg:.2f}<{pmin}"))
                continue
            mi = [self.idx[m] for m in mem]
            pg = float(p[mi].sum())                              # 묶음 합
            top = mem[int(np.argmax(p[mi]))]
            asg = float(av[self.as_idx[g]].max()) if have_as and self.as_idx[g] else 0.0
            tag_scores[g] = asg

            L = G.LABELS[mem[0]]
            confirm = kind == "confirm" and have_as
            cmin = L.get("min", G.CLAP_MIN if confirm else G.CLAP_SOLO_MIN)
            amin = L.get("as_min", G.AS_FLOOR)
            pmin = L.get("plus_min", G.AS_STRONG)
            if confirm:                                          # 검증 = AudioSet 하한
                passed = pg >= cmin and asg >= amin
            else:                                                # 검증 = 절대 검사
                passed = clap_ok and pg >= cmin
            # impulse_min — '툭 튀는' 소리여야 하는 라벨 (쾅·점프 스케어)
            imin = L.get("impulse_min")
            imp_fail = passed and imin is not None and (impulse_db is None or impulse_db < imin)
            passed = passed and not imp_fail
            # 확인형인데 AudioSet 이 음악에 묻혀 못 들을 때: CLAP 높음 + 돌발성 + 절대 검사로 대신 확인 (노크)
            # v0.2: solo_cos 가 있으면 전체 최고 cos 대신 '이 라벨 자신의' cos 로 절대 검사
            own_cos = float(cos[self.idx[top]])
            cos_ok = own_cos >= L["solo_cos"] if "solo_cos" in L else clap_ok
            solo = (not passed and confirm and cos_ok and "solo_min" in L and pg >= L["solo_min"]
                    and (not L.get("need_impulse") or (impulse_db is not None and impulse_db >= G.IMPULSE_MIN_DB)))

            # v0.2: 거부 — 키보드 타자처럼 헷갈리는 소리를 AudioSet 이 들으면 표시 안 함
            vg = float(av[self.veto_idx[g]].max()) if have_as and self.veto_idx[g] else 0.0
            if (passed or solo) and vg >= L.get("veto_min", 1.0):
                rejected.append((G.LABELS[top]["name"], pg, f"거부 AudioSet {vg:.2f}≥{L['veto_min']}"))
                continue
            # v0.2: 분위기 판단이 없으면 표시 안 함 (배경음악)
            if L.get("need_mood") and not mood_name:
                if passed or solo or (kind == "confirm" and have_as and self.as_idx[g] and asg >= pmin):
                    rejected.append((L["name"], max(pg, asg), "분위기 판단 없음"))
                continue

            if passed or solo:
                shown = name(top)
                pn = G.LABELS[top].get("prompt_names")           # v0.7: 1등 문장에 따라 이름만 바꿈
                if pn:
                    rows = np.where(self.owner == self.idx[top])[0]
                    bp = G.LABELS[top]["prompts"][int(np.argmax(pc[rows]))]
                    shown = pn.get(bp, shown)
                item = (g, shown, pg, "*" if have_as and asg >= G.STAR_MIN else "")
            elif kind == "confirm" and have_as and self.as_idx[g] and asg >= pmin:
                # AudioSet 혼자 '+' 는 확인형만
                item = (g, name(mem[0]), asg, "+")
            else:
                if pg >= G.NEAR_MISS:                            # 디버그: 왜 떨어졌는지
                    if pg < cmin:
                        why = f"CLAP {pg:.2f}<{cmin}"
                    elif imp_fail:
                        why = f"돌발 {impulse_db if impulse_db is not None else 0:.0f}dB<{L['impulse_min']:.0f}"
                    elif confirm:
                        why = f"보조 {asg:.2f}<{amin}"
                        if "solo_min" in L and pg >= L["solo_min"]:
                            why += f", 돌발 {impulse_db if impulse_db is not None else 0:.0f}dB<{G.IMPULSE_MIN_DB:.0f}"
                    else:
                        why = f"cos {best_cos:.2f}<{G.COS_MIN}"
                    rejected.append((G.LABELS[top]["name"], pg, why))
                continue
            (sustained if self.form[g] == "sustained" else instant).append(item)

        # 지속음 유지: 한 번 잡힌 지속음은 hold 번 동안 안 잡혀도 계속 표시 (깜빡임 방지)
        seen = {it[0] for it in sustained}
        for it in sustained:
            self.held[it[0]] = [self._hold_n(G.LABELS[self.groups[it[0]][0]].get("hold", G.HOLD_SEC)), it]
        for g in list(self.held):
            if g in seen:
                continue
            self.held[g][0] -= 1
            if self.held[g][0] > 0:
                sustained.append(self.held[g][1])
            else:
                del self.held[g]

        instant.sort(key=lambda x: -x[2])
        sustained.sort(key=lambda x: -x[2])
        instant, sustained = instant[:G.MAX_INSTANT], sustained[:G.MAX_SUSTAINED]

        order = np.argsort(-p)[:3]
        rejected.sort(key=lambda x: -x[1])
        # CLAP 1등 라벨에서 가장 잘 맞은 문장 (어느 문장이 소리를 끌어오는지 보려고)
        i0 = int(order[0])
        sidx = np.where(self.owner == i0)[0]
        best_prompt = G.LABELS[self.keys[i0]]["prompts"][int(np.argmax(pc[sidx]))] if len(sidx) > 1 else None
        dbg = dict(best_cos=best_cos, speech=speech, rejected=rejected, impulse_db=impulse_db, mood=mood_dbg,
                   best_prompt=best_prompt,
                   clap_top=[(G.LABELS[self.keys[i]]["name"], float(p[i]), float(cos[i])) for i in order])
        dbg["watch"] = [(G.LABELS[k]["name"], float(p[self.idx[k]]), float(cos[self.idx[k]]))
                        for k in getattr(G, "WATCH", []) if k in self.idx]
        if have_as:
            ai = np.argsort(-av)[:3]
            dbg["as_top"] = [(self.csv_names[i], float(av[i])) for i in ai]
        return dict(instant=instant, sustained=sustained, items=instant + sustained,
                    tag_scores=tag_scores, speech=speech, debug=dbg)
