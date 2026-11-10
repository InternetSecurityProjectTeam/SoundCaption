"""
sound_live.py (v16) — CLAP / MS-CLAP / EfficientAT / PANNs 를 골라서 같이 돌리기

모델 고르기 (--models, 쉼표로 여러 개)
  clap    : LAION CLAP (laion/clap-htsat-unfused)         라벨 직접 지정
  msclap  : Microsoft CLAP 2023                           라벨 직접 지정 (CLAP과 같은 라벨 사용)
  at      : EfficientAT (mn10_as, AudioSet 527클래스)      정해진 클래스, 클래스별 점수
  panns   : PANNs CNN14 (AudioSet 527클래스)               정해진 클래스, 클래스별 점수

합치는 방식
  1) CLAP 계열(clap, msclap)이 여러 개면 → 같은 라벨의 확률을 평균 → 메인 순위
  2) 클래스 모델(at, panns)이 여러 개면 → 같은 표시 항목 점수를 평균 → 보조
  3) 메인 + 보조:
       - 메인 소리를 보조도 잡았으면 '*' 표시 + 점수 가산 (FAMILY에 적은 이름은 같은 계열로 인정)
       - 보조만 잡은 소리는 점수가 높을 때만 '+' 표시로 추가 (music은 추가 안 함)

실행 예 (실시간):
    python sound_live.py --models clap
    python sound_live.py --models clap,msclap
    python sound_live.py --models clap,at
    python sound_live.py --models clap,msclap,at
    python sound_live.py --models clap,msclap,panns
    python sound_live.py --models clap,msclap,at,panns
파일로 같은 소리 비교:
    python sound_live.py --models clap,msclap,at --file test_134235.wav --silence 0.003 --csv out.csv

설치는 파일 맨 아래 INSTALL 설명 참고
종료: Ctrl + C
"""

import argparse
import csv
import os
import sys
import threading
import time
from math import gcd, ceil

import numpy as np
from scipy.signal import resample_poly

VERSION = "v16.1"

# ======================================================================
# 공통 설정
# ======================================================================
WINDOW_SEC = 2.0          # 분석에 사용할 오디오 길이(초)
HOP_SEC = 1.0             # 분석 주기(초)
SILENCE_PEAK_RMS = 0.05   # 2초 중 가장 큰 50ms 음량이 이보다 작으면 무음 (--silence로 변경)
CENTER_DB = 2.0           # |L/R 차이(dB)| 가 이 값보다 작으면 '중앙'
TOP_K = 3                 # 최대 출력 개수

# 라벨별로 더 엄격한 기준 (자주 잘못 뜨는 소리) — 모든 모델 공통
LABEL_MIN_P = {
    "dog barking": 0.30,
}

# ======================================================================
# CLAP 계열 (clap, msclap) — 같은 라벨 목록 사용
# ======================================================================
# 범용 라벨 — 설계 문서의 대분류 5개 기준 (특정 게임·영상용 아님)
ZS_LABELS = [
    # 사람 소리 (말 제외)
    "laughter", "crying", "screaming", "sighing", "applause", "coughing",
    # 신호음
    "doorbell", "knocking", "telephone ringing", "alarm", "siren", "car horn", "beep",
    # 사건음
    "glass breaking", "crash", "gunshot", "explosion", "footsteps", "door closing",
    "car engine", "machinery",
    # 환경음
    "rain", "wind", "water", "dog barking", "cat meowing", "bird chirping", "crowd murmuring",
    # 음악
    "music", "singing",
    # 비교에만 쓰고 출력 안 함
    "human speech", "silence",
]
ZS_PROMPT = "This is a sound of {}."
ZS_HIDDEN = {"human speech", "silence"}          # 비교에는 참여, 출력 제외
ZS_DISPLAY = {"door closing": "door"}            # 표시 이름을 클래스 모델 쪽과 맞춤

ZS_MIN_P = 0.10
MUSIC_MIN_WITH_SPEECH = 0.30
GLASS_MIN_WITH_BLAST = 0.30
BLAST_LABELS = {"gunshot", "explosion"}
SPEECH_REL_MIN = 0.30     # 말소리가 1위일 때: 말소리 뺀 나머지 안에서 비율이 이 이상
SPEECH_RAW_MIN = 0.03

LAION_CLAP_NAME = "laion/clap-htsat-unfused"

# ======================================================================
# 클래스 모델 (at, panns) — AudioSet 527클래스를 표시 항목으로 묶음
# ======================================================================
TAG_MIN_P = 0.15
TAG_SPEECH_CLASSES = ["Speech", "Male speech, man speaking", "Female speech, woman speaking",
                      "Child speech, kid speaking", "Conversation", "Narration, monologue"]
TAG_SPEECH_ON = 0.50
TAG_MUSIC_MIN_WITH_SPEECH = 0.50

# 표시 이름 ← AudioSet 클래스 이름들 (그중 최고 점수 사용). 말소리 계열은 없음 → 자동 제외
TAG_MAP = {
    # 사람 소리 (말 제외)
    "laughter":          ["Laughter", "Giggle", "Belly laugh", "Chuckle, chortle", "Baby laughter", "Snicker"],
    "crying":            ["Crying, sobbing", "Baby cry, infant cry", "Whimper"],
    "screaming":         ["Screaming"],
    "sighing":           ["Sigh"],
    "applause":          ["Applause", "Clapping", "Cheering"],
    "coughing":          ["Cough"],
    # 신호음
    "doorbell":          ["Doorbell", "Ding-dong"],
    "knocking":          ["Knock"],
    "telephone ringing": ["Telephone bell ringing", "Ringtone", "Telephone"],
    "alarm":             ["Alarm", "Alarm clock", "Smoke detector, smoke alarm", "Fire alarm", "Buzzer", "Car alarm"],
    "siren":             ["Siren", "Police car (siren)", "Ambulance (siren)",
                          "Fire engine, fire truck (siren)", "Civil defense siren"],
    "car horn":          ["Vehicle horn, car horn, honking", "Air horn, truck horn"],
    "beep":              ["Beep, bleep", "Chime", "Ding"],
    # 사건음
    "glass breaking":    ["Shatter", "Breaking"],
    "crash":             ["Smash, crash", "Bang", "Thump, thud", "Crushing"],
    "gunshot":           ["Gunshot, gunfire", "Machine gun", "Fusillade", "Cap gun"],
    "explosion":         ["Explosion", "Boom", "Artillery fire", "Fireworks", "Firecracker", "Eruption"],
    "footsteps":         ["Walk, footsteps", "Run", "Shuffle"],
    "door":              ["Door", "Slam", "Sliding door"],
    "car engine":        ["Car", "Motor vehicle (road)", "Accelerating, revving, vroom", "Truck",
                          "Motorcycle", "Idling", "Traffic noise, roadway noise"],
    "aircraft":          ["Aircraft", "Helicopter", "Fixed-wing aircraft, airplane"],
    "train":             ["Train", "Rail transport"],
    "machinery":         ["Power tool", "Drill", "Jackhammer", "Sawing", "Vacuum cleaner", "Hair dryer", "Blender"],
    # 환경음
    "rain":              ["Rain", "Raindrop", "Rain on surface"],
    "wind":              ["Wind", "Wind noise (microphone)", "Rustling leaves"],
    "water":             ["Water", "Splash, splatter", "Stream", "Pour", "Drip", "Waves, surf",
                          "Trickle, dribble", "Water tap, faucet", "Toilet flush"],
    "dog barking":       ["Dog", "Bark", "Bow-wow", "Yip", "Growling"],
    "cat meowing":       ["Cat", "Meow", "Purr"],
    "bird chirping":     ["Bird", "Bird vocalization, bird call, bird song", "Chirp, tweet"],
    "crowd murmuring":   ["Crowd"],
    # 음악
    "music":             ["Music"],
    "singing":           ["Singing", "Male singing", "Female singing", "Choir", "Child singing"],
}

EFFICIENTAT_DIR = "EfficientAT"    # git clone 한 폴더 (--at-dir 로 변경)
EFFICIENTAT_MODEL = "mn10_as"      # mn04_as(더 가벼움) / mn10_as / mn20_as(더 정확, 더 느림)
AT_PAD_SEC = 10                    # EfficientAT 입력을 이 길이로 반복해서 채움

# ======================================================================
# 메인(CLAP 계열) + 보조(클래스 모델) 합치기
# ======================================================================
FAMILY = {}   # CLAP 표시이름 → 보조 쪽 표시이름 (같은 계열로 인정). 범용 라벨은 이름이 같아서 비워 둠
TAG_CONFIRM_MIN = 0.15    # 보조 점수가 이 이상이면 '확인됨(*)'
TAG_BONUS = 0.5           # 확인됐을 때 순위 점수에 더하는 비율 (CLAP 점수 + 0.5 × 보조 점수)
TAG_ADD_MIN = 0.50        # 보조만 잡은 소리는 이 점수 이상일 때만 추가('+')
TAG_ONLY_WEIGHT = 0.6     # 보조만 잡은 소리의 순위 점수 = 보조 점수 × 0.6 (메인보다 뒤로)
MERGE_REQUIRE_MAIN = {"music"}   # 보조 혼자서는 추가하지 않는 소리

# ======================================================================
# 한국어 표시 이름 (--en 을 주면 영어 그대로)
# ======================================================================
LANG = "ko"
KO = {
    "laughter": "웃음", "crying": "울음", "screaming": "비명", "sighing": "한숨",
    "applause": "박수·환호", "coughing": "기침",
    "doorbell": "초인종", "knocking": "노크", "telephone ringing": "전화벨", "alarm": "알람",
    "siren": "사이렌", "car horn": "경적", "beep": "신호음",
    "glass breaking": "유리 깨짐", "crash": "충돌음", "gunshot": "총성", "explosion": "폭발",
    "footsteps": "발소리", "door": "문", "car engine": "차량", "machinery": "기계음",
    "aircraft": "비행기", "train": "기차",
    "rain": "비", "wind": "바람", "water": "물소리", "dog barking": "개 짖음",
    "cat meowing": "고양이", "bird chirping": "새소리", "crowd murmuring": "군중 웅성임",
    "music": "음악", "singing": "노래",
}

# ======================================================================
# 음악 분위기 — 음악이 잡혔을 때만 붙임. 화면에는 '음악(긴박한)' 처럼 표시
# ======================================================================
# CLAP 계열: 분위기 문장끼리만 따로 비교 (메인 라벨 확률을 희석시키지 않음, 소리 임베딩 재사용)
#   라벨은 자유롭게 정할 수 있음 — AudioSet 7종에 맞출 필요 없음. 아래는 '성격' 묘사용
ZS_MOODS = [
    ("긴박한",  "tense, suspenseful music"),
    ("신나는",  "upbeat, energetic music"),
    ("잔잔한",  "calm, gentle music"),
    ("슬픈",    "sad, melancholic music"),
    ("무서운",  "scary, eerie music"),
    ("밝은",    "happy, cheerful music"),
    ("웅장한",  "epic, dramatic music"),
    ("코믹한",  "funny, playful music"),
]
ZS_MOOD_MIN = 0.35        # 8개 중 하나라 고르게 나누면 0.125 → 0.35 이상일 때만 붙임
# 클래스 모델(at, panns): AudioSet에 원래 있는 분위기 클래스 7개
TAG_MOODS = {
    "Happy music": "밝은", "Funny music": "코믹한", "Sad music": "슬픈", "Tender music": "잔잔한",
    "Exciting music": "신나는", "Angry music": "격한", "Scary music": "무서운",
}
TAG_MOOD_MIN = 0.10       # AudioSet 분위기 클래스는 점수가 낮게 나오는 편이라 기준을 낮게 둠

# ======================================================================
# 말소리 거부권 (CLAP + AT/PANNs를 같이 쓸 때만)
#  CLAP은 조용한 말소리를 노래·음악·군중 소리와 헷갈림 (목소리끼리 비슷해서).
#  AT/PANNs는 AudioSet에서 말소리(Speech)를 가장 많이 배워서 말소리 판단이 안정적.
#  → AT/PANNs가 '말소리'라고 강하게 판단했고, 그 소리(노래 등)는 AT/PANNs가 따로 확인하지 않았으면
#    CLAP이 낸 그 소리는 합침에서 뺌
# ======================================================================
# 말소리와 헷갈리는 소리: 목소리 계열 전체 + 음악·군중
#  (예: 울먹이는 말투 → 울음, 감탄하는 말투 → 웃음·비명, 숨 섞인 말 → 한숨)
VOICE_LIKE = {"singing", "music", "crowd murmuring",
              "crying", "laughter", "sighing", "screaming"}
SPEECH_VETO_ON = 0.50     # AT/PANNs 말소리 점수가 이 이상이면 거부권 발동
VOICE_CONFIRM = 0.30      # AT/PANNs가 그 소리(노래 등)를 이 점수 이상 잡았으면 진짜로 보고 살림

# 구간 음량 맞추기(--normalize)
NORM_TARGET_PEAK_RMS = 0.10
NORM_MAX_GAIN = 30.0


# ======================================================================
# 공통 유틸
# ======================================================================
def resample(x, sr_from, sr_to):
    if sr_from == sr_to:
        return x.astype(np.float32)
    g = gcd(sr_from, sr_to)
    return resample_poly(x, sr_to // g, sr_from // g).astype(np.float32)


def peak_rms(mono, sr, frame_ms=50):
    fl = int(sr * frame_ms / 1000)
    n = len(mono) // fl
    if n == 0:
        return float(np.sqrt(np.mean(mono ** 2)))
    frames = mono[: n * fl].reshape(n, fl)
    return float(np.sqrt((frames ** 2).mean(axis=1)).max())


def estimate_direction(stereo):
    """좌/우 RMS 비교로 방향 추정 (+면 오른쪽)"""
    l = np.sqrt(np.mean(stereo[:, 0] ** 2)) + 1e-9
    r = np.sqrt(np.mean(stereo[:, 1] ** 2)) + 1e-9
    db = 20 * np.log10(r / l)
    pan = (r - l) / (r + l)
    if abs(db) < CENTER_DB:
        label = "중앙"
    elif db > 0:
        label = "오른쪽"
    else:
        label = "왼쪽"
    return label, db, pan


def display_name(name, mood=None):
    """영어 라벨 → 표시 이름. 끝의 * / + 표시는 유지. music에는 분위기를 괄호로 붙임"""
    base, mark = name.rstrip("*+"), name[len(name.rstrip("*+")):]
    shown = KO.get(base, base) if LANG == "ko" else base
    if base == "music" and mood:
        shown += f"({mood})"
    return shown + mark


def fmt(results, mood=None):
    return ", ".join(f"{display_name(n, mood)} {p:.2f}" for n, p in results)


def torch_device():
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


# ======================================================================
# CLAP 계열: 확률(ZS_LABELS 순서) → 출력 목록 (v9 규칙)
# ======================================================================
def filter_zeroshot(probs, top_k=TOP_K):
    labels = ZS_LABELS
    order = np.argsort(probs)[::-1]
    speech_first = labels[order[0]] == "human speech"
    blast_sum = sum(float(probs[j]) for j, n in enumerate(labels) if n in BLAST_LABELS)
    visible_sum = sum(float(probs[j]) for j, n in enumerate(labels) if n not in ZS_HIDDEN) + 1e-9

    out = []
    for i in order:
        name, p = labels[i], float(probs[i])
        if name in ZS_HIDDEN:
            continue
        if speech_first:
            score = p / visible_sum
            if p < SPEECH_RAW_MIN or score < SPEECH_REL_MIN:
                continue
            if name == "music" and p < MUSIC_MIN_WITH_SPEECH:
                continue
        else:
            score = p
            if p < ZS_MIN_P:
                continue
        if score < LABEL_MIN_P.get(name, 0.0):
            continue
        if name == "glass breaking" and p < GLASS_MIN_WITH_BLAST and blast_sum > p:
            continue
        out.append((ZS_DISPLAY.get(name, name), score))
        if len(out) == top_k:
            break
    return out


class LaionClap:
    name, kind = "CLAP", "zs"

    def __init__(self):
        import torch
        from transformers import ClapModel, ClapProcessor
        self.torch = torch
        self.device = torch_device()
        print(f"[CLAP] 로딩 중... ({LAION_CLAP_NAME})")
        self.processor = ClapProcessor.from_pretrained(LAION_CLAP_NAME)
        self.model = ClapModel.from_pretrained(LAION_CLAP_NAME).to(self.device).eval()
        prompts = [ZS_PROMPT.format(l) for l in ZS_LABELS]
        with torch.no_grad():
            t_in = self.processor(text=prompts, return_tensors="pt", padding=True)
            t_in = {k: v.to(self.device) for k, v in t_in.items()}
            te = self.model.get_text_features(**t_in)
            te = te if hasattr(te, "norm") else te.pooler_output
            self.text_emb = te / te.norm(dim=-1, keepdim=True)
            m_in = self.processor(text=[p for _, p in ZS_MOODS], return_tensors="pt", padding=True)
            m_in = {k: v.to(self.device) for k, v in m_in.items()}
            me = self.model.get_text_features(**m_in)
            me = me if hasattr(me, "norm") else me.pooler_output
            self.mood_emb = me / me.norm(dim=-1, keepdim=True)
        self.last_ae = None
        print(f"[CLAP] 준비 완료 ({self.device})")

    def mood(self):
        """직전 run()의 소리 임베딩을 재사용해 분위기 문장끼리만 비교 → (분위기, 확률) 또는 None"""
        if self.last_ae is None:
            return None
        with self.torch.no_grad():
            p = (self.model.logit_scale_a.exp() * self.last_ae @ self.mood_emb.T).softmax(dim=-1)[0]
        i = int(p.argmax())
        return (ZS_MOODS[i][0], float(p[i])) if float(p[i]) >= ZS_MOOD_MIN else None

    def run(self, mono, sr):
        torch = self.torch
        x = resample(mono, sr, 48000)
        with torch.no_grad():
            a_in = self.processor(audio=x, sampling_rate=48000, return_tensors="pt")
            a_in = {k: v.to(self.device) for k, v in a_in.items()}
            ae = self.model.get_audio_features(**a_in)
            ae = ae if hasattr(ae, "norm") else ae.pooler_output
            ae = ae / ae.norm(dim=-1, keepdim=True)
            self.last_ae = ae
            probs = (self.model.logit_scale_a.exp() * ae @ self.text_emb.T).softmax(dim=-1)[0]
        return probs.cpu().numpy()


def _ensure_torchaudio_for_msclap():
    """msclap은 import할 때 torchaudio를 불러오지만, 이 코드에서는 실제로 쓰지 않음.
    torchaudio가 없으면 빈 모듈로 대신 채워서 import만 통과시킴."""
    try:
        import torchaudio  # noqa: F401
    except ImportError:
        import types
        ta = types.ModuleType("torchaudio")
        tr = types.ModuleType("torchaudio.transforms")
        ta.transforms = tr
        sys.modules["torchaudio"] = ta
        sys.modules["torchaudio.transforms"] = tr


class MsClap:
    name, kind = "MS-CLAP", "zs"

    def __init__(self):
        import torch
        _ensure_torchaudio_for_msclap()
        from msclap import CLAP
        self.torch = torch
        self.use_cuda = torch.cuda.is_available()
        print("[MS-CLAP] 로딩 중... (version 2023)")
        self.m = CLAP(version="2023", use_cuda=self.use_cuda)
        self.sr = int(self.m.args.sampling_rate)      # 44100
        self.dur = int(self.m.args.duration)          # 7초
        prompts = [ZS_PROMPT.format(l) for l in ZS_LABELS]
        with torch.no_grad():
            te = self.m._get_text_embeddings(self._tokenize(prompts))
            self.text_emb = te / te.norm(dim=-1, keepdim=True)
            self.scale = self.m.clap.logit_scale.exp()
            me = self.m._get_text_embeddings(self._tokenize([p for _, p in ZS_MOODS]))
            self.mood_emb = me / me.norm(dim=-1, keepdim=True)
        self.last_ae = None
        # 자체 점검: 라벨 문장끼리 임베딩이 거의 같으면 텍스트 처리가 잘못된 것
        sim = (self.text_emb @ self.text_emb.T).cpu().numpy()
        off = sim[~np.eye(len(sim), dtype=bool)]
        print(f"[MS-CLAP] 라벨 임베딩 유사도 평균 {off.mean():.2f} / 최대 {off.max():.2f} "
              f"(토큰 길이 {min(self.text_len_used)}~{max(self.text_len_used)})")
        if off.mean() > 0.90:
            print("[MS-CLAP] 경고: 라벨끼리 너무 비슷합니다. 텍스트 처리에 문제가 있을 수 있어요.")
        print(f"[MS-CLAP] 준비 완료 ({'cuda' if self.use_cuda else 'cpu'}, {self.sr}Hz, {self.dur}s)")

    def mood(self):
        if self.last_ae is None:
            return None
        with self.torch.no_grad():
            p = (self.scale * self.last_ae @ self.mood_emb.T).softmax(dim=-1)[0]
        i = int(p.argmax())
        return (ZS_MOODS[i][0], float(p[i])) if float(p[i]) >= ZS_MOOD_MIN else None

    def _tokenize(self, texts):
        """msclap의 preprocess_text와 같은 결과를 만듦.
        msclap은 tokenizer.encode_plus를 쓰는데, transformers 5부터 encode_plus가 없어져서 직접 처리."""
        torch = self.torch
        if "gpt" in self.m.args.text_model:
            texts = [t + " <|endoftext|>" for t in texts]
        L = int(self.m.args.text_len)
        # 토크나이저의 자동 채우기(padding)를 쓰지 않고 직접 0으로 채움.
        # MS-CLAP은 'id가 0이 아닌 마지막 토큰'(= <|endoftext|>)의 출력을 문장 대표값으로 씀.
        # 원래 msclap은 채우기 토큰을 '!'(id 0)로 지정하는데, transformers 5에서는 이 지정이
        # 다르게 먹혀서 채우기 id가 0이 아니게 되면 → 모든 라벨이 같은 위치(맨 끝)를 대표값으로 써서
        # 라벨끼리 구분이 안 됨(door·bird·glass가 아무 데서나 뜨는 증상).
        enc = self.m.tokenizer(texts, add_special_tokens=True, truncation=True, max_length=L)
        ids = torch.zeros((len(texts), L), dtype=torch.long)
        mask = torch.zeros((len(texts), L), dtype=torch.long)
        for i, row in enumerate(enc["input_ids"]):
            row = list(row)[:L]
            ids[i, :len(row)] = torch.tensor(row, dtype=torch.long)
            mask[i, :len(row)] = 1
        self.text_len_used = [len(r) for r in enc["input_ids"]]
        tok = {"input_ids": ids, "attention_mask": mask, "token_type_ids": torch.zeros_like(ids)}
        batch = {k: tok[k] for k in self.m.token_keys}
        if self.use_cuda:
            batch = {k: v.cuda() for k, v in batch.items()}
        return batch

    def run(self, mono, sr):
        torch = self.torch
        x = resample(mono, sr, self.sr)
        n = self.dur * self.sr
        x = np.tile(x, int(ceil(n / max(1, len(x)))))[:n]     # msclap과 같은 방식: 반복해서 7초로 채움
        t = torch.from_numpy(x).float().reshape(1, 1, -1)
        if self.use_cuda:
            t = t.cuda()
        with torch.no_grad():
            ae = self.m._get_audio_embeddings(t)
            ae = ae / ae.norm(dim=-1, keepdim=True)
            self.last_ae = ae
            probs = (self.scale * ae @ self.text_emb.T).softmax(dim=-1)[0]
        return probs.cpu().numpy()


# ======================================================================
# 클래스 모델: 527 점수 → 표시 항목 점수
# ======================================================================
class TaggerBase:
    kind = "tag"

    def _build_groups(self, labels):
        self.labels = list(labels)
        idx = {n: i for i, n in enumerate(self.labels)}
        self.groups, missing = [], []
        for disp, names in TAG_MAP.items():
            ii = [idx[n] for n in names if n in idx]
            missing += [n for n in names if n not in idx]
            if ii:
                self.groups.append((disp, ii))
        self.speech_idx = [idx[n] for n in TAG_SPEECH_CLASSES if n in idx]
        self.mood_idx = [(idx[n], ko) for n, ko in TAG_MOODS.items() if n in idx]
        if missing:
            print(f"[{self.name}] 클래스 목록에 없는 이름(무시됨): {missing}")

    def summarize(self, scores):
        """반환: (표시항목 점수 dict, 말소리 점수, 원본 상위5)"""
        g = {disp: float(scores[ii].max()) for disp, ii in self.groups}
        sp = float(scores[self.speech_idx].max()) if self.speech_idx else 0.0
        top = np.argsort(scores)[::-1][:5]
        raw = [(self.labels[i], float(scores[i])) for i in top]
        mood = None
        if self.mood_idx:
            i, ko = max(self.mood_idx, key=lambda t: scores[t[0]])
            if float(scores[i]) >= TAG_MOOD_MIN:
                mood = (ko, float(scores[i]))
        return g, sp, raw, mood


def filter_tagger(groups, speech, top_k=TOP_K):
    speaking = speech >= TAG_SPEECH_ON
    out = []
    for disp, s in groups.items():
        if s < max(TAG_MIN_P, LABEL_MIN_P.get(disp, 0.0)):
            continue
        if disp == "music" and speaking and s < TAG_MUSIC_MIN_WITH_SPEECH:
            continue
        out.append((disp, s))
    out.sort(key=lambda t: -t[1])
    return out[:top_k]


class EfficientAT(TaggerBase):
    name = "AT"

    def __init__(self, repo_dir=EFFICIENTAT_DIR, model_name=EFFICIENTAT_MODEL):
        import torch
        self.torch = torch
        repo = os.path.abspath(repo_dir)
        if not os.path.isdir(os.path.join(repo, "models", "mn")):
            raise SystemExit(
                f"[AT] EfficientAT 폴더를 찾지 못했습니다: {repo}\n"
                f"     이 파일이 있는 폴더에서:  git clone https://github.com/fschmid56/EfficientAT\n"
                f"     다른 곳에 받았다면:      --at-dir 경로")
        print(f"[AT] 로딩 중... ({model_name})")
        if repo not in sys.path:
            sys.path.insert(0, repo)
        cwd = os.getcwd()
        os.chdir(repo)          # EfficientAT는 라벨 파일·가중치 저장 위치를 현재 폴더 기준으로 찾음
        try:
            from models.mn.model import get_model as get_mobilenet
            from models.preprocess import AugmentMelSTFT
            from helpers.utils import NAME_TO_WIDTH, labels
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()):       # 모델 구조 출력 숨김
                self.model = get_mobilenet(width_mult=NAME_TO_WIDTH(model_name), pretrained_name=model_name)
        finally:
            os.chdir(cwd)
        self.device = torch_device()
        self.mel = AugmentMelSTFT(n_mels=128, sr=32000, win_length=800, hopsize=320, fmax=15000)
        self.model.to(self.device).eval()
        self.mel.to(self.device).eval()
        self._build_groups(labels)
        print(f"[AT] 준비 완료 ({self.device})")

    def run(self, mono, sr):
        torch = self.torch
        x = resample(mono, sr, 32000)
        # EfficientAT는 10초 클립으로 학습돼서 2초를 그대로 넣으면 점수가 전부 1.00으로 망가짐
        # → CLAP처럼 반복해서 10초로 채운 뒤 넣음 (직접 확인: 2초 그대로=엉터리, 10초로 채움=정상)
        n = AT_PAD_SEC * 32000
        x = np.tile(x, int(ceil(n / max(1, len(x)))))[:n]
        w = torch.from_numpy(x[None, :]).to(self.device)
        with torch.no_grad():
            spec = self.mel(w)
            preds, _ = self.model(spec.unsqueeze(0))
        return self.summarize(torch.sigmoid(preds.float()).squeeze().cpu().numpy())


class Panns(TaggerBase):
    name = "PANNs"

    def __init__(self):
        from panns_inference import AudioTagging, labels
        print("[PANNs] 로딩 중... (Cnn14)")
        self.at = AudioTagging(checkpoint_path=None, device=torch_device())
        self._build_groups(labels)
        print("[PANNs] 준비 완료")

    def run(self, mono, sr):
        x = resample(mono, sr, 32000)[None, :]
        clipwise, _ = self.at.inference(x)
        return self.summarize(clipwise[0])


# ======================================================================
# 합치기
# ======================================================================
def average_zs(prob_list):
    return np.mean(np.stack(prob_list), axis=0)


def average_tag(tag_list):
    """tag_list: [(groups, speech, raw), ...] → (평균 groups, 평균 speech)"""
    keys = set().union(*[t[0].keys() for t in tag_list])
    g = {k: float(np.mean([t[0].get(k, 0.0) for t in tag_list])) for k in keys}
    sp = float(np.mean([t[1] for t in tag_list]))
    return g, sp


def assist_merge(main_list, tag_groups, tag_list, top_k=TOP_K):
    """main_list: CLAP 계열 결과 [(이름, 점수)], tag_groups: 보조 전체 점수 dict,
    tag_list: 보조 필터 통과 결과 [(이름, 점수)]"""
    rows, used = [], set()
    for name, s in main_list:
        g = FAMILY.get(name, name)
        if g in used:              # 같은 계열이 이미 있으면 생략
            continue
        t = tag_groups.get(g, 0.0)
        if t >= TAG_CONFIRM_MIN:
            rows.append((s + TAG_BONUS * t, f"{name}*", min(1.0, s + TAG_BONUS * t)))
        else:
            rows.append((s, name, s))
        used.add(g)
    for g, t in tag_list:
        if g in used or g in MERGE_REQUIRE_MAIN or t < TAG_ADD_MIN:
            continue
        rows.append((t * TAG_ONLY_WEIGHT, f"{g}+", t))
    rows.sort(key=lambda r: -r[0])
    return [(name, shown) for _, name, shown in rows[:top_k]]


# ======================================================================
# 분석기
# ======================================================================
MODEL_CLASSES = {"clap": LaionClap, "msclap": MsClap, "at": EfficientAT, "panns": Panns}


class Analyzer:
    def __init__(self, model_keys, normalize=False, raw=False, quiet=False,
                 at_dir=EFFICIENTAT_DIR, at_model=EFFICIENTAT_MODEL):
        self.dets = []
        for k in model_keys:
            if k == "at":
                self.dets.append(EfficientAT(at_dir, at_model))
            else:
                self.dets.append(MODEL_CLASSES[k]())
        self.normalize, self.raw, self.quiet = normalize, raw, quiet
        self.times = {d.name: [] for d in self.dets}
        # 첫 분석은 준비 작업 때문에 몇 초 걸리므로 미리 한 번 돌려 둠 (시간 기록에는 안 넣음)
        warm = (np.random.randn(int(48000 * WINDOW_SEC)) * 0.01).astype(np.float32)
        for d in self.dets:
            d.run(warm, 48000)

    def analyze(self, stereo, sr):
        mono = stereo.mean(axis=1)
        if peak_rms(mono, sr) < SILENCE_PEAK_RMS:
            return None, None

        direction, db, pan = estimate_direction(stereo)
        lines = [f"[방향: {direction:3s} | L/R {db:+5.1f}dB | pan {pan:+.2f}]"]
        rec = {"direction": direction, "db": round(db, 1), "pan": round(pan, 2)}
        if self.normalize:
            gain = min(NORM_MAX_GAIN, NORM_TARGET_PEAK_RMS / (peak_rms(mono, sr) + 1e-9))
            mono = np.clip(mono * gain, -1.0, 1.0)

        zs_probs, tag_outs, total = [], [], 0.0
        zs_mood = tag_mood = None
        for d in self.dets:
            t0 = time.perf_counter()
            out = d.run(mono, sr)
            dt = time.perf_counter() - t0
            total += dt
            self.times[d.name].append(dt)
            if d.kind == "zs":
                zs_probs.append(out)
                res = filter_zeroshot(out)
                m = d.mood() if any(n == "music" for n, _ in res) else None
                zs_mood = zs_mood or m
            else:
                tag_outs.append(out)
                res = filter_tagger(out[0], out[1])
                m = out[3] if any(n == "music" for n, _ in res) else None
                tag_mood = tag_mood or m
            mood_txt = m[0] if m else None
            rec[d.name] = fmt(res, mood_txt)
            rec[d.name + "_sec"] = round(dt, 3)
            if not self.quiet or len(self.dets) == 1:
                if len(self.dets) > 1 or res:
                    extra = f"  [분위기 {m[0]} {m[1]:.2f}]" if m else ""
                    lines.append(f"    {d.name:<7} ({dt:.2f}s): {fmt(res, mood_txt) or '-'}{extra}")
            if self.raw and d.kind == "tag":
                lines.append(f"      ({d.name} 원본 상위5: {fmt(out[2])})")

        if len(self.dets) > 1:
            main = filter_zeroshot(average_zs(zs_probs), top_k=len(ZS_LABELS)) if zs_probs else None
            vetoed = []
            if tag_outs:
                tg, tsp = average_tag(tag_outs)
                tag_list = filter_tagger(tg, tsp)
                if main is not None and tsp >= SPEECH_VETO_ON:
                    keep = []
                    for n, sc in main:
                        if n in VOICE_LIKE and tg.get(n, 0.0) < VOICE_CONFIRM:
                            vetoed.append(n)
                        else:
                            keep.append((n, sc))
                    main = keep
            if main is not None:
                main = main[:TOP_K]
            if main is not None and tag_outs:
                merged = assist_merge(main, tg, tag_list)
            elif main is not None:
                merged = main
            else:
                merged = tag_list
            # 합친 결과의 분위기: CLAP 계열 판단을 우선, 없으면 클래스 모델 판단
            mm = zs_mood or tag_mood
            mood_txt = mm[0] if mm else None
            rec["merged"] = fmt(merged, mood_txt)
            note = ""
            if vetoed:
                note = f"   (말소리 {tsp:.2f} → 제외: {', '.join(display_name(v) for v in vetoed)})"
                rec["vetoed"] = ",".join(vetoed)
            if merged or not self.quiet:
                lines.append(f"    {'합침':<6} ({total:.2f}s): {rec['merged'] or '-'}{note}")
        return "\n".join(lines), rec

    def summary(self):
        print("\n[처리 시간 요약 — 2초 구간 1개당]")
        total = 0.0
        for name, ts in self.times.items():
            if ts:
                a = np.array(ts)
                total += a.mean()
                print(f"  {name:<8} 평균 {a.mean():.3f}s · 최소 {a.min():.3f}s · 최대 {a.max():.3f}s · {len(a)}회")
        if total:
            warn = "  ← 분석 간격보다 길어서 실시간이면 지연이 생김" if total > HOP_SEC else ""
            print(f"  합계     평균 {total:.3f}s (분석 간격 {HOP_SEC:.1f}s){warn}")


# ======================================================================
# 파일 입력
# ======================================================================
def load_audio(path, target_sr=48000):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".wav", ".flac", ".ogg", ".aiff", ".aif"):
        import soundfile as sf
        data, sr = sf.read(path, dtype="float32", always_2d=True)
    else:
        import av
        container = av.open(path)
        stream = container.streams.audio[0]
        rs = av.AudioResampler(format="flt", layout="stereo", rate=target_sr)
        chunks = []
        for frame in container.decode(stream):
            for f in rs.resample(frame) or []:
                chunks.append(f.to_ndarray().reshape(-1, 2))
        for f in rs.resample(None) or []:
            chunks.append(f.to_ndarray().reshape(-1, 2))
        container.close()
        data, sr = np.concatenate(chunks).astype(np.float32), target_sr
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    data = data[:, :2]
    if sr != target_sr:
        data = np.stack([resample(data[:, 0], sr, target_sr),
                         resample(data[:, 1], sr, target_sr)], axis=1)
        sr = target_sr
    return data, sr


def mmss(sec):
    return f"{int(sec // 60):02d}:{sec % 60:04.1f}"


def run_file(analyzer, path, csv_path):
    print(f"[파일] {path} 읽는 중...")
    data, sr = load_audio(path)
    dur = len(data) / sr
    m = data.mean(axis=1)
    fl = int(sr * 0.05)
    n = len(m) // fl
    fr = np.sqrt((m[: n * fl].reshape(n, fl) ** 2).mean(axis=1))
    loud = float(np.percentile(fr, 95))
    print(f"[파일] 길이 {dur:.1f}초 · {sr}Hz · 구간 {WINDOW_SEC}s / 간격 {HOP_SEC}s")
    print(f"[파일] 음량(50ms 기준) 상위5% {loud:.4f} · 최대 {fr.max():.4f} · 무음 기준 {SILENCE_PEAK_RMS}")
    if loud < SILENCE_PEAK_RMS:
        print(f"[주의] 파일 대부분이 무음 기준보다 작습니다. --silence {max(0.001, round(loud / 3, 4))} 정도로 낮춰 보세요.")
    print()

    win, hop = int(WINDOW_SEC * sr), int(HOP_SEC * sr)
    rows = []
    for start in range(0, max(1, len(data) - win + 1), hop):
        seg = data[start:start + win]
        t0, t1 = start / sr, (start + len(seg)) / sr
        text, rec = analyzer.analyze(seg, sr)
        head = f"[{mmss(t0)}~{mmss(t1)}] "
        if text is None:
            print(head + "[무음]")
            rec = {"direction": "무음"}
        else:
            print(head + text)
        rows.append({"start": round(t0, 1), "end": round(t1, 1), **rec})

    analyzer.summary()
    if csv_path:
        keys = ["start", "end", "direction", "db", "pan"]
        for d in analyzer.dets:
            keys += [d.name, d.name + "_sec"]
        keys.append("merged")
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"\n[저장] {csv_path}")


# ======================================================================
# 실시간 입력 (WASAPI Loopback)
# ======================================================================
class LoopbackCapture:
    def __init__(self, buffer_sec=10.0):
        import pyaudiowpatch as pyaudio
        self.pyaudio = pyaudio
        self.pa = pyaudio.PyAudio()
        self.device = self._find_loopback_device()
        self.sr = int(self.device["defaultSampleRate"])
        self.channels = int(self.device["maxInputChannels"])
        if self.channels < 2:
            raise RuntimeError("스테레오(2채널 이상) 출력 장치가 필요합니다.")
        self.buf = np.zeros((int(self.sr * buffer_sec), 2), dtype=np.float32)
        self.lock = threading.Lock()
        self.stream = None

    def _find_loopback_device(self):
        wasapi = self.pa.get_host_api_info_by_type(self.pyaudio.paWASAPI)
        speakers = self.pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
        if not speakers.get("isLoopbackDevice", False):
            for lb in self.pa.get_loopback_device_info_generator():
                if speakers["name"] in lb["name"]:
                    return lb
            raise RuntimeError("기본 출력 장치의 loopback 장치를 찾지 못했습니다.")
        return speakers

    def _callback(self, in_data, frame_count, time_info, status):
        data = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
        data = data.reshape(-1, self.channels)[:, :2]
        n = len(data)
        with self.lock:
            self.buf = np.roll(self.buf, -n, axis=0)
            self.buf[-n:] = data
        return (None, self.pyaudio.paContinue)

    def start(self):
        self.stream = self.pa.open(
            format=self.pyaudio.paInt16, channels=self.channels, rate=self.sr,
            input=True, input_device_index=self.device["index"],
            frames_per_buffer=1024, stream_callback=self._callback,
        )
        self.stream.start_stream()
        print(f"[캡처 시작] {self.device['name']} | {self.sr} Hz | {self.channels}ch")

    def get_last(self, seconds):
        n = int(self.sr * seconds)
        with self.lock:
            return self.buf[-n:].copy()

    def stop(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.pa.terminate()


def run_live(analyzer):
    cap = LoopbackCapture(buffer_sec=max(10.0, WINDOW_SEC * 2))
    cap.start()
    print("소리를 재생해 보세요. (Ctrl+C 로 종료)\n")
    time.sleep(WINDOW_SEC)
    try:
        while True:
            t0 = time.time()
            text, _ = analyzer.analyze(cap.get_last(WINDOW_SEC), cap.sr)
            if text is None:
                print("[무음]", end="\r")
            else:
                print(" " * 20, end="\r")
                print(text)
            time.sleep(max(0.0, HOP_SEC - (time.time() - t0)))
    except KeyboardInterrupt:
        print("\n종료합니다.")
        analyzer.summary()
    finally:
        cap.stop()


def main():
    global SILENCE_PEAK_RMS, HOP_SEC, LANG
    ap = argparse.ArgumentParser(description="CLAP / MS-CLAP / EfficientAT / PANNs 소리 분류 + 방향")
    ap.add_argument("--models", default="clap",
                    help="쉼표로 구분: clap, msclap, at, panns  (예: clap,msclap,at)")
    ap.add_argument("--file", default=None, help="분석할 녹음/영상 파일 (없으면 실시간)")
    ap.add_argument("--csv", default=None, help="--file 결과를 CSV로 저장")
    ap.add_argument("--silence", type=float, default=None,
                    help=f"무음 기준(가장 큰 50ms 음량). 기본 {SILENCE_PEAK_RMS}")
    ap.add_argument("--hop", type=float, default=None, help=f"분석 간격(초). 기본 {HOP_SEC}")
    ap.add_argument("--normalize", action="store_true", help="구간마다 음량을 맞춘 뒤 분류")
    ap.add_argument("--raw", action="store_true", help="클래스 모델(at, panns)의 원본 상위 5개도 출력")
    ap.add_argument("--quiet", action="store_true", help="모델별 줄은 숨기고 합친 결과만 출력")
    ap.add_argument("--en", action="store_true", help="소리 이름을 영어로 표시")
    ap.add_argument("--at-dir", default=EFFICIENTAT_DIR, help="EfficientAT를 clone한 폴더")
    ap.add_argument("--at-model", default=EFFICIENTAT_MODEL, help="mn04_as / mn10_as / mn20_as 등")
    args = ap.parse_args()

    keys = [k.strip().lower() for k in args.models.split(",") if k.strip()]
    bad = [k for k in keys if k not in MODEL_CLASSES]
    if bad or not keys:
        raise SystemExit(f"--models 에는 {', '.join(MODEL_CLASSES)} 중에서 고르세요. (잘못된 값: {bad})")
    if args.silence is not None:
        SILENCE_PEAK_RMS = args.silence
    if args.en:
        LANG = "en"
    if args.hop is not None:
        HOP_SEC = args.hop

    print(f"[sound_live {VERSION} · models={','.join(keys)}] {os.path.abspath(__file__)}")
    if len(keys) > 1:
        print("  표시: 이름*  = 메인(CLAP 계열)과 보조(클래스 모델)가 모두 잡음 / 이름+ = 보조만 강하게 잡음")
    analyzer = Analyzer(keys, normalize=args.normalize, raw=args.raw, quiet=args.quiet,
                        at_dir=args.at_dir, at_model=args.at_model)
    if args.file:
        run_file(analyzer, args.file, args.csv)
    else:
        run_live(analyzer)


if __name__ == "__main__":
    main()


INSTALL = r"""
[공통]  pip install numpy scipy torch transformers soundfile pyaudiowpatch

[clap]   추가 설치 없음 (처음 실행 시 모델 자동 다운로드)

[msclap] pip install --no-deps msclap torchlibrosa
         pip install pyyaml huggingface_hub
         (그냥 pip install msclap 하면 numpy·transformers 버전을 내려버릴 수 있어서 --no-deps 권장)
         처음 실행 시 가중치와 gpt2 토크나이저 자동 다운로드

[at]     이 파일이 있는 폴더에서:
           git clone https://github.com/fschmid56/EfficientAT
         torchaudio, torchvision 필요 — torch와 버전이 맞아야 함:
           python -c "import torch; print(torch.__version__)"   → 예: 2.5.1
           pip install torchaudio==2.5.1 torchvision==0.20.1     (torch 버전에 맞는 짝으로)
         처음 실행 시 가중치(mn10_as)를 EfficientAT/resources 에 자동 다운로드

[panns]  pip install panns_inference librosa
         C:\Users\<이름>\panns_data\ 에 class_labels_indices.csv, Cnn14_mAP=0.431.pth
"""
