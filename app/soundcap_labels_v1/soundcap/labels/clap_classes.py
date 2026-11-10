"""CLAP 세분 클래스 (제로샷 텍스트 프롬프트).

PANNs·BEATs와 클래스를 맞추지 않고 더 잘게 나눈다. 대신 모든 클래스는
서비스 카테고리(cat) 하나에 속하므로, 결합은 카테고리 층에서 한다.

필드
- id        : 고유 id
- cat       : 상위 서비스 카테고리 (categories.py)
- ko        : 화면 표시명 (CLAP이 이 클래스를 고르면 이 이름이 뜸)
- prompts   : 영어 문장 프롬프트. 텍스트 임베딩을 평균해서 클래스 벡터로 쓴다
- clap_only : AudioSet에 대응 라벨이 없어 CLAP 단독 검출을 허용하는 클래스
              (더 높은 기준값을 적용. fusion.py 참고)

역할 분담
- PANNs·BEATs : "어느 카테고리인가"를 주로 판단 (검출)
- CLAP        : 같은 카테고리 안에서 "구체적으로 무슨 소리인가"를 판단 (표시명)
                + AudioSet이 모르는 소리 보완 (clap_only)

프롬프트 작성 규칙
- "the sound of ~" 보다 구체적 상황 문장이 CLAP에서 잘 맞는다
- 한 클래스에 2~3개, 서로 다른 표현으로
- 해석이 아니라 소리의 생김새를 쓴다 (O "a woman screaming"  X "a scary moment")
"""


def K(id, cat, ko, *prompts, clap_only=False):
    return dict(id=id, cat=cat, ko=ko, prompts=list(prompts), clap_only=clap_only)


CLAP_CLASSES = [
    # ── 사람 소리 ──────────────────────────────────────
    K("scream_terror", "scream", "비명", "a person screaming in terror", "a loud horrified scream"),
    K("scream_shriek", "scream", "날카로운 비명", "a high-pitched shriek", "a woman shrieking loudly"),
    K("scream_crowd", "scream", "여러 사람의 비명", "a crowd of people screaming", "many people screaming at once"),
    K("cry_sob", "cry", "흐느끼는 소리", "a person sobbing", "someone crying and sniffling"),
    K("cry_baby", "cry", "아기 울음소리", "a baby crying", "an infant wailing"),
    K("cry_wail", "cry", "통곡하는 소리", "a person wailing loudly in grief", "loud anguished crying"),
    K("shout_yell", "shout", "외치는 소리", "a man yelling loudly", "a person shouting"),
    K("shout_battle", "shout", "함성", "a group of people shouting a battle cry", "a loud collective shout"),
    K("laugh_person", "laugh", "웃음소리", "a person laughing", "someone laughing out loud"),
    K("laugh_audience", "laugh", "관객 웃음소리", "audience laughter", "a studio audience laughing", "a sitcom laugh track"),
    K("laugh_baby", "laugh", "아기 웃음소리", "a baby laughing", "a giggling toddler"),
    K("laugh_cackle", "laugh", "낄낄거리는 웃음", "a maniacal cackling laugh", "an exaggerated evil laugh"),
    K("applause_audience", "applause", "관객 박수", "an audience applauding", "a large crowd clapping"),
    K("applause_single", "applause", "손뼉 치는 소리", "one person clapping hands", "a few slow hand claps"),
    K("cheer_crowd", "cheer", "관중 환호", "a crowd cheering", "people cheering and whooping"),
    K("cheer_stadium", "cheer", "경기장 함성", "a stadium crowd roaring", "sports fans cheering in an arena"),
    K("sigh", "sigh", "한숨", "a person sighing", "a long tired sigh"),
    K("cough", "cough", "기침", "a person coughing", "repeated coughing"),
    K("throat_clear", "cough", "헛기침", "someone clearing their throat"),
    K("sneeze", "sneeze", "재채기", "a person sneezing", "a loud sneeze"),
    K("gasp", "gasp", "놀라 숨 들이켜는 소리", "a sharp gasp of surprise", "someone gasping"),
    K("pant", "breathing", "헐떡이는 숨소리", "heavy panting breath", "a person breathing hard after running"),
    K("breath_heavy", "breathing", "거친 숨소리", "heavy breathing close to the microphone", "slow deep breathing"),
    K("snore", "snore", "코골이", "a person snoring", "loud snoring while sleeping"),
    K("groan_pain", "groan", "아파하는 신음", "a person groaning in pain", "a pained moan"),
    K("grunt_effort", "groan", "힘주는 소리", "a person grunting with effort", "straining grunts while lifting"),
    K("burp", "bodily", "트림", "a person burping", "a loud burp"),
    K("hiccup", "bodily", "딸꾹질", "a person hiccuping"),
    K("fart", "bodily", "방귀 소리", "a fart sound", "a person farting"),
    K("stomach", "bodily", "배에서 꼬르륵 소리", "a stomach growling with hunger"),
    K("whistling", "whistling", "휘파람", "a person whistling a tune", "someone whistling"),
    K("finger_snap", "snap", "손가락 튕기는 소리", "fingers snapping", "a finger snap"),
    K("heartbeat", "heartbeat", "심장 박동", "a heart beating", "a loud heartbeat thumping"),

    # ── 신호음 ─────────────────────────────────────────
    K("doorbell_dingdong", "doorbell", "딩동 초인종", "a ding-dong doorbell", "a doorbell chime ringing"),
    K("doorbell_buzzer", "doorbell", "버저식 초인종", "an electric door buzzer", "a buzzing doorbell"),
    K("intercom", "doorbell", "인터폰 소리", "an apartment intercom ringing", "a video intercom call tone",
      clap_only=True),
    K("knock_door", "knock", "문 두드리는 소리", "someone knocking on a door", "knock knock on a wooden door"),
    K("knock_bang", "knock", "문을 세게 두드리는 소리", "someone banging on a door with a fist", "loud pounding on a door"),
    K("knock_window", "knock", "창문 두드리는 소리", "tapping on a glass window", "knocking on a window"),
    K("phone_ring", "phone", "전화벨", "a telephone ringing", "an old landline phone ringing"),
    K("phone_ringtone", "phone", "휴대폰 벨소리", "a smartphone ringtone", "a mobile phone ringing with a melody"),
    K("phone_vibrate", "phone_vibe", "휴대폰 진동", "a phone vibrating on a table", "a cell phone buzzing on vibrate",
      clap_only=True),
    K("siren_police", "siren", "경찰차 사이렌", "a police car siren", "a police siren wailing"),
    K("siren_ambulance", "siren", "구급차 사이렌", "an ambulance siren"),
    K("siren_fire", "siren", "소방차 사이렌", "a fire truck siren"),
    K("siren_raid", "siren", "공습경보", "an air raid siren", "a civil defense warning siren"),
    K("alarm_clock", "alarm", "알람 시계", "an alarm clock ringing", "a beeping alarm clock"),
    K("alarm_fire", "alarm", "화재경보", "a fire alarm ringing", "a smoke detector beeping loudly"),
    K("alarm_car", "alarm", "자동차 경보음", "a car alarm going off"),
    K("alarm_buzzer", "beep", "버저", "a loud buzzer", "a game show buzzer"),
    K("alarm_crossing", "alarm", "건널목 경보음", "a railroad crossing bell ringing", "a level crossing warning signal",
      clap_only=True),
    K("horn_car", "horn", "자동차 경적", "a car horn honking", "a car beeping its horn"),
    K("horn_truck", "horn", "트럭 경적", "a loud truck air horn"),
    K("horn_train", "horn", "기차 경적", "a train horn blowing", "a train whistle"),
    K("horn_ship", "horn", "뱃고동 소리", "a ship horn", "a foghorn blowing"),
    K("whistle_referee", "whistle", "호루라기", "a referee blowing a whistle", "a sharp whistle blow"),
    K("whistle_kettle", "household", "주전자 끓는 소리", "a tea kettle whistling", clap_only=True),

    # ── 사건음 ─────────────────────────────────────────
    K("gun_single", "gunshot", "총성", "a single gunshot", "a pistol firing"),
    K("gun_auto", "gunshot", "연발 총성", "automatic gunfire", "a machine gun firing rapidly"),
    K("gun_silenced", "gunshot", "소음기 총성", "a gun firing with a silencer", "a suppressed gunshot"),
    # (2026-10-12) 멀리서 나는 총성·게임 총성 문장을 넣어 봤으나 놓친 총성은 그대로, 오표시만 1→3 → 되돌림
    K("gun_reload", "gun_handling", "총기 장전 소리", "a gun being cocked and reloaded", "a metallic rifle reload click",
      clap_only=True),
    K("explosion_big", "explosion", "큰 폭발음", "a huge explosion", "a loud bomb blast"),
    K("explosion_small", "explosion", "폭발음", "a small explosion", "a grenade exploding"),
    K("glass_shatter", "breaking", "유리 깨지는 소리", "glass shattering", "a window breaking"),
    K("plate_break", "breaking", "그릇 깨지는 소리", "a plate smashing on the floor", "ceramic dishes breaking"),
    K("wood_break", "breaking", "나무 부서지는 소리", "wood cracking and breaking", "a wooden plank snapping"),
    K("collapse", "breaking", "무너지는 소리", "a building collapsing", "debris crashing down"),
    K("car_crash", "breaking", "차량 충돌음", "a car crash", "two cars colliding"),
    K("punch", "impact", "주먹으로 치는 소리", "a punch hitting a body", "a fist punch impact"),
    K("body_fall", "impact", "바닥에 쓰러지는 소리", "a body falling onto the floor", "a heavy thud of someone falling"),
    K("object_drop", "impact", "물건 떨어지는 소리", "an object dropped on the floor", "something falling with a clatter"),
    K("metal_clang", "impact", "금속 부딪히는 소리", "metal objects clanging", "a metal pipe hitting the ground"),
    K("slap", "impact", "찰싹 때리는 소리", "a hand slapping a face", "a sharp slap"),
    K("desk_bang", "impact", "책상 내리치는 소리", "a fist banging on a table", "slamming hands on a desk"),
    K("balloon_pop", "impact", "펑 터지는 소리", "a balloon popping", "a loud pop"),
    K("fireworks", "explosion", "폭발음", "fireworks exploding in the sky", "a fireworks show"),
    K("firecracker", "explosion", "폭발음", "firecrackers popping"),
    # 가스 분출 (v12·v13 gas leak 계승 + 연막탄)
    K("gas_leak", "gas", "가스 새는 소리", "gas leak", "gas hissing"),
    K("gas_smoke", "gas", "가스 분출 소리", "a smoke grenade hissing", "gas spraying out loudly"),
    K("gas_steam", "gas", "증기 뿜는 소리", "steam hissing from a pipe", "a steam vent releasing pressure"),
    K("gas_spray", "gas", "분사 소리", "a spray can spraying", "an aerosol spray"),
    K("door_open", "door", "문 여는 소리", "a door opening", "a door handle turning and a door opening"),
    K("door_close", "door", "문 닫히는 소리", "a door closing", "a door shutting gently"),
    K("door_slam", "door", "문 쾅 닫히는 소리", "a door slamming shut", "a loud door slam"),
    K("door_lock", "door", "도어락 소리", "a digital door lock keypad beeping and unlocking",
      "an electronic door lock opening", clap_only=True),
    K("door_sliding", "door", "미닫이문 소리", "a sliding door opening"),
    K("creak_door", "creak", "문 삐걱거리는 소리", "a creaky door slowly opening", "squeaky door hinges"),
    K("creak_floor", "creak", "마룻바닥 삐걱거리는 소리", "creaking wooden floorboards", "old floor creaking under footsteps"),
    K("footsteps_walk", "footsteps", "발소리", "footsteps walking", "a person walking on a hard floor"),
    K("footsteps_run", "footsteps", "뛰는 발소리", "footsteps running", "a person running fast"),
    K("footsteps_stairs", "footsteps", "계단 발소리", "footsteps on stairs", "someone walking up wooden stairs"),
    K("footsteps_heels", "footsteps", "구두 발소리", "high heels walking on a hard floor", "dress shoes clicking on tiles"),
    K("footsteps_grass", "footsteps", "풀·자갈 밟는 소리", "footsteps on gravel", "walking through grass and leaves"),
    K("car_engine", "vehicle", "자동차 엔진 소리", "a car engine running", "a car engine revving"),
    K("car_start", "vehicle", "시동 거는 소리", "a car engine starting"),
    K("car_pass", "vehicle", "차 지나가는 소리", "a car driving past", "a vehicle passing by"),
    K("car_brake", "vehicle", "급브레이크 소리", "car tires screeching", "a car braking hard"),
    K("motorcycle", "vehicle", "오토바이 소리", "a motorcycle engine", "a motorbike revving"),
    K("tool_hammer", "tools", "망치질 소리", "hammering nails", "a hammer hitting wood"),
    K("tool_drill", "tools", "드릴 소리", "an electric drill", "a power drill running"),
    K("tool_saw", "tools", "톱질 소리", "sawing wood", "a chainsaw cutting"),
    K("machine_fan", "machine", "선풍기·에어컨 소리", "an electric fan running", "an air conditioner humming"),
    K("machine_washer", "machine", "세탁기 소리", "a washing machine running", clap_only=True),
    K("machine_vacuum", "machine", "청소기 소리", "a vacuum cleaner"),
    K("machine_dryer", "machine", "드라이기 소리", "a hair dryer blowing"),
    K("machine_factory", "machine", "기계 작동 소리", "industrial machinery operating", "machines running in a factory"),
    K("dishes", "household", "그릇 부딪히는 소리", "dishes clattering", "washing dishes in a sink"),
    K("cooking_fry", "household", "기름에 굽는 소리", "food sizzling in a frying pan", "frying meat"),
    K("chopping", "household", "칼질 소리", "a knife chopping vegetables on a cutting board"),
    K("keys", "household", "열쇠 짤랑이는 소리", "keys jingling"),
    K("zipper", "household", "지퍼 소리", "a zipper being zipped"),
    K("paper", "household", "종이 넘기는 소리", "pages of a book turning", "paper rustling and crumpling"),
    K("tearing", "tear", "찢는 소리", "paper tearing", "ripping open a package", "tearing tape off a cardboard box"),
    K("plastic_bag", "tear", "비닐 구기는 소리", "a plastic bag crinkling", clap_only=True),
    K("camera_shutter", "household", "카메라 셔터 소리", "a camera shutter clicking"),
    K("can_open", "household", "캔 따는 소리", "a soda can opening with a fizz", clap_only=True),
    K("toilet", "household", "변기 물 내리는 소리", "a toilet flushing"),
    K("splash", "splash", "물 튀는 소리", "water splashing", "a big splash"),
    K("dive", "splash", "물에 뛰어드는 소리", "someone jumping into a pool", "a person diving into water"),
    K("typing", "typing", "키보드 소리", "typing on a computer keyboard", "fast mechanical keyboard typing"),
    K("mouse_click", "typing", "마우스 클릭 소리", "computer mouse clicking"),

    # ── 환경음 ─────────────────────────────────────────
    K("rain_light", "rain", "빗소리", "light rain falling", "gentle rain"),
    K("rain_heavy", "rain", "세찬 빗소리", "heavy rain pouring down", "a downpour"),
    K("rain_window", "rain", "창문에 빗방울 떨어지는 소리", "rain hitting a window", "rain drops on a roof"),
    K("thunder_clap", "thunder", "천둥", "a loud clap of thunder", "a thunder crack"),
    K("thunder_roll", "thunder", "멀리서 우르릉거리는 천둥", "rolling thunder rumbling"),
    K("wind_strong", "wind", "세찬 바람 소리", "strong wind howling", "a windstorm"),
    K("wind_breeze", "wind", "바람 소리", "a gentle breeze", "wind blowing"),
    K("leaves", "wind", "나뭇잎 스치는 소리", "leaves rustling in the wind"),
    K("stream", "water", "시냇물 소리", "a flowing stream", "a babbling brook"),
    K("waves", "water", "파도 소리", "ocean waves crashing on a beach"),
    K("waterfall", "water", "폭포 소리", "a waterfall"),
    K("tap_water", "water", "수돗물 소리", "water running from a faucet"),
    K("pour", "water", "따르는 소리", "pouring a drink into a glass", "pouring milk into a cup"),
    K("drip", "water", "방울 떨어지는 소리", "water dripping", "drops of water falling in a cave"),
    K("boiling", "water", "끓는 소리", "water boiling in a pot"),
    K("campfire", "fire", "모닥불 타는 소리", "a crackling campfire", "wood burning in a fireplace"),
    K("fire_big", "fire", "불길 소리", "a large fire roaring", "a burning building"),
    K("dog_bark", "animal", "개 짖는 소리", "a dog barking", "a big dog barking loudly"),
    K("dog_small", "animal", "작은 개 짖는 소리", "a small dog yapping", "a puppy barking"),
    K("dog_growl", "animal", "개 으르렁거리는 소리", "a dog growling"),
    K("dog_whine", "animal", "개 낑낑거리는 소리", "a dog whining", "a dog whimpering"),
    K("wolf_howl", "animal", "울부짖는 소리", "a wolf howling", "a dog howling"),
    K("cat_meow", "animal", "고양이 울음소리", "a cat meowing"),
    K("cat_hiss", "animal", "고양이 하악질", "an angry cat hissing"),
    K("cat_purr", "animal", "고양이 가르랑거리는 소리", "a cat purring"),
    K("rooster", "animal", "수탉 우는 소리", "a rooster crowing"),
    K("cow", "animal", "소 울음소리", "a cow mooing"),
    K("horse", "animal", "말 울음소리", "a horse neighing", "horse hooves galloping"),
    K("pig", "animal", "돼지 울음소리", "a pig oinking"),
    K("lion", "animal", "맹수 포효", "a lion roaring", "a tiger growling"),
    K("birds", "bird_insect", "새 지저귀는 소리", "birds chirping", "birds singing in the morning"),
    K("crow", "bird_insect", "까마귀 우는 소리", "a crow cawing"),
    K("owl", "bird_insect", "부엉이 우는 소리", "an owl hooting at night"),
    K("cricket", "bird_insect", "귀뚜라미 소리", "crickets chirping at night"),
    K("cicada", "bird_insect", "매미 소리", "cicadas buzzing loudly in summer", clap_only=True),
    K("mosquito", "bird_insect", "모기 소리", "a mosquito buzzing near the ear"),
    K("bee", "bird_insect", "벌 소리", "bees buzzing"),
    K("frog", "animal", "개구리 우는 소리", "frogs croaking"),
    K("crowd_murmur", "crowd", "웅성거림", "a crowd murmuring", "many people talking in the background"),
    K("crowd_cafe", "crowd", "식당·카페 소음", "background chatter in a busy restaurant", "a noisy cafe"),
    K("children_play", "crowd", "아이들 노는 소리", "children playing and laughing in a playground"),
    K("city_traffic", "traffic", "교통 소음", "city traffic noise", "cars on a busy street"),
    K("helicopter", "aircraft", "헬리콥터 소리", "a helicopter flying overhead"),
    K("airplane", "aircraft", "비행기 소리", "an airplane flying", "a jet plane passing overhead"),
    K("train_pass", "train", "기차 지나가는 소리", "a train passing by on the tracks"),
    K("subway", "train", "지하철 소리", "a subway train arriving at a station"),
    K("boat", "boat", "배 소리", "a motorboat engine", "a boat on the water"),
    K("clock_tick", "clock", "시계 초침 소리", "a clock ticking", "tick tock of a wall clock"),

    # ── 음악·효과음 ────────────────────────────────────
    K("music_bg", "music", "음악", "background music", "instrumental music playing"),
    K("music_band", "music", "음악", "a rock band playing", "electronic dance music"),
    K("music_classic", "music", "음악", "an orchestra playing", "solo piano music"),
    K("music_tension", "music", "음악", "suspenseful horror movie music", "dramatic cinematic music"),
    K("singing", "singing", "노랫소리", "a person singing a song", "a singer performing"),
    K("choir", "singing", "합창", "a choir singing"),
    K("rap", "singing", "랩", "a person rapping"),
    K("beep_short", "beep", "신호음", "a short electronic beep", "a single beep"),
    K("beep_notify", "beep", "알림음", "a phone notification sound", "a short digital notification chime"),
    K("beep_microwave", "beep", "전자레인지 완료음", "a microwave oven beeping when done", clap_only=True),
    K("beep_monitor", "beep", "심전도 모니터 소리", "a hospital heart monitor beeping", clap_only=True),
    K("beep_countdown", "beep", "카운트다운 신호음", "countdown timer beeps", "a timer beeping"),
    K("beep_reverse", "beep", "후진 경고음", "a truck reversing beeping"),
    K("bell", "chime", "종소리", "a bell ringing", "a church bell tolling"),
    K("bell_school", "chime", "학교 종소리", "a school bell ringing"),
    K("elevator_ding", "chime", "엘리베이터 도착음", "an elevator arrival ding", clap_only=True),
    K("wind_chime", "chime", "풍경 소리", "wind chimes tinkling"),
    K("sfx_whoosh", "sfx", "휙 지나가는 효과음", "a whoosh transition sound effect", "a fast swoosh"),
    K("sfx_boing", "sfx", "띠용 효과음", "a cartoon boing sound effect", "a comedic spring sound"),
    K("sfx_rimshot", "sfx", "예능 드럼 효과음", "a comedy drum rimshot ba dum tss", "a comedic drum sting"),
    K("sfx_scratch", "sfx", "레코드 긁는 효과음", "a record scratch sound effect"),
    K("sfx_sparkle", "sfx", "반짝이는 효과음", "a magical sparkle chime sound effect", "a twinkling sound effect"),
    K("sfx_sting", "sfx", "강조 효과음", "a dramatic sound effect sting", "a sudden dramatic hit"),
    K("sfx_pop", "sfx", "뿅 효과음", "a cute pop sound effect", "a bubbly pop sound"),
]

# 네거티브 클래스: 카테고리가 없다. CLAP이 이쪽을 고르면 "서비스 대상 아님".
# 이게 없으면 말소리·잡음도 억지로 가장 가까운 클래스(예: 웃음, 바람)로 끌려간다.
CLAP_NEGATIVES = [
    dict(id="neg_speech", role="voice", prompts=["a man speaking", "a woman talking", "people having a conversation"]),
    dict(id="neg_narration", role="voice", prompts=["a narrator speaking clearly", "a streamer talking into a microphone"]),
    dict(id="neg_whisper", role="voice", prompts=["a person whispering"]),
    dict(id="neg_silence", role="silence", prompts=["silence", "a quiet empty room"]),
    dict(id="neg_noise", role="noise", prompts=["background noise", "static hiss", "microphone noise"]),
]

# 야외 촬영 흡수용 (2026-10-12 브이로그 테스트): 걸으며 찍은 영상의 마이크 바람·손떨림·거리 배경음이
# 가스 분출(0.80)·비행기(0.66)·손가락 튕기는 소리 등으로 끌려감. AudioSet 도 'Wind noise (microphone)'는
# 소리 사건이 아니라 녹음 잡음으로 분류(제외)함. sound_direction_classifier 의 'background noise' 흡수용과 같은 발상.
# coarse2 에서만 사용 (--eval 로 기존 coarse 와 비교)
CLAP_AMBIENT = [
    dict(id="amb_mic_wind", role="ambient", prompts=["wind blowing into a microphone", "wind noise on a camera microphone outdoors"]),
    dict(id="amb_street", role="ambient", prompts=["outdoor street ambience", "background ambience of a city"]),
    dict(id="amb_handling", role="ambient", prompts=["handheld camera handling noise", "clothes rustling while walking with a camera"]),
]
