# SPEC-LOTTO-090 구현 계획

## 충돌 확인 결과
- `get_last_digit_sum_stats` (SPEC-063): 개별 번호 끝자리 합 → low/mid/high 3구간, 관측값만. 별개 지표.
- `get_digit_sum_dist_stats` (SPEC-079): 6개 고정 키 분포. 별개 지표.
- `get_sum_last_digit_stats`, `/stats/sum_last_digit`, `/stats/sum-last-digit`, "합산끝자리" nav:
  모두 미존재. 충돌 없음.

## 단계
1. SPEC 문서 3종 작성 (spec/plan/acceptance)
2. RED: tests/test_sum_last_digit_analysis.py 작성 (~27 tests)
3. GREEN: data.py에 상수/캐시/get_sum_last_digit_stats 추가 (get_low_high_stats 뒤),
   invalidate_cache에 _sum_last_digit_cache.clear() 추가
4. API: lotto/web/routes/api.py 엔드포인트
5. Page: lotto/web/routes/pages.py 라우트
6. Template: lotto/web/templates/sum_last_digit.html (median_range.html 10-key 패턴)
7. base.html nav에 "합산끝자리" 추가

## 기술 제약
- Python 3.9: walrus/zip(strict)/match-case 금지
- draw.numbers()는 본번호 6개(보너스 제외)
- 기존 함수 미수정

## 캐시 격리
- conftest.py autouse fixture가 wd.invalidate_cache() 호출 → 캐시 추가만으로 격리 보장.
