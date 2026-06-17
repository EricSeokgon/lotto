# SPEC-LOTTO-045 구현 계획

## 전략 개요

대부분(437건+)이 출하되지 않는 테스트 코드의 타입 미주석이므로,
테스트 파일 400여 개를 수정하는 대신 **mypy.ini 모듈별 override**로
테스트 엄격도를 완화한다(표준 관행). 프로덕션 코드(`lotto/`)는 strict 유지.

## 작업 단위

### 1. mypy.ini override (대량 해소: ~450건)

- `[mypy-conftest,test_*...]` 섹션 추가 (tests에 `__init__.py`가 없어 모듈명이
  bare stem이므로 전체 모듈명을 명시 나열):
  - `disallow_untyped_defs/incomplete_defs/untyped_calls = False`
  - `disallow_any_generics = False` (bare list/set/dict 허용)
  - `no_implicit_reexport = False` (소스 심볼 패치 접근 허용)
  - `check_untyped_defs = True` (본문 타입 검사 유지)
  - `warn_return_any = False`
- `[mypy-apscheduler]`, `[mypy-apscheduler.*]` `ignore_missing_imports = True`

### 2. 프로덕션 코드 개별 수정 (~10건)

| 파일 | 오류 | 수정 |
|------|------|------|
| config.py:25 | misc (dotenv shim) | `# type: ignore[misc]` (시그니처 불일치 폴백) |
| pdf_report.py:14 | import-untyped (fpdf) | `# type: ignore[import-untyped]` (스텁 레지스트리 등록 라이브러리는 ignore_missing_imports 미적용) |
| web/routes/purchases.py:30 | union-attr | `{...} if draws else {}` (pages.py와 동일 idiom, None→빈 매핑) |
| web/scheduler.py:188 | no-any-return | `next_run: str = ...` 명시 |

### 3. 소스 모듈 명시적 재노출 (PEP 484 redundant-alias, ~18건 attr-defined)

`no_implicit_reexport`는 **임포트되는 소스 모듈**의 정책이므로 테스트 override로
해소 불가. 소스 모듈에서 명시적 재노출:

- recommender: `Recommendation as Recommendation`
- analyzer: `FrequencyStats as FrequencyStats`, `Statistics as Statistics`
- simulator: `SimulationResult as SimulationResult`
- web/notifier, web/scheduler: `settings as settings`
- web/data: `import time as time`

`__all__` 미사용(별칭 형태가 더 국소적). 별칭 재노출은 `import *`에만 영향이며
런타임 속성 접근/동작에는 영향 없음.

### 4. 테스트 코드 국소 수정 (config override로 해소 불가한 실제 타입 오류, ~13건)

- test_scraper_edge.py: `caplog: logging.LogRecord` → `pytest.LogCaptureFixture` (잘못된 주석 수정)
- test_favorites.py, test_check.py: 제너레이터 픽스처 `-> TestClient` → `-> Iterator[TestClient]`
- test_collector.py: `responses: list[dict[str, Any]]` 명시
- test_data_cache.py: `assert cached is not None` 내로잉
- test_scheduler.py: `assert sched_mod._scheduler is not None` 내로잉
- test_settings.py, test_recommender.py: 재노출로 불필요해진 `# type: ignore` 제거

## 검증

1. `mypy .` → Success: no issues found
2. `pytest` → 1087 passed
3. `ruff check` → All checks passed

## 동작 보존 근거

- mypy.ini/`# type: ignore`/재노출 별칭: 런타임 무관
- purchases.py: pages.py:listings의 검증된 `if draws else {}` idiom 차용
  (None일 때 빈 매핑 → 등수 정보 없는 구매 이력 반환, 기존 crash 의도 아님)
- 테스트 주석/내로잉: assert는 기존에 항상 참인 조건(테스트가 통과하던 상태)
