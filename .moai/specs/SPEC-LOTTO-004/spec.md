---
id: SPEC-LOTTO-004
version: "0.1.0"
status: completed
created: "2026-05-21"
updated: "2026-05-21"
author: ircp
priority: high
issue_number: 0
---

# SPEC-LOTTO-004: 통합 테스트 및 커버리지 강화

## HISTORY

| 버전 | 일자 | 작성자 | 변경 내용 |
|------|------|--------|-----------|
| 0.1.0 | 2026-05-21 | ircp | 초기 SPEC 작성 — 통합 E2E 테스트, FastAPI lifespan 검증, recommender 폴백 경로, scraper 워커 통합, 설정 검증 에러 경로 커버리지 강화 |

---

## Overview (개요)

### What (무엇을 만드는가)

SPEC-LOTTO-001~003 및 SPEC-WEB-001 완료 시점에서 286개 테스트와 91.49% 커버리지를 달성했다. 그러나 다음 영역은 단위 테스트로만 검증되어 실제 통합 시나리오와 폴백 경로가 누락되어 있다:

1. **파이프라인 통합 테스트**: `collect → analyze → recommend → simulate` 전체 흐름이 단일 시나리오에서 검증되지 않는다. CSV 저장/로딩 라운드트립도 통합 관점에서 명시적이지 않다.
2. **FastAPI lifespan 및 주간 자동수집 태스크**: `_lifespan` 컨텍스트 매니저, `_weekly_collect_task` 코루틴, `_next_monday_midnight` 헬퍼가 직접 테스트되지 않는다.
3. **Recommender 엣지케이스**: `_pick_set`의 후보 소진 시 폴백 경로(line 228~243), 보너스 회피 가중치 활성 분기(line 106~110)가 부분 검증 상태이다.
4. **API scraper 워커 및 에러 브랜치**: `_scrape_worker`(line 372~422), `_collect_worker`의 최종 저장 실패 브랜치(line 221~223)가 미커버이다.
5. **Config 검증 에러 경로**: 부동소수 가중치 파싱 실패, dotenv 미설치 분기가 일부만 검증된다.

본 SPEC은 이 누락 영역을 통합 테스트와 폴백 경로 테스트로 보완하여 전체 커버리지를 95% 이상으로 끌어올린다.

### Why (왜 만드는가)

- **운영 신뢰성**: 자동 주간 수집 태스크는 실서비스의 핵심 백엔드 기능이지만 테스트가 전무하다. 회귀 시 사용자가 통계 업데이트를 잃을 위험이 있다.
- **폴백 경로 검증**: Recommender와 scraper의 예외 경로는 도메인 가정이 깨졌을 때 실행된다. 폴백이 실제로 호환 가능한 결과를 반환하는지 보장이 필요하다.
- **통합 회귀 안전망**: 단위 테스트가 통과해도 통합 시나리오에서 데이터 형식 불일치/순서 의존성 등이 발생할 수 있다. E2E 흐름 1개라도 명시적으로 검증해두면 리팩토링 안전성이 크게 향상된다.

### Scope (적용 범위)

- **포함**:
  - `tests/test_integration_pipeline.py` (신규) — 전체 파이프라인 E2E
  - `tests/test_app_lifespan.py` (신규) — FastAPI lifespan + 주간 태스크
  - `tests/test_recommender_edge.py` (신규) — 폴백 및 보너스 회피 활성 경로
  - `tests/test_api_scraper_worker.py` (신규) — scraper 워커 및 collect 워커 에러 분기
  - `tests/test_config_edge.py` (신규) — 부동소수/dotenv 미설치 경로
- **제외**: 새 기능 추가, 소스 코드 동작 변경, UI 변경, 외부 의존성 추가
- **제약**: Python 3.9 호환 유지(`zip(strict=True)` 금지, `match` 문 금지, walrus operator 금지). 기존 286개 테스트 모두 통과 유지. 새 의존성 추가 금지(`httpx`, `pytest-asyncio`는 이미 설치됨).

---

## Requirements (요구사항)

### REQ-INT-001: 전체 파이프라인 E2E 테스트

**[Ubiquitous]** 시스템은 `collect → analyze → recommend → simulate` 전체 파이프라인이 단일 통합 시나리오에서 작동함을 보장해야 한다.

**[Event-driven]** 50개 임의 회차 데이터가 주어졌을 때, 시스템은 다음을 수행해야 한다:
1. `LottoAnalyzer().analyze(draws)`가 `total_rounds == 50`이고 `bonus_frequency`가 비어있지 않은 `Statistics`를 반환해야 한다.
2. `LottoRecommender(stats).recommend(5)`가 6개 번호로 구성된 5개의 추천 세트를 반환해야 한다.
3. `LottoSimulator(draws).simulate(rounds=20)`가 `prize_counts` 딕셔너리를 포함한 `SimulationResult`를 반환해야 한다.

**[State-driven]** `LottoCollector(data_dir=tmp_path)`로 저장된 CSV를 동일 컬렉터로 다시 로드할 때, 회차 수와 첫 회차 번호는 원본과 일치해야 한다.

### REQ-INT-002: FastAPI lifespan 및 주간 자동수집 태스크 테스트

**[Ubiquitous]** 시스템은 FastAPI 앱의 라이프사이클 후크가 백그라운드 태스크를 정상적으로 생성/취소함을 보장해야 한다.

**[Event-driven]** `_next_monday_midnight()` 호출 시 시스템은 다음 월요일 자정까지의 양수 초를 반환해야 한다(< 7*24*3600).

**[Event-driven]** `_weekly_collect_task()` 코루틴이 `asyncio.Task`로 실행 중 `task.cancel()`을 호출하면, 시스템은 `CancelledError`를 외부로 전파하지 않고 깨끗하게 종료해야 한다.

**[Event-driven]** `app`의 lifespan이 시작/종료되면 시스템은 weekly task를 생성한 후 종료 시 취소해야 한다.

### REQ-INT-003: Recommender 엣지케이스 폴백 경로 테스트

**[Ubiquitous]** 시스템은 `_pick_set`의 후보 소진/중복 회피 실패 시 안전한 폴백 동작을 보장해야 한다.

**[Event-driven]** 20개 추천 세트(`count=20`)를 요청하면, 시스템은 후보가 부족한 전략에서도 `ValueError`/`RuntimeError` 없이 20개 세트를 반환해야 한다.

**[State-driven]** `settings.bonus_avoidance_weight = 0.5`이고 보너스 빈도가 채워진 통계가 주어지면, 시스템은 보너스 회피 분기를 실행하여 `compute_scores()`가 정상 반환해야 한다.

### REQ-INT-004: API scraper 통합 워커 및 에러 브랜치 테스트

**[Ubiquitous]** 시스템은 `_scrape_worker`와 `_collect_worker`의 모든 분기(성공/실패/저장 오류)를 검증해야 한다.

**[Event-driven]** `POST /api/scrape` 요청 시 시스템은 202 Accepted를 반환하고 `status: started` 응답을 제공해야 한다.

**[Event-driven]** `scrape_all`이 모의로 빈 리스트를 반환하면, 시스템은 `_collect_state["status"]`를 `"error"`로 설정해야 한다.

**[Event-driven]** `_collect_worker`의 저장 단계(`save_csv`)에서 예외가 발생하면, 시스템은 `_collect_state["status"]`를 `"error"`로 갱신하고 메시지에 `"저장 실패"`를 포함해야 한다.

### REQ-INT-005: Config 검증 에러 경로 테스트

**[Ubiquitous]** 시스템은 `lotto.config._load_settings()`의 모든 검증 에러 분기를 검증해야 한다.

**[Event-driven]** `LOTTO_BONUS_AVOIDANCE_WEIGHT`에 비숫자 값(`"abc"`)이 주어지면, 시스템은 명확한 `ValueError`를 발생시켜야 한다.

**[State-driven]** `dotenv` 패키지를 사용할 수 없는 환경(`_DOTENV_AVAILABLE = False`)에서도 `_load_settings()`는 예외 없이 `Settings` 인스턴스를 반환해야 한다.

### NFR: 전체 커버리지 95% 이상 달성

**[Ubiquitous]** 본 SPEC의 모든 테스트가 통과한 상태에서 `pytest --cov=lotto`로 측정한 전체 라인 커버리지는 95% 이상이어야 한다.

**[Ubiquitous]** 기존 286개 테스트는 모두 통과 상태를 유지해야 한다(회귀 0).

---

## Out of Scope (범위 외)

- 새 기능 또는 API 엔드포인트 추가
- 소스 코드 리팩토링(폴백 동작/시그니처 변경)
- 성능 최적화
- 새 외부 의존성 도입
- Python 3.10+ 전용 문법 사용

---

@MX:SPEC: SPEC-LOTTO-004 REQ-INT-001~005, NFR-COV-95
