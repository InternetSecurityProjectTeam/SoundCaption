"""
variety_labels.py — 📺 예능 모드 라벨 세트 v0.1 (2026-10-14, 총게임 gun v1.7 구조 기준)

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
  impulse_min  : (v0.2) clap_only 도 돌발성 ≥ 이 값(dB)이어야 통과 — 효과음
"""

VERSION = "variety v0.15"   # sound_live_variety.py · variety_judge.py 와 같아야 함 (다르면 실행 시 경고)

LABELS = {
    # ---------------- 사람 반응 ----------------
    # 웃음: 출연자·관객 웃음을 한 라벨로 (나누면 확률을 나눠 가짐 — 총성 4종 교훈)
    "laughter": dict(name="웃음소리", group="laughter", kind="confirm", form="instant",
                     prompts=["people laughing", "a studio audience laughing out loud",
                              "a man laughing loudly", "a woman giggling"],
                     audioset=["Laughter", "Giggle", "Belly laugh", "Chuckle, chortle", "Snicker"]),
    # v0.9: 7차 19:58:03~04 관객 웃음·환호에 [박수] 0.26·0.49 (AudioSet Applause 0.14 이하). 진짜 박수는 AudioSet 이 잘 들음
    "applause": dict(name="박수", group="applause", kind="confirm", form="instant", as_min=0.20,
                     prompts=["an audience applauding", "people clapping their hands"],
                     audioset=["Applause", "Clapping"]),
    # 환호: AudioSet Yell 은 일부러 안 넣음 — 출연자 대사 외침까지 환호로 끌려옴 (v2.2 시절 문제)
    # v0.6: 관객 반응(웃음+환호 섞임)에 CLAP 이 매초 웃음/환호를 번갈아 고름 (0.16~0.19 낮은 점수). AudioSet 은 Laughter 0.21~0.23, Cheering 은 거의 0
    #       → 환호는 CLAP 0.25 이상 + AudioSet Cheering·Whoop 0.10 이상일 때만
    # v0.9: 7차 20:00:32 책상 쾅 직후 외침에 [환호] 0.53 → AudioSet 하한 0.10 → 0.20
    "cheer": dict(name="환호", group="cheer", kind="confirm", form="instant", min=0.25, as_min=0.20,
                  prompts=["a crowd cheering", "people cheering and whooping excitedly"],
                  audioset=["Cheering", "Whoop"]),
    "scream": dict(name="비명", group="scream", kind="confirm", form="instant", as_min=0.10,
                   prompts=["a person screaming in fear", "a loud shrill scream"],
                   audioset=["Screaming"]),
    # 울음: v2.2 시절 "뭐가!!" 같은 외침 대사 → 울음 오인식. 오인식 방지 세 겹
    #   ① AudioSet 하한 0.15 (CLAP 혼자서는 못 띄움)  ② CLAP 기준 0.30
    #   ③ 목소리 흡수 라벨에 '신나서 크게 떠드는 소리'·'허스키한 목소리' 문장   ※ 돌발성 대체 경로 없음
    "crying": dict(name="울음", group="crying", kind="confirm", form="instant",
                   min=0.30, as_min=0.15, plus_min=0.45,
                   prompts=["a person crying and sobbing", "someone weeping with a trembling voice"],
                   audioset=["Crying, sobbing", "Whimper"]),

    # ---------------- 정답·오답 (게임 코너) ----------------
    # v0.11: '딩동 소리' 라벨 삭제 — 'correct answer chime' 문장이 예능의 반짝이는·띵 하는 효과음을 거의 다 끌어옴
    #        (8차 20:09:48~49, 9차 20:12:44·20:12:50·20:13:03 모두 사용자 확인 결과 효과음). 정답 딩동도 예능에선 효과음의 한 종류
    #        → 문장은 효과음 라벨로 옮기고, 상황극 초인종만 AudioSet 단독 '초인종'으로 남김
    "doorbell": dict(name="초인종", group="doorbell", kind="as_only", form="instant", plus_min=0.40,
                     prompts=[], audioset=["Doorbell", "Ding-dong"]),
    # v0.10: 지금까지 뜬 [땡 부저] 4번이 전부 다른 소리 — 1차·5차 '띠리링' 효과음, 7차 잡음, 8차 20:07:55 쨍그랑 소리
    #        (AudioSet Chink, clink 0.28). 전부 AudioSet Buzzer 가 0 인데 CLAP + 돌발성 대체 경로로 통과
    #        → 대체 경로 삭제, AudioSet Buzzer 0.10 이상일 때만 (진짜 퀴즈 부저는 AudioSet 이 Buzzer 로 들음)
    # v0.15: 표시 이름 '땡 부저' → '오답'
    "buzzer": dict(name="오답", group="buzzer", kind="confirm", form="instant", as_min=0.10,
                   prompts=["a wrong answer buzzer on a game show", "a loud harsh buzzer"],
                   audioset=["Buzzer"]),

    # ---------------- 예능 효과음 (CLAP 주도, 한 라벨) ----------------
    # 종류별로 쪼개지 않고 문장 중 최대값으로 받음. AudioSet 혼자 '+' 경로 없음 (Boing·Whoosh 는 넓은 라벨)
    # ⚠ 자석 라벨이 될 위험이 제일 큼 — 로그에서 2·3등으로 계속 따라붙으면 문장을 줄이거나 기준을 올림
    # v0.2: 긴장감 있는 배경음악(AudioSet Theme/Scary music)에 효과음 0.8~0.99 가 13초 연속으로 뜸 → 음악을 효과음으로 들음
    #       - 'dramatic dun dun dun sting' 문장 삭제 (효과성 음악이라 긴장 배경음악과 소리가 같음) → 배경음악 문장으로 옮김
    #       - 기준 0.30 → 0.35, 돌발성 ≥ 12dB 필요 (impulse_min). 진짜 효과음은 18~21dB, 음악 구간은 3~15dB 였음
    # v0.13: 효과음이 잘 안 잡힘 — 효과음은 0.3~1초로 짧아 2초 구간 대부분이 대사·음악이라 CLAP 이 낮게 줌 (목소리·배경음악이 1등)
    #        AudioSet 은 섞인 소리에서도 소리별로 따로 점수를 매기므로, CLAP 이 낮아도 AudioSet 이 동의하면 통과시키는 보조 경로 추가
    #        assist_min : 보조 경로의 CLAP 기준 (평소 min 0.35) · assist_as : 보조 경로의 AudioSet 하한
    #        돌발성(impulse_min)은 보조 경로에도 그대로 적용 → 음악을 효과음으로 듣던 v0.2 문제는 막힘
    #        audioset 에 Ding·Chime 추가 (보조 경로 전용: sfx 는 AudioSet 혼자 '+' 로는 안 뜸)
    "sfx": dict(name="효과음", group="sfx", kind="clap_only", form="instant", min=0.35, impulse_min=12.0,
                assist_min=0.15, assist_as=0.10,
                prompts=["a cartoon boing sound effect", "a comedic slide whistle",
                         "a rimshot drum ba-dum-tss", "a cartoon pop sound effect",
                         "a whoosh transition sound effect",
                         "a short sparkling chime sound effect",    # v0.10: '띠링' 반짝이는 효과음 (딩동으로 가던 것)
                         "a correct answer ding dong chime on a game show"],   # v0.11: 딩동 라벨에서 옮김
                audioset=["Boing", "Zing", "Whoosh, swoosh, swish", "Ding", "Chime"]),

    # ---------------- 상황극 소리 ----------------
    "knock": dict(name="노크", group="knock", kind="confirm", form="instant",
                  solo_min=0.45, need_impulse=True,
                  prompts=["knocking on a door"],
                  audioset=["Knock"]),
    # v0.9: 7차 20:00:30 책상을 쾅 내리친 소리가 [문 소리] 0.37 ('door slamming' + AudioSet Hammer·Door) → 'Slam' 빼고 기준 0.35,
    #       '쾅' 소리는 아래 impact 라벨로
    "door": dict(name="문 소리", group="door", kind="confirm", form="instant", min=0.35,
                 prompts=["a door opening and closing", "a door slamming shut"],
                 audioset=["Door", "Creak"]),
    # v0.9 새 라벨: 책상·탁자를 쾅 내리치는 둔탁음 (예능 리액션). 클랩 전용 + 돌발성 15dB 이상 (7차 책상 쾅 17dB)
    #   ⚠ 드럼 한 방·발 구르기도 끌어올 수 있음 — 다음 테스트에서 확인
    # v0.12: 10차 20:18:47 쾅이 아닌 소리에 [쾅 치는 소리] 0.66 (돌발 19dB, AudioSet 상위는 말소리·음악뿐) → 클랩 전용 → 확인형.
    #        AudioSet 이 둔탁한 충격음(Thump·Bang·Slam·Hammer·Knock 중 하나)을 0.10 이상 들어야 표시
    #        진짜 책상 쾅(7차 20:00:30)은 AudioSet Hammer 0.20 이었음. AudioSet 혼자('+')는 0.60 으로 사실상 막음
    "impact": dict(name="쾅 치는 소리", group="impact", kind="confirm", form="instant", min=0.40, as_min=0.10,
                   plus_min=0.60, impulse_min=15.0,
                   prompts=["slamming a hand down hard on a table", "a loud dull thud of something hitting a desk"],
                   audioset=["Thump, thud", "Bang", "Slam", "Hammer", "Knock"]),
    # v0.7: 예능 '띠리링' 효과음에 AudioSet Bicycle bell 0.42 → Telephone bell ringing 0.39 가 떠서 AudioSet 혼자('+')로 전화벨 표시
#       (CLAP 전화벨은 0.01). 진짜 전화벨이면 CLAP 도 잡을 것 → AudioSet 혼자 기준 0.50, 넓은 'Telephone' 삭제
    "phone": dict(name="전화벨", group="phone", kind="confirm", form="instant", plus_min=0.50,
                  prompts=["a phone ringing", "a smartphone ringtone"],
                  audioset=["Telephone bell ringing", "Ringtone"]),
    # v0.8: 6차 19:51:53 대화 중 [발소리] 0.29 — AudioSet 'Run' 0.15 가 확인해 줌. 'Run' 은 예능 대화·음악에 늘 0.1~0.2 로 깔림
#       → 'Run' 삭제, CLAP 기준 0.35 (진짜 발소리면 CLAP 이 높게 잡음: 19:51:37 0.86)
    "footsteps": dict(name="발소리", group="footsteps", kind="confirm", form="instant", min=0.35,
                      prompts=["footsteps walking", "footsteps running"],
                      audioset=["Walk, footsteps"]),
    # v0.13: 삐 소리(검열음) — 예능 단골인데 문장이 없었음. AudioSet 단독 (CLAP 확률을 안 뺏음, 폭죽·초인종과 같은 방식)
    #        'Beep, bleep' 은 게임 신호음·전자레인지에도 뜰 수 있으나 예능에선 검열음이 대부분. 오탐이 보이면 plus_min 을 올림
    "censor": dict(name="삐 소리(검열음)", group="censor", kind="as_only", form="instant", plus_min=0.45,
                   prompts=[], audioset=["Beep, bleep"]),
    # 폭죽: 축하·생일·여행 장면에 가끔. CLAP 선택지에 안 넣어 다른 소리 확률을 안 뺏음
    "fireworks": dict(name="폭죽 소리", group="fireworks", kind="as_only", form="instant", plus_min=0.40,
                      prompts=[], audioset=["Fireworks", "Firecracker"]),

    # ---------------- 음악 (지속음) ----------------
    # 배경음악: 메인 선택지에는 '하나'만 (분위기별로 라벨을 나누면 음악 위에 깔린 웃음·박수·효과음이 1등을 못 함)
    #   AudioSet 은 음악을 잘 들으니, CLAP 이 다른 소리를 1등으로 골라도 '+' 로 같이 뜸
    # v0.2: 긴장·극적인 배경음악이 갈 곳이 없어서 효과음으로 감 → 문장 추가 (라벨은 하나, 문장 중 최대값)
    # v0.4: 문장은 아래 MUSIC_GENERIC + MUSIC_MOODS 에서 채움 (분위기 = 이 라벨 안에서 가장 잘 맞은 문장의 분위기)
    # v0.8: hold=1 — 음악이 끝나도 3초 더 표시되던 문제 (6차 19:51:09~11: 같은 점수 0.64 가 3번 = 유지 표시).
    #       AudioSet 이 음악을 안정적으로 들어서 깜빡임 방지가 거의 필요 없음
    # v0.9: 7차 — 배경음악이 없는 대화 구간에 AudioSet Music 0.31~0.43 만으로 '+' 표시 (19:59:19~39 등),
    #       CLAP 'dun dun sting' + Music 0.10 으로도 표시 (19:58:47). 진짜 배경음악은 대부분 Music 0.5 이상
    #       → AudioSet 혼자 0.30 → 0.45, CLAP 이 잡아도 Music 0.20 이상 필요
    "music": dict(name="배경음악", group="music", kind="confirm", form="sustained", plus_min=0.45, as_min=0.20, mood=True, hold=1,
                  prompts=[],   # 아래에서 채움
                  audioset=["Music", "Background music", "Theme music", "Soundtrack music"]),
    # 노래: 출연자가 직접 부르는 노래. 배경음악 보컬에도 뜰 수 있어 AudioSet 혼자 기준을 높게
    "singing": dict(name="노래 부르는 소리", group="singing", kind="confirm", form="sustained",
                    as_min=0.15, plus_min=0.50,
                    prompts=["a person singing a song", "people singing karaoke"],
                    audioset=["Singing", "Male singing", "Female singing"]),

    # ---------------- 흡수 라벨 (표시 안 함, 거부권 없음) ----------------
    # 목소리: 대사가 외침·환호·울음·비명으로 끌려가지 않게 받아 주는 곳
    "voice": dict(name="목소리", group="voice", kind="sink", form="instant",
                  prompts=["a person talking", "a TV host talking to the audience",
                           "several people chatting and talking over each other",
                           "a person shouting excitedly while talking",
                           "people bickering loudly and jokingly",
                           "a man talking with a husky voice"], audioset=[]),
    "studio": dict(name="방송 배경 소음", group="studio", kind="sink", form="sustained",
                   prompts=["TV studio background noise with people murmuring", "quiet room tone"],
                   audioset=[]),
    "other": dict(name="기타 소리", group="other", kind="sink", form="instant",
                  prompts=["a random everyday sound"], audioset=[]),
}

# ---------------- 음악 분위기 (v0.4) ----------------
# v0.3 까지는 분위기 문장을 따로 비교했는데, 2차 테스트에서 같은 코믹 음악에 코믹·신남·긴장을 오감.
# 반면 배경음악 라벨 안에서 가장 잘 맞은 문장은 매우 안정적이었음 (말소리가 음악만큼 커도)
#   긴장 구간 19:17:45~53 → 9초 내내 'dramatic background music with heavy drums'
#   코믹 구간 19:17:54~19:19:48 → 거의 전부 'playful comedic background music'
# → 분위기 = 배경음악 라벨 문장들 중 가장 잘 맞은 문장의 분위기. 분위기 문장이 곧 배경음악 라벨의 문장
# v0.7: 'dun dun dun sting' 은 곡 전체 분위기가 아니라 '한 방' 소리 → 분위기 투표에서 뺌 (일반 칸으로)
#       5차 테스트: 같은 코믹 곡 안의 드럼 한 방마다 이 문장이 1등 → 긴장으로 바뀜 (19:45:48~54)
#       문장 자체는 배경음악 라벨에 남김 (빼면 v0.1 때처럼 긴장 음악이 효과음으로 감)
MUSIC_GENERIC = ["background music playing", "music playing in a TV show",
                 "a dramatic dun dun dun music sting"]    # 이게 이기면 '판단 없음'(분위기 이름 안 바꿈)
MUSIC_MOODS = {
    # v0.6: 'sneaky suspenseful' 추가 — 예능의 살금살금·통통 튀는 긴장 음악용 (시험 중, 4차 로그 확인 필요)
    "긴장감 있는 음악": ["tense suspenseful background music", "dramatic background music with heavy drums",
                    "sneaky suspenseful background music"],
    # v0.6: 'silly bouncy cartoon' 삭제 — 4차 테스트에서 거의 모든 배경음악에 1등(0.7~1.0)으로 붙는 자석 문장.
    #       사용자가 긴장감 있다고 한 음악(19:38:0x~30)도 이 문장이 가져감. 2차 테스트(이 문장 없던 때)는 'playful comedic' 만으로 코믹을 잘 잡았음
    # v0.8: 코믹 + 신나는 → '경쾌한 음악' 하나로 (사용자 결정). 같은 곡 안에서 구간마다 둘이 번갈아 1등 (5차 ★#3)
    "경쾌한 음악": ["playful comedic background music", "upbeat energetic pop background music"],
    "슬픈 음악": ["sad emotional piano background music"],
    "잔잔한 음악": ["calm gentle acoustic background music"],
    "웅장한 음악": ["epic grand orchestral background music"],
}
LABELS["music"]["prompts"] = MUSIC_GENERIC + [p for ps in MUSIC_MOODS.values() for p in ps]

# v0.14: 음악 분위기에 AudioSet '음악 분위기' 라벨을 보조 증거로 추가 (긴장 음악을 경쾌로 듣던 문제)
#   지금까지 분위기는 CLAP 문장 유사도 하나로만 정했음 → 다른 라벨처럼 AudioSet 의 의견도 반영
#   분위기 이름 → AudioSet 라벨 (class_labels_indices.csv 표기 그대로). 없는 이름은 실행 시 경고 후 무시
#   'Exciting music' 은 긴장 음악에도 뜨는 애매한 라벨이라 일단 뺌
MUSIC_MOOD_AUDIOSET = {
    "긴장감 있는 음악": ["Scary music"],
    "경쾌한 음악": ["Happy music", "Funny music"],
    "슬픈 음악": ["Sad music"],
    "잔잔한 음악": ["Tender music"],
}
# AudioSet 분위기 점수 1.0 당 CLAP 유사도(cos)에 더해 주는 값. 가산점이라 CLAP 이 확실하면 영향이 작고 애매할 때만 뒤집음
#   긴장 음악이 아직 경쾌로 나오면 올리고(0.15~0.20), 코믹 곡이 긴장으로 넘어가면 내림(0.05). 0 이면 v0.13 과 동일
MOOD_AS_W = 0.10

MOOD_MIN = 0.35       # 분위기(일반 포함 7칸) 1등 확률이 이 이상일 때만 이름
MOOD_LEAD = 0.10      # 1등 − 2등 ≥ 이 값 (비슷하면 '배경음악')
MOOD_GAP = -0.10      # 음악 − 말소리 ≥ 이 값 (말소리가 음악보다 확실히 클 때만 막음. 2차 로그: −0.06 에서도 맞았음)
# v0.5: 3차 테스트 — 같은 코믹 음악인데 말소리·웃음이 커질 때마다 '판단 없음'이 나와 배경음악 ↔ 코믹이 계속 깜빡임
#       (133초 중 45초가 판단 없음, 그때 이번 1등은 대부분 여전히 '코믹')
#       → 판단 없음은 '모른다'일 뿐, '배경음악으로 바꿔라'가 아님. 표시를 그대로 두고, 오래 모르면 그때 배경음악
# v0.15: 아래 MOOD_CONFIRM·MOOD_KEEP·hold 는 '초' 기준 (분석 간격 0.5초면 횟수를 두 배로 셈, variety_judge.set_hop)
MOOD_CONFIRM = 3      # 다른 분위기로 바꾸려면 같은 판단이 연속 몇 번 (판단 없음은 건너뜀). v0.6: 2 → 3 (코믹 중 신나는 2초짜리 끼어듦)
MOOD_STRONG = 0.85    # 확률이 이 이상이면 한 번에 바꿈 (코믹이 시작됐는데 한참 뒤에야 바뀌던 문제). v0.6: 0.70 → 0.85 (신나는 0.77 한 번에 바뀜)
MOOD_KEEP = 5         # 판단 없음이 이 초 넘게 이어지면 '배경음악'으로 (재생이 멈추면 바로 초기화). 3차 로그: 판단 없음은 대부분 1~4초, 6·8초 한 번씩

# 말소리 점수 (디버그 출력용. 판정에는 안 씀)
SPEECH_AUDIOSET = ["Speech", "Male speech, man speaking", "Female speech, woman speaking",
                   "Child speech, kid speaking", "Conversation", "Narration, monologue"]

# ---------------- 판정 기준 (총게임 v1.7 값에서 시작, 테스트로 조정) ----------------
COS_MIN = 0.15        # 절대 검사 (clap_only 만): CLAP 원래 유사도 최고값이 이보다 낮으면 버림
CLAP_MIN = 0.15       # confirm 의 CLAP 확률 기준
CLAP_SOLO_MIN = 0.25  # clap_only 의 CLAP 확률 기준
AS_FLOOR = 0.05       # confirm 은 AudioSet 이 이 미만이면 CLAP 찐빠로 보고 버림
STAR_MIN = 0.30       # AudioSet 이 이 이상이면 '*'(둘 다 동의)
AS_STRONG = 0.35      # CLAP 이 못 잡아도 AudioSet 혼자 이 이상이면 '+' (확인형만)
BEATS_WEIGHT = 0.6    # AudioSet 결합: BEATs 0.6 + PANNs 0.4
MAX_INSTANT = 5       # 순간음 최대 개수
MAX_SUSTAINED = 2     # 지속음 최대 개수 (배경음악 + 노래)
NEAR_MISS = 0.05      # 디버그: CLAP 이 이 이상 잡았는데 탈락한 소리는 탈락 이유 출력
IMPULSE_MIN_DB = 12.0 # 돌발성 기준 (dB). 딩동·부저·노크의 solo_min 경로에서 사용
HOLD_SEC = 3          # 지속음은 한 번 잡히면 이 횟수(초) 동안 유지 (깜빡임 방지). 라벨별 hold 로 따로 (배경음악 1 = 유지 없음)

# 정답 구간 평가(--eval)용: 정답 라벨 → group
TRUTH = {"웃음": "laughter", "박수": "applause", "환호": "cheer", "비명": "scream", "울음": "crying",
         "딩동": "sfx", "초인종": "doorbell", "땡": "buzzer", "효과음": "sfx", "검열": "censor", "노크": "knock", "문": "door", "전화": "phone",
         "발소리": "footsteps", "쾅": "impact", "폭죽": "fireworks", "음악": "music", "노래": "singing"}


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
    "applause": "짝짝",
    "doorbell": "딩동",
    "buzzer": "땡!",
    "knock": "똑똑",
    "phone": "따르릉",
    "fireworks": "펑",
}
PROMPT_ONOMA = {
    "sfx": {"a cartoon boing sound effect": "띠용!",
            "a cartoon pop sound effect": "뿅!",
            "a whoosh transition sound effect": "휙",
            "a short sparkling chime sound effect": "띠링",
            "a correct answer ding dong chime on a game show": "딩동댕"},   # slide whistle·rimshot 은 의성어 없음
    "door": {"a door slamming shut": "쾅!"},
}
CAT = {
    "scream": "1-1",
    "laughter": "1-2", "crying": "1-2",
    "singing": "1-3",
    "applause": "1-5", "cheer": "1-5", "footsteps": "1-5",
    "music": "3-13",
    "doorbell": "5-4", "knock": "5-4", "door": "5-4",
    "phone": "5-5",
    "buzzer": "5-6",
    "fireworks": "5-8",
    "impact": "6-1",
    "censor": "6-3",
    "sfx": "6-5",
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
