# SPEC-LOTTO-084 구현 계획

## 대상 파일

| 파일 | 변경 |
|------|------|
| `lotto/web/data.py` | 상수 `_PARITY_TRANS_KEYS`, `_parity_trans_cache` 추가, 헬퍼 `_count_parity_transitions`, 집계 `get_parity_transition_stats`, `invalidate_cache`에 캐시 clear 추가 |
| `lotto/web/routes/api.py` | GET /stats/parity_transition 라우트 |
| `lotto/web/routes/pages.py` | GET /stats/parity-transition 페이지 라우트 |
| `lotto/web/templates/parity_transition.html` | 신규 템플릿 (다크모드 Tailwind) |
| `lotto/web/templates/base.html` | "홀짝전환" 내비 링크 추가 |
| `tests/test_parity_transition_analysis.py` | RED 테스트 (~27개) |

## TDD 절차

1. RED: 손계산 4회차 픽스처 기반 테스트 작성 → 실패 확인
2. GREEN: data.py에 SPEC-083 패턴을 따라 헬퍼·집계·캐시 구현
3. 라우트·템플릿·내비 추가
4. REFACTOR: 중복 제거, 문서화 정리, ruff·pytest 통과 확인

## 핵심 로직

```python
def _count_parity_transitions(numbers):
    sorted_nums = sorted(numbers)
    transitions = 0
    for i in range(len(sorted_nums) - 1):
        if (sorted_nums[i] % 2) != (sorted_nums[i + 1] % 2):
            transitions += 1
    return transitions
```

## 손계산 검증 (4회차 픽스처)

- D1 [1,2,3,4,5,6] → 5회 → "5"
- D2 [1,3,5,7,9,11] → 0회 → "0"
- D3 [1,3,5,7,9,10] → 1회 → "1"
- D4 [2,3,4,5,6,7] → 5회 → "5"

분포: "0"=1(25.0), "1"=1(25.0), "2"=0, "3"=0, "4"=0, "5"=2(50.0)
avg_transitions = (5+0+1+5)/4 = 2.75
most_common_transitions = 5
high_alternation_pct = 2/4*100 = 50.0

## 제약

- Python 3.9 호환: walrus/`zip(strict=)`/`match-case` 금지
- 기존 함수 미수정 (SPEC-060 get_odd_even_stats와 독립)
- 6개 고정 키 항상 존재
