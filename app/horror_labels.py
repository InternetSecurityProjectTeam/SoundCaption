"""
horror_labels.py — 👻 공포게임 모드 라벨 세트 v0.1 (2026-10-14, 예능 variety v0.12 구조 복제)

라벨 종류 (kind)
  confirm   : AudioSet(PANNs·BEATs)에도 확실히 있는 소리. CLAP 이 잡아도 AudioSet 이 거의 0 이면 버림
  clap_only : AudioSet 에 대응이 약하거나 없는 소리. CLAP 단독으로 판정, 기준은 높게
  sink      : 흡수 라벨. 엉뚱한 소리가 갈 곳. 화면에 안 띄우고, 다른 소리를 지우지도 않음
  as_only   : AudioSet 단독. CLAP 선택지에 안 넣고, AudioSet 이 plus_min 이상이면 '+' 로 표시

group : 같은 group 은 CLAP 확률을 '합쳐서' 검출하고, 이름은 group 안 1등 (지금은 전부 라벨 1개)
form  : instant(순간음 칸) / sustained(지속: 칸)
mood  : True 면 표시 이름을 '음악 분위기'로 바꿈 (배경음악 전용, 아래 MUSIC_MOODS)
audioset : 대응 AudioSet 라벨 이름 (class_labels_indices.csv 표기 그대로). 없는 이름은 실행 시 경고 후 무시

라벨별 옵션
  min          : CLAP 기준 (기본 confirm=CLAP_MIN, clap_only=CLAP_SOLO_MIN)
  as_min       : 확인형 AudioSet 하한 (기본 AS_FLOOR)
  plus_min     : AudioSet 혼자 '+' 기준 / as_only 기준 (기본 AS_STRONG)
  solo_min     : 확인형인데 AudioSet 이 못 들어도 CLAP 이 이 이상이면 표시
  need_impulse : solo_min 경로는 돌발성 ≥ IMPULSE_MIN_DB 도 필요
  impulse_min  : 돌발성 ≥ 이 값(dB)이어야 통과 (확인형·클랩 전용 모두)
  hold         : 지속음 유지 횟수(초). 없으면 HOLD_SEC
  solo_cos     : (v0.2) 대체 경로 절대 검사를 '이 라벨 자신의' CLAP 원래 유사도로 (없으면 전체 최고 cos ≥ COS_MIN)
  veto/veto_min: (v0.2) 이 AudioSet 라벨들이 veto_min 이상이면 표시 안 함
  need_mood    : (v0.2) 분위기 판단이 있을 때만 표시
  prompt_names : (v0.7) {문장: 표시 이름} — 그 문장이 라벨 안 1등이면 이름만 바꿈 (판정·확률은 그대로)

공포게임 특징 (설계 메모)
  - 조용한 구간이 길고 작은 소리(발소리·문 삐걱·숨소리)가 핵심 → 기준을 예능보다 낮게 시작
  - 조용한 구간의 작은 잡음이 갈 곳이 필요 → '조용한 배경' 흡수 라벨이 핵심
  - 게임 방송(스트리머)도 잘 돼야 함 → 목소리 흡수에 방송 말투 문장, 키보드·마우스 소리는 기타 흡수로
  - 한계: 스트리머 본인의 비명·웃음·숨소리는 게임 속 소리와 구분 불가 (그대로 표시됨)
"""

VERSION = "horror v0.11"   # sound_live_horror.py · horror_judge.py 와 같아야 함 (다르면 실행 시 경고)

LABELS = {
    # ---------------- 움직임·접근 (작은 소리가 핵심) ----------------
    # 발소리: 공포에선 작은 발소리가 핵심 정보 → 예능(0.35)보다 낮게 시작. 'Run' 은 넣지 않음 (예능 v0.8: 대화·음악에 늘 깔림)
    # v0.2: 1차(게임 방송) — CLAP 은 발소리를 1등으로 잡았는데(0.50·0.28·0.24, 자기 cos 0.25~0.29) AudioSet Walk 는 매번 0.00
    #       (말소리 0.6 이상이라 묻힘, 말소리 0.20 일 때도 0.00 — 게임 발소리를 AudioSet 이 잘 못 들음)
    #       → 대체 경로: CLAP ≥ 0.22 + 발소리 자기 cos ≥ 0.24. 키보드 타자(AudioSet Typing·Computer keyboard ≥ 0.10)면 거부
    #       ※ 돌발성은 안 씀 — 방송은 말소리 때문에 돌발이 늘 20~40dB 라 구분이 안 됨
    # v0.5: 3차 21:05:13·16·17·18·22 [문 소리] 0.34~0.66 — 사용자 확인: 전부 발소리. 모두 'slow knocking on a wooden door' 문장이 1등
    #       (자기 cos 0.20~0.27). 발소리 문장은 cos 0.10~0.12 → 이 게임의 발소리를 CLAP 은 '나무 문 두드리는 소리'로 들음
    #       → 그 문장을 발소리로 옮김 + '나무 바닥 쿵쿵 발소리' 문장 추가. 대체 경로 solo_cos 0.24 → 0.20, solo_min 0.22 → 0.30
    #       (2차 20:57:14~15 '노크'도 같은 문장이었음 — 발소리였을 가능성)
    "footsteps": dict(name="발소리", group="footsteps", kind="confirm", form="instant", min=0.22,
                      solo_min=0.30, solo_cos=0.20,
                      veto=["Typing", "Computer keyboard"], veto_min=0.10,
                      prompts=["footsteps walking", "footsteps running",
                               "slow footsteps on a creaky wooden floor",
                               "heavy footsteps thudding on a wooden floor",
                               "slow knocking on a wooden door"],   # v0.5: 문 소리(노크)에서 옮김 — CLAP 귀에는 이게 발소리
                      audioset=["Walk, footsteps"]),
    # 문 소리: 삐걱을 따로 쪼개지 않고 한 라벨 (쪼개면 확률 분산). 'Slam' 은 아래 '쾅'으로 (예능 v0.9)
    #   Creak·Squeak 은 넓은 라벨이라 AudioSet 혼자('+')는 0.45 로 높게
    # v0.3: 노크와 같은 group (사용자: 합칠까?) — 2차 20:56:57~58 노크 0.37 / 문 소리 0.21 → 다음 초 문 소리 0.49 처럼 서로 확률을 나눠 가짐
    #       → 검출은 둘의 CLAP 확률 합으로, 표시 이름은 그 순간 1등 (노크 또는 문 소리). 설정은 group 첫 라벨(문 소리) 것을 씀
    #       대체 경로: AudioSet 이 말소리에 묻혀 못 들어도 CLAP 합 ≥ 0.30 + 1등 문장 자기 cos ≥ 0.20. 키보드면 거부
    #       돌발성은 안 씀 (방송은 말소리 때문에 늘 20~40dB)
    # v0.6: 4차 ★5 21:13:05~06 문 소리(사용자 확인)를 CLAP 은 '쇠사슬' 0.57·0.36 으로 들음 (금속성 문), 문 소리 0.25 로 기준 미달
    #       → 무거운 금속 문 문장 추가, 기준 0.30 → 0.25
    "door": dict(name="문 소리", group="door", kind="confirm", form="instant", min=0.25, plus_min=0.45,
                 solo_min=0.25, solo_cos=0.20,
                 veto=["Typing", "Computer keyboard"], veto_min=0.10,
                 prompts=["a door opening and closing", "a creaky door slowly opening",
                          "a door hinge creaking",
                          "a heavy metal door creaking open"],   # v0.6
                 # v0.7: 끼익 문장이 1등이면 '문 끼익 소리' (사용자 요청). 같은 라벨 안이라 확률은 안 나뉨
                 # 2026-10-22: '문 끼익 소리' 이름 폐지 → 이름은 '문 소리' 그대로, 끼익 문장 3개는 의성어 '끼익…' (파일 맨 아래)
                 audioset=["Door", "Creak", "Squeak", "Knock"]),
    # 쾅: 문 쾅 닫힘·무거운 물건 떨어짐. 예능 '쾅 치는 소리' v0.12 구조 그대로 (AudioSet 둔탁음 + 돌발 15dB)
    # 2026-10-22: 표시명 '쾅' 폐지 → 1등 문장에 따라 '문 닫히는 소리' / '물건 떨어지는 소리' (의성어 쾅! / 쿵!)
    "impact": dict(name="문 닫히는 소리", group="impact", kind="confirm", form="instant", min=0.40, as_min=0.10,
                   plus_min=0.60, impulse_min=15.0,
                   prompts=["a door slamming shut loudly", "a heavy object falling and crashing to the floor"],
                   prompt_names={"a door slamming shut loudly": "문 닫히는 소리",
                                 "a heavy object falling and crashing to the floor": "물건 떨어지는 소리"},
                   audioset=["Slam", "Bang", "Thump, thud"]),
    # v0.2: 1차 — CLAP 노크 0.43·0.31·0.44 (자기 cos 0.20~0.29) 가 AudioSet Knock 0.00 으로 탈락 → solo_min 0.45 → 0.30,
    #       절대 검사는 노크 자기 cos ≥ 0.20. 20:47:52 노크 0.78 은 AudioSet Typing·Computer keyboard 0.18 → 키보드였을 가능성 → 거부 추가
    # v0.4: 2차 노크 표시가 사용자 확인 결과 문 소리 — 전부 'slow knocking on a wooden door' 문장이 끌어옴 (나무 문 쿵 소리)
    #       → 표시 이름도 '문 소리'로 완전히 합침 (사용자 결정). 노크 문장은 문 쪽 소리를 잡는 데 계속 씀
    "knock": dict(name="문 소리", group="door", kind="confirm", form="instant",   # v0.3: group door (설정은 문 소리 것)
                  prompts=["knocking on a door"],   # v0.5: 'slow knocking on a wooden door' 는 발소리로 옮김
                  audioset=["Knock"]),

    # ---------------- 사람·괴물 소리 ----------------
    # v0.3: 2차 20:57:03 스트리머 비명 — CLAP 비명 0.39·자기 cos 0.50 (아주 높음) 인데 AudioSet Screaming 0.01 (Sigh 0.47·Gasp 0.25 로 들음)
    #       → 대체 경로: CLAP ≥ 0.35 + 비명 자기 cos ≥ 0.40 (보통 소리는 cos 0.1~0.3)
    "scream": dict(name="비명", group="scream", kind="confirm", form="instant", as_min=0.10,
                   solo_min=0.35, solo_cos=0.40,
                   prompts=["a person screaming in fear", "a loud shrill scream",
                            "a short startled scream"],   # v0.8: 5차 21:24:52 놀란 비명을 '악당 웃음' 0.40 으로 들음 (비명 0.11)
                   audioset=["Screaming"]),
    # 괴물 소리: AudioSet 은 Growling·Roar 가 동물 라벨이라 넓고, 게임 괴물 소리는 합성음이 많아 잘 못 들을 수 있음
    #   → 클랩 전용, 기준 0.40 으로 높게 시작. 자석 라벨이 되면(2·3등으로 계속 따라붙음) 문장을 줄임
    # v0.2: 1차 20:49:32 [괴물 소리] 0.42 ('demonic distorted growl', AudioSet Speech 0.56·Snoring 0.07) — 스트리머 목소리 의심 → 0.50
    # v0.3: 2차 ★1·★2 사용자 확인 '괴물 소리' — 안 뜬 이유
    #       ★1 (20:57:26~27): CLAP 은 스트리머 목소리를 1등으로 고름 (괴물 0.08). AudioSet 은 Roaring cats 0.25·Wild animals 0.26 으로 들음
    #       ★2 (20:57:33~38): CLAP 괴물 0.26~0.41 (불길한 드론과 확률을 나눔) → v0.2 기준 0.50 에 막힘
    #       1차 20:48:08~09 에도 같은 패턴 (Roaring cats 0.18·0.23, Wild animals 0.22) — 두 로그에서 이 라벨들은 괴물 구간에만 나옴
    #       → 클랩 전용 → 확인형. CLAP ≥ 0.20 + AudioSet 맹수·으르렁 ≥ 0.10, 또는 AudioSet 혼자 ≥ 0.17 ('+')
    #       ('Animal' 은 너무 넓어서 안 넣음. 게임 속 진짜 동물 소리도 괴물 소리로 뜰 수 있음 — 한계)
    #       v0.2 의 스트리머 목소리 오표시(20:49:32)는 AudioSet 맹수 0 이라 이제 안 뜸
    "monster": dict(name="괴물 소리", group="monster", kind="confirm", form="instant",
                min=0.20, as_min=0.10, plus_min=0.17,
                solo_min=0.28, solo_cos=0.18,          # AudioSet 이 못 들어도 CLAP 이 확실하면 표시
                prompts=["a monster growling", "a creature roaring", "a demonic distorted growl",
                         "a zombie groaning",                      # 좀보이드 좀비용
                         "a low raspy zombie moan",
                         "a guttural undead growl",
                         "a gurgling rattling groan"],
                prompt_names={"a zombie groaning": "좀비 소리",
                              "a low raspy zombie moan": "좀비 소리",
                              "a guttural undead growl": "좀비 소리",
                              "a gurgling rattling groan": "좀비 소리"},
                audioset=["Roaring cats (lions, tigers)", "Growling", "Wild animals"]),   # 'zombie' 삭제 (없는 이름)
    "breathing": dict(name="거친 숨소리", group="breathing", kind="confirm", form="instant",
                      as_min=0.15, plus_min=0.45,
                      prompts=["heavy panting breathing", "a person gasping in fear"],
                      audioset=["Breathing", "Gasp", "Pant"]),
    # 울음: 예능 오인식 방지 세 겹 그대로 (AudioSet 하한 0.15, CLAP 0.30, 목소리 흡수 문장). 돌발 경로 없음
    "crying": dict(name="울음", group="crying", kind="confirm", form="instant",
                   min=0.30, as_min=0.15, plus_min=0.45,
                   prompts=["a person crying and sobbing", "a child crying"],
                   audioset=["Crying, sobbing", "Baby cry, infant cry", "Whimper"]),
    # 웃음: 기괴한 아이 웃음·악당 웃음. 스트리머 웃음도 뜸 (한계)
    "laughter": dict(name="웃음소리", group="laughter", kind="confirm", form="instant",
                     as_min=0.15, plus_min=0.45,
                     prompts=["a creepy child giggling", "a sinister evil laugh", "a person laughing"],
                     audioset=["Laughter", "Giggle", "Chuckle, chortle", "Snicker", "Belly laugh"]),

    # ---------------- 점프 스케어 ----------------
    # 괴물이 갑자기 튀어나올 때 크게 터지는 음악 한 방·효과음. 공포에서 가장 중요한 순간
    #   예능의 'dun dun dun sting'(배경음악 일반 칸)을 여기로 옮김. 음악이 점점 커지는 부분과 구분하려고 돌발 15dB 필요
    #   (예능 실측: 진짜 효과음 18~21dB, 음악 오인 3~15dB)
    "jumpscare": dict(name="깜짝 효과음",   # 2026-10-22: '점프 스케어' → '깜짝 효과음'
                       group="jumpscare", kind="clap_only", form="instant",
                      min=0.35, impulse_min=15.0,
                      prompts=["a sudden loud horror jump scare sound",
                               "a loud orchestral horror music sting",
                               "a dramatic dun dun dun music sting"],
                      audioset=[]),

    # ---------------- 사물·환경 ----------------
    # 유리 깨짐: 총게임 방식 그대로 AudioSet 단독 (CLAP 선택지에 안 넣음)
    "glass": dict(name="유리 깨짐", group="glass", kind="as_only", form="instant", plus_min=0.40,
                  prompts=[], audioset=["Shatter"]),
    # 전화벨: 예능 v0.7 교훈 — AudioSet 혼자 기준 0.50, 넓은 'Telephone' 은 안 넣음
    "phone": dict(name="전화벨", group="phone", kind="confirm", form="instant", plus_min=0.50,
                  prompts=["a phone ringing", "an old telephone ringing"],
                  audioset=["Telephone bell ringing", "Ringtone"]),
    "thunder": dict(name="천둥", group="thunder", kind="confirm", form="instant", plus_min=0.45,
                    prompts=["thunder rumbling", "a loud thunder crack"],
                    audioset=["Thunder", "Thunderstorm"]),
    # 물 떨어짐: 작고 반복적이라 발소리·딸깍과 헷갈릴 수 있음 → AudioSet Drip 0.15 이상 필요. 오탐 많으면 삭제
    "drip": dict(name="물방울",   # 2026-10-22: '물 떨어짐' → '물방울'
                  group="drip", kind="confirm", form="instant",
                 min=0.30, as_min=0.15, plus_min=0.45,
                 prompts=["water dripping", "water drops falling in a quiet room"],
                 audioset=["Drip"]),
    # v0.10: 물 찰박거리는 소리 — 물웅덩이·얕은 물을 걷거나 첨벙이는 소리. 물 떨어짐(drip)과 별도 라벨
    #        ⚠ 물 속 발소리는 발소리 라벨과 겹침. 확인형 + AudioSet 0.15 이상 필요로 해서 CLAP 이 마음대로 못 가져가게 함
    #          발소리가 찰박으로 바뀌어 뜨거나 발소리가 줄면 min 을 올리거나 삭제
    "splash": dict(name="물 찰박거리는 소리", group="splash", kind="confirm", form="instant",
                   min=0.30, as_min=0.15, plus_min=0.50,
                   prompts=["wading through shallow water with splashing footsteps",
                            "water sloshing and splashing"],
                   audioset=["Splash, splatter", "Slosh"]),
    # v0.10: 까마귀·부엉이 — AudioSet 단독 (CLAP 선택지에 안 넣어 다른 소리 확률을 안 뺏음, glass 와 같은 방식)
    #        야외 맵 분위기 소리. 넓은 'Bird' 라벨은 일부러 안 넣음 (작은 새소리까지 다 걸림). 오탐 많으면 plus_min 을 올림
    "birds": dict(name="까마귀·부엉이 소리", group="birds", kind="as_only", form="instant", plus_min=0.40,
                  prompts=[], audioset=["Crow", "Caw", "Owl", "Hoot"]),
    # v0.10: 라디오·TV 잡음 — AudioSet 단독. 지직거리는 정적(Static) 만 받음. 'White noise' 는 선풍기·바람까지 걸려서 안 넣음
    "static": dict(name="라디오·TV 잡음", group="static", kind="as_only", form="instant", plus_min=0.50,
                   prompts=[], audioset=["Static"]),
    # 쇠사슬·금속: 자석 라벨 위험 1순위 → CLAP 혼자 못 띄우게 확인형 (AudioSet 금속음 0.10 이상), 혼자 '+' 는 0.60
    #   잡음에 자주 걸리거나 2·3등으로 계속 따라붙으면 삭제
    "chain": dict(name="쇠사슬 소리", group="chain", kind="confirm", form="instant",
                  min=0.35, as_min=0.10, plus_min=0.60,
                  prompts=["metal chains rattling", "metal scraping against metal"],
                  # 2026-10-22: 긁는 문장이 1등이면 '쇠 긁히는 소리' (의성어 없음). 사슬 문장은 '쇠사슬 소리' 그대로
                  prompt_names={"metal scraping against metal": "쇠 긁히는 소리"},
                  audioset=["Rattle", "Scrape", "Chink, clink"]),

    # ---------------- 지속음 ----------------
    # 배경음악: 메인 선택지에는 하나만. 분위기 = 이 라벨 문장 중 가장 잘 맞은 문장의 분위기 (예능 v0.4~)
    #   불길한 드론도 흡수가 아니라 여기 '불길한 음악' 분위기로 표시 (사용자 결정)
    #   ⚠ 드론은 AudioSet 이 Music 으로 잘 안 들을 수 있음 → as_min 0.20 에 막히는지 첫 테스트에서 확인
    # v0.2: 1차 — 127초 중 46초 표시 (사용자: 긴장감 음악일 땐 잘 잡는데 아닐 땐 남발)
    #       - 분위기 판단이 있을 때만 표시 (need_mood). 공포게임은 음악이 거의 항상 깔려 그냥 '배경음악'은 정보가 없음
    #       - CLAP 기준 0.15 → 0.30 (CLAP 1등이 목소리인데 배경음악 0.15~0.24 로 뜨던 8번)
    "music": dict(name="배경음악", group="music", kind="confirm", form="sustained", min=0.30, plus_min=0.45, as_min=0.20,
                  mood=True, hold=1, need_mood=True,
                  prompts=[],   # 아래에서 채움
                  audioset=["Music", "Background music", "Theme music", "Soundtrack music",
                            "Scary music", "Ambient music"]),
    "heartbeat": dict(name="심장 박동", group="heartbeat", kind="confirm", form="sustained",
                      as_min=0.10, plus_min=0.45, hold=2,
                      prompts=["a heartbeat pounding", "a fast thumping heartbeat"],
                      audioset=["Heart sounds, heartbeat"]),
    # 바람: 야외 맵에선 계속 깔림. 지속음 칸이라 표시해도 방해 적음. 'Wind noise (microphone)' 는 안 넣음 (마이크 잡음)
    "wind": dict(name="바람 소리", group="wind", kind="confirm", form="sustained",
                 min=0.25, as_min=0.15, plus_min=0.45, hold=2,
                 prompts=["wind howling", "strong wind blowing outside"],
                 audioset=["Wind"]),

    # ---------------- 흡수 라벨 (표시 안 함, 거부권 없음) ----------------
    # 목소리: 게임 캐릭터 대사 + 스트리머 말소리. 속삭임 문장은 일부러 안 넣음
    "voice": dict(name="목소리", group="voice", kind="sink", form="instant",
                  prompts=["a person talking", "a streamer talking to the chat",
                           "a person muttering quietly to themselves",
                           "a person exclaiming in surprise while talking",
                           "a game character speaking dialogue"], audioset=[]),
    # 조용한 배경: 조용한 구간의 작은 잡음이 발소리·숨소리로 끌려가지 않게 (공포에서 특히 중요). 바람 문장은 넣지 않음
    "quiet": dict(name="조용한 배경", group="quiet", kind="sink", form="sustained",
                  prompts=["a quiet empty room", "faint background room tone"], audioset=[]),
    # v0.9: 빗소리 — 흡수 라벨 (표시 안 함). 야외·창가 맵에서 비가 바람·발소리·숨소리로 가지 않게
    #       바람 라벨처럼 화면에 띄우고 싶으면 kind="confirm", min=0.25, as_min=0.15, plus_min=0.45, hold=2,
    #       audioset=["Rain", "Raindrop"] 으로 바꾸면 됨 (이 경우 MAX_SUSTAINED=3 이 빠듯해질 수 있음)
    "rain": dict(name="빗소리", group="rain", kind="sink", form="sustained",
                 prompts=["rain falling outside", "rain pattering on a window or roof"], audioset=[]),
    # 기타: 방송 중 키보드·마우스 딸깍이 노크·발소리로 가지 않게
    # v0.8: 5차 — 종이 단서를 휙 집는 소리가 발소리로 뜸 (사용자 확인). 게임 속 물건 줍기·종이 소리가 갈 곳
    "other": dict(name="기타 소리", group="other", kind="sink", form="instant",
                  prompts=["a random everyday sound", "keyboard typing and mouse clicking",
                           "paper rustling", "quickly picking up a sheet of paper",
                           "picking up an item in a video game"], audioset=[]),
}

# ---------------- 음악 분위기 ----------------
# 분위기 = 배경음악 라벨 문장들 중 가장 잘 맞은 문장의 분위기 (예능 v0.4 방식)
MUSIC_GENERIC = ["background music playing", "music playing in a video game"]   # 이게 이기면 '판단 없음'
MUSIC_MOODS = {
    # v0.6: '추격 음악' 을 여기로 합침 — 4차: 실제로는 쫓기지 않는데 '추격'이 자주 뜸 (사용자: 이름이 틀림),
    #       같은 곡 안에서 추격↔긴장감이 계속 바뀜 (21:10:49~54, 21:13:43~47). 빠르고 강한 문장은 긴장감 쪽으로
    "긴장감 있는 음악": ["tense suspenseful background music", "slow building tension horror music",
                    "fast intense chase music", "frantic pounding horror chase music"],
    # 불길한: 공포게임에 거의 항상 깔리는 저음 드론·웅웅 (사용자 결정: 흡수 대신 분위기로 표시)
    "불길한 음악": ["a dark ominous ambient drone", "a low ominous rumbling drone sound"],
    "기괴한 음악": ["a creepy music box melody", "eerie children's choir singing"],
    # v0.2: '잔잔한 음악' 삭제 — 사용자: 장면과 안 맞음. 'calm gentle safe room music' 문장이 1차에서 거의 모든 음악의 1등 (자석 문장)
}
LABELS["music"]["prompts"] = MUSIC_GENERIC + [p for ps in MUSIC_MOODS.values() for p in ps]

MOOD_MIN = 0.35       # 분위기 1등 확률이 이 이상일 때만 이름
MOOD_LEAD = 0.10      # 1등 − 2등 ≥ 이 값 (비슷하면 판단 없음)
MOOD_GAP = -0.55      # 음악 − 말소리 ≥ 이 값
# v0.2: −0.10 → −0.55. 게임 방송은 말소리가 늘 0.6~0.7 이라 음악−말소리가 −0.3~−0.5 → 분위기 판단이 거의 전부 막힘
#       (1차 20:48:51~53 '표시 유지 34~36초째'). 음악이 거의 안 들릴 때만 막음
# v0.11: 아래 MOOD_CONFIRM·MOOD_KEEP·hold 는 '초' 기준 (분석 간격 0.5초면 횟수를 두 배로 셈, horror_judge.set_hop)
MOOD_CONFIRM = 3      # 다른 분위기로 바꾸려면 같은 판단이 연속 몇 번 (판단 없음은 건너뜀)
MOOD_STRONG = 0.85    # 확률이 이 이상이면 한 번에 바꿈
MOOD_KEEP = 5         # 판단 없음이 이 초 넘게 이어지면 '배경음악'으로

# 말소리 점수 (디버그 출력용. 판정에는 안 씀)
SPEECH_AUDIOSET = ["Speech", "Male speech, man speaking", "Female speech, woman speaking",
                   "Child speech, kid speaking", "Conversation", "Narration, monologue"]

# ---------------- 판정 기준 (예능 v0.12 값에서 시작, 테스트로 조정) ----------------
COS_MIN = 0.15        # 절대 검사 (clap_only · 돌발성 대체 경로): CLAP 원래 유사도 최고값이 이보다 낮으면 버림
CLAP_MIN = 0.15       # confirm 의 CLAP 확률 기준
CLAP_SOLO_MIN = 0.25  # clap_only 의 CLAP 확률 기준
AS_FLOOR = 0.05       # confirm 은 AudioSet 이 이 미만이면 CLAP 찐빠로 보고 버림
STAR_MIN = 0.30       # AudioSet 이 이 이상이면 '*'(둘 다 동의)
AS_STRONG = 0.35      # CLAP 이 못 잡아도 AudioSet 혼자 이 이상이면 '+' (확인형만)
BEATS_WEIGHT = 0.6    # AudioSet 결합: BEATs 0.6 + PANNs 0.4
MAX_INSTANT = 5       # 순간음 최대 개수
MAX_SUSTAINED = 3     # 지속음 최대 개수 (배경음악 + 심장 박동 + 바람)
NEAR_MISS = 0.05      # 디버그: CLAP 이 이 이상 잡았는데 탈락한 소리는 탈락 이유 출력
IMPULSE_MIN_DB = 12.0 # 돌발성 기준 (dB). 노크의 solo_min 경로에서 사용
HOLD_SEC = 3          # 지속음 유지 기본값 (라벨별 hold 가 우선)

# 정답 구간 평가(--eval)용: 정답 라벨 → group
# v0.3: 디버그에 CLAP 1~3등이 아니어도 항상 점수·자기 cos 를 찍어 볼 라벨 (작은 소리를 왜 못 잡는지 보려고)
WATCH = ["footsteps", "door", "knock", "monster", "scream"]

TRUTH = {"발소리": "footsteps", "문": "door", "쾅": "impact", "노크": "door", "비명": "scream",
         "괴물": "monster", "숨소리": "breathing", "울음": "crying", "웃음": "laughter",
         "점프스케어": "jumpscare", "유리": "glass", "전화": "phone", "천둥": "thunder", "물": "drip",
         "쇠사슬": "chain", "음악": "music", "심장": "heartbeat", "바람": "wind",
         "찰박": "splash", "새": "birds", "잡음": "static"}


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
    "glass": "쨍그랑!",
    "thunder": "쾅!",
    "phone": "따르릉",
    "knock": "똑똑",           # 표시명은 '문 소리' (door 그룹) → "문 소리 똑똑"
    "drip": "똑똑",
    "heartbeat": "두근두근",   # 지속음 중 유일한 의성어
}
PROMPT_ONOMA = {
    "door": {"a creaky door slowly opening": "끼익…",
             "a door hinge creaking": "끼익…",
             "a heavy metal door creaking open": "끼익…"},
    "impact": {"a door slamming shut loudly": "쾅!",
               "a heavy object falling and crashing to the floor": "쿵!"},
}
CAT = {
    "footsteps": "1-5",
    "door": "5-4", "knock": "5-4",          # 둘 다 표시명 '문 소리' → 토글도 하나로 합쳐짐
    "impact": "6-1",
    "scream": "1-1",
    "crying": "1-2", "laughter": "1-2",
    "breathing": "1-4", "heartbeat": "1-4",
    "monster": "2-3", "birds": "2-4",
    "music": "3-13",
    "thunder": "4-1", "wind": "4-1",
    "phone": "5-5",
    "glass": "5-9", "drip": "5-9", "splash": "5-9",
    "chain": "6-4",
    "jumpscare": "6-5",
    "static": "7-2",
}
TOGGLE_NAME = {   # 1등 문장에 따라 이름이 두 개로 뜨는 라벨 → 필터 토글에는 둘을 합친 이름
    "impact": "문 닫힘·물건 떨어짐",
    "chain": "쇠사슬·쇠 긁힘",
}

for _k, _v in ONOMA.items():
    LABELS[_k]["onoma"] = _v
for _k, _v in PROMPT_ONOMA.items():
    assert all(p in LABELS[_k]["prompts"] for p in _v), f"prompt_onoma 문장 오타: {_k}"
    LABELS[_k]["prompt_onoma"] = _v
for _k, _v in CAT.items():
    LABELS[_k]["cat"] = _v
for _k, _v in TOGGLE_NAME.items():
    LABELS[_k]["toggle_name"] = _v
