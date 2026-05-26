# SPEC-LOTTO-011: 테스트 커버리지 향상

## 목표

현재 96.26% 커버리지를 97%+ 이상으로 향상.

## 미커버 경로 목록

### REQ-COV-001: recommender.py 폴백 경로 (현재 87%)

| 경로 | 트리거 조건 |
|------|-----------|
| 홀짝균형 100회 실패 → candidates 폴백 (line 200) | excluded에 모든 홀짝 조합 포함 |
| 번호대균형 100회 실패 → candidates 폴백 (line 214) | excluded에 모든 존 조합 포함 |
| 핫콜드혼합 100회 실패 → candidates 폴백 (line 225) | excluded에 모든 핫/콜드 조합 포함 |
| 후보 부족 경고 (line 230) | candidates 길이 < 6 |
| 모든 시도 실패 경고 + RuntimeError (lines 237-244) | excluded에 1~45 전체 조합 포함 |

테스트 방법: `random.sample`을 mock하여 항상 excluded 세트와 중복되는 값을 반환하도록 조작.

### REQ-COV-002: api.py 미커버 분기 (현재 95%)

| 경로 | 조건 |
|------|------|
| `_run_analyze_sync` draws 있을 때 분석 (lines 179-181) | `LottoCollector().load_existing()` → 비어있지 않은 목록 |
| CSV 빈파일 삭제 in collect worker (line 214) | `csv_path.stat().st_size < 10` |
| CSV 빈파일 삭제 in scrape worker (line 419) | 동일 조건 |
| `_on_progress` drw_no 비어있지 않을 때 (lines 467-471) | drw_no != 0 |

### REQ-COV-003: pages.py 분기 (현재 96%)

| 경로 | 조건 |
|------|------|
| analyze 페이지 stats not None + freq_dict 존재 (lines 112-129) | stats 객체 포함한 응답 |
| simulate 페이지 result not None (lines 195-225) | simulation 결과 포함 |

### REQ-COV-004: config.py dotenv 경로 (현재 94%)

| 경로 | 조건 |
|------|------|
| `_DOTENV_AVAILABLE = True` 분기 (line 21) | dotenv 설치 상태 mock |
| `_load_dotenv` no-op 구현 (line 27) | dotenv 미설치 mock |
| `_load_settings` 내 dotenv 호출 (line 103) | _DOTENV_AVAILABLE=True mock |

## 성공 기준

- [ ] 403 기존 테스트 전부 통과 (회귀 없음)
- [ ] 추가 테스트 후 총 커버리지 97%+
- [ ] `python3.9 -m ruff check lotto/` 통과
- [ ] 새 테스트 파일: tests/test_recommender_fallback.py, tests/test_web_coverage.py
