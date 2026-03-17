# Village RP Engine

텍스트 기반 마을 시뮬레이션 엔진이다. 1단계 목표는 "작은 마을이 플레이어 없이도 돌아가고, 플레이어가 그 안에 개입했을 때 사건과 반응이 읽히는가"를 검증하는 것이다.

## 1단계 범위

이번 단계에 포함한 것:

- 마을 시뮬레이션
  - 시간대 순환: `아침 / 낮 / 저녁 / 밤 / 새벽`
  - day / tick 기반 월드 진행
  - NPC 일정 기반 이동
  - 장소 / 시간 / 참여자 조건 기반 이벤트 발생
- 장면 / 대화 / 루머
  - visible scene 생성
  - entry / observe 문맥 분리
  - visible event overheard dialogue
  - rumor log 생성 및 dedupe
- NPC 상태 / 관계 / 인지
  - recent state(이벤트 여파) 부여 / 만료
  - NPC 간 관계 점수
  - 공통 NPC notice 레이어
  - notice 기반 분위기 scene 및 후속 talk 반응
- 플레이어 상호작용
  - 행동: `move`, `wait`, `talk`
  - `talk`는 무시간 행동으로 처리
  - 자연어 alias 입력 지원
- 플레이어 개입 구조
  - NPC -> PLAYER 호감도
  - 촌장이 주는 초미니 퀘스트 1개
    - `mediate_tavern_conflict`
- 검증 도구
  - CLI 실행
  - flow / injection demo 분리
  - 최소 텍스트 웹 UI
  - 테스트 스위트

## 구현된 기능 목록

현재 구현된 핵심 기능:

- 시간대와 day가 순환하는 tick 기반 월드 엔진
- RP mode / Observer mode 분리
- NPC 일정 기반 이동과 상태 기반 이동 override
- 술집 말다툼과 후속 이벤트(`farmer_grumbling_square`)
- rumor 생성, dedupe, hidden event rumor 처리
- recent state 기반 대화 / 현장 대사 반영
- guard_captain, village_elder 포함 역할별 대사 정체성 분리
- 공통 notice 생성과 notice 기반 반응
- 플레이어 무시간 `talk` 인터랙션
- 플레이어 호감도(`-2 ~ +2`)
- 촌장 중재 퀘스트 1개
- 텍스트 웹 UI에서 scene / dialogue / event / rumor / 관계 / 퀘스트 / favor 표시

## 실행 방법

### CLI 실행

```powershell
python -m village_rp_engine.main --mode rp
```

### Flow Demo 실행 순서

실제 사건 -> 상태 -> 후속 반응 흐름을 보고 싶을 때:

```powershell
python run_demo.py
```

### Injection Demo 실행 순서

특정 반응만 짧게 검증하고 싶을 때:

1. 경비대장 새벽 notice / 경계 반응 확인

```powershell
python demo_guard_dawn.py
```

2. 촌장 간접 중재 반응 확인

```powershell
python demo_elder_mediation.py
```

### 웹 UI 실행

엔진 상태 변화를 한 화면에서 보고 싶을 때:

```powershell
python web_ui.py
```

기본 주소:

- `http://127.0.0.1:8000`

## Demo 구조

검증용 demo는 두 종류다.

- Flow Demo
  - 실제 사건 -> 상태 -> 후속 반응을 따라가는 통합 검증용
  - 파일: `run_demo.py`
- Injection Demo
  - 특정 상태나 조건을 사전 주입해서 반응만 빠르게 확인하는 디버깅용
  - 파일: `demo_guard_dawn.py`, `demo_elder_mediation.py`

모든 demo는 시작 시 `Demo Type`과 목적 설명을 먼저 출력한다.

## 테스트

```powershell
pytest -q
```

## 플레이어 행동 규칙

- `move` -> tick 소비
- `wait` -> tick 소비
- `talk` -> tick 소비하지 않음

즉, 플레이어 대화는 현재 시점 내부 인터랙션으로 처리되고 NPC 이동 / 이벤트 / rumor tick 구조는 그대로 유지된다.

## 이번에 안 한 것

1단계에서 의도적으로 제외한 것:

- 저장 / 불러오기
- 다중 퀘스트
- 인벤토리 / 보상 아이템
- reputation 시스템
- stealth / 은신
- 검문 / 체포 / 제재
- 전투
- 다중 마을 / 글로벌 뉴스
- 더 많은 장소 / 더 많은 NPC 대규모 확장
- 복잡한 UI(지도, 게이지, 설정창)

## 다음 단계에서 할 것

2단계 후보:

- 저장 / 불러오기
- 다중 퀘스트 구조
- 더 많은 장소와 NPC 추가
- stealth / 은신 기초 규칙
- guard 검문 / 의심 행동 처리
- 플레이어 호감도 활용 대사 확장
- 퀘스트 2개 이상 지원
- 웹 UI에서 로그 탐색성과 상태 표시 개선
