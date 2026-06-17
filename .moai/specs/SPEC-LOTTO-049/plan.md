---
id: SPEC-LOTTO-049
version: 0.1.0
status: Planned
created: 2026-06-02
updated: 2026-06-02
author: ircp
priority: medium
---

# SPEC-LOTTO-049 구현 계획

## 방법론

TDD (RED → GREEN → REFACTOR). 데이터 계층 → API 계층 → 페이지 계층 순으로
각 계층마다 실패 테스트 작성 후 최소 구현.

## 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `lotto/web/data.py` | `sum_range_analysis`, `evaluate_sum`, `_percentile_nearest_rank`, `_SUM_BUCKET_EDGES` 추가; `import math` |
| `lotto/web/routes/api.py` | `GET /api/stats/sum-range`, `GET /api/stats/sum-range/evaluate` (n 6개 검증); `_SUM_EVAL_REQUIRED_COUNT` |
| `lotto/web/routes/pages.py` | `GET /stats/sum-range` 페이지 라우트 |
| `lotto/web/templates/sum_range.html` | 신규 템플릿 (요약/차트/테이블/체커 폼) |
| `lotto/web/templates/base.html` | 네비게이션 3곳에 "합계 분석" 추가 |
| `tests/test_sum_range.py` | 데이터 계층 단위 테스트 (12개) |
| `tests/test_api_sum_range.py` | API 통합 테스트 (6개) |
| `tests/test_sum_range_page.py` | 페이지/네비 테스트 (4개) |
| `mypy.ini` | 테스트 override 목록에 신규 모듈 3개 추가 |

## 설계 결정

- **버킷**: 폭 20 고정, 마지막 241-255만 폭 15. 12개 버킷이 21..255 전 구간을 빈틈없이 커버.
- **백분위**: nearest-rank 방식 채택(단순·결정적). p10/p90을 정수 경계로 사용.
- **데이터 계층 관대성**: `evaluate_sum`은 입력 검증 없이 합산만 수행. 검증은 API가 담당.
- **_UNSET 센티넬**: cycle_analysis와 동일 패턴(인자 생략 시 get_draws 자동 로드, 명시적 None은 데이터 없음).
- **테스트 호환 동적 호출**: API/페이지에서 `from lotto.web import data as wd` 동적 임포트로 patch 호환.

## 품질 게이트

- mypy . = Success (테스트 모듈 mypy.ini 등록)
- ruff clean, 신규 외부 의존성 없음
- Python 3.9 런타임 위치 타입: List[int]=Query(...) 사용
- 전체 스위트 1143 → 1165 통과
