"""
kids_labels.py — 🧸 아동 모드 라벨 세트 v0.1 (2026-11-05)

근거 문서 : 프로젝트 '아동 모드 - 라벨 목록' · '아동 모드 - 라벨·자막 v0.1'
구조      : 공포게임 horror_labels.py v0.11 과 같은 형식 (판정은 kids_judge.py = horror_judge 구조)
대상      : 청각장애 아동이 애니메이션·동물·탈것·키즈 영상을 볼 때

라벨 종류 (kind) — horror_labels.py 와 같음
  confirm   : CLAP + AudioSet 확인. AudioSet 이 거의 0 이면 버림
  clap_only : CLAP 단독 (기준 높게)
  as_only   : AudioSet 단독. CLAP 선택지에 안 넣음
  sink      : 흡수 라벨. 화면에 안 띄움

아동 모드에서 추가된 필드 (판정에는 안 씀, 화면·애니메이션 전용)
  emoji : 화면에 크게 띄울 이모티콘 (문서의 이모티콘 열. ⚠ 없는 소리는 공용 '💫')
  anim  : 애니메이션 종류 (kids_anim.py)
          그림 애니메이션 (assets/kids_anim, 2026-11-06 v0.2 — 효과음 통합 26종 시안 + 시안 3 문·종·사이렌)
                                    효과음 boing·whoosh·zing·thud·splash / 동물 dog·cat·cow·pig·sheep·horse·duck·chicken
                                    bird·frog·owl·lion·bee / 사람 crying·laugh·surprise·clap·snore·sneeze·tummy·whistle
                                    / door·bell·siren   (bird·snore 는 지속음이라 계속 반복)
                                    v0.3 (2026-11-06): train·footsteps·fireworks·explosion / 지속음 kids_play·helicopter
                                    airplane·water·waves (반복)
                                    v0.3.3 (2026-11-06): 효과음 통합 43종 시안으로 13종 교체 (사용자 선택) — 첨벙·사이렌·경적
                                    기차·헬리콥터·노크·전화벨·발소리·유리·천둥·불(campfire)·바람(windy)·파도
          이모티콘 움직임 이름은 그림 이름과 겹치면 안 됨 (v0.2 에서 'whoosh' 가 겹쳐 기차·발소리에 종이비행기가 떴음
          → 움직임 이름을 'slide' 로 바꿈). kids_anim.check_names() 가 시작할 때 확인
          이모티콘 움직임         : jump(동물: 울 때마다 점프) · bounce(띠용) · whoosh(휙) · wobble(첨벙·출렁)
                                    sparkle(반짝) · shake(천둥·벨·알람) · pop(기본 '팡')
          지속음 효과             : rain · wind · fire · music · breathe(그 외 지속음: 숨 쉬듯)
  grade : 문서 등급 1·2·3. 같은 순간에 여러 개면 1등급을 앞에 (kids_judge GRADE_WEIGHT)
          3등급은 지속음 칸(구석)에 표시

결정 사항 (문서 v0.1 + 2026-11-05 사용자 확인)
  - 자막 = [원인 + 의성어] 허용 (예: '강아지 멍멍'). 의성어 단독 금지
    → 의성어가 자막 이름 안에 들어 있어서 설정 '의성어 켜기/끄기'와 상관없이 같은 이름
  - 무서운 소리 완화: 비명(Screaming) → '깜짝 놀라는 소리' (판정은 그대로, 이름·그림만 순하게)
  - 세부 라벨은 부모로 출발: 사이렌 3종(경찰·구급·소방)은 '사이렌' 하나. 로그 확인 후 나눔
  - 동시 표시 개수는 고정하지 않음 (앱 설정 칸 수를 따름)
  - 같은 소리 3초 쿨다운: 애니메이션을 다시 시작하는 간격 (kids_anim.COOLDOWN_SEC)
  - AudioSet 527개 안에서만
⚠ 기준값은 전부 출발값. 실제 영상 테스트 로그를 보고 조정 (다른 모드와 같은 방식)
"""

VERSION = "kids v0.70"   # 판정 계산 버전 (라벨 추가는 kids_labels 기록 참고)   # kids_judge.py 와 같아야 함

LABELS = {
    # ================= 1. 만화 효과음 =================
    # 만화 효과음은 AudioSet 데이터가 적어 점수가 낮을 수 있음 (문서 '예상 문제') → AudioSet 하한을 낮추고
    # AudioSet 이 못 들어도 CLAP 이 확실하면 표시하는 대체 경로(solo_min + 자기 cos)를 둠
    "boing": dict(name="띠용 효과음", group="boing", kind="confirm", form="instant",
                  min=0.20, as_min=0.03, plus_min=0.40, solo_min=0.35, solo_cos=0.25,
                  prompts=["a cartoon boing spring sound effect", "a bouncy cartoon spring boing"],
                  audioset=["Boing", "Bouncing"],
                  emoji="💫", anim="boing", grade=2, cat="5-10"),
    "whoosh": dict(name="휙 지나가는 소리", group="whoosh", kind="confirm", form="instant",
                   min=0.20, as_min=0.05, plus_min=0.40, solo_min=0.35, solo_cos=0.25,
                   prompts=["a fast whoosh swoosh sound effect", "something swishing past quickly"],
                   audioset=["Whoosh, swoosh, swish"],
                   emoji="💨", anim="whoosh", grade=2, cat="5-10"),
    "zing": dict(name="반짝 효과음", group="zing", kind="confirm", form="instant",
                 min=0.20, as_min=0.03, plus_min=0.45, solo_min=0.35, solo_cos=0.25,
                 prompts=["a magical sparkle twinkle sound effect", "a cartoon zing chime"],
                 audioset=["Zing", "Jingle, tinkle"],
                 emoji="✨", anim="zing", grade=2, cat="6-3"),
    "squeak": dict(name="삑삑 효과음", group="squeak", kind="confirm", form="instant",
                   min=0.25, as_min=0.05, plus_min=0.50,
                   prompts=["a squeaky toy squeaking", "a cartoon squeak sound effect"],
                   audioset=["Squeak"],
                   emoji="💫", anim="bounce", grade=2, cat="6-3"),
    # 쿵: 돌발일 때만 (문서 '1 (돌발 시)') → impulse_min. 공포 '문 닫히는 소리'와 같은 방식
    "thud": dict(name="쿵 부딪히는 소리", group="thud", kind="confirm", form="instant",
                 min=0.40, as_min=0.10, plus_min=0.35, impulse_min=12.0,   # 4차: CLAP 0.30 → 0.40 (오탐 0.23~0.37, 맞은 건 0.58~0.66)
                 # 15차: AudioSet 혼자 0.55 → 0.35 + 'Thunk'(퉁) 추가 — Thunk 0.38 인 진짜 쿵을 놓침
                 # 15차: CLAP 혼자 띄우는 길 다시 (진짜 쿵 CLAP 0.58~0.66·돌발 27~30dB 를 놓침).
                 #   단 음악이 뚝 끊기는 순간(장면 전환)이거나 돌발 40dB 넘으면 안 됨 — 가짜 쿵 두 번은 음악 끊김 + 42~47dB
                 solo_min=0.55, solo_cos=0.25, need_impulse=True, solo_impulse=18.0, solo_impulse_max=40.0, solo_no_cut=True,
                 # 11-06 라바 2차: 음악 끊긴 사이 CLAP 0.45·0.47 + 돌발 24dB 인데 AudioSet 이 못 들어 놓침
                 #   → CLAP(음악 뺀 확률) ≥ 0.40 + 돌발 ≥ 18dB(3차: 20 → 18, 19dB 로 1초 늦음) 면 AudioSet 없이도 표시
                 # 14차: CLAP 혼자 띄우는 길 없앰 — 쿵 소리가 안 났는데 CLAP 0.49·0.63 (같은 장면 두 번). AudioSet 도 들어야 뜸
                 prompts=["a cartoon bonk hitting sound", "something falling down with a thud"],
                 audioset=["Thump, thud", "Bang", "Whack, thwack", "Thunk"],
                 emoji="💥", anim="thud", grade=1, cat="6-1"),
    "splash": dict(name="첨벙 물소리", group="splash", kind="confirm", form="instant",
                   min=0.25, as_min=0.10, plus_min=0.45,
                   # 2026-11-06 라바 시험: 물에 빠져 허우적대는 소리를 못 잡음 (음악에 묻힘, AudioSet 도 못 들음)
                   #   → 허우적 문장 추가 + 음악을 뺀 CLAP 확률이 높고 이 라벨 cos 도 충분하면 표시 (ex_music·solo)
                   solo_min=0.45, solo_cos=0.22, ex_music=True, ex_raw_min=0.20,
                   plus_clap=0.15,   # 11-06 라바 2차: 만화 '뽁' 효과음을 AudioSet 이 Plop 으로 듣고 혼자 띄움 → CLAP 도 첨벙 쪽이어야
                   prompts=["a splash into water", "a plop of something dropping into water",
                            "someone splashing and thrashing around in water", "water splashing around wildly"],
                   audioset=["Splash, splatter", "Plop", "Slosh"],
                   emoji="💦", anim="splash", grade=2, cat="4-2"),

    # 11-06 라바 6차: 짧게 탁 치는 악기 소리 (심벌즈·북·징·실로폰·드럼 연타) — 심벌즈 '챙'이 배경음악으로 뜸
    #   돌발일 때만 + AudioSet 악기 칸 확인. 배경음악이 떠 있으면 음악 속 드럼으로 보고 안 띄움 (yield_to)
    #   AudioSet 'Drum'·'Drum kit' 는 음악 전체에 걸려서 뺌
    "instrument": dict(name="챙챙 악기 소리", group="instrument", kind="confirm", form="instant",
                       min=0.25, as_min=0.20, plus_min=0.50, impulse_min=15.0, yield_to=["music"],
                       prompts=["a cymbal crash", "a drum hit sound effect", "a gong being struck",
                                "a quick xylophone run", "a snare drum roll"],
                       audioset=["Cymbal", "Gong", "Drum roll", "Snare drum", "Bass drum", "Timpani",
                                 "Tambourine", "Marimba, xylophone", "Glockenspiel"],
                       emoji="🥁", anim="shake", grade=2, cat="3-4"),   # 타악기

    # ================= 2. 동물 =================
    # 문서: 동물 → 울 때마다 점프. 강아지·고양이는 시안 3 그림 애니메이션
    # 보류(로그 확인 후): 강아지 으르렁·낑낑·하울링, 고양이 하악·그르릉 → 부모 이름으로 표시
    "dog": dict(name="강아지 멍멍", group="dog", kind="confirm", form="instant", as_min=0.10, plus_min=0.40,
                prompts=["a dog barking", "a small puppy yapping"],
                audioset=["Dog", "Bark", "Yip", "Bow-wow"],
                emoji="🐶", anim="dog", grade=2, cat="2-1"),
    "cat": dict(name="고양이 야옹", group="cat", kind="confirm", form="instant", as_min=0.10, plus_min=0.40,
                prompts=["a cat meowing", "a kitten mewing"],
                audioset=["Cat", "Meow"],
                emoji="🐱", anim="cat", grade=2, cat="2-1"),
    "cow": dict(name="소 음매", group="cow", kind="confirm", form="instant", as_min=0.10, plus_min=0.40,
                prompts=["a cow mooing"], audioset=["Cattle, bovinae", "Moo"],
                emoji="🐮", anim="cow", grade=2, cat="2-2"),
    "pig": dict(name="돼지 꿀꿀", group="pig", kind="confirm", form="instant", as_min=0.10, plus_min=0.40,
                prompts=["a pig oinking and grunting"], audioset=["Pig", "Oink"],
                emoji="🐷", anim="pig", grade=2, cat="2-2"),
    "sheep": dict(name="양 매애", group="sheep", kind="confirm", form="instant", as_min=0.10, plus_min=0.40,
                  prompts=["a sheep bleating", "a goat bleating"], audioset=["Sheep", "Bleat"],
                  emoji="🐑", anim="sheep", grade=2, cat="2-2"),
    "horse": dict(name="말 히힝", group="horse", kind="confirm", form="instant", as_min=0.10, plus_min=0.40,
                  prompts=["a horse neighing", "a horse whinnying"], audioset=["Horse", "Neigh, whinny"],
                  emoji="🐴", anim="horse", grade=2, cat="2-2"),
    "duck": dict(name="오리 꽥꽥", group="duck", kind="confirm", form="instant", as_min=0.10, plus_min=0.40,
                 prompts=["a duck quacking"], audioset=["Duck", "Quack"],
                 emoji="🦆", anim="duck", grade=2, cat="2-4"),
    "chicken": dict(name="닭 꼬끼오", group="chicken", kind="confirm", form="instant", as_min=0.10, plus_min=0.40,
                    prompts=["a rooster crowing", "chickens clucking"],
                    audioset=["Chicken, rooster", "Crowing, cock-a-doodle-doo", "Cluck"],
                    emoji="🐔", anim="chicken", grade=2, cat="2-2"),
    # 새 짹짹: 3등급(배경) → 지속음 칸. 넓은 'Bird' 는 하한을 높게
    "bird": dict(name="새 짹짹", group="bird", kind="confirm", form="sustained", as_min=0.15, plus_min=0.50, hold=2,
                 prompts=["birds chirping and tweeting", "a small bird singing"],
                 audioset=["Bird vocalization, bird call, bird song", "Chirp, tweet"],
                 emoji="🐦", anim="bird", grade=3, cat="2-4"),
    "frog": dict(name="개구리 개굴개굴", group="frog", kind="confirm", form="instant", as_min=0.10, plus_min=0.40,
                 prompts=["a frog croaking", "frogs ribbiting"], audioset=["Frog", "Croak"],
                 emoji="🐸", anim="frog", grade=2, cat="2-5"),
    "owl": dict(name="부엉이 부엉부엉", group="owl", kind="confirm", form="instant", as_min=0.10, plus_min=0.40,
                prompts=["an owl hooting"], audioset=["Owl", "Hoot"],
                emoji="🦉", anim="owl", grade=2, cat="2-4"),
    # 사자 어흥: 돌발이면 1등급 — 판정은 같고 화면 앞순위만 (grade 1)
    "lion": dict(name="사자 어흥", group="lion", kind="confirm", form="instant", as_min=0.10, plus_min=0.40,
                 prompts=["a lion roaring", "a big cat growling and roaring"],
                 audioset=["Roaring cats (lions, tigers)", "Roar"],
                 emoji="🦁", anim="lion", grade=1, cat="2-3"),
    "bee": dict(name="벌 윙윙", group="bee", kind="confirm", form="instant", as_min=0.10, plus_min=0.45,
                prompts=["a bee buzzing", "insects buzzing around"], audioset=["Bee, wasp, etc.", "Buzz"],
                emoji="🐝", anim="bee", grade=2, cat="2-5"),

    # ================= 3. 아이·사람 =================
    # v0.37: '아기 응애 우는 소리'(baby_cry) 라벨 뺌 (사용자 요청) — 아기 울음 문장·칸은 여기로 옮겨 계속 '엉엉 우는 소리'로 잡음
    "crying": dict(name="엉엉 우는 소리", group="crying", kind="confirm", form="instant",
                   min=0.25, as_min=0.12, plus_min=0.45, as_sum=True,
                   prompts=["a child crying and sobbing", "a person sobbing", "a baby crying", "an infant wailing"],
                   audioset=["Crying, sobbing", "Wail, moan", "Whimper", "Baby cry, infant cry"],   # 아기 울음 칸은 baby_cry 쪽에 (묶음이라 합쳐짐)   # v0.24: 흐느낌 0.28·훌쩍 0.11 로 들음 (울음 칸 0.07)
                   emoji="😢", anim="crying", grade=1, cat="1-2"),   # v0.37: 묶음 맨 앞이던 baby_cry 의 1등급을 그대로
    # 11-06 라바 3차: 만화식 과장된 웃음 (레드 웃음을 AudioSet 은 '끙'으로만 들음) → 문장 추가 +
    #   CLAP(음악 뺀 확률) ≥ 0.40 + 돌발 ≥ 15dB 면 AudioSet 없이도 표시. 다른 목소리 오탐 주의 (시험 중)
    # 11-07 v0.13: CLAP 혼자 띄우는 길 없앰 — 대사 목소리를 웃음으로 착각 (AudioSet 웃음 0). AudioSet 웃음 0.20 이상이어야
    "laugh": dict(name="까르르 웃음소리", group="laugh", kind="confirm", form="instant", as_min=0.20, plus_min=0.45,
                  prompts=["a baby giggling", "children laughing happily", "a person laughing",
                           "a cartoon character laughing hysterically", "a goofy cartoon voice cackling with laughter"],
                  audioset=["Baby laughter", "Giggle", "Laughter"],
                  emoji="😆", anim="laugh", grade=2, cat="1-2"),
    # 무서운 소리 완화 (사용자 확인 2026-11-05): 비명 → '깜짝 놀라는 소리', 그림은 화들짝 놀라는 캐릭터
    # 11-07 v0.13: AudioSet 0.08 → 0.20 (한숨을 놀람으로), CLAP 혼자는 0.35 → 0.50
    "surprise": dict(name="깜짝 놀라는 소리", group="surprise", kind="confirm", form="instant", as_min=0.20,
                     plus_min=0.40, solo_min=0.50, solo_cos=0.40,
                     plus_by={"Screaming": 0.30},   # v0.30: 비명이 0.30~0.39 로 0.6~1.2초 늦게 뜨거나 놓침 (로그 4번 모두 진짜 비명). Gasp 0.30~0.33 4번은 한숨·대사라 제외
                     prompts=["a person screaming in surprise", "a short startled scream", "a sharp gasp of surprise"],
                     audioset=["Screaming", "Gasp"],
                     emoji="😲", anim="surprise", grade=1, cat="1-1"),
    # 15차: 한숨 (예전엔 AudioSet Sigh 0.26~0.41 인 소리가 '깜짝 놀라는 소리'로 잘못 뜸)
    "sigh": dict(name="휴~ 한숨 소리", group="sigh", kind="confirm", form="instant", min=0.20, as_min=0.20, plus_min=0.40,
                 prompts=["a person sighing deeply", "a tired sigh"], audioset=["Sigh"],
                 emoji="😮‍💨", anim="wobble", grade=2, cat="1-1"),
    "hiss": dict(name="쉬익 가스 소리", group="hiss", kind="confirm", form="instant", min=0.15, as_min=0.18, plus_min=0.20, plus_clap=1.01, plus_cos=0.20, plus_strong=0.20,   # v0.23: 0.35 → 0.20 (로그 5개에서 합 0.20 넘은 7번이 모두 가스 장면, CLAP 은 cos 0.09~0.17 로 못 따라옴)
                 solo_min=0.15, solo_cos=0.24,
                 as_alt=["Mechanisms", "Ratchet, pawl"], as_alt_min=0.25, as_alt_cos=0.20,
                 weak_as=0.06, weak_cos=0.15, weak_block_top=("voice",),   # v0.26: 캐릭터가 '쉬익' 비슷하게 말한 걸 가스로 (CLAP 1등 목소리 0.67~0.81). 진짜 가스 뜬 15판은 모두 1등이 배경음악·쉬익·엉엉   # v0.25: 말소리·음악에 묻힌 가스 (스프레이 0.07 + 쉬익 0.03, cos 0.21) — 로그 5개 9번 중 6번이 표시된 가스 장면   # v0.22: 소화기를 기계·래칫 0.29~0.33 으로 들음 (cos 0.22~0.26)   # v0.21: AudioSet 증기 0.29+쉬익 0.23 인데 CLAP 0 / CLAP 0.16·cos 0.26 인데 AudioSet 기계 소리
                 prompts=["gas hissing out of a pipe", "steam hissing", "air leaking with a hiss",
                          "a fire extinguisher spraying"],
                 audioset=["Hiss", "Steam", "Spray", "Steam whistle"], as_sum=True,   # v0.20: 소화기 분사 (증기 0.12 + 쉬익 0.10 → 합 0.22)
                 emoji="💨", anim="wobble", grade=2, cat="2-4"),   # v0.19: 증기 0.22 / 쉬익 0.16 인데 받을 라벨이 없었음
    "sizzle": dict(name="지글지글 굽는 소리", group="sizzle", kind="confirm", form="instant",   # v0.21: 순간 소리로
                   min=0.20, as_min=0.04, plus_min=0.25, as_sum=True,
                   veto=["Water", "Liquid", "Pour", "Fill (with liquid)", "Drip"], veto_min=0.06,   # v0.29: 물 따르는 소리를 굽는 소리로 (물 0.07). 진짜 굽는 소리 15판은 물 ≤ 0.02
                   prompts=["meat sizzling on a hot frying pan", "food frying in oil", "pancakes cooking on a griddle"],
                   audioset=["Sizzle", "Frying (food)"],
                   emoji="🍳", anim="wobble", grade=3, cat="2-4"),   # v0.20: 굽는 소리를 빗소리로 들음 (Rain 0.20, Sizzle 0.06)
    "buzzer": dict(name="땡 부저 소리", group="buzzer", kind="confirm", form="instant", min=0.15, as_min=0.12, plus_min=0.10, plus_clap=1.01, plus_cos=0.15,
                   plus_strong=0.18,   # v0.27: 0.10~0.18 은 CLAP 부저 cos 0.15 확인 ('땡' 순간 Buzzer 0.11~0.14)   # v0.26: AudioSet Buzzer 0.19~0.44 인데 받을 라벨이 없었음 (퀴즈 '땡' 부저)
                   prompts=["a game show buzzer", "a wrong answer buzzer sound"], audioset=["Buzzer"],
                   emoji="🚫", anim="shake", grade=2, cat="5-5"),
    "kids_play": dict(name="아이들 노는 소리", group="kids_play", kind="confirm", form="sustained",
                      as_min=0.12, plus_min=0.45, hold=2,
                      prompts=["children playing and shouting in a playground"],
                      audioset=["Children playing", "Children shouting"],
                      emoji="🧒", anim="kids_play", grade=3, cat="1-5"),
    "clap": dict(name="짝짝 박수 소리", group="clap", kind="confirm", form="instant", as_min=0.10, plus_min=0.40,
                 prompts=["people clapping their hands", "an audience applauding"],
                 audioset=["Clapping", "Applause"],
                 emoji="👏", anim="clap", grade=2, cat="1-5"),
    "cheer": dict(name="와~ 환호 소리", group="cheer", kind="confirm", form="instant", as_min=0.10, plus_min=0.45, as_sum=True,
                  prompts=["a crowd cheering", "kids cheering yay"], audioset=["Cheering", "Children shouting"],   # v0.26: 와~ 를 아이들 외침 0.22·환호 0.09 로 들음
                  emoji="🙌", anim="bounce", grade=2, cat="1-5"),
    "snore": dict(name="드르렁 코 고는 소리", group="snore", kind="confirm", form="sustained",
                  as_min=0.10, plus_min=0.40, hold=2,
                  prompts=["a person snoring loudly"], audioset=["Snoring"],
                  emoji="😴", anim="snore", grade=2, cat="1-4"),
    "sneeze": dict(name="에취 재채기", group="sneeze", kind="confirm", form="instant", as_min=0.10, plus_min=0.40,
                   prompts=["a person sneezing achoo"], audioset=["Sneeze"],
                   emoji="🤧", anim="sneeze", grade=2, cat="1-4"),
    # 11-06 라바 3차: 라바 '끙' 목소리가 CLAP 0.12·AudioSet 0.1 로 기침이 됨 → 기준 올림
    "cough": dict(name="콜록 기침", group="cough", kind="confirm", form="instant", min=0.25, as_min=0.15, plus_min=0.35, as_sum=True,
                  prompts=["a person coughing"], audioset=["Cough", "Throat clearing"],   # v0.21: 기침 0.27+헛기침 0.22, CLAP 은 웃음으로 들음
                  emoji="😷", anim="cough", grade=2, cat="1-4"),
    "hiccup": dict(name="딸꾹질 소리", group="hiccup", kind="confirm", form="instant", as_min=0.08, plus_min=0.40,
                   prompts=["a person hiccuping"], audioset=["Hiccup"],
                   emoji="💫", anim="bounce", grade=2, cat="1-4"),
    # 11-06 라바 6차: 방귀를 AudioSet 은 트림(0.51), CLAP 은 꼬르륵으로 들음 — 둘을 못 가름 → 한 묶음 '뿡 꺼억 소리'
    #   (key 는 burp·fart 그대로, group 만 같게 → 확률 합침. 기준은 앞 라벨(burp) 것)
    "burp": dict(name="뿡 꺼억 소리", group="gas", kind="confirm", form="instant", as_min=0.08, plus_min=0.40,
                 prompts=["a loud burp", "someone burping after drinking"], audioset=["Burping, eructation"],
                 emoji="💫", anim="bounce", grade=2, cat="1-4"),
    "fart": dict(name="뿡 꺼억 소리", group="gas", kind="confirm", form="instant", as_min=0.08, plus_min=0.40,
                 prompts=["a cartoon fart sound", "a long loud fart", "a short squeaky fart"], audioset=["Fart"],
                 emoji="💫", anim="bounce", grade=2, cat="1-4"),
    # 11-06 라바 6차: 먹는 소리 추가 (AudioSet 이 Crunch 0.24 로 들었는데 맞는 라벨이 없었음)
    "eat": dict(name="냠냠 먹는 소리", group="eat", kind="confirm", form="instant", min=0.20, as_min=0.15, plus_min=0.45,
                prompts=["someone chewing and eating food", "crunchy munching and eating sounds"],
                audioset=["Chewing, mastication", "Crunch"],
                emoji="😋", anim="bounce", grade=2, cat="1-4"),
    # 8차: 방귀를 꼬르륵(CLAP 0.13)으로도 같이 띄움 → 기준 올림 + '뿡 꺼억'이 같이 잡히면 그쪽만 (yield_to)
    "tummy": dict(name="꼬르륵 배고픈 소리", group="tummy", kind="confirm", form="instant", min=0.25, as_min=0.15,
                  plus_min=0.40, yield_to=["gas"],
                  prompts=["a hungry stomach growling and rumbling"], audioset=["Stomach rumble"],
                  emoji="💫", anim="tummy", grade=2, cat="1-4"),
    "whistle": dict(name="휘파람 소리", group="whistle", kind="confirm", form="instant", as_min=0.10, plus_min=0.45,
                    prompts=["a person whistling a tune"], audioset=["Whistling"],
                    emoji="😙", anim="whistle", grade=2, cat="1-3"),

    # ================= 4. 탈것 =================
    # 사이렌: 부모 '사이렌' 하나로 표시 (경찰·구급·소방 3종 보류 — 학습 데이터가 해외 사이렌, 애니 사이렌은 또 다름)
    # 애니메이션: 시안 3 사이렌. 점멸 금지(광과민성) 규칙에 맞춰 번쩍임 대신 부드럽게 도는 빛
    "siren": dict(name="사이렌", group="siren", kind="confirm", form="instant", as_min=0.40, plus_min=0.40,   # v0.26: 0.12 → 0.40 (사이렌 아닌데 AudioSet 0.33. 진짜 사이렌은 매번 0.46~0.63 까지 올라감, 최근 1.5초 근거로 봄)
                  prompts=["a police siren wailing", "an ambulance siren", "a fire truck siren"],
                  audioset=["Siren", "Police car (siren)", "Ambulance (siren)", "Fire engine, fire truck (siren)"],
                  emoji="🚨", anim="siren", grade=1, cat="5-6"),
    "horn": dict(name="빵빵 경적 소리", group="horn", kind="confirm", form="instant", as_min=0.10, plus_min=0.40,
                 prompts=["a car horn honking", "a truck horn beeping"],
                 audioset=["Vehicle horn, car horn, honking", "Air horn, truck horn"],
                 emoji="🚗", anim="horn", grade=1, cat="5-1"),
    # 11-07 v0.13: 자동차 달리는 소리·브레이크 (차가 많이 나오는 영상에서 띄울 게 없었음)
    # 13차: 헬리콥터를 자동차로 (Vehicle 0.17~0.24) → AudioSet 0.20 → 0.30, 헬리콥터·비행기가 들리면 안 띄움 (veto)
    "car": dict(name="부릉부릉 자동차 소리", group="car", kind="confirm", form="instant", min=0.20, as_min=0.30,   # v0.37: 브레이크와 같이 순간음 (사용자 요청)
                plus_min=0.50,
                veto=["Helicopter", "Aircraft", "Fixed-wing aircraft, airplane", "Propeller, airscrew", "Aircraft engine"],
                veto_min=0.15,
                prompts=["a car engine driving by", "cars driving on a road", "a cartoon car speeding past"],
                # 12차: 'Vehicle'(차량) 추가 — Car 0.12~0.16 인데 Vehicle 0.38~0.45 로 놓침. 배·비행기에도 붙지만 CLAP 이 자동차여야 뜸
                audioset=["Car", "Motor vehicle (road)", "Car passing by", "Race car, auto racing", "Truck",
                          "Motorcycle", "Engine", "Vehicle"],
                emoji="🚙", anim="breathe", grade=2, cat="5-1"),
    "brake": dict(name="끼익 브레이크 소리", group="brake", kind="confirm", form="instant", min=0.20, as_min=0.20,
                  plus_min=0.40,
                  prompts=["a car braking hard with screeching tires", "tires skidding and screeching"],
                  audioset=["Skidding", "Tire squeal", "Air brake"],
                  emoji="🚗", anim="slide", grade=1, cat="5-1"),
    "train": dict(name="칙칙폭폭 기차 소리", group="train", kind="confirm", form="instant", as_min=0.12, plus_min=0.45,
                  prompts=["a steam train chugging", "a train whistle blowing"],
                  audioset=["Train", "Train whistle", "Train horn"],
                  emoji="🚂", anim="train", grade=2, cat="5-2"),
    "helicopter": dict(name="헬리콥터 소리", group="helicopter", kind="confirm", form="sustained",
                       as_min=0.12, plus_min=0.45, hold=2,
                       prompts=["a helicopter flying overhead"], audioset=["Helicopter"],
                       emoji="🚁", anim="helicopter", grade=2, cat="5-2"),
    # 15차: 차 소리를 비행기로 (AudioSet 0.10~0.13) → 0.20, 자동차가 떠 있으면 안 띄움
    "airplane": dict(name="비행기 소리", group="airplane", kind="confirm", form="sustained",
                     as_min=0.20, plus_min=0.50, hold=2, yield_to=["car"],
                     prompts=["an airplane flying overhead", "a jet plane engine roaring"],
                     audioset=["Aircraft", "Fixed-wing aircraft, airplane", "Aircraft engine"],
                     emoji="✈️", anim="airplane", grade=3, cat="5-2"),
    # 후진 경고음: 삑삑 일정한 비프 → 다른 전자음(알람·전화)과 CLAP 확률 다툼이 심해 AudioSet 단독
    "reverse_beep": dict(name="삐삐 후진 소리", group="reverse_beep", kind="as_only", form="instant", plus_min=0.40,
                         prompts=[], audioset=["Reversing beeps"],
                         emoji="💫", anim="shake", grade=2, cat="5-1"),
    # 2026-11-06: '아이스크림 트럭 음악' 뺌 (사용자 요청)
    "bike_bell": dict(name="따르릉 자전거 벨", group="bike_bell", kind="confirm", form="instant",
                      as_min=0.10, plus_min=0.45,
                      prompts=["a bicycle bell ringing ring ring"], audioset=["Bicycle bell"],
                      emoji="🚲", anim="shake", grade=2, cat="5-1"),

    # ================= 5. 생활 소리 =================
    # 초인종: 애니메이션은 시안 3 '종' (좌우로 달랑달랑 + 음표)
    "doorbell": dict(name="딩동 초인종", group="doorbell", kind="confirm", form="instant", min=0.40, as_min=0.20, plus_min=0.40,   # v0.19: CLAP 0.32 + 징글로 잘못 뜸
                     prompts=["a doorbell ringing ding dong", "a ding dong chime"],
                     audioset=["Doorbell", "Ding-dong"],
                     emoji="🔔", anim="bell", grade=1, cat="5-4"),
    # 노크·문: 같은 🚪 이모티콘 (문서 '예상 문제': 글자로 구분). 노크는 흔들림, 문 여닫기는 시안 3 '문 쾅'
    "knock": dict(name="똑똑 노크 소리", group="knock", kind="confirm", form="instant", as_min=0.08, plus_min=0.40,
                  veto=["Typing", "Computer keyboard"], veto_min=0.10,
                  prompts=["knocking on a door"], audioset=["Knock"],
                  emoji="🚪", anim="knock", grade=1, cat="5-4"),
    "door": dict(name="문 여닫는 소리", group="door", kind="confirm", form="instant", as_min=0.10, plus_min=0.45,
                 prompts=["a door opening and closing", "a door slamming shut"],
                 audioset=["Door", "Slam", "Sliding door"], as_sum=True,   # v0.21: Door 0.08 + 미닫이 0.05 를 놓침
                 emoji="🚪", anim="door", grade=2, cat="5-4"),
    "phone": dict(name="따르릉 전화벨", group="phone", kind="confirm", form="instant", as_min=0.10, plus_min=0.50,
                  prompts=["a phone ringing", "a telephone ringtone"],
                  audioset=["Telephone bell ringing", "Ringtone", "Telephone"], as_sum=True,   # v0.23: 전화벨 0.0996<0.10 으로 놓침
                  emoji="📞", anim="phone", grade=1, cat="5-5"),
    "alarm": dict(name="알람 소리", group="alarm", kind="confirm", form="instant", as_min=0.10, plus_min=0.45,
                  prompts=["an alarm clock ringing", "a beeping alarm clock"], audioset=["Alarm clock"],
                  emoji="⏰", anim="shake", grade=1, cat="5-6"),
    "footsteps": dict(name="저벅저벅 발소리", group="footsteps", kind="confirm", form="instant",
                      min=0.22, as_min=0.08, plus_min=0.45,
                      veto=["Typing", "Computer keyboard"], veto_min=0.10,
                      prompts=["footsteps walking", "cartoon footsteps tiptoeing"],
                      audioset=["Walk, footsteps"],
                      emoji="👣", anim="footsteps", grade=2, cat="1-5"),
    "toilet": dict(name="변기 물 내리는 소리", group="toilet", kind="confirm", form="instant",
                   as_min=0.10, plus_min=0.40,
                   prompts=["a toilet flushing"], audioset=["Toilet flush"],
                   emoji="🚽", anim="toilet", grade=2, cat="5-4"),
    # 2026-11-06: '수돗물 소리' → '물소리', 💧 (사용자 요청). key 는 tap 그대로 (설정의 소리 필터 호환)
    # 2026-11-06: 졸졸 시냇물·똑똑 떨어지는 물·따르는 물까지 (AudioSet 은 구체적인 이름만, 넓은 'Water' 는 뺌)
    #   첨벙·비·파도·변기가 떠 있으면 그쪽이 우선 (yield_to)
    "tap": dict(name="물소리", group="tap", kind="confirm", form="sustained", as_min=0.12, plus_min=0.45, hold=2,
                yield_to=["splash", "rain", "waves", "toilet"],
                prompts=["water running from a tap into a sink", "water dripping and trickling",
                         "a small stream trickling over rocks", "water dripping drop by drop",
                         "pouring water into a cup"],
                audioset=["Water tap, faucet", "Trickle, dribble", "Stream", "Pour", "Drip"],
                emoji="💧", anim="water", grade=3, cat="5-4"),
    "toothbrush": dict(name="치카치카 양치 소리", group="toothbrush", kind="confirm", form="instant",
                       as_min=0.08, plus_min=0.40,
                       prompts=["someone brushing their teeth"], audioset=["Toothbrush", "Electric toothbrush"],
                       emoji="🪥", anim="shake", grade=2, cat="5-4"),
    "vacuum": dict(name="윙 청소기 소리", group="vacuum", kind="confirm", form="sustained",
                   as_min=0.12, plus_min=0.45, hold=2,
                   prompts=["a vacuum cleaner running"], audioset=["Vacuum cleaner"],
                   emoji="🧹", anim="sweep", grade=3, cat="5-7"),   # 2026-11-06: 청소기 이모지가 없어 🧹 (사용자 요청)
    "glass": dict(name="쨍그랑 유리 깨지는 소리", group="glass", kind="as_only", form="instant", plus_min=0.40,
                  prompts=[], audioset=["Shatter", "Breaking"], as_sum=True,   # v0.23: Shatter 0.34+Breaking 0.12 를 0.34<0.40 으로 놓침
                  emoji="💫", anim="glass", grade=1, cat="5-9"),

    # ================= 6. 자연 =================
    # 천둥: 돌발이면 1등급. 문서: 천둥 → 흔들림
    "thunder": dict(name="우르르 쾅 천둥", group="thunder", kind="confirm", form="instant", plus_min=0.45,
                    prompts=["thunder rumbling", "a loud thunder crack"], audioset=["Thunder", "Thunderstorm"],
                    emoji="⛈️", anim="thunder", grade=1, cat="4-1"),
    "fireworks": dict(name="펑펑 불꽃놀이", group="fireworks", kind="confirm", form="instant",
                      as_min=0.12, plus_min=0.45,
                      prompts=["fireworks popping and exploding in the sky"], audioset=["Fireworks", "Firecracker"],
                      emoji="🎆", anim="fireworks", grade=2, cat="5-8"),
    # 2026-11-06: 팀원 분류 체계의 '폭발음' 추가. 아동 모드라 이름을 순하게 (비명 → 깜짝 놀라는 소리와 같은 방식)
    #   쿵(Bang)·불꽃놀이와 겹칠 수 있음 → AudioSet 하한을 조금 높게, 돌발일 때만 (impulse_min)
    "explosion": dict(name="쾅 터지는 소리", group="explosion", kind="confirm", form="instant",
                      min=0.25, as_min=0.12, plus_min=0.45, impulse_min=10.0,
                      prompts=["a loud explosion boom", "a cartoon explosion kaboom"],
                      audioset=["Explosion", "Boom"],
                      emoji="💥", anim="explosion", grade=2, cat="5-8"),
    # 지속음 효과 4종은 시안 3 (불: 아지랑이처럼 일렁, 비: 실제 비처럼 떨어짐, 바람: 휘감기는 바람 줄기)
    "fire": dict(name="타닥타닥 불 타는 소리", group="fire", kind="confirm", form="sustained",
                 min=0.22, as_min=0.12, plus_min=0.45, hold=2,
                 prompts=["a campfire crackling", "wood burning in a fireplace"], audioset=["Fire", "Crackle"],
                 emoji="🔥", anim="campfire", grade=3, cat="4-1"),
    "rain": dict(name="빗소리", group="rain", kind="confirm", form="sustained",
                 min=0.22, as_min=0.12, plus_min=0.45, hold=2,
                 prompts=["rain falling", "rain pattering on a window"], audioset=["Rain", "Raindrop", "Rain on surface"],
                 yield_to=["sizzle"],   # v0.20
                 emoji="🌧️", anim="rain", grade=3, cat="4-1"),
    "wind": dict(name="바람 소리", group="wind", kind="confirm", form="sustained",
                 min=0.22, as_min=0.15, plus_min=0.45, hold=2,
                 prompts=["wind blowing", "strong wind howling"], audioset=["Wind", "Rustling leaves"],
                 emoji="🌬️", anim="windy", grade=3, cat="4-1"),
    "waves": dict(name="파도 소리", group="waves", kind="confirm", form="sustained",
                  min=0.30, as_min=0.12, plus_min=0.45, hold=2,   # 15차: CLAP 0.22 → 0.30 (차 소리 장면에서 0.24 로 뜸)
                  prompts=["ocean waves crashing on a beach"], audioset=["Ocean", "Waves, surf"],
                  emoji="🌊", anim="waves", grade=3, cat="4-2"),

    # ================= 7. 배경음악 (지속음 칸 = 화면 구석) =================
    # 문서: 배경음악은 구석에 음표 아이콘 + 분위기 이름. 분위기 판단이 없으면 '배경음악' (애매할 때)
    # 애니메이션: 시안 3 아코디언 (음악 = music)
    # 2026-11-07 v0.13: 배경음악은 일반 라벨 계산을 안 탐 — kids_judge 의 음악 전용 판단(MUSIC_* 아래)으로
    #   '있는지'는 AudioSet 음악 점수의 길이로, '분위기'는 AudioSet 분위기 칸 + CLAP 이 같을 때만
    "music": dict(name="배경음악", group="music", kind="confirm", form="sustained", min=0.25, plus_min=0.45,
                  as_min=0.20, mood=True, hold=2,
                  prompts=[],   # 아래에서 채움
                  audioset=["Music", "Background music", "Theme music", "Music for children", "Lullaby",
                            "Happy music", "Funny music", "Sad music", "Scary music", "Exciting music", "Tender music"],
                  emoji="🎵", anim="music", grade=3, cat="3-13"),

    # ================= 흡수 라벨 (표시 안 함) =================
    # 목소리: 캐릭터 대사·내레이션·아이 말소리가 사람 소리 라벨(웃음·울음·놀람)로 끌려가지 않게
    "voice": dict(name="목소리", group="voice", kind="sink", form="instant",
                  prompts=["a person talking", "a cartoon character speaking dialogue",
                           "a narrator telling a story", "a child talking"], audioset=[]),
    # 노래: 동요를 부르는 목소리가 휘파람·웃음으로 가지 않게 (노래 자체는 배경음악 분위기 '동요'로 잡힘)
    "singing": dict(name="노래", group="singing", kind="sink", form="instant",
                    prompts=["children singing a song", "a person singing"], audioset=[]),
    "quiet": dict(name="조용한 배경", group="quiet", kind="sink", form="sustained",
                  prompts=["a quiet room", "faint background room tone"], audioset=[]),
    "other": dict(name="기타 소리", group="other", kind="sink", form="instant",
                  prompts=["a random everyday sound", "keyboard typing and mouse clicking", "paper rustling"],
                  audioset=[]),
}

# ---------------- 5차 (2026-11-06): 기준 근처 통과 막기 ----------------
# 라바처럼 캐릭터 목소리가 끙·삑·꿀꿀 같은 효과음인 영상에서, 동물 소리·만화 효과음이 기준을 아슬아슬하게 넘겨 뜸
#   (돼지 CLAP 0.13 / AudioSet 0.12, 삑삑 AudioSet 0.09) → AudioSet 하한을 두 배로 (최대 0.25). 쿵·첨벙은 따로 조정해서 제외
STRICT_AS = ["boing", "whoosh", "zing", "squeak",
             "dog", "cat", "cow", "pig", "sheep", "horse", "duck", "chicken", "bird", "frog", "owl", "lion", "bee"]
LABELS["dog"]["plus_min"] = 0.30   # v0.19: 개 Dog 0.36 을 놓침 (cos 확인이 같이 있어서 낮춤)
for _k in STRICT_AS:
    LABELS[_k]["as_min"] = min(0.25, round(LABELS[_k].get("as_min", 0.05) * 2, 2))
# 7차: 동물은 CLAP 도 0.12 → 0.25 (돼지 CLAP 0.14 / AudioSet 0.22 로 라바 목소리가 또 뜸)
for _k in ["dog", "cat", "cow", "pig", "sheep", "horse", "duck", "chicken", "bird", "frog", "owl", "lion", "bee"]:
    LABELS[_k]["min"] = max(0.25, LABELS[_k].get("min", 0.0))
    LABELS[_k]["plus_cos"] = 0.15    # v0.19: 또는 이 동물 문장 cos ≥ 0.15 (음악이 크면 CLAP 확률이 0 으로 눌림 — 개 Dog 0.36, cos 0.17)
    LABELS[_k]["plus_clap"] = 0.10   # 9차: AudioSet 혼자로는 안 띄움 (방귀를 야옹 0.41 로 들음, CLAP 고양이 0.00)

# ---------------- 음악 분위기 (문서 7번) ----------------
# 분위기 = 배경음악 문장 중 가장 잘 맞은 문장의 분위기 (공포·예능과 같은 방식)
MUSIC_GENERIC = ["background music playing", "music playing in a cartoon"]   # 이게 이기면 '판단 없음'
# v0.20: '밝은 음악'은 판단은 하되 화면엔 '배경음악' (만화 음악이 거의 다 밝은 0.85~0.98 로 들려 틀린 표시가 너무 많음).
#   문장에서 cartoon 도 뺌 (만화 소리면 분위기 상관없이 붙었음). 다시 띄우려면 MOOD_HIDDEN = ()
MOOD_HIDDEN = ("밝은 음악",)   # v0.22: 다시 숨김 — 틀린 밝은 0.88~0.93 이 맞은 밝은 0.74~0.78 보다 높아 기준으로 못 가름. v0.21: 다시 띄움 (cartoon 뺀 뒤 밝은 0.55~0.78 로 내려옴, 진짜 밝은 음악까지 숨겨져서)
MUSIC_MOODS = {
    # 2026-11-07 v0.13: 분위기 4가지 (AudioSet 분위기 칸이 있는 것만). '동요'는 빼고 노래하는 목소리가 들릴 때만 '노래'
    #   예전 이름: 자장가 → 잔잔한 음악, 조마조마한 음악 → 무서운 음악, 웃긴 음악(6차에 없앰) → 밝은 음악
    "밝은 음악": ["happy upbeat cheerful music", "bright bouncy music", "upbeat cheerful jazz music",
              "fast playful chase music"],
    "슬픈 음악": ["sad slow music with soft strings", "slow sorrowful violin music"],
    "잔잔한 음악": ["a soft gentle lullaby", "a slow music box lullaby", "calm gentle relaxing music"],
    "무서운 음악": ["tense suspenseful music", "spooky mysterious music", "scary creepy music"],
}
LABELS["music"]["prompts"] = MUSIC_GENERIC + [p for ps in MUSIC_MOODS.values() for p in ps]
# AudioSet 분위기 칸 (CLAP 과 같은 쪽이어야 그 분위기)
MOOD_AS = {"밝은 음악": ["Happy music", "Funny music", "Exciting music"],
           "슬픈 음악": ["Sad music"],
           "잔잔한 음악": ["Tender music", "Lullaby"],
           "무서운 음악": ["Scary music", "Angry music"]}
SING_AS = ["Singing", "Male singing", "Female singing", "Child singing", "Choir"]
SING_MIN = 0.30          # 노래하는 목소리가 이 이상이면 분위기 대신 '노래'
SING_NAME = "노래"
MOOD_EMOJI = {"밝은 음악": "😊", "슬픈 음악": "😢", "잔잔한 음악": "🌙", "무서운 음악": "😰",
              SING_NAME: "🎤", "배경음악": "🎵"}
# 분위기 판단 v0.15 (12차 시험: AudioSet 분위기 칸은 아동 만화에서 0.00~0.04 → 밝은·슬픈·잔잔한은 CLAP 만)
#   0.5초마다 한 표: CLAP 분위기 문장 1등 ≥ MOOD_CLAP_MIN + 2등보다 MOOD_CLAP_LEAD 앞섬 (일반 문장 1등이면 안 됨)
#   다른 소리가 크게 겹치면 그 0.5초는 쉼: AudioSet 음악·말소리 아닌 칸 ≥ MOOD_BUSY_MIN, 또는 그 순간 순간음 자막이 뜸
#     (오프닝 음악에 브레이크·차 소리가 섞여 '무서운'이 됨)
#   표시: 최근 MOOD_WINDOW 초(쉰 칸 포함) 중 MOOD_MAJOR 이상이 같은 분위기
MOOD_CLAP_MIN = 0.50    # 14차: 0.60 → 0.50 ("배경음악이 너무 많다" — 밝은이 0.49~0.57 로 못 넘음)
MOOD_CLAP_LEAD = 0.15   # 14차: 0.25 → 0.15
MOOD_BUSY_MIN = 0.45    # 14차: 0.30 → 0.45 (차량 0.20~0.44 로 분위기를 계속 쉼. 브레이크 오프닝은 0.56~0.77 이라 그대로 걸림)
MOOD_BUSY_IGNORE = ["Silence", "Inside, small room", "Inside, large room or hall", "Inside, public space",
                    "Outside, urban or manmade", "Outside, rural or natural", "Sound effect", "Noise",
                    "Environmental noise", "Echo", "Reverberation", "Narration, monologue", "Conversation",
                    "Speech synthesizer", "Animal", "Domestic animals, pets"]
# '무서운 음악'만 더 엄격: CLAP ≥ SCARY_CLAP_MIN + AudioSet 무서운·화난 음악 ≥ SCARY_AS_MIN 둘 다,
#   최근 SCARY_WINDOW 초 중 SCARY_MAJOR 이상 (일렉 기타 록 오프닝을 CLAP 혼자 '무서운' 0.65~0.86 으로 들음, AudioSet 0.00~0.01)
SCARY_NAME = "무서운 음악"
SCARY_CLAP_MIN = 0.80
SCARY_AS = ["Scary music", "Angry music"]
SCARY_AS_MIN = 0.10
SCARY_WINDOW = 6
SCARY_MAJOR = 0.8

# 배경음악 있는지 (v0.13): 목소리와 비교 안 함. AudioSet 음악 점수의 '길이'로
#   로그 11개 실측: 짧은 음악 0.5~5초(21개), 진짜 배경음악 9초 이상(22개) → 6초
MUSIC_ON = 0.50          # 시작: 이 이상이
MUSIC_START_SEC = 3.0    #       이만큼 이어져야 띄움 (사이 MUSIC_GAP_SEC 이하로 끊긴 건 이어진 걸로)
#   v0.60: 6.0 → 3.0 (사용자: 처음 뜰 때 너무 늦음). 로그 전체 재현: 배경음악 236번 중 105번이 평균 2.4초 빨리 뜸,
#          대신 짧은 음악(징글·전환음)에 🎵 가 새로 18번 (대부분 1~3초 떴다 꺼짐). 4초면 81번 1.9초 빨라짐 · 새로 14번
MUSIC_KEEP = 0.40        # 유지: 이 이상이면 계속
MUSIC_GAP_SEC = 1.0      # 이보다 오래 MUSIC_KEEP 아래면 내림 (12차: 1.5 → 1.0, 음악 끝난 뒤 남는 시간 줄임)
MUSIC_RESUME_SEC = 3.0   # 내린 지 이 안에 다시 들리면 6초 안 기다리고 바로 (같은 곡이 잠깐 끊긴 것)
MUSIC_DROP = 0.20        # 13차: 떠 있는 음악이 이 아래로 확 떨어지면 기다리지 않고 바로 내림 (끝났는데 늦게 꺼짐)
MUSIC_FAST_SEC = 3.0     # 13차: 처음 3초 동안 음악이 세고 고르면 6초 안 기다리고 바로 띄움 (너무 늦게 뜸)
MUSIC_FAST_AVG = 0.74    #   로그 실측: 짧은 음악(3~4.5초)은 처음 3초 평균 최대 0.72 · 최저 0.63, 진짜 배경음악은 대부분 0.74·0.65 이상
MUSIC_FAST_MIN = 0.65
MOOD_CONTRA = 2          # 13차: 떠 있는 분위기와 다른 분위기를 CLAP 이 연속 이만큼 강하게(≥ MOOD_CLAP_MIN) 말하면 '배경음악'으로
JINGLE_AS = ["Jingle (music)", "Sound effect"]
JINGLE_MAX = 0.30        # 시작 확인 중 이 칸이 이 이상이면 짧은 음악·효과음으로 보고 안 셈

# 분위기 바꾸기 규칙: 문서 '애매하면 유지, 근거 없을 때만 배경음악, 직전 분위기 기억' (드라마 v1.4 출발점)
MOOD_MIN = 0.35
MOOD_LEAD = 0.10
MOOD_GAP = -0.40      # 음악 − 말소리. 아동 영상은 대사·내레이션 위에 음악이 깔리는 경우가 많아 공포(−0.55)보다 약간 엄격
MOOD_CONFIRM = 3      # 초
MOOD_STRONG = 0.85    # 2번 연속일 때만 바로 바꿈 (v0.8)
# 11-06 라바 3차: 말소리 대신 '목소리'(말 + 끙·신음·웃음·한숨) 가 음악보다 크면 배경음악 안 띄움
VOICE_AS = ["Grunt", "Groan", "Laughter", "Giggle", "Chuckle, chortle", "Belly laugh", "Snicker", "Sigh", "Baby laughter"]
MUSIC_CUT_DB = 15     # v0.9: 마지막 0.5초가 앞 1.5초보다 이만큼 작아지면 '음악 끊김' → 🎵 내림
MUSIC_CUT_SEC = 2.0   #       내린 채로 두는 시간 (2초 묶음에서 끊기기 전 음악이 빠지는 시간)
MUSIC_BACK_DB = 6     #       그 사이 끊기기 전 크기에서 6dB 안으로 돌아오면 바로 다시 띄움
MOOD_FIRST = 2        # 초. 처음엔 '배경음악' → 같은 분위기가 2초 이어져야 정함 (라바: 신스 도입부 → 슬픈)
MOOD_WINDOW = 6       # 초. v0.19: 3 → 6 (밝은 3초 만에 띄웠다가 바로 무서운으로 뒤집힘 → 확실할 때까지 '배경음악')
MOOD_MAJOR = 0.7      # v0.19: 0.5 → 0.7 (최근 6초 중 70% 가 같은 분위기여야 띄움. 한 번 뜬 뒤 유지는 MOOD_KEEP 그대로)
# v0.28: 비명(AudioSet Screaming ≥ 0.25) 뒤 3초 안에 '우는 소리'가 잡히면 '깜짝 놀라는 소리'로 바꿔 띄움. 끄려면 SCREAM_TO = None
SCREAM_AS = ["Screaming"]
SCREAM_MIN = 0.25
SCREAM_SEC = 3.0
SCREAM_FROM = ("crying",)
SCREAM_TO = "surprise"
EVIDENCE_SEC = 1.5     # v0.24: 라벨 판단에 최근 1.5초(2~3판) 근거를 모음. 0 이면 예전처럼 한 판씩
MOOD_KEEP = 8         # 판단 없음이 이 초 넘게 이어지면 '배경음악' (애매하면 유지 → 공포 5초보다 길게)

SPEECH_AUDIOSET = ["Speech", "Male speech, man speaking", "Female speech, woman speaking",
                   "Child speech, kid speaking", "Conversation", "Narration, monologue"]

# ---------------- 판정 기준 (공포 v0.11 값에서 시작) ----------------
# 라벨이 65개라 CLAP 확률이 여러 라벨로 나뉨 → CLAP 기준을 조금 낮추고 AudioSet 확인으로 막음
COS_MIN = 0.15
CLAP_MIN = 0.12
CLAP_SOLO_MIN = 0.25
AS_FLOOR = 0.05
STAR_MIN = 0.30
AS_STRONG = 0.35
BEATS_WEIGHT = 0.6
MAX_INSTANT = 5
MAX_SUSTAINED = 3
NEAR_MISS = 0.05
IMPULSE_MIN_DB = 12.0
HOLD_SEC = 3
# 같은 순간에 여러 소리면 순서 = 점수 × 등급 가중치 (1등급 사건 소리를 앞에). 점수 자체는 안 바꿈
GRADE_WEIGHT = {1: 1.3, 2: 1.0, 3: 0.8}

WATCH = ["hiss", "sizzle", "buzzer", "boing", "whoosh", "zing", "dog", "cat", "surprise", "doorbell", "knock"]

TRUTH = {"띠용": "boing", "휙": "whoosh", "반짝": "zing", "삑삑": "squeak", "쿵": "thud", "첨벙": "splash",
         "강아지": "dog", "개": "dog", "고양이": "cat", "소": "cow", "돼지": "pig", "양": "sheep", "말": "horse",
         "오리": "duck", "닭": "chicken", "새": "bird", "개구리": "frog", "부엉이": "owl", "사자": "lion",
         "벌": "bee", "아기": "crying", "울음": "crying", "웃음": "laugh", "놀람": "surprise", "한숨": "sigh", "가스": "hiss", "부저": "buzzer", "땡": "buzzer", "소화기": "hiss", "굽는": "sizzle", "지글": "sizzle", "쉬익": "hiss", "비명": "surprise",
         "아이들": "kids_play", "박수": "clap", "환호": "cheer", "코골이": "snore", "재채기": "sneeze",
         "기침": "cough", "딸꾹질": "hiccup", "트림": "burp", "방귀": "fart", "먹는": "eat", "냠냠": "eat", "악기": "instrument", "심벌즈": "instrument", "꼬르륵": "tummy",
         "휘파람": "whistle", "자동차": "car", "브레이크": "brake", "노래": "music", "사이렌": "siren", "경적": "horn", "기차": "train", "헬리콥터": "helicopter",
         "비행기": "airplane", "후진": "reverse_beep", "자전거": "bike_bell",
         "초인종": "doorbell", "노크": "knock", "문": "door", "전화": "phone", "알람": "alarm",
         "발소리": "footsteps", "변기": "toilet", "수돗물": "tap", "물소리": "tap", "폭발": "explosion", "쾅": "explosion", "양치": "toothbrush", "청소기": "vacuum",
         "유리": "glass", "천둥": "thunder", "불꽃놀이": "fireworks", "불": "fire", "비": "rain",
         "바람": "wind", "파도": "waves", "음악": "music"}


def groups():
    """group → [label key ...] (LABELS 순서 유지)"""
    g = {}
    for k, v in LABELS.items():
        g.setdefault(v["group"], []).append(k)
    return g


def anim_of(key):
    """라벨 키 → (애니메이션 종류, 이모티콘). 모르는 키는 기본 '팡'"""
    L = LABELS.get(key) or {}
    return L.get("anim", "pop"), L.get("emoji", "💫")


# 표시 전용: 의성어는 자막 이름 안에 이미 들어 있어 따로 붙이지 않음 (ONOMA 없음)
# 소리 필터 분류 코드(cat)는 라벨마다 위에서 지정 (sound_tree.CATS 중분류)


# =====================================================================================
# v0.38 (2026-11-08) 기준 목록 '태초마을' — 에피소드마다 라벨·길을 덧붙이던 걸 멈추고 대전제부터
#   · 화면에 띄우는 라벨 = 아래 BASE 목록만 (사용자 확정). 나머지는 지우지 않고 '숨김 흡수'(sink)로 바꿈
#     → 그 소리의 CLAP 확률을 흡수해서 비슷한 다른 라벨로 잘못 뜨지 않게 (기침 → 재채기, 가스 → 휙 등)
#   · 판정 길은 두 개만: 확인형(CLAP + AudioSet) / '+'(AudioSet 강하게, 동물은 CLAP cos 확인)
#     CLAP 혼자 길(solo)·다른 칸 길(as_alt)·약한 길(weak)·비명→놀람 바꾸기는 끔
#   · 시험으로 찾은 칸 추가(유리 Breaking·전화 Telephone·울음 Whimper 등)·동물 cos 확인·사이렌 0.40 은 유지
#   · 되돌리려면 BASELINE_V38 = False
# =====================================================================================
BASELINE_V38 = True

BASE = {
    # 1. 효과음
    "boing": "띠용 효과음", "whoosh": "휙 지나가는 소리", "zing": "반짝 효과음",
    "thud": "쿵 부딪히는 소리", "splash": "첨벙 물소리",
    # 2. 동물
    "dog": "강아지 멍멍", "cat": "고양이 야옹", "cow": "소 음매", "pig": "돼지 꿀꿀", "sheep": "양 매애",
    "horse": "말 히힝", "duck": "오리 꽥꽥", "chicken": "닭 꼬끼오", "bird": "새 짹짹", "frog": "개구리 개굴개굴",
    "owl": "부엉이 부엉부엉", "lion": "사자 어흥", "bee": "벌 윙윙",
    # 3. 아이·사람
    "crying": "우는 소리", "laugh": "웃음소리", "surprise": "깜짝 놀라는 소리", "clap": "짝짝 박수 소리",
    "sigh": "숨소리",
    "cough": "콜록 기침",   # v0.41: 다시 살림 (사용자)   # v0.40: 복원 (숨소리가 '깜짝 놀라는 소리'로 뜸 — Gasp 0.52·Sigh 0.23·Snort 0.19)
    "snore": "드르렁 코 고는 소리", "sneeze": "에취 재채기", "tummy": "꼬르륵 배고픈 소리", "whistle": "휘파람 소리",
    # 4. 탈것
    "siren": "사이렌", "horn": "빵빵 경적 소리", "train": "칙칙폭폭 기차 소리", "helicopter": "헬리콥터 소리",
    "car": "부릉부릉 자동차 소리",
    "brake": "끼익 브레이크 소리",   # v0.48: 다시 살림 — 미끄러지는 장면에 자동차만 뜸 (Skidding 0.3~0.57)   # v0.39: 다시 넣음 (사용자 요청, 순간음)
    # 5. 생활 소리
    "doorbell": "딩동 벨소리", "knock": "똑똑 노크 소리", "door": "문 여닫는 소리", "phone": "따르릉 전화벨",
    "footsteps": "저벅저벅 발소리", "glass": "쨍그랑 유리 깨지는 소리",
    # 6. 자연
    "thunder": "우르르 쾅 천둥", "explosion": "폭발음", "fire": "타닥타닥 불 타는 소리",
    "hiss": "쉬익 가스 소리",   # v0.41: 다시 살림 (사용자). 시험으로 만든 길(소화기=기계 칸, 말소리에 묻힌 약한 가스) 그대로
    "rain": "빗소리",
    "wind": "바람 소리", "waves": "파도 소리",
    # 7. 배경음악
    "music": "배경음악",
}
# 사용자 표에 있는데 지금 칸에 없던 것만 더함 (있던 칸은 그대로 — 시험으로 찾은 개선)
BASE_ADD_AS = {
    "bird": ["Bird"],
    "doorbell": ["Bell"],
    "glass": ["Glass"],   # v0.43: Smash, crash 는 합에서 빼고 as_or 로 따로   # v0.40: 와장창 소리 (★ 유리·폭발음 둘 다 Smash 0.22~0.39, CLAP 은 음악에 묻힘)
    "sigh": ["Breathing", "Gasp", "Snort", "Pant"],
}
# 숨긴 소리의 AudioSet 칸이 들리면 거부 (숨기기 전엔 그 라벨이 가져가던 소리)
#   빗소리 ← 굽는 소리(예전엔 yield_to sizzle), 우는 소리 ← 한숨 (로그: 한숨 장면에 Wail 0.15~0.18 + Sigh 0.11)
BASE_VETO = {
    "rain": (["Sizzle", "Frying (food)"], 0.06),
    "crying": (["Sigh", "Cat", "Meow"], 0.13),   # v0.50: 0.10 → 0.13 — 진짜 울음에 섞인 한숨·고양이 칸 0.12 로 막힘 (11-08 19:08·19:27 두 영상), 깨짐 0
}
# v0.39: 라벨별 기준 덮어쓰기 (로그 18개 재채점: 우는 소리 오탐 '환호·어떡해·웃음·안 울었어', 반짝 '반짝?·안 들림')
BASE_SET = {
    "crying": dict(min=0.40, plus_min=0.60),   # 0.25 / 0.45 → 아이가 칭얼대는 대사에 울음 칸 합 0.45~0.55
    "splash": dict(as_min=0.13),               # v0.49: 0.10 → 0.13 — 11-08 18:26·19:04 두 영상 첨벙 오탐(물 칸 0.12), 깨짐 0
    "zing": dict(min=0.30),                    # 0.20 → 동요 'Jingle, tinkle' 0.15~0.38 + CLAP 0.21 로 뜸
    "sneeze": dict(as_min=0.15),               # v0.68: 0.10 → 0.15 — 11-10 17:56:08 재채기 찐빠 (Sneeze 0.12, CLAP 0.13). 로그 89개 중 재채기가 뜬 건 이 한 번뿐
    "boing": dict(min=0.25),                   # v0.67: 0.20 → 0.25 — 11-10 17:12:01 띠용 찐빠 CLAP 0.22 (그 장면은 Boing 칸 0.15~0.20 이 늘 깔림). 사라지는 판 1 · 깨짐 0
    # v0.40 (29차): ★ 찍은 우는 소리는 전부 우는 소리 아님 (사용자). 진짜 울음(11-07 17:09:43)은 울음 칸 합 0.38~0.48
    #   AudioSet 혼자 길 끔 (오탐 4판 중 메모 2판 다 오탐) / 울음 칸 합 0.12 → 0.30 / 최근 1.5초 고양이 들리면 거부 (새끼 고양이를 아기 울음 0.83 으로)
    # v0.49: CLAP 0.40 → 0.60 — 진짜 울음일 때만 (사용자). 영상 3개 ★ 4개 오탐(CLAP 0.43~0.57) 고쳐짐, 깨짐 0. 진짜 울음 CLAP 0.76
    "crying": dict(min=0.60, as_min=0.35,   # v0.48: 0.30 → 0.35 (오탐 0.31, 진짜 울음 0.38~0.48)
                   plus_min=1.01, veto_recent=True,
                   alt_min=0.45, alt_as=0.55,
                   alt2_min=0.70, alt2_as=0.20,   # v0.53: 지금 판 CLAP ≥ 0.70 + 울음 칸 ≥ 0.20 (같은 장면도 잘라 듣는 위치 따라 칸 0.25~0.64 로 흔들림)
                   veto_skip_clap=0.75,
                   # v0.65 (사용자 예외, 근거 한 영상): 만화 울음을 CLAP 이 삑삑 장난감·깔깔 웃음으로 들어 5~7초 늦음 (11-10 16:29·16:36).
                   #   AudioSet 'Wail, moan' ≥ 0.30 + 대사 < 0.40 이 2판 연속이면 통과. 칸 합으로 하면 '우는 거 아니라니까' 등 ★ 2~4개 깨짐
                   #   (그 장면들은 대사 0.50 이상 + Wail 0.05~0.11). 깨짐 0 · 새로 뜨는 곳 0
                   seq_as="Wail, moan", seq_min=0.30, seq_n=2, seq_block=["Speech"], seq_block_max=0.40),   # v0.53: 0.80 → 0.75. 사용자: 히죽임 찐빠를 울음으로 띄워도 좋으니 진짜 울음은 다 잡기   # v0.52: 지금 판 CLAP ≥ 0.80 이면 한숨·고양이 거부 안 함 — 울음을 새끼 고양이로 같이 들어 막힘 (19:26·19:44 같은 장면, 16:52:05 예전엔 뜨던 울음). 0.75 면 굽는 소리·고양이 ★ 깨짐   # v0.51: 지금 판 CLAP ≥ 0.45 + 울음 칸 합 ≥ 0.55 (19:35:54 진짜 울음 CLAP 0.59·칸 0.64 놓침). 오탐 장면은 지금 판 칸 0.30~0.36
    # 놀람: AudioSet 혼자는 비명(Screaming 0.30)일 때만. Gasp(숨) 혼자는 숨소리로
    "surprise": dict(plus_min=1.01),
    # v0.56: 발소리 늦게 뜸 — 대사가 깔리면 AudioSet 'Walk, footsteps' 가 0.03~0.07 로 눌려 as_min 0.08 에 1~2초 막힘
    #   (CLAP 은 0.30~0.58 로 이미 발소리). 지금 판 CLAP ≥ 0.30 + 발소리 칸 ≥ 0.05 이면 통과.
    #   로그 전체 재판정: 발소리 5번 중 4번이 0.4~2.0초 빨라짐, 새로 생긴 발소리 0번, 채점 74/162 그대로
    "footsteps": dict(alt2_min=0.30, alt2_as=0.05),
    # v0.58: 문 늦게 뜸·놓침 — 끼익 문소리를 CLAP 이 개구리(0.47~0.57)+문(0.23~0.35)으로 나눠 듣고 문 칸 합 0.08~0.09 로 0.10 에 막힘.
    #   0.10 → 0.08: 로그 재판정 새로 뜨는 5곳 모두 문 장면(CLAP 개구리+문), ★ 16:48:12 '문여는 소리' 고쳐짐, 깨짐 0 (74 → 75)
    # v0.61: 배경음악 깔린 문 장면 — CLAP 은 배경음악 0.85~0.94 로 묻혀 문을 못 듣고, AudioSet 은 미닫이문·문 칸 합 0.15~0.34 로 이미 들음
    #   (11-10 09:52:23 → 문이 26.3 에 뜸 = 3초 늦음). CLAP 1등이 배경음악이면 AudioSet 문 칸 합 ≥ 0.15 만으로 띄움.
    #   로그 재판정: 새로 뜨는 5곳 모두 배경음악 + 문 칸 (같은 영상 문 장면 4번 · 09:51:53), 쿵 장면(CLAP 쿵 + 문 칸 0.15~0.18)은 안 걸림. 채점 75 그대로
    "door": dict(as_min=0.08, plus_mood_min=0.15),
    # v0.65: 웃음 늦게 뜸 — 만화 웃음은 CLAP 0.95~0.99 인데 AudioSet 웃음 칸이 음악·대사에 섞여 0.05~0.17 → 0.20 에 0.5~1초 막히거나 안 뜸.
    #   지금 판 CLAP ≥ 0.90 + 웃음 칸 ≥ 0.10 이면 통과 (v0.13 대사 오탐은 칸 0 이라 그대로 막힘). 채점 75 그대로·깨짐 0,
    #   빨라짐 2 · 새로 뜨는 7곳(CLAP 0.96~0.99, 칸 0.10~0.17) 진짜 웃음인지 미확인 → 사용자가 같은 영상으로 시험 후 판단
    # v0.68: min 0.12 → 0.25 — 웃음 꼬리(CLAP 0.12~0.24 · 웃음 칸 0)가 최근 1.5초 근거로 계속 통과돼 뒤 기침 장면까지 웃음이 남음 (11-10 17:55:37).
    #   로그 89개: 사라지는 판 11 (전부 11-10 영상 웃음 바로 뒤 꼬리) · 다른 영상 변화 0 · 깨짐 0
    # v0.70: v0.65 길(CLAP 0.90 + 웃음 칸 0.10) 뺌 — 11-10 같은 장면 웃음 찐빠 3번 (CLAP 0.92~0.98 · 칸 0.11~0.16, 진짜 웃음 첫 판과 숫자 같음). 진짜 웃음은 0.5~1초 늦어짐
    "laugh": dict(min=0.25),
    # v0.65: 새 늦게 뜸 — AudioSet 은 새 0.32 로 먼저 듣는데 CLAP 은 쿵·배경음악으로 들어 0 (plus_clap 0.10 에 막힘). 0.50 → 0.30 + CLAP 조건 없앰.
    #   로그 83개: 깨짐 0 · 새로 뜨는 곳 0 · 이미 뜨던 새 3번 0.5~1.3초 빨라짐 (근거 11-10 영상)
    "bird": dict(plus_min=0.30, plus_clap=0.0, hold=1),   # v0.67: hold 2 → 1 (마지막으로 들린 뒤 1초 더 판정하던 것 없앰)
    "glass": dict(plus_min=0.40),   # v0.46: 와장창(Smash) 혼자 → 유리 규칙 뺌 — 11-08 18:03 영상에서 '유리 안 깨짐' 2번, 이전 영상에서도 '폭발음'·'유리' 엇갈림   # v0.43: 쨍그랑 칸 합 0.40 또는 와장창 혼자 0.30 (합 0.30 은 가스 장면 오탐 5판)
    # v0.42 (31차): 아깝게 놓침. 로그 21개에서 새로 걸리는 판은 모두 그 장면 근처 (오탐 메모 0)
    "phone": dict(min=0.07, as_min=0.06,
                  veto=["Electronic music", "Electronica", "Sonar", "Synthesizer", "Coin (dropping)", "Dubstep", "Cacophony", "Beep, bleep"],
                  veto_min=0.05, veto_recent=True),   # v0.55: 해킹·전자음을 전화벨로 (11-09 같은 장면 3번, 전화 칸 0.31~0.77). 진짜 전화 장면엔 이 칸 0. 근거 한 영상 — 사용자 예외 허락, 진짜 전화벨 놓치면 재고
        # CLAP 0.12 → 0.07, AudioSet 0.10 → 0.06 (전화 장면 CLAP 0.06~0.11·전화 칸 0.05~0.14)
    # v0.67: 새 짹짹 다음 장면 기침 찐빠 (11-10 같은 장면 4번: 대사 0.78~0.84 · CLAP 배경음악 0.87 · 기침 칸 0.13~0.19)
    #   → CLAP 1등 배경음악 + 대사 ≥ 0.70 + CLAP 기침 < 0.25 면 AudioSet 혼자 기준 0.14 → 0.25. 로그 전체 사라지는 판 2 (둘 다 그 장면) · 깨짐 0
    "cough": dict(plus_min=0.14, plus_busy_min=0.25, plus_busy_speech=0.70, veto_recent=True, veto_sec=3.0,
                  veto=["Water", "Slosh", "Steam", "Hiss", "Spray", "Liquid", "Pour"], veto_min=0.03),
    # v0.45: AudioSet 혼자 0.14 다시 켬 + 최근 3초 안 물·증기·분사 ≥ 0.03 이면 거부.
    #   시험 13번: 가스 장면(기침 칸 0.26~0.50)은 13곳 모두 물·증기 칸이 같이 들림, 진짜 기침 13곳은 한 번도 없음. 1.5초면 장면 끝 3판이 샘
    "rain": dict(veto_recent=True),           # 굽는 소리가 1초 전 판에만 들려도 거부 (11-08 17:11:06 빗소리 오탐)   # v0.40: 0.40 → 0.30 (Smash 포함 합). 로그 19개 유리 판 18 → 71
    # v0.47: 대사·나레이션 중(말소리 칸 ≥ 0.50)엔 숨소리 안 띄움 — 11-08 18:01·18:26 두 영상에서 대사 중 한숨 칸 0.29~0.45 오탐. 대사 없는 숨(말소리 0.12~0.25)은 그대로
    "sigh": dict(min=0.20, as_min=0.20, plus_min=0.50,   # v0.48: AudioSet 혼자 0.40 → 0.50 (너무 자주 뜸, 사용자)
                  as_sum=True, veto=["Speech"], veto_min=0.50,
                 prompts=["a person sighing deeply", "a tired sigh", "heavy breathing", "a person gasping for breath"]),
}
EVIDENCE_TOP1 = True   # v0.39: 지금 판 CLAP 1등이 다른 순간 소리면 1.5초 근거 안 씀 (kids_judge)
# 끄는 길 (판정기가 이 키가 없으면 그 길을 안 탐)
FLAT_KEEP = {"hiss"}   # v0.41: 가스는 22~27차에 맞춘 길(as_alt·weak·weak_block_top·solo)을 그대로 씀
_FLAT_DROP = ("solo_min", "solo_cos", "need_impulse", "solo_impulse", "solo_impulse_max", "solo_no_cut",
              "ex_raw_min", "as_alt", "as_alt_min", "as_alt_cos", "weak_as", "weak_cos", "weak_block_top")

if BASELINE_V38:
    for _k in list(LABELS):
        _L = LABELS[_k]
        if _L.get("kind") == "sink":
            continue
        if _k not in BASE:                       # 숨김 흡수: 문장만 남기고 화면·판정에서 빠짐
            LABELS[_k] = dict(name=_L["name"], group="hidden", kind="sink", form="instant",
                              prompts=list(_L.get("prompts", [])), audioset=[])
            continue
        _L["name"] = BASE[_k]
        for _o in (() if _k in FLAT_KEEP else _FLAT_DROP):
            _L.pop(_o, None)
        if _k == "hiss":   # v0.48: CLAP 혼자 길 끔 — 나레이션·배·차 미끄러짐 장면을 CLAP 이 '쉬익'으로 (세 영상 ★ 4번 오탐, 깨짐 0)
            _L.pop("solo_min", None); _L.pop("solo_cos", None)
        for _a in BASE_ADD_AS.get(_k, []):
            if _a not in _L["audioset"]:
                _L["audioset"].append(_a)
        _L.update(BASE_SET.get(_k, {}))
        if _k in BASE_VETO:
            _v, _m = BASE_VETO[_k]
            _L["veto"] = list(dict.fromkeys(list(_L.get("veto", [])) + _v))
            _L["veto_min"] = min(_L.get("veto_min", _m), _m) if _L.get("veto") != _v else _m
        if "yield_to" in _L:                      # 없어진 라벨에 양보하던 것 정리
            _L["yield_to"] = [g for g in _L["yield_to"] if g in BASE]
            if not _L["yield_to"]:
                _L.pop("yield_to")
    # 숨김 흡수 라벨들은 한 묶음 'hidden' — 문장이 없는 건 빼서 빈 계산 방지
    for _k in [k for k, v in LABELS.items() if v.get("group") == "hidden" and not v["prompts"]]:
        LABELS.pop(_k)
    MOOD_HIDDEN = tuple(MUSIC_MOODS) + (SING_NAME, SCARY_NAME)   # v0.40: 분위기 상관없이 '배경음악'만 (사용자)
    SCREAM_TO = None                              # 비명 → 놀람 바꾸기 끔 (놀람 라벨이 Screaming 을 직접 봄)
    WATCH = [k for k in ["hiss", "cough", "boing", "whoosh", "zing", "dog", "cat", "surprise", "doorbell", "knock", "thud"] if k in LABELS]
    TRUTH = {w: k for w, k in TRUTH.items() if k in BASE}
    TRUTH.update({"벨": "doorbell", "딩동": "doorbell", "폭발": "explosion"})
