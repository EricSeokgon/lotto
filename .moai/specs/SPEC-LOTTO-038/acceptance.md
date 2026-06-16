# SPEC-LOTTO-038 인수 기준 (Acceptance Criteria)

모든 시나리오는 `PYTHONPATH=/home/sklee/moai/lotto` 환경에서 pytest로 검증한다.
테스트 픽스처는 기존 `tests/fixtures` 및 `tests/conftest.py` 패턴을 재사용한다.

---

## 데이터 집계 — `dashboard_overview()`

### AC-1: 정상 데이터에서 핵심 요약 반환 (REQ-DASH-001, 003, 004)

- **Given** 당첨금 정보가 있는 회차 N개를 포함한 `draws` 리스트가 주어졌을 때
- **When** `dashboard_overview(draws)`를 호출하면
- **Then** `total_draws == N`이고, `total_prize1_sum`이 모든 `prize1Amount`(None 제외)의 정수 합과 같다.

### AC-2: 번호별 출현 횟수에 1~45 전 키 존재 (REQ-DASH-005)

- **Given** 알려진 당첨번호 분포를 가진 `draws`가 주어졌을 때
- **When** `dashboard_overview(draws)`를 호출하면
- **Then** `number_frequency`는 1부터 45까지 모든 번호를 포함하고, 각 번호의 count가 해당 번호의 본번호 출현 횟수와 일치한다. (보너스 번호는 집계되지 않는다 — EXC-001)

### AC-3: 최고/최저 1등 당첨금 회차 식별 (REQ-DASH-006)

- **Given** 서로 다른 `prize1Amount`를 가진 회차들이 주어졌을 때
- **When** `dashboard_overview(draws)`를 호출하면
- **Then** `highest_prize1_draw`는 최대 `prize1Amount` 회차의 `{drwNo, date, prize1Amount}`를, `lowest_prize1_draw`는 최소 회차의 동일 구조를 반환한다.

### AC-4: 당첨금 정보 없는 회차만 존재 시 None 처리 (REQ-DASH-007)

- **Given** 모든 회차의 `prize1Amount`가 `None`인 `draws`가 주어졌을 때
- **When** `dashboard_overview(draws)`를 호출하면
- **Then** `total_prize1_sum == 0`, `highest_prize1_draw is None`, `lowest_prize1_draw is None`이고, `total_draws`는 회차 수와 같다.

### AC-5: 홀짝 분포 및 번호대 분포 (REQ-DASH-008, 009)

- **Given** 알려진 번호 구성을 가진 `draws`가 주어졌을 때
- **When** `dashboard_overview(draws)`를 호출하면
- **Then** `odd_even`는 `{"odd", "even"}` 키를 가지며 홀/짝 합이 `total_draws * 6`과 같고, `range_distribution`는 `1-9 / 10-19 / 20-29 / 30-39 / 40-45` 5개 키를 모두 가지며 구간 합이 `total_draws * 6`과 같다.

### AC-6: 연도별 평균 당첨금 추이 (REQ-DASH-010)

- **Given** 2개 이상의 연도에 걸친, 당첨금 정보가 있는 `draws`가 주어졌을 때
- **When** `dashboard_overview(draws)`를 호출하면
- **Then** `yearly_avg_prize`는 연도 오름차순 리스트이며, 각 항목의 `avg_prize1`은 해당 연도 당첨금 보유 회차들의 평균(정수)과 일치하고 `draws` 필드는 그 회차 수와 같다.

### AC-6b: 빈 데이터 일관 구조 (REQ-DASH-011)

- **Given** `draws`가 빈 리스트 또는 `None`일 때
- **When** `dashboard_overview(draws)`를 호출하면
- **Then** `total_draws == 0`, `total_prize1_sum == 0`, `number_frequency`의 1~45 모든 count가 0, `odd_even == {"odd":0,"even":0}`, `range_distribution`의 5구간 모두 0, `yearly_avg_prize == []`, 최고/최저 회차가 `None`인 구조를 반환한다 (예외 없음).

### AC-6c: 인자 생략 시 자동 로드 (REQ-DASH-002)

- **Given** `get_draws()`가 일정한 회차를 반환하도록 monkeypatch된 상태에서
- **When** `dashboard_overview()`를 인자 없이 호출하면
- **Then** `get_draws()`가 호출되어 그 결과로 집계가 수행된다.

---

## API — `GET /api/stats/overview`

### AC-7: 정상 데이터에서 200 + 전체 구조 (REQ-DASH-API-001)

- **Given** 회차 데이터가 존재하는 TestClient 환경에서
- **When** `GET /api/stats/overview`를 호출하면
- **Then** HTTP 200이며 JSON 본문에 `total_draws`, `total_prize1_sum`, `number_frequency`, `highest_prize1_draw`, `lowest_prize1_draw`, `odd_even`, `range_distribution`, `yearly_avg_prize` 8개 키가 모두 존재한다.

### AC-8: 데이터 부재 시에도 200 + 빈 구조 (REQ-DASH-API-002)

- **Given** `get_draws()`가 `None`을 반환하도록 monkeypatch된 환경에서
- **When** `GET /api/stats/overview`를 호출하면
- **Then** HTTP 200이며 본문은 빈 구조(`total_draws == 0` 등)를 반환한다 (503이 아니다).

### AC-9: 부작용 없음 (REQ-DASH-API-003)

- **Given** 회차 데이터가 존재하는 환경에서
- **When** `GET /api/stats/overview`를 호출하면
- **Then** `lotto/data/` 내 어떤 파일도 생성/수정되지 않으며 외부 네트워크 호출이 발생하지 않는다.

---

## 웹 페이지 — `/stats`

### AC-10: 페이지 렌더링 및 active_tab (REQ-DASH-PAGE-001)

- **Given** 회차 데이터가 존재하는 TestClient 환경에서
- **When** `GET /stats`를 호출하면
- **Then** HTTP 200이며 `text/html` 응답이고, 통계 대시보드 네비게이션 탭이 활성 상태(`active_tab == "stats"`)로 표시된다.

### AC-11: 7개 통계 요소 노출 (REQ-DASH-PAGE-002)

- **Given** 회차 데이터가 존재하는 환경에서
- **When** `GET /stats` HTML을 받으면
- **Then** 응답 본문에 총 회차수, 총 1등 당첨금 합계, 번호별 출현 횟수 차트 영역, 최고/최저 당첨금 회차, 홀짝 분포, 번호대 분포, 연도별 평균 당첨금 추이를 나타내는 마커/텍스트가 모두 포함된다.

### AC-12: 빈 데이터 안내 + 네비게이션 진입점 (REQ-DASH-PAGE-003, 004)

- **Given** `get_draws()`가 `None`을 반환하도록 monkeypatch된 환경에서
- **When** `GET /stats`를 호출하면
- **Then** HTTP 200이며 빈 상태 안내 메시지가 표시되고 서버 오류가 없다.
- **And** 임의의 기존 페이지(예: `GET /`)의 HTML에 `/stats`로 연결되는 네비게이션 링크가 포함된다.

---

## 비기능 / 회귀

### AC-13: 회귀 무결성 및 커버리지 (REQ-DASH-NFR-001, 002, 003)

- **Given** 신규 코드와 테스트가 추가된 상태에서
- **When** `PYTHONPATH=/home/sklee/moai/lotto pytest`를 전체 실행하면
- **Then** 기존 939개 테스트가 모두 통과하고, 신규 테스트가 12개 이상 추가되어 전체가 통과하며, 신규 코드(`dashboard_overview`, `/stats/overview`, `/stats`)의 라인 커버리지가 85% 이상이고, `requirements`/`pyproject.toml`에 새로운 외부 의존성이 추가되지 않았다.

---

## 엣지 케이스 체크리스트

- [ ] 단일 회차만 존재 (min == max 1등 당첨금 → highest == lowest)
- [ ] 동일 `prize1Amount`를 가진 복수 회차 (최고/최저 타이브레이크: 결정적 선택 — 더 낮은 `drwNo` 우선)
- [ ] 한 해에 회차가 1개뿐인 연도의 평균 = 그 회차 금액
- [ ] 일부 회차만 `prize1Amount` 보유 (혼합) → 합계/평균은 보유 회차만 반영, `total_draws`는 전체
- [ ] 모든 번호가 균등 분포일 때 `number_frequency` 합 == `total_draws * 6`
- [ ] `prize1Amount`가 매우 큰 값(40조+)일 때 정수 오버플로 없음 (Python int 무한 정밀도)

## Definition of Done

- [ ] AC-1 ~ AC-13 전 시나리오 통과
- [ ] 엣지 케이스 체크리스트 전 항목 검증
- [ ] `dashboard_overview`, `/stats/overview`, `/stats` 신규 코드에 `# @MX:SPEC: SPEC-LOTTO-038` 태그 부착
- [ ] `base.html` 네비게이션에 `통계 대시보드` 항목 추가 확인
- [ ] ruff / mypy 통과 (기존 Python 3.9 호환 noqa 관례 유지)
- [ ] 신규 외부 의존성 0개
- [ ] EXC-001 ~ EXC-008 범위 외 기능 미포함 확인
