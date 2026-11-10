"""
sound_live_plus.py — sound_live.py(v16.1) 규칙 그대로 + AST, BEATs 모델 추가

sound_direction_ast_panns_beats_clap.py 의 모델 구성(CLAP + AST + PANNs + BEATs)을
sound_live.py 의 정제된 규칙으로 돌리는 버전.

※ sound_live.py 와 같은 폴더에 두어야 함 (캡처·CLAP·PANNs·AT·규칙·출력을 전부 거기서 가져다 씀)

적용되는 규칙 (sound_live.py v16.1과 동일)
  - 범용 라벨 30개 + 한국어 표시, 말소리(대사) 제외, 상위 3개
  - CLAP이 메인, 클래스 모델(AST·PANNs·BEATs·AT)은 점수를 평균해서 보조
      이름*  = CLAP 소리를 보조도 잡음 (점수 가산)
      이름+  = 보조만 0.5 이상으로 강하게 잡음
  - 말소리 거부권: 보조의 말소리 점수가 0.5 이상이면 CLAP의 노래·음악·군중·울음·웃음·한숨·비명은
    보조도 0.3 이상 잡았을 때만 표시
  - 음악 분위기(CLAP), 무음 판단, 방향(좌우 음량차)

모델 (--models, 쉼표로)
  clap, msclap, at, panns  : sound_live.py와 동일
  ast                      : MIT/ast-finetuned-audioset-10-10-0.4593 (2초를 반복해 10초로 채움)
  beats                    : Microsoft BEATs iter3+ (AS2M 파인튜닝). 처음 실행 시 ~/beats_data 에 자동 다운로드

실행 예
  python sound_live_plus.py                                   # 기본: clap,ast,panns,beats
  python sound_live_plus.py --models clap,beats
  python sound_live_plus.py --models clap,ast,panns,beats --file test_134235.wav --silence 0.003 --csv out.csv
  python sound_live_plus.py --models clap,beats --beats-pad   # BEATs도 10초로 채워서 (느리지만 학습 조건과 같음)

주의: AST는 이 노트북 CPU에서 구간당 약 1.5초. 넷을 다 켜면 1초 간격보다 길어서 결과가 건너뛰며 나옴.
     정확도 비교는 --file 로 하는 걸 권장.
"""

import os
import sys
import urllib.request
from math import ceil
from pathlib import Path

import numpy as np

import sound_live as SL

# ----------------------------------------------------------------------
# AST
# ----------------------------------------------------------------------
AST_NAME = "MIT/ast-finetuned-audioset-10-10-0.4593"
AST_SR = 16000
AST_PAD_SEC = 10


class AST(SL.TaggerBase):
    name, kind = "AST", "tag"

    def __init__(self):
        import torch
        from transformers import ASTFeatureExtractor, ASTForAudioClassification
        self.torch = torch
        self.device = SL.torch_device()
        print(f"[AST] 로딩 중... ({AST_NAME})")
        self.fe = ASTFeatureExtractor.from_pretrained(AST_NAME)
        self.model = ASTForAudioClassification.from_pretrained(AST_NAME).to(self.device).eval()
        id2label = self.model.config.id2label
        self._build_groups([id2label[i] for i in range(len(id2label))])
        print(f"[AST] 준비 완료 ({self.device})")

    def run(self, mono, sr):
        torch = self.torch
        x = SL.resample(mono, sr, AST_SR)
        n = AST_PAD_SEC * AST_SR
        x = np.tile(x, int(ceil(n / max(1, len(x)))))[:n]      # 10초 클립으로 학습 → 반복해서 10초로
        inp = self.fe(x, sampling_rate=AST_SR, return_tensors="pt")
        inp = {k: v.to(self.device) for k, v in inp.items()}
        with torch.no_grad():
            scores = torch.sigmoid(self.model(**inp).logits)[0].cpu().numpy()
        return self.summarize(scores)


# ----------------------------------------------------------------------
# BEATs
# ----------------------------------------------------------------------
BEATS_SR = 16000
BEATS_PAD_SEC = 10
BEATS_PAD = False            # --beats-pad 로 켬. BEATs는 길이가 달라도 돌아가는 구조라 기본은 2초 그대로
BEATS_DIR = Path.home() / "beats_data"
BEATS_CKPT_NAME = "BEATs_iter3_plus_AS2M_finetuned_on_AS2M_cpt2.pt"
BEATS_SRC_BASE = "https://raw.githubusercontent.com/microsoft/unilm/master/beats/"
BEATS_SRC_FILES = ["BEATs.py", "backbone.py", "modules.py"]
BEATS_CKPT_URLS = [
    # Microsoft 공식 체크포인트를 개인이 올려둔 Hugging Face 사본 (원본 스크립트와 같은 주소)
    "https://huggingface.co/WeiChihChen/BEATs_iter3_plus_AS2M_finetuned_on_AS2M_cpt2/"
    "resolve/main/BEATs_iter3_plus_AS2M_finetuned_on_AS2M_cpt2.pt?download=true",
]
AUDIOSET_CSV_URLS = [
    "https://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/class_labels_indices.csv",
    "https://raw.githubusercontent.com/qiuqiangkong/audioset_tagging_cnn/master/metadata/class_labels_indices.csv",
]


def _download(urls, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    last = None
    for url in urls:
        try:
            print(f"[다운로드] {dest.name}")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
                total, done = int(r.headers.get("Content-Length") or 0), 0
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total > 5_000_000:
                        print(f"\r    {done / total * 100:5.1f}% ({done / 1e6:.0f}/{total / 1e6:.0f} MB)", end="")
            if total > 5_000_000:
                print()
            tmp.replace(dest)
            return
        except Exception as e:
            last = e
            print(f"    실패: {e}")
    if tmp.exists():
        tmp.unlink()
    raise RuntimeError(f"{dest.name} 다운로드 실패: {last}")


def _audioset_mid_to_name():
    """AudioSet MID(/m/...) → 클래스 이름. PANNs가 쓰는 csv가 있으면 그걸 사용"""
    import csv
    for path in [Path.home() / "panns_data" / "class_labels_indices.csv", BEATS_DIR / "class_labels_indices.csv"]:
        if path.exists() and path.stat().st_size > 1000:
            break
    else:
        path = BEATS_DIR / "class_labels_indices.csv"
        _download(AUDIOSET_CSV_URLS, path)
    with open(path, newline="", encoding="utf-8") as f:
        return {row["mid"]: row["display_name"] for row in csv.DictReader(f)}


class BEATsDet(SL.TaggerBase):
    name, kind = "BEATs", "tag"

    def __init__(self):
        import torch
        self.torch = torch
        self.device = SL.torch_device()
        print("[BEATs] 로딩 중... (iter3+ AS2M)")
        BEATS_DIR.mkdir(parents=True, exist_ok=True)
        for f in BEATS_SRC_FILES:
            dest = BEATS_DIR / f
            if not dest.exists() or dest.stat().st_size < 500:
                _download([BEATS_SRC_BASE + f], dest)
        ckpt_path = BEATS_DIR / BEATS_CKPT_NAME
        if not ckpt_path.exists() or ckpt_path.stat().st_size < 1e8:
            try:
                _download(BEATS_CKPT_URLS, ckpt_path)
            except Exception as e:
                raise SystemExit(f"[BEATs] 체크포인트 다운로드 실패({e}).\n"
                                 f"  {BEATS_CKPT_NAME} 을 https://github.com/microsoft/unilm/tree/master/beats 에서\n"
                                 f"  직접 받아 {BEATS_DIR} 에 넣어주세요.")
        if str(BEATS_DIR) not in sys.path:
            sys.path.insert(0, str(BEATS_DIR))
        from BEATs import BEATs, BEATsConfig
        try:
            ckpt = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
        except TypeError:
            ckpt = torch.load(str(ckpt_path), map_location="cpu")
        self.model = BEATs(BEATsConfig(ckpt["cfg"]))
        self.model.load_state_dict(ckpt["model"])
        self.model.to(self.device).eval()

        # 출력 번호 → AudioSet 클래스 이름 (체크포인트에는 MID로 들어 있음)
        label_dict = ckpt.get("label_dict", {})
        mid2name = _audioset_mid_to_name()
        n = int(self.model.predictor.out_features)
        labels = []
        for i in range(n):
            try:
                mid = label_dict[i]
            except (KeyError, IndexError, TypeError):
                mid = str(i)
            labels.append(mid2name.get(mid, mid))
        self._build_groups(labels)
        print(f"[BEATs] 준비 완료 ({self.device}, 입력 {'10초로 채움' if BEATS_PAD else '2초 그대로'})")

    def run(self, mono, sr):
        torch = self.torch
        x = SL.resample(mono, sr, BEATS_SR)
        if BEATS_PAD:
            n = BEATS_PAD_SEC * BEATS_SR
            x = np.tile(x, int(ceil(n / max(1, len(x)))))[:n]
        wav = torch.from_numpy(x).float().unsqueeze(0).to(self.device)
        mask = torch.zeros(wav.shape, dtype=torch.bool, device=self.device)
        with torch.no_grad():
            probs = self.model.extract_features(wav, padding_mask=mask)[0][0].cpu().numpy()
        return self.summarize(probs)


# ----------------------------------------------------------------------
# sound_live.py 에 모델 등록 후 그대로 실행
# ----------------------------------------------------------------------
SL.MODEL_CLASSES["ast"] = AST
SL.MODEL_CLASSES["beats"] = BEATsDet


def main():
    global BEATS_PAD
    if "--beats-pad" in sys.argv:
        sys.argv.remove("--beats-pad")
        BEATS_PAD = True
    if not any(a == "--models" or a.startswith("--models=") for a in sys.argv):
        sys.argv += ["--models", "clap,ast,panns,beats"]
    print(f"[sound_live_plus · sound_live {SL.VERSION} 규칙] {os.path.abspath(__file__)}")
    SL.main()


if __name__ == "__main__":
    main()
