# -*- coding: utf-8 -*-
"""
휴대용 실행기 (SoundCaption Portable)

이 폴더만 있으면 파이썬·라이브러리·AI 모델이 없는 PC에서도 실행되게 함.
  - 모델 파일은 models/ 안에서만 찾음 (인터넷 연결 없이 동작)
  - 설정은 models/home/.sound-caption/settings.json 에 저장 (그 PC 사용자 폴더를 건드리지 않음)
  - 콘솔 창 없이 실행되므로, 화면에 나오던 기록은 logs/ 에 저장
"""
import os
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # SoundCaption 폴더
APP = os.path.join(ROOT, "app")
HOME = os.path.join(ROOT, "models", "home")
LOGS = os.path.join(ROOT, "logs")

# 1) 모델 위치를 이 폴더 안으로 고정 (Path.home() → models/home)
#    panns_data, beats_data, .cache/huggingface 가 모두 models/home 아래에 있음
os.environ["USERPROFILE"] = HOME
os.environ["HOME"] = HOME
os.environ["HF_HOME"] = os.path.join(HOME, ".cache", "huggingface")
os.environ["HF_HUB_OFFLINE"] = "1"          # 인터넷에서 받지 않음
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# 2) 기록 파일 (pythonw 는 콘솔이 없어서 print 가 사라지므로 파일로)
os.makedirs(LOGS, exist_ok=True)
log_path = os.path.join(LOGS, time.strftime("app_%m%d_%H%M%S.txt"))
try:
    _log = open(log_path, "w", encoding="utf-8", buffering=1)
except OSError:                                   # 폴더에 쓸 수 없으면 임시 폴더에
    import tempfile
    log_path = os.path.join(tempfile.gettempdir(), os.path.basename(log_path))
    _log = open(log_path, "w", encoding="utf-8", buffering=1)
if sys.stdout is None or not sys.stdout.isatty():
    sys.stdout = _log
    sys.stderr = _log
print(f"[portable] root={ROOT}")
print(f"[portable] python={sys.version}")

# 3) 앱 실행 (원래 run_app.bat 이 하던 'python main.py' 와 같음)
os.chdir(APP)
sys.path.insert(0, APP)
sys.argv = [os.path.join(APP, "main.py")] + sys.argv[1:]


def _show_error(msg):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None, msg + f"\n\n자세한 내용: {log_path}", "SoundCaption 실행 오류", 0x10)
    except Exception:
        pass


try:
    import runpy
    runpy.run_path(os.path.join(APP, "main.py"), run_name="__main__")
except SystemExit:
    raise
except BaseException:
    traceback.print_exc()
    _log.flush()
    _show_error("앱을 시작하지 못했어요.\n" + traceback.format_exc(limit=3)[-800:])
    sys.exit(1)
