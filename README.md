# Village RP Engine

텍스트 기반 마을 시뮬레이션 엔진이다. 현재 저장소 상태는 단일 정착지 실험 단계를 넘어, 정착지-지역-대륙 계층과 chronicle/history 조회, 저장/불러오기, 선택형 플레이어 상호작용까지 포함한 검증용 MVP로 올라와 있다.

이 문서는 현재 코드 기준 상태를 설명한다.

## 현재 구현 범위

- 정착지 3개
  - `village_1`
  - `village_2`
  - `town_1`
- 지역 2개
  - `north_fields`
  - `river_trade`
- 대륙 1개
  - `continent_1`
- 시뮬레이션 depth 분리
  - `ACTIVE`
  - `RECENT`
  - `UNVISITED`
- 정착지 간 이동과 rumor propagation
- 지역 influence와 대륙 influence의 하향 반영
- chronicle archive 및 history query/comparison
- 플레이어 선택 기반 delayed influence
- 특수 NPC 상태 추적
  - `DORMANT -> LINKED -> CONVERGING -> ENCOUNTERED`
- 저장 / 불러오기 / 월드 리셋
- CLI / 데모 / 최소 Web UI
- 테스트 스위트

## 시스템 요약

### 1. Settlement Layer

- 시간대 순환: `아침 / 낮 / 저녁 / 밤 / 새벽`
- tick / day 기반 진행
- NPC 일정 기반 이동
- 조건부 이벤트 발동
- scene / dialogue on-demand 생성
- rumor 생성 및 dedupe
- NPC recent state, notice, 관계도 관리
- 플레이어 호감도 추적
- 퀘스트 상태 추적

### 2. World Layer

- multi-settlement registry
- settlement link 기반 이동 가능 여부 판정
- `ACTIVE / RECENT / UNVISITED` 별 차등 시뮬레이션
- cross-settlement rumor propagation
- recently visited settlement 추적
- pending influence 누적 및 지연 적용

### 3. Region / Continent Layer

- region runtime state 갱신
  - `security_risk`
  - `trade_flow`
  - `rumor_density`
  - `stress_modifier`
- continent runtime state 갱신
  - `global_tension`
  - `trade_pressure`
  - `migration_pressure`
  - `rumor_noise`
  - `stability`
- continent -> region -> settlement 방향의 influence 반영

### 4. Chronicle / History Layer

- chronicle archive 누적
- 최근 세계 변화 조회
- settlement / region / continent 단위 history 조회
- 기간 기반 조회
- scope diff 요약
- settlement / region / continent 비교
- 플레이어 기준 direct / indirect timeline 조회

### 5. Gameplay Layer

- `choose <선택>` 기반 플레이어 선택 입력
- 선택 결과를 즉시 수치 변경하지 않고 influence packet으로 지연 반영
- 현재 기본 선택
  - `support_guard`
  - `ignore_murmurs`
  - `follow_whisper`
- 선택 누적에 따른 특수 NPC 진행
  - `wandering_stranger`

### 6. Persistence Layer

- 저장 슬롯 3개
- 저장 파일 위치: `saves/slot_<1-3>.json`
- 저장 대상
  - settlement states
  - region states
  - continent states
  - chronicle archive
  - pending influences
  - interaction runtime state
  - special NPC states
- `reset` 시 seed snapshot으로 복귀

## 실행

### 테스트

```powershell
pytest -q
```

### CLI

RP 모드:

```powershell
python -m village_rp_engine.main --mode rp
```

Observer 모드:

```powershell
python -m village_rp_engine.main --mode observer --ticks 10
```

추가 옵션:

```powershell
python -m village_rp_engine.main --mode rp --ticks 20
```

### Web UI

```powershell
python web_ui.py
```

기본 주소:

- `http://127.0.0.1:8000`

호스트/포트 변경:

```powershell
python web_ui.py --host 0.0.0.0 --port 8010
```

### 데모

Flow demo:

```powershell
python run_demo.py
```

경비대장 새벽 notice/injection demo:

```powershell
python demo_guard_dawn.py
```

촌장 중재 반응 demo:

```powershell
python demo_elder_mediation.py
```

## CLI 명령

기본 행동:

- `wait`
- `move <장소>`
- `talk <대상>`
- `travel <settlement>`
- `choose <선택>`
- `save <1-3>`
- `load <1-3>`
- `reset`

history 조회:

- `history recent`
- `history settlement <id>`
- `history region <id>`
- `history continent <id>`
- `history compare settlement <a> <b>`
- `history compare region <a> <b>`
- `history compare continent <a> [b]`

입력 별칭 예시:

- `이동 술집`
- `시장가기`
- `대화 촌장`
- `말걸기 경비대장`
- `travel village_2`
- `선택 follow_whisper`

## 플레이어 행동 규칙

- `wait`는 tick을 소비한다.
- `move`는 tick을 소비한다.
- `travel`은 world-level 이동이며 tick을 소비한다.
- `talk`는 현재 시점 내부 상호작용이라 tick을 소비하지 않는다.
- `choose`는 즉시 world state를 크게 바꾸지 않고, 이후 tick에서 여파가 반영될 수 있다.

## Web UI에서 볼 수 있는 것

- 현재 정착지, 위치, 시간대
- visible scenes / dialogues / 발생 이벤트
- rumor 요약
- quest / favor / relationship
- 최근 저장 목록
- NPC 위치 / 상태 로그
- chronicle 요약
- 이동 / 대화 / 선택 / 저장 / 불러오기 / 리셋 버튼

## 현재 문서 기준으로 이미 구현된 것

- Phase 2: multi-settlement world
- Phase 3: region layer
- Phase 4: continent layer
- Phase 5: chronicle archive
- Phase 6: history query / comparison
- Phase 8: gameplay interaction layer 일부
- save / load / reset

즉, 예전 README에 있던 "저장/불러오기 미구현", "RegionLayer 미구현", "ContinentLayer 미구현" 설명은 이제 맞지 않는다.

## 아직 없는 것

- inventory / 아이템 보상
- reputation 전역 시스템
- stealth / 검문 / 체포
- 전투
- caravan / trade simulation 심화
- pathfinding / multi-hop travel
- NPC의 full cross-settlement simulation
- 복잡한 지도형 UI
- 콘텐츠 볼륨이 큰 다중 퀘스트 구조

## 저장소에서 먼저 볼 파일

- `village_rp_engine/main.py`
- `village_rp_engine/core/mode_controller.py`
- `village_rp_engine/core/world_engine.py`
- `village_rp_engine/logs/chronicle.py`
- `web_ui.py`

## 참고

- 저장 데이터는 실행 중 자동 생성될 수 있으므로 `saves/` 디렉터리가 생긴다.
- 현재 작업 트리에는 코드 변경이 이미 존재할 수 있으므로, 문서는 코드 기준 동작만 반영한다.
