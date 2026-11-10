# SoundCaption — 대사 너머의 소리까지, 실시간으로 보이게

청각장애인을 위한 **실시간 비언어 소리 자막** 데스크톱 앱 (Windows).
PC에서 나오는 소리를 루프백으로 캡처해 AI 모델(CLAP · PANNs · BEATs)로 분류하고,
중요한 소리만 골라 화면 위 투명 오버레이에 자막으로 보여 줍니다.
모드: 🔫 총게임 · 👻 공포게임 · 📺 예능 · 🧸 아동(그림 애니메이션)

## ▶ 바로 실행 (설치 필요 없음 — 시연용)

파이썬·라이브러리·AI 모델이 모두 들어 있는 휴대용 실행판입니다. 인터넷도 필요 없어요.

1. 오른쪽 **Releases** 에서 아래 두 파일을 받습니다.
   - `SoundCaption_1_program.zip` (약 530MB) — 프로그램 + 파이썬 + 라이브러리
   - `SoundCaption_2_models.zip` (약 1.3GB) — AI 모델
2. **두 zip 을 같은 곳에 압축 풀기** 합니다 (예: 바탕화면).
   둘 다 `SoundCaption` 폴더로 풀려서 한 폴더로 합쳐집니다.
   (zip 안에서 바로 실행하지 말고 꼭 "압축 풀기" 후 실행)
3. `SoundCaption\SoundCaption 실행.bat` 더블클릭.
   - 처음엔 모델을 올리느라 20초~1분 걸립니다 (창 아래 상태 줄).
   - "Windows의 PC 보호" 창이 뜨면 **추가 정보 → 실행**.
4. 문제가 생기면 `문제확인용 실행(콘솔).bat` 으로 실행하면 오류가 검은 창에 그대로 보입니다.
   기록은 `SoundCaption\logs\` 에 남습니다.

> 게임은 **테두리 없는 창 모드**로 해야 자막이 위에 보입니다.
> 압축은 바탕화면·USB 등 쓰기 가능한 곳에 푸세요 (`C:\Program Files` 는 피하기).

## 폴더 구성

| 폴더 | 내용 |
|---|---|
| `app/` | 앱 코드 (PySide6 UI, 엔진, 모드별 라벨·판정), 아동 모드 애니메이션 그림 `app/assets/kids_anim` |
| `launcher/boot.py` | 휴대용 실행기 — 모델 위치를 폴더 안(`models/home`)으로 고정, 오프라인, 오류 기록 |
| `runtime/` | 파이썬 3.11 + 라이브러리 (Release zip 에만 있음) |
| `models/` | CLAP(laion/clap-htsat-unfused) · PANNs Cnn14 · BEATs iter3+ (Release zip 에만 있음) |

## 개발용으로 직접 실행

```bat
py -3.11 -m pip install -r requirements_portable.txt
cd app
py -3.11 main.py
```
처음 실행 시 모델을 인터넷에서 받습니다 (Hugging Face · Zenodo · GitHub).

## 보안 · 프라이버시
- 모든 처리는 PC 안에서만, 외부 전송 없음, 녹음 파일 저장 안 함
- 게임 메모리 접근 · 코드 주입 · 입력 자동화 없음 (별도의 투명 창만 띄움)
- 실행판은 `HF_HUB_OFFLINE=1` 로 실행되어 네트워크에 접속하지 않음

## 실행판 구성 (재현 방법)
- Python: [python-build-standalone](https://github.com/astral-sh/python-build-standalone) 3.11.18 (Windows x64)
- 라이브러리: `requirements_portable.txt` (torch 2.8.0 CPU, torchaudio 2.8.0, transformers 5.x, PySide6-Essentials 등)
- 모델 라이선스는 각 원저작자(LAION, Kong et al. PANNs, Microsoft BEATs)를 따릅니다.
