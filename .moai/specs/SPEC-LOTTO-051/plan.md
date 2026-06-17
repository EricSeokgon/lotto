---
id: SPEC-LOTTO-051
version: 0.1.0
status: draft
created: 2026-06-05
updated: 2026-06-05
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-051 구현 계획

## 방법론

TDD (RED → GREEN → REFACTOR), 브라운필드 보강. 기존 동작을 보존하며 표시용
오버레이만 추가한다. 데이터 계층(`get_cross_strategy_consensus`) → API 계층 →
페이지/템플릿 계층 순으로 각 계층마다 실패 테스트 작성 후 최소 구현.

채택안: research.md의 **Option A (서버사이드 요청별 전체 전략 스캔)**.
검증된 `strategy_compare()` 패턴을 재사용하며 JavaScript/캐시 무효화가 불필요하다.

## 변경 파일

| 파일 | 변경 내용 | 델타 |
|------|-----------|------|
| `lotto/recommender.py` | `recommend_by_strategy()` 호출만, 수정 없음 | [EXISTING] |
| `lotto/web/data.py` | `get_cross_strategy_consensus(recommender, target_numbers)` 신규 함수 추가 | [NEW] |
| `lotto/web/routes/pages.py` | `recommend` 라우트에서 합의도 계산 후 템플릿 컨텍스트에 전달 | [MODIFY] |
| `lotto/web/routes/api.py` | `/api/recommendations` 응답에 추천별 `consensus` 필드 추가 | [MODIFY] |
| `lotto/web/templates/recommend.html` | 번호별 합의도 배지(주의 하이라이트 포함) 렌더링 추가 | [MODIFY] |
| `tests/test_web_data.py` | `get_cross_strategy_consensus` 단위 테스트 | [NEW/MODIFY] |
| `tests/test_api_recommendations.py` (또는 기존 API 테스트 모듈) | API 응답 `consensus` 필드 통합 테스트 | [NEW/MODIFY] |
| `tests/test_web_pages.py` (또는 기존 페이지 테스트 모듈) | 추천 페이지 합의도 배지/임계값 통합 테스트 | [NEW/MODIFY] |
| `mypy.ini` | 신규 테스트 모듈을 override 목록에 추가(필요 시) | [MODIFY] |

## 함수 시그니처 (제안)

```python
def get_cross_strategy_consensus(
    recommender: "LottoRecommender",
    target_numbers: list[int],
) -> dict[int, int]:
    """타깃 번호들이 11개 전략 중 몇 개에 포함되는지 집계한다.

    11개 전략(STRATEGY_LABELS)에 대해 recommend_by_strategy(label)를 한 번씩
    호출하여 등장 번호를 모으고, target_numbers 각 번호의 합의도를 반환한다.

    Returns:
        {번호: 합의도(0~11)} — target_numbers에 포함된 모든 번호에 대한 매핑.
    """
```

호출 측(pages.py / api.py)은 동일 `recommender` 인스턴스(동일 `Statistics`
스냅샷)를 모든 11회 호출에 공유하여 데이터 일관성을 보장한다.

## 설계 결정

- **계층 경계**: `get_cross_strategy_consensus`는 `recommender` 객체만 받는다.
  raw draws나 `get_draws`에 접근하지 않는다(REQ-CONS-009).
- **단일 스캔 재사용(REQ-CONS-011)**: 페이지 요청당 11개 전략을 한 번만
  스캔하여 등장 번호 카운트를 만들고, 표시되는 모든 추천 번호에 재사용한다.
  (추천 카드마다 11회 재스캔하지 않음.)
- **주의 임계값**: 합의도 >= 4를 주의 표시 기준으로 고정(REQ-CONS-006).
  임계값은 템플릿/상수로 단일 정의하여 표시와 판정이 일치하도록 한다.
- **결정성 주의**: `recommend_by_strategy()`는 내부적으로 random 표본을 사용하므로
  호출마다 결과가 달라질 수 있다. 합의도는 "이번 분석 세션 기준"의 값임을 UI
  문구로 명확히 한다(research.md 7절 참조). 재현성 보장은 범위 밖.
- **빈 데이터 처리**: 추천이 None(통계 부재)이면 합의도 계산을 건너뛰고 페이지는
  HTTP 200으로 렌더(REQ-CONS-007).
- **테스트 호환 동적 호출**: 기존 라우트 패턴과 동일하게 `from lotto.web import
  data as wd` 동적 임포트로 patch 호환성을 유지한다.

## Python 3.9 호환성

- `zip(strict=True)` 사용 금지 (Python 3.10+). 필요 시 단순 루프 또는
  `# noqa: B905`로 처리.
- 워러스(`:=`) 연산자는 가독성 저해 시 사용하지 않음.
- 런타임 위치 타입은 기존 모듈 컨벤션을 따른다(예: `List[int]` Query 등).

## MX 태그 계획

- `get_cross_strategy_consensus`: pages.py와 api.py 두 곳에서 호출되어
  fan_in >= 2 → `@MX:ANCHOR` 부여(공개 분석 경계 함수).
- 11개 전략 순회 루프: 외부 의존(전략 호출) 비용이 있으므로 필요 시
  `@MX:NOTE`로 "요청당 1회 스캔, 카드별 재호출 금지" 의도를 명시.

## 품질 게이트

- `~/.local/bin/pytest` 전체 스위트 통과 (기준 1174 → 신규 테스트 추가분 포함).
- 신규 함수 커버리지 목표 90%+.
- mypy 통과(신규 테스트 모듈 mypy.ini 등록), ruff clean, 신규 외부 의존성 없음.
- 페이지 로드 시 합의도 계산으로 인한 타임아웃 없음(요청당 11회 전략 호출 허용 범위).
- 함수/변수명은 영어, docstring/주석은 한국어.
