# SPEC-LOTTO-085 구현 계획

## 목표
회차별 본번호 6개의 일의 자리 중복 그룹 수(0~3) 분포를 분석하는 기능을 TDD로 구현한다.

## 변경 파일
1. `lotto/web/data.py`
   - 상수: `_LAST_DIGIT_PAIR_KEYS = ["0", "1", "2", "3"]`
   - 캐시: `_last_digit_pair_cache: dict[str, Any] = {}`
   - 헬퍼: `_count_last_digit_pairs(numbers)` (일의 자리 그룹화, 2개 이상 그룹 수, min(..,3) 상한)
   - 집계: `get_last_digit_pair_stats(draws)` (캐시 적용, 빈 입력 zero 구조)
   - `invalidate_cache()`에 `_last_digit_pair_cache.clear()` 추가
   - SPEC-084(get_parity_transition_stats) 다음에 삽입
2. `lotto/web/routes/api.py`
   - GET /stats/last_digit_pair 엔드포인트
3. `lotto/web/routes/pages.py`
   - GET /stats/last-digit-pair 페이지 라우트
4. `lotto/web/templates/last_digit_pair.html`
   - odd_run.html / parity_transition.html 패턴 따른 4키 분포 페이지
5. `lotto/web/templates/base.html`
   - "끝자리쌍" 내비게이션 링크 2곳(desktop_nav_items, nav_items)
6. `tests/test_last_digit_pair_analysis.py`
   - ~27개 테스트 (RED-GREEN-REFACTOR)

## TDD 순서
1. RED: 테스트 작성 후 실패 확인
2. GREEN: data.py 구현 → API/페이지 라우트 → 템플릿 → 내비게이션
3. REFACTOR: 중복 제거, @MX 태그 정리

## 기존 기능 충돌 검증
- `get_last_digit_pair_stats`, `_count_last_digit_pairs`, `_last_digit_pair_cache` 미존재 확인 완료.
- `/api/stats/last_digit_pair`, `/stats/last-digit-pair` 라우트 미존재 확인 완료.
- 기존 함수는 수정하지 않는다(REQ-LP-030).

## 기술 제약
- Python 3.9 호환: walrus(:=), zip(strict=True), match-case 금지.
- draw.numbers()는 본번호 6개(보너스 제외) 반환.
