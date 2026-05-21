# SPEC-LOTTO-009 인수 기준 (Acceptance Criteria)

## REQ-CACHE-001: get_draws TTL 캐시

- [ ] **AC-CACHE-001-1**: `get_draws()`를 1초 간격으로 두 번 호출하면, 내부 디스크 로드(`LottoCollector.load_existing`)는 정확히 1회만 실행된다.
- [ ] **AC-CACHE-001-2**: 첫 호출 후 시간을 61초 진행시킨 뒤 다시 호출하면, 디스크 로드가 다시 실행된다(총 2회).
- [ ] **AC-CACHE-001-3**: TTL 만료 후 재로드 결과는 첫 호출 결과와 동일한 객체 형태(타입·항목 수)를 갖는다.

## REQ-CACHE-002: get_stats TTL 캐시

- [ ] **AC-CACHE-002-1**: `get_stats()`를 1초 간격으로 두 번 호출하면, `LottoAnalyzer.load_stats`는 정확히 1회만 실행된다.
- [ ] **AC-CACHE-002-2**: 캐시 만료 후 재호출 시 디스크 로드가 다시 실행된다.

## REQ-CACHE-003: 캐시 무효화

- [ ] **AC-CACHE-003-1**: `get_draws()` 호출 → `invalidate_cache()` → `get_draws()` 호출 시퀀스에서 디스크 로드는 2회 실행된다.
- [ ] **AC-CACHE-003-2**: `invalidate_cache()`는 `get_draws`와 `get_stats` 양쪽 캐시를 모두 비운다.
- [ ] **AC-CACHE-003-3**: 백그라운드 워커(`_collect_worker`, `_scrape_worker`, `_run_analyze_sync`)는 작업 완료 후 `invalidate_cache()`를 호출한다.

## REQ-CACHE-004: 캐시 적중 동등성

- [ ] **AC-CACHE-004-1**: 캐시 적중 호출의 반환값은 캐시 미스 호출의 반환값과 동일한 회차 수, 동일한 첫 번째 회차 번호를 가진다.

## REQ-LAST-001: 인덱스 페이지 last_date 컨텍스트

- [ ] **AC-LAST-001-1**: `GET /` 요청 시 응답 HTML에 `last_sync.json`의 `synced_at` 앞 10자(YYYY-MM-DD)가 포함된다.
- [ ] **AC-LAST-001-2**: 헤더 영역에 "최근 수집: <date>" 형식의 텍스트가 렌더링된다.

## REQ-LAST-002: last_date 소스 폴백

- [ ] **AC-LAST-002-1**: `last_sync.json`이 없고 `draws.csv`만 있을 때, `get_last_sync_date()`는 가장 최신 회차의 date 문자열을 반환한다.
- [ ] **AC-LAST-002-2**: 두 소스 모두 없을 때, `get_last_sync_date()`는 `None`을 반환하며 인덱스 라우트는 200 응답을 반환한다(크래시 없음).
- [ ] **AC-LAST-002-3**: `last_sync.json`에 `synced_at`이 존재하면 `draws.csv`의 값보다 우선한다.

## NFR-001/002/003/004: 회귀 없음

- [ ] **AC-REG-001**: `pytest tests/ -q` 결과 기존 379개 테스트가 모두 통과한다.
- [ ] **AC-REG-002**: 신규 테스트 추가 후 전체 테스트 수가 379개를 초과한다.
- [ ] **AC-REG-003**: 전체 커버리지가 95% 이상을 유지한다.
- [ ] **AC-REG-004**: `import time` 외에는 새 의존성을 추가하지 않는다.
