# SPEC-LOTTO-075 구현 계획

## 목표

회차별 본번호 6개 중 5의 배수(5,10,...,45) 포함 개수(0~6) 분포를 분석하는 읽기
전용 통계 기능을 SPEC-073/074 확장 패턴으로 추가한다.

## 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `lotto/web/data.py` | `_mult5_cache`, `_MULT5_KEYS`, `get_mult5_stats()` 추가; `invalidate_cache()` 에 `_mult5_cache.clear()` 추가 |
| `lotto/web/routes/api.py` | `GET /stats/mult5` 엔드포인트 추가 |
| `lotto/web/routes/pages.py` | `GET /stats/mult5` 페이지 라우트 추가 |
| `lotto/web/templates/mult5.html` | 신규 템플릿 (다크 모드 Tailwind, 요약 카드 4개 + 분포 테이블 7행) |
| `lotto/web/templates/base.html` | "5배수" 네비 링크 추가(desktop/mobile), active_tab 타이틀 분기 추가 |
| `tests/test_mult5_analysis.py` | 신규 테스트 ~25개 |

## TDD 사이클

1. **RED**: `tests/test_mult5_analysis.py` 작성 후 실패 확인
2. **GREEN**: `data.py`에 `get_mult5_stats` 구현 + 라우트/템플릿/네비 추가 → 통과
3. **REFACTOR**: SPEC-074 패턴과 일관성 유지, ruff 통과

## 핵심 로직

```python
mult5_counts = [sum(1 for num in d.numbers() if num % 5 == 0) for d in draws]
```

- 분포: `dict.fromkeys(_MULT5_KEYS, 0)` 후 각 count 버킷 증가
- most_common: `max(_MULT5_KEYS, key=lambda k: dist_counts[k])` (동률 시 작은 키 우선)
- high: `sum(1 for c in mult5_counts if c >= 3)`
- 캐시 키: `str(len(draws) if draws else 0)`

## 제약

- Python 3.9 호환 (walrus/zip strict/match-case 금지)
- 코어 모듈 무수정, 읽기 전용
- 서버 렌더링 only (JS 없음)
