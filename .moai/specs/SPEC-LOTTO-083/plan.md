# SPEC-LOTTO-083 구현 계획

## 접근 방식

SPEC-LOTTO-081(짝수 연속)의 검증된 패턴을 그대로 재사용하되, 추출 대상을
홀수(`n % 2 == 1`)로 바꾸고 묶음 수 캡(min(groups, 3))을 적용한다.
TDD(RED-GREEN-REFACTOR)로 진행한다.

## 대상 파일

| 파일 | 변경 내용 |
|------|-----------|
| `tests/test_odd_run_analysis.py` | 신규 — 약 27개 테스트 (RED) |
| `lotto/web/data.py` | `_ODD_RUN_KEYS`, `_odd_run_cache`, `_count_odd_runs`, `get_odd_run_stats` 추가; `invalidate_cache()`에 `_odd_run_cache.clear()` 추가 |
| `lotto/web/routes/api.py` | GET `/stats/odd_run` 엔드포인트 추가 |
| `lotto/web/routes/pages.py` | GET `/stats/odd-run` 페이지 라우트 추가 |
| `lotto/web/templates/odd_run.html` | 신규 — 다크모드 Tailwind 4키 분포 페이지 |
| `lotto/web/templates/base.html` | "홀수연속" 내비 링크 추가 (desktop_nav_items, nav_items) |
| `CHANGELOG.md` | [1.44.0] 항목 추가 |

## 핵심 로직

```python
_ODD_RUN_KEYS = ["0", "1", "2", "3"]
_odd_run_cache: dict[str, Any] = {}


def _count_odd_runs(numbers: list[int]) -> int:
    odds = sorted(n for n in numbers if n % 2 == 1)
    if len(odds) < 2:
        return 0
    groups = 0
    run_len = 1
    for i in range(1, len(odds)):
        if odds[i] == odds[i - 1] + 2:
            run_len += 1
        else:
            if run_len >= 2:
                groups += 1
            run_len = 1
    if run_len >= 2:
        groups += 1
    return min(groups, 3)  # 3 이상은 3으로 캡
```

`get_odd_run_stats`는 SPEC-081 구조를 동일하게 따른다(캐시 키 = str(len(draws)),
동률 시 작은 키 선택, zero-fill 분포).

## 기술 제약

- Python 3.9: walrus(`:=`), `zip(strict=True)`, `match-case` 사용 금지.
- 기존 함수 미수정.
- conftest.py 의 autouse 픽스처가 invalidate_cache 를 호출하므로 캐시 격리는
  `_odd_run_cache.clear()` 추가만으로 보장된다.

## 검증

- `pytest tests/test_odd_run_analysis.py -q` 전부 통과.
- `ruff check` 통과.
- 전체 스위트는 test_web_pages 행으로 타임아웃하므로 모듈 단위로 검증한다.
