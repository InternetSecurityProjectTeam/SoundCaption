# SoundCaption — 대사 너머의 소리까지, 실시간으로 보이게

청각장애인을 위한 **실시간 비언어 소리 자막** 데스크톱 앱 (Windows).
PC에서 나오는 소리를 루프백으로 캡처해 AI 모델(CLAP · PANNs · BEATs)로 분류하고,
중요한 소리만 골라 화면 위 투명 오버레이에 자막으로 보여 줍니다.
모드: 🔫 총게임 · 👻 공포게임 · 📺 예능 · 🧸 아동(그림 애니메이션)

## ▶ 시연 PC에서 실행 (아무것도 설치 안 된 PC OK)

파이썬·라이브러리·AI 모델이 모두 이 저장소 안에 들어 있어요. 설치도 인터넷 연결(받은 뒤)도 필요 없어요.

1. 이 페이지 위쪽 초록색 **Code → Download ZIP** (약 1.8GB)
2. 받은 zip 을 우클릭 → **압축 풀기** (바탕화면 같은 짧은 경로 추천)
3. 풀린 폴더 안의 **`시연_설치및실행.bat`** 더블클릭
   - 처음 한 번만 `release_parts` 조각을 합쳐 `SoundCaption` 폴더로 풉니다 (1~3분, 창을 닫지 마세요)
   - 그다음부터는 누르면 바로 켜져요 (모델을 올리느라 20초~1분)
   - "Windows의 PC 보호" / 보안 경고가 뜨면 **추가 정보 → 실행** 또는 **실행**

문제가 생기면 `SoundCaption\문제확인용 실행(콘솔).bat` 을 실행하면 오류가 검은 창에 그대로 보이고,
기록은 `SoundCaption\logs\` 에 남아요.

> 게임은 **테두리 없는 창 모드**로 해야 자막이 위에 보여요.
> `C:\Program Files` 처럼 쓰기 금지된 곳에는 풀지 마세요.

## 저장소 구성

| 경로 | 내용 |
|---|---|
| `시연_설치및실행.bat` | 시연용 원클릭 실행 (처음엔 자동 설치) |
| `release_parts/` | 실행판 zip 2개를 90MB 조각으로 나눈 것 (GitHub 파일 크기 제한 때문) · `SHA256SUMS.txt` |
| `source/app/` | 앱 코드 (PySide6 UI, 엔진, 모드별 라벨·판정), 아동 모드 애니메이션 `source/app/assets/kids_anim` |
| `source/launcher/boot.py` | 휴대용 실행기 — 모델 위치를 폴더 안(`models/home`)으로 고정, 오프라인, 오류 기록 |
| `source/_setup/setup.ps1` | 조각 합치기 + 풀기 + 실행 (윈도우 기본 PowerShell만 사용) |

실행판(`SoundCaption` 폴더, 풀린 뒤) 구성: `app/` 코드 · `runtime/` 파이썬 3.11 + 라이브러리 · `models/` CLAP(laion/clap-htsat-unfused) · PANNs Cnn14 · BEATs iter3+ · `launcher/`

## 개발용으로 직접 실행

```bat
py -3.11 -m pip install -r source/requirements_portable.txt
cd source/app
py -3.11 main.py
```
처음 실행 시 모델을 인터넷에서 받습니다 (Hugging Face · Zenodo · GitHub).

## 보안 · 프라이버시
- 모든 처리는 PC 안에서만, 외부 전송 없음, 녹음 파일 저장 안 함
- 게임 메모리 접근 · 코드 주입 · 입력 자동화 없음 (별도의 투명 창만 띄움)
- 실행판은 `HF_HUB_OFFLINE=1` 로 실행되어 네트워크에 접속하지 않음

## 실행판 구성 (재현 방법)
- Python: [python-build-standalone](https://github.com/astral-sh/python-build-standalone) 3.11.18 (Windows x64)
- 라이브러리: `source/requirements_portable.txt` (torch 2.8.0 CPU, torchaudio 2.8.0, transformers 5.x, PySide6-Essentials 등)
- 모델 라이선스는 각 원저작자(LAION, Kong et al. PANNs, Microsoft BEATs)를 따릅니다.
