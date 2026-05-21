# SPEC-LOTTO-004: 인수 기준 (Acceptance Criteria)

본 문서는 SPEC-LOTTO-004 통합 테스트 및 커버리지 강화의 인수 기준을 Given-When-Then 형식으로 기술한다.

---

## REQ-INT-001: 전체 파이프라인 E2E 테스트

### Scenario 1.1: 분석 단계 통과

- **Given** 50개의 임의 `DrawResult` 객체가 생성되어 있고,
- **When** `LottoAnalyzer().analyze(draws)`를 호출하면,
- **Then** 반환된 `Statistics`의 `total_rounds`는 50이어야 하고, `bonus_frequency.absolute`는 비어있지 않아야 한다.

### Scenario 1.2: 추천 단계 통과

- **Given** 50개의 임의 회차 데이터로부터 계산된 `Statistics`가 있고,
- **When** `LottoRecommender(stats).recommend(count=5)`를 호출하면,
- **Then** 5개의 `Recommendation` 객체가 반환되어야 하고, 각 객체의 `numbers` 길이는 6이어야 한다.

### Scenario 1.3: 시뮬레이션 단계 통과

- **Given** 100개의 회차 데이터가 있고,
- **When** `LottoSimulator(draws).simulate(rounds=20)`을 호출하면,
- **Then** 반환된 `SimulationResult.total_rounds`는 20이어야 하고, `prize_counts`는 `"1등"~"낙첨"` 키를 포함해야 한다.

### Scenario 1.4: CSV 저장-로드 라운드트립

- **Given** 임시 디렉토리(`tmp_path`)와 10개의 임의 회차 데이터가 있고,
- **When** `LottoCollector(data_dir=tmp_path).save_csv(draws)` 후 새 컬렉터로 `load_existing()`을 호출하면,
- **Then** 로드된 회차 수는 원본과 동일해야 하고, 첫 회차의 `drwNo`와 `bonus` 필드도 보존되어야 한다.

---

## REQ-INT-002: FastAPI lifespan 및 주간 자동수집 태스크 테스트

### Scenario 2.1: `_next_monday_midnight` 양수 반환

- **Given** 임의 시점에 호출하면,
- **When** `_next_monday_midnight()`를 실행하면,
- **Then** 반환된 초는 양수여야 하고, 7일(604800초) 미만이어야 한다.

### Scenario 2.2: `_next_monday_midnight` 월요일 보장

- **Given** 현재 datetime이 임의 요일이고,
- **When** `_next_monday_midnight()`만큼 더한 datetime을 계산하면,
- **Then** 결과 datetime의 `weekday()`는 0(월요일)이어야 한다.

### Scenario 2.3: `_weekly_collect_task` 취소 처리

- **Given** `asyncio.create_task(_weekly_collect_task())`로 태스크가 실행 중이고,
- **When** `task.cancel()` 호출 후 `await task` 또는 `asyncio.gather(task, return_exceptions=True)`로 대기하면,
- **Then** `CancelledError`만 발생하고, 외부로 다른 예외가 전파되지 않아야 한다.

### Scenario 2.4: lifespan 컨텍스트 매니저 사이클

- **Given** `lotto.web.app.app` FastAPI 인스턴스가 있고,
- **When** `httpx.AsyncClient`로 lifespan을 가동(`async with`)했다가 종료하면,
- **Then** 시작 시 weekly task가 생성되고, 종료 시 정상적으로 취소되며 예외가 발생하지 않아야 한다.

---

## REQ-INT-003: Recommender 엣지케이스 폴백 경로 테스트

### Scenario 3.1: 후보 소진 시 안전 반환

- **Given** 극히 편향된 `Statistics`(특정 번호에만 점수 집중)가 있고,
- **When** `LottoRecommender(stats).recommend(count=20)`을 호출하면,
- **Then** `RuntimeError`/`ValueError` 없이 정확히 20개의 `Recommendation`이 반환되어야 한다.

### Scenario 3.2: 보너스 회피 가중치 활성 분기

- **Given** `lotto.recommender.settings.bonus_avoidance_weight`를 0.5로 설정하고 보너스 빈도가 채워진 `Statistics`가 있을 때,
- **When** `LottoRecommender(stats).compute_scores()`를 호출하면,
- **Then** 45개 번호 모두에 대한 점수 딕셔너리가 반환되어야 하고, 보너스 빈도가 높은 번호의 점수는 가중치 0인 경우보다 낮아야 한다.

---

## REQ-INT-004: API scraper 통합 워커 및 에러 브랜치 테스트

### Scenario 4.1: scrape 엔드포인트 트리거

- **Given** FastAPI `TestClient`가 준비되어 있고 현재 수집 상태가 idle이며,
- **When** `POST /api/scrape`를 호출하면,
- **Then** 응답 코드는 202이고, JSON body에 `status: "started"`가 포함되어야 한다.

### Scenario 4.2: scrape worker 빈 결과 처리

- **Given** `lotto.scraper.scrape_all`이 빈 리스트를 반환하도록 모킹되어 있고,
- **When** `_scrape_worker()`를 직접 호출하면,
- **Then** `_collect_state["status"]`는 `"error"`로 설정되어야 한다.

### Scenario 4.3: collect worker 저장 실패 처리

- **Given** `LottoCollector.save_csv`가 예외를 던지도록 모킹되어 있고 임의 회차 데이터가 fetch에서 성공하도록 모킹되어 있을 때,
- **When** `_collect_worker(full=False, start_from=1, max_drw_no=N)`를 호출하면,
- **Then** `_collect_state["status"]`는 `"error"`이고, `_collect_state["message"]`에 `"저장 실패"`가 포함되어야 한다.

---

## REQ-INT-005: Config 검증 에러 경로 테스트

### Scenario 5.1: 잘못된 보너스 회피 가중치

- **Given** `LOTTO_BONUS_AVOIDANCE_WEIGHT` 환경 변수에 `"abc"`가 설정되어 있고,
- **When** `lotto.config` 모듈을 재임포트하면,
- **Then** `ValueError`가 발생하고 메시지에 `"LOTTO_BONUS_AVOIDANCE_WEIGHT"`가 포함되어야 한다.

### Scenario 5.2: dotenv 미설치 경로

- **Given** `lotto.config._DOTENV_AVAILABLE`을 `False`로 패치하면,
- **When** `_load_settings()`를 호출하면,
- **Then** 예외 없이 `Settings` 인스턴스가 반환되어야 한다.

---

## NFR: 커버리지 및 회귀 검증

### Scenario 6.1: 전체 커버리지 95% 이상

- **Given** 본 SPEC의 모든 테스트가 추가된 상태에서,
- **When** `python3.9 -m pytest --cov=lotto`를 실행하면,
- **Then** 출력된 전체 커버리지 비율은 95% 이상이어야 한다.

### Scenario 6.2: 회귀 0

- **Given** 본 SPEC 추가 전 286개 테스트가 통과하고 있을 때,
- **When** 본 SPEC의 테스트 추가 후 전체 테스트 스위트를 실행하면,
- **Then** 모든 기존 테스트가 통과해야 한다(0 회귀).

---

@MX:SPEC: SPEC-LOTTO-004 REQ-INT-001~005, NFR-COV-95
