# Village RP Engine

텍스트 기반 마을 시뮬레이션 엔진이다. 현재 상태는 Continental RP 구조의 `Phase 2: Multi-Settlement Network`까지 반영된 검증용 엔진이다.

## 현재 범위

이번 버전(`v0.2-phase2`)에 포함된 것:

- 단일 엔진 위의 multi-settlement world wrapper
- 3개 settlement registry
  - `village_1`
  - `village_2`
  - `town_1`
- canonical seed container
  - `SettlementDefinition`
- world root wrapper
  - `WorldSnapshot`
  - `Phase1WorldEngine` 기반 multi-settlement dispatch
- depth policy
  - `ACTIVE`
  - `RECENT`
  - `UNVISITED`
- settlement link 기반 이동 및 rumor propagation
- ACTIVE settlement 전용 scene / dialogue 생성
- player 무시간 `talk`
- NPC 상태 / 관계 / 루머 / notice
- 플레이어 호감도
- 촌장 중재 퀘스트 1개
- CLI / demo / 텍스트 웹 UI
- 테스트 스위트

## 구조 원칙

- Invisible World = State
- Visible World = Scene
- `SettlementDefinition`은 seed source다
- runtime truth는 settlement state에만 존재한다
- `presentation_state`는 항상 derived-only다
- scene / dialogue는 on-demand 생성이다
- ACTIVE settlement만 full interaction을 수행한다
- RECENT / UNVISITED는 경량 업데이트만 수행한다
- cross-settlement에서는 event가 아니라 rumor만 전파한다

## 구현된 기능 목록

### Settlement Layer

- 시간대 순환: `아침 / 낮 / 저녁 / 밤 / 새벽`
- tick / day 기반 월드 진행
- NPC 일정 기반 이동
- 장소 / 시간 / 참여자 조건 기반 이벤트 발생
- recent state 부여 / 만료
- NPC 간 관계 점수
- rumor 생성 / dedupe
- 공통 NPC notice 레이어
- 플레이어 호감도 `-2 ~ +2`
- 초미니 퀘스트 1개
  - `mediate_tavern_conflict`

### World Wrapper

- multi-settlement registry 관리
- settlement link registry 관리
- depth별 dispatch
  - `ACTIVE`: full interaction
  - `RECENT`: lightweight update
  - `UNVISITED`: numeric-only update
- settlement 간 rumor propagation
- player inter-settlement travel
- chronicle summary hook

### Presentation Layer

- visible scene 생성
- dialogue surface 생성
- world log / rumor log / chronicle 표시
- 최소 텍스트 웹 UI

## 실행 순서

### 1. 테스트

```powershell
pytest -q
```

### 2. CLI 실행

```powershell
python -m village_rp_engine.main --mode rp
```

지원 행동:

- `wait`
- `move <장소>`
- `talk <대상>`
- `travel <settlement>`

### 3. Flow Demo

```powershell
python run_demo.py
```

### 4. Injection Demo

경비대장 새벽 notice 확인:

```powershell
python demo_guard_dawn.py
```

촌장 간접 중재 반응 확인:

```powershell
python demo_elder_mediation.py
```

### 5. Web UI

```powershell
python web_ui.py
```

기본 주소:

- `http://127.0.0.1:8000`

## 플레이어 행동 규칙

- `move` -> tick 소비
- `wait` -> tick 소비
- `talk` -> tick 소비하지 않음
- `travel` -> world-level settlement 이동

즉, 대화는 현재 시점 내부 인터랙션이고, settlement 이동은 link 기반 world action이다.

## 이번 버전에 포함된 것

- 마을 3개 이상을 가진 연결 world
- settlement link 기반 이동 제한
- cross-settlement rumor propagation
- ACTIVE / RECENT / UNVISITED 차등 처리
- 플레이어 존재를 active settlement 하나로만 유지
- scene / dialogue를 ACTIVE settlement에만 표시
- 플레이어 호감도
- 퀘스트 1개

## 이번에 안 한 것

- 저장 / 불러오기
- 다중 퀘스트
- inventory / 보상 아이템
- reputation 시스템
- stealth / 은신
- 검문 / 체포 / 제재
- 전투
- RegionLayer 실제 구현
- ContinentLayer 실제 구현
- diplomacy
- macro economy
- caravan / trade simulation
- pathfinding / multi-hop travel
- NPC cross-settlement full simulation
- 복잡한 UI(지도, 게이지, 설정창)

## 다음 단계에서 할 것

- RegionLayer stub를 실제 influence producer로 확장
- RECENT / UNVISITED 정책 정교화
- settlement별 seed 다양화
- chronicle surface 강화
- 다중 퀘스트 구조
- 저장 / 불러오기
- 더 많은 settlement / 장소 / NPC 확장
