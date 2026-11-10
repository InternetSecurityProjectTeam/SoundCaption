"""
gun_labels.py — 총게임 모드 라벨 세트 v2 (2026-10-14)

라벨 종류 (kind)
  confirm   : AudioSet(PANNs·BEATs)에도 확실히 있는 소리. CLAP 이 잡아도 AudioSet 이 거의 0 이면 버림
  clap_only : AudioSet 에 대응이 약하거나 없는 소리. CLAP 단독으로 판정, 기준은 높게
  sink      : 흡수 라벨. 엉뚱한 소리가 갈 곳. 화면에 안 띄우고, 다른 소리를 지우지도 않음
  as_only   : AudioSet 단독. CLAP 선택지에 안 넣고, AudioSet 이 plus_min 이상이면 '+' 로 표시 (유리)

group : 같은 group 은 CLAP 확률을 '합쳐서' 검출하고, 이름은 group 안 1등 (총성 4종·발소리 2종)
form  : instant(순간음 칸) / sustained(지속: 칸)
audioset : 대응 AudioSet 라벨 이름 (class_labels_indices.csv 표기 그대로). 없는 이름은 실행 시 경고 후 무시
"""

VERSION = "gun v1.12"   # sound_live_gun.py · gun_judge.py 와 같아야 함 (다르면 실행 시 경고)

LABELS = {
    # ---------------- 총성 ----------------
    # v1.1: 4종(단발·연발·먼·소음기)을 하나로 합침. 4개 라벨이 '큰 탕 소리' 선택지를 4배로 차지해서
    #       폭발까지 총성 묶음이 가져갔고, 이름은 항상 연발 총성이 1등이었음
    # v1.4: 작고 날카로운 '틱틱' 총소리(권총·소음기·멀리서 단발)용 문장 추가. 이 문장이 없어서 유리 깨지는 소리로 감
    #       (v1.1 에서 4종을 합칠 때 소음기·권총 문장이 빠졌음). 라벨 점수는 문장 중 최대값이라 큰 총성은 안 약해짐
    # v1.6: 실제 로그 — 이 게임의 작은 '틱틱' 총소리를 CLAP 은 '유리 깨지는 소리'로 0.5~0.75 줬고 총성 문장은 0.05~0.24.
    #       → 유리 라벨을 없애고 유리 문장을 총성 쪽으로 옮김 (CLAP 에게 유리처럼 들리는 소리 = 이 게임에선 총소리)
    #       AudioSet Gunshot 은 배경음악에 묻혀 0.00~0.01 → AudioSet 확인 대신 '돌발성'(신호 분석)으로 확인하는 길 추가
    #       solo_min: AudioSet 이 0 이어도 CLAP ≥ 이 값 + 돌발성 ≥ IMPULSE_MIN_DB 이면 표시
    # v1.10: 말소리가 총성으로 뜨는 문제 — 말하는 중(AudioSet 말소리 ≥ SPEECH_GUARD)이면 총성 기준을 올림
    #        talk_as_min : 말하는 중 AudioSet 하한 (평소 AS_FLOOR 0.05)
    #        talk_solo_min: 말하는 중 solo 경로 CLAP 기준 (평소 solo_min 0.40) + 돌발성은 IMPULSE_TALK_DB
    "gunshot": dict(name="총성", group="gunshot", kind="confirm", form="instant", solo_min=0.40, need_impulse=True,
                    talk_as_min=0.12, talk_solo_min=0.60,
                    # v1.11: solo 경로는 CLAP 원래 유사도(cos)도 이 이상이어야 함 (13:39:09 확률 0.59·cos 0.22 오표시)
                    # v1.11b: 0.30 → 0.25 — 15:01:42·43·47 진짜 총성이 cos 0.28~0.30 으로 막힘.
                    #         오표시 소리(Quack/Duck 패턴, 13:39:09 0.22 · 14:58:41 0.20)는 계속 막힘
                    solo_cos=0.25,
                    prompts=["gunshots from a rifle", "a single gunshot",
                             "small sharp ticking gunshots from a pistol",
                             "a suppressed gun firing with a quiet metallic tick",
                             "distant gunfire popping far away",
                             "glass window shattering", "breaking glass"],
                    audioset=["Gunshot, gunfire", "Machine gun", "Fusillade", "Cap gun"]),

    # ---------------- 총알·장전 (CLAP 주도) ----------------
    # v1.2: 피격음(bullet_hit) 삭제 — 총알이 벽에 맞는 소리도 '짧고 날카로운 충격음'이라 총성과 소리로 구분이 안 됨.
    #       게임에서 '피격'은 내가 맞았다는 뜻으로도 읽혀서 표시명도 헷갈림
    # min = 이 라벨만 따로 쓰는 CLAP 기준 (확신도 높을 때만)
    "bullet_whiz": dict(name="총알 스치는 소리", group="bullet_whiz", kind="clap_only", form="instant", min=0.60,
                        prompts=["bullets whizzing past", "a bullet flying by close to the ear"],
                        audioset=["Whoosh, swoosh, swish", "Whip"]),
    # v1.3: 장전 소리 삭제 — 0.7 이상에서도 실제 장전이 아니었음. 로그상 거의 모든 소리에서 2·3등으로 따라붙는
    #       '자석' 라벨이었고, 금속성 게임 소리 전반을 끌어당김. 내 장전은 내가 눌러서 아는 정보라 표시 가치도 낮음

    # ---------------- 발소리 (group: footsteps) ----------------
    "footsteps": dict(name="발소리", group="footsteps", kind="confirm", form="instant",
                      prompts=["footsteps walking", "footsteps running on the ground"],
                      audioset=["Walk, footsteps", "Run"]),

    # ---------------- 투척물 ----------------
    # v1.8: 3차(21:39~21:41) — 폭발이 자주 안 뜸. CLAP 은 폭발의 낮은 울림을 '차량 소리'로 들음
    #       (21:40:35~36 폭발음+ 순간에도 CLAP 1등은 차량 0.78·0.72, 폭발 0.05 이하)
    #       → 멀리서 웅 울리는 폭발 문장 추가, AudioSet 혼자 기준 0.35 → 0.20
    #         (21:40:39 Boom 0.20, 21:40:59 Artillery fire 0.26 이 기준 미달로 놓침)
    "explosion": dict(name="폭발음", group="explosion", kind="confirm", form="instant", plus_min=0.20,
                      prompts=["a grenade explosion", "a big explosion boom with a deep rumble",
                               "a distant explosion rumbling far away"],
                      audioset=["Explosion", "Boom", "Artillery fire"]),
    # v1.8: ★5 (21:41:18) 연막탄 — CLAP 연막탄 0.14 로 기준 0.25 미달 (1등은 차량 0.60) → 기준 0.20, 문장 추가
    "smoke": dict(name="연막탄 소리", group="smoke", kind="clap_only", form="instant", min=0.20,
                  prompts=["a smoke grenade hissing", "gas spraying out loudly",
                           "a smoke grenade releasing a long steady hiss"],
                  audioset=["Hiss", "Steam", "Spray"]),
    "flashbang": dict(name="섬광탄 소리", group="flashbang", kind="clap_only", form="instant",
                      prompts=["a flashbang bang followed by high pitched ringing"],
                      audioset=[]),
    # v1.9: 수류탄 핀 뽑는 소리 — 작고 금속성인 소리라 CLAP 단독 판정. 기준은 높게 (min 0.55)
    #       ⚠ v1.3 에서 삭제한 '장전' 라벨이 금속성 게임 소리를 끌어당기는 자석이었음. 같은 문제가 생기면
    #         (2·3등으로 계속 따라붙으면) 문장을 줄이거나 삭제. 'cos' 절대 검사(COS_MIN)도 함께 적용됨
    "grenade_pin": dict(name="수류탄 핀 소리", group="grenade_pin", kind="clap_only", form="instant", min=0.55,
                        prompts=["a grenade pin being pulled out with a metallic click",
                                 "a sharp metal ping of a grenade lever releasing"],
                        audioset=[]),

    # ---------------- 탈것 ----------------
    # v1.6: 배경음악 때문에 AudioSet Vehicle 이 0.13~0.29 로 약하게만 잡힘 → 차량만 AudioSet 혼자 기준 0.20 (plus_min)
    #       CLAP 문장에 평범한 주행 소리 추가 (기존은 굉음·질주뿐)
    # v1.8: 3차 — 차량이 계속 안 나는데 '차량 소리'가 자주 뜸 (사용자). CLAP 차량이 거의 모든 소리에 1~2등 (0.4~0.98) — 자석 라벨
    #       폭발 울림·연막탄 소리까지 차량으로 감. 표시된 순간의 AudioSet 차량 점수는 0.05~0.21 로 약함
    #       - 'driving a vehicle in a video game' 문장 삭제 (게임 소리 전반을 끌어오는 넓은 문장)
    #       - CLAP 이 잡아도 AudioSet 차량 0.15 이상 필요 (0.05 → 0.15), AudioSet 혼자 0.20 → 0.25
    #       - 유지 3초 → 2초 (한 번 뜨면 3초씩 남아서 더 자주 보였음)
    "vehicle": dict(name="차량 소리", group="vehicle", kind="confirm", form="sustained",
                    as_min=0.15, plus_min=0.25,          # v1.11: hold 삭제 (지속음 시작·유지 규칙으로 대체)
                    prompts=["a car engine revving", "a motorcycle driving fast",
                             "a car driving on a road with the engine humming"],
                    audioset=["Vehicle", "Car", "Motorcycle", "Engine", "Accelerating, revving, vroom",
                              "Motor vehicle (road)"]),
    # v1.8: 3차 ★2·★3 (21:40:38~47) 차량 충돌이 없었는데 [차량 충돌음]+ 0.40~0.65 가 7번 — 전부 AudioSet 'Smash, crash' 혼자.
    #       CLAP 충돌 문장은 한 번도 상위권에 없었음. Smash, crash 는 넓은 라벨 (교전 중 부서지는 소리·폭발 잔해 등)
    #       → AudioSet 혼자('+')는 사실상 막음 (0.35 → 0.80). CLAP 이 충돌로 들을 때만 표시
    "vehicle_crash": dict(name="차량 충돌음", group="vehicle_crash", kind="confirm", form="instant", plus_min=0.80,
                          prompts=["a car crashing into something", "a vehicle collision"],
                          audioset=["Smash, crash", "Skidding"]),
    "aircraft": dict(name="비행기 소리", group="aircraft", kind="confirm", form="sustained", min=0.30,
                     prompts=["a propeller airplane flying overhead", "a plane passing above"],
                     audioset=["Aircraft", "Fixed-wing aircraft, airplane", "Propeller, airscrew",
                               "Aircraft engine"]),
    # v1.9: 헬기 추가 — 비행기와 같은 group (aircraft). 헬기와 프로펠러 비행기는 CLAP 귀에 비슷해서
    #       라벨을 따로 두면 확률을 나눠 가짐 (총성 4종 교훈). group 으로 묶으면 합쳐서 검출하고 이름은 1등 라벨
    #       설정(min·hold 등)은 group 첫 라벨(비행기 소리) 것을 씀. 반드시 aircraft 바로 아래에 둘 것
    "helicopter": dict(name="헬기 소리", group="aircraft", kind="confirm", form="sustained",
                       prompts=["a helicopter flying overhead with thumping rotor blades",
                                "a helicopter hovering with a loud chopping sound"],
                       audioset=["Helicopter"]),

    # ---------------- 그 외 ----------------
    # v1.11: 13:39:26 교전 중 [문 소리] 오표시 (CLAP 0.56 · AudioSet Door 0.17) → AudioSet 하한 0.05 → 0.20
    "door": dict(name="문 소리", group="door", kind="confirm", form="instant", as_min=0.20,
                 prompts=["a door opening and closing", "a wooden door creaking open"],
                 audioset=["Door", "Slam", "Creak"]),
    # v1.6: 유리 깨지는 소리를 CLAP 선택지에서 뺌 — 이 게임 총소리를 계속 가져감. 문장은 총성으로 옮김
    # v1.7: 대신 AudioSet 단독(as_only)으로 복귀 — Shatter(산산조각) ≥ 0.40 이면 '+' 로 표시. CLAP 은 안 봄
    #       총소리일 때 Shatter 는 0.00~0.13 이었으니 0.40 이면 총소리를 유리로 착각할 일은 거의 없음
    #       한계: 배경음악이 크게 깔리면 AudioSet 이 진짜 유리 소리도 못 들을 수 있음
    "glass": dict(name="유리 깨지는 소리", group="glass", kind="as_only", form="instant", plus_min=0.40,
                  prompts=[], audioset=["Shatter"]),
    # v1.9: 화염병 — AudioSet 단독 (CLAP 선택지에 안 넣어 다른 소리 확률을 안 뺏음, glass 와 같은 방식)
    #       Fire 는 폭발·연막 직후에도 올라올 수 있어 시작 기준을 0.40 으로 높게. Crackle 은 넓은 라벨이라 오탐 많으면 삭제
    #       화염병 던지는 순간의 유리 깨짐은 glass 라벨이 따로 잡음
    "fire": dict(name="불 타는 소리", group="fire", kind="as_only", form="sustained", plus_min=0.40,   # v1.11: hold 삭제
                 prompts=[], audioset=["Fire", "Crackle"]),
    # 타격음 = 근접 공격(주먹·프라이팬). 소리 생김새가 '퍽·쿵' 이라 착지·물건 부딪힘·문 쿵 같은 둔탁한 소리를 다 끌어옴
    # v1.4: 확신도 높을 때만 (0.25 → 0.55)
    "punch": dict(name="타격음", group="punch", kind="clap_only", form="instant", min=0.55,
                  prompts=["punching sound", "a hit with a frying pan"],
                  audioset=["Slap, smack", "Whack, thwack"]),
    "water": dict(name="물소리", group="water", kind="confirm", form="sustained",
                  prompts=["swimming and splashing in water"],
                  audioset=["Splash, splatter", "Water"]),
    "beep": dict(name="신호음", group="beep", kind="confirm", form="instant",
                 prompts=["an electronic warning beep", "a game notification sound"],
                 audioset=["Beep, bleep", "Alarm"]),

    # ---------------- 흡수 라벨 (표시 안 함, 거부권 없음) ----------------
    # v1.3: 목소리 문장 추가 — 말소리 0.5~0.65 + 음악 0.45 구간이 목소리로 안 가고 유리 깨지는 소리(0.8)로 끌려갔음
    "voice": dict(name="목소리", group="voice", kind="sink", form="instant",
                  # v1.10: 말소리의 파열음·마찰음(ㅅ·ㅊ·ㅌ)이 총성 문장과 닮아 총성으로 가던 것을 흡수 (문장 2개 추가)
                  prompts=["a person talking", "people talking on voice chat",
                           "a streamer talking over background music",
                           "a person shouting excitedly",
                           "fast speech with sharp consonant sounds"], audioset=[]),
    "music": dict(name="음악", group="music", kind="sink", form="sustained",
                  prompts=["background music"], audioset=[]),
    "wind": dict(name="바람 소리", group="wind", kind="sink", form="sustained",
                 prompts=["wind blowing outdoors"], audioset=[]),
    "rain": dict(name="빗소리", group="rain", kind="sink", form="sustained",
                 prompts=["rain falling"], audioset=[]),
    "ambient": dict(name="조용한 배경", group="ambient", kind="sink", form="sustained",
                    prompts=["quiet outdoor ambience with faint wind and insects", "quiet room tone"],
                    audioset=[]),
    "ui_click": dict(name="메뉴 클릭음", group="ui_click", kind="sink", form="instant",
                     prompts=["a menu button click in a video game interface"], audioset=[]),
    "gear": dict(name="옷·장비 스치는 소리", group="gear", kind="sink", form="instant",
                 prompts=["clothes rustling and gear moving"], audioset=[]),
    "other": dict(name="기타 소리", group="other", kind="sink", form="instant",
                  prompts=["a random everyday sound"], audioset=[]),
}

# 말소리 점수 (디버그 출력용. 판정에는 안 씀)
SPEECH_AUDIOSET = ["Speech", "Male speech, man speaking", "Female speech, woman speaking",
                   "Child speech, kid speaking", "Conversation", "Narration, monologue"]

# ---------------- 판정 기준 (초기값, 테스트로 조정) ----------------
COS_MIN = 0.15        # 절대 검사 (clap_only 만): CLAP 원래 유사도 최고값이 이보다 낮으면 어느 라벨에도 안 맞는 소리 → 버림
# v1.1: 기준 낮춤 — 흡수 라벨 8개(음악·목소리·배경 등)가 확률을 나눠 가져서, 게임 소리 확률이 0.3 을 거의 못 넘었음
CLAP_MIN = 0.15       # confirm 의 CLAP 확률 기준 (0.30 → 0.15)
CLAP_SOLO_MIN = 0.25  # clap_only 의 CLAP 확률 기준 (0.45 → 0.25)
AS_FLOOR = 0.05       # confirm 은 AudioSet 이 이 미만이면 CLAP 찐빠로 보고 버림 (0.10 → 0.05)
STAR_MIN = 0.30       # AudioSet 이 이 이상이면 '*'(둘 다 동의)
AS_STRONG = 0.35      # CLAP 이 못 잡아도 AudioSet 혼자 이 이상이면 '+' (0.50 → 0.35)
                      # CLAP 은 softmax 라 겹친 소리 중 1등만 남음 → 동시에 난 2·3번째 소리는 AudioSet 이 받아줌
BEATS_WEIGHT = 0.6    # AudioSet 결합: BEATs 0.6 + PANNs 0.4
MAX_INSTANT = 5       # 순간음 최대 개수 (3 → 5)
MAX_SUSTAINED = 2     # 지속음 최대 개수
NEAR_MISS = 0.05      # 디버그: CLAP 이 이 이상 잡았는데 탈락한 소리는 탈락 이유 출력
IMPULSE_MIN_DB = 12.0 # 돌발성: 2초 구간 안에서 가장 센 10ms 순간이 보통 수준보다 몇 dB 튀었는지 (고음 위주)
                      # 총소리는 음악에 묻혀도 순간적으로 튐. 말소리·잔잔한 음악은 덜 튐. 초기값 — 로그의 '돌발' 숫자로 조정
SPEECH_GUARD = 0.40   # v1.10: AudioSet 말소리가 이 이상이면 '말하는 중' → 라벨의 talk_* 기준 적용 (총성만 사용)
IMPULSE_TALK_DB = 20.0  # v1.10: 말하는 중일 때 돌발성 기준 (평소 IMPULSE_MIN_DB 12). 말소리 자음도 12dB 은 쉽게 넘음
# v1.11: 지속음 시작·유지 분리 (예전 HOLD_SEC·라벨별 hold 대신)
SUS_START_AS = 0.50   # 지속음 시작은 CLAP 확인이 1번 이상 필요. 예외: 2초 연속 AudioSet 이 이 이상이면 AudioSet 만으로 시작
SUS_KEEP_RATIO = 0.5  # 유지: AudioSet 이 그 이벤트 최고점의 이 비율 이상 (CLAP 이 잡으면 비율 상관없이 유지)
SUS_GRACE = 1.0       # 유지 조건이 깨진 뒤 몇 초 더 보여 줄지 (깜빡임 방지)
SUS_START_SEC = 1.0   # v1.12: 시작하려면 이 시간(초) 이상 연속으로 잡혀야 함 (분석 간격 1초면 2회, 0.5초면 3회)
# 라벨별 따로 기준
#   min        : CLAP 기준 — 총알 스치는 소리 0.60 · 타격음 0.55 · 비행기 0.30 · 연막탄 0.20
#   as_min     : 확인형 AudioSet 하한 (기본 AS_FLOOR) — 차량 0.15 · 문 0.20
#   plus_min   : AudioSet 혼자 '+' 기준 (기본 AS_STRONG) — 차량 0.25 · 폭발 0.20 · 차량 충돌 0.80
#   solo_min   : 확인형인데 AudioSet 이 못 들어도 CLAP 이 이 이상이면 표시 — 총성 0.40
#   need_impulse: solo_min 경로는 돌발성 ≥ IMPULSE_MIN_DB 도 필요 — 총성
#   solo_cos   : (v1.11) solo 경로 CLAP 원래 유사도 기준 — 총성 0.25 (v1.11b)
#   (hold 는 v1.11 에서 삭제 — SUS_* 참고)
#   talk_as_min / talk_solo_min : (v1.10) 말하는 중(말소리 ≥ SPEECH_GUARD)일 때만 쓰는 기준 — 총성 0.12 · 0.60

# 정답 구간 평가(--eval)용: 정답 라벨 → group
TRUTH = {"연막": "smoke", "발소리": "footsteps", "총성": "gunshot", "폭발": "explosion"}


def groups():
    """group → [label key ...] (LABELS 순서 유지)"""
    g = {}
    for k, v in LABELS.items():
        g.setdefault(v["group"], []).append(k)
    return g


# =====================================================================
# 표시 전용 (2026-10-22) — 판정(계산)에는 전혀 쓰지 않음. 화면에 보일 때만 씀
#   onoma        : 기본 의성어. 의성어 켜짐이면 "표시명 의성어" (예: "총성 탕!")
#   prompt_onoma : {문장: 의성어} — 그 라벨 안에서 1등 문장이 이것이면 이 의성어 (기본 의성어보다 우선)
#   cat          : (2026-10-24) 소리 필터 분류 코드 = 분류.txt 중분류 (예: "5-8" 폭발·총기). 이름표는 sound_tree.CATS
#                  프론트 소리 필터는 대분류 > 중분류 > 이 라벨 3단 토글. 꺼 둔 라벨 키는 설정 'sounds_off' 로 옴
#                  계산은 다 하고, 칸 수 안에 뽑혔을 때 화면에서만 탈락 (빈자리는 안 채움)
#   toggle_name  : 소리 필터 토글에 보일 이름 (없으면 name). 같은 모드에서 이름이 같은 라벨은 토글 하나로 합쳐짐
#   표시 규칙   : sound_engine.display() — 의성어 꺼짐이면 표시명만
#   근거        : '모드별 의성어 매핑표' (gun v1.9 · variety v0.12 · horror v0.7 기준). 표에 없는 라벨은 의성어 없음
# =====================================================================
ONOMA = {
    "gunshot": "탕!",          # 총성은 문장별 구분 안 함 ('유리' 문장이 이 게임의 작은 총소리를 잡고 있어서)
    "explosion": "쾅!",
    "vehicle_crash": "쾅!",
    "flashbang": "펑!",
    "glass": "쨍그랑!",
    "punch": "퍽!",
    "smoke": "치익…",
    "beep": "삐빅",
}
PROMPT_ONOMA = {
    "door": {"a wooden door creaking open": "끼익…"},   # 기본 문 소리는 의성어 없음
}
CAT = {
    # 총·투척물은 소리 생김새(AudioSet 위치)가 아니라 사용자가 찾을 자리(5-8 폭발·총기)에 둠
    "gunshot": "5-8", "bullet_whiz": "5-8", "explosion": "5-8",
    "smoke": "5-8", "flashbang": "5-8", "grenade_pin": "5-8",
    "footsteps": "1-5",
    "vehicle": "5-1", "vehicle_crash": "5-1",
    "aircraft": "5-2", "helicopter": "5-2",
    "door": "5-4",
    "glass": "5-9",
    "fire": "4-1", "water": "4-2",
    "punch": "6-1",
    "beep": "6-3",
}
TOGGLE_NAME = {}

for _k, _v in ONOMA.items():
    LABELS[_k]["onoma"] = _v
for _k, _v in PROMPT_ONOMA.items():
    assert all(p in LABELS[_k]["prompts"] for p in _v), f"prompt_onoma 문장 오타: {_k}"
    LABELS[_k]["prompt_onoma"] = _v
for _k, _v in CAT.items():
    LABELS[_k]["cat"] = _v
for _k, _v in TOGGLE_NAME.items():
    LABELS[_k]["toggle_name"] = _v
