# SPEC-LOTTO-170: 쌍둥이 소수 포함 분포 분석

## 메타데이터

| 항목 | 값 |
|------|-----|
| SPEC ID | SPEC-LOTTO-170 |
| 제목 | 쌍둥이 소수 포함 분포 분석 |
| 상태 | DONE |
| 우선순위 | Medium |
| 생성일 | 2026-06-30 |

## 개요

쌍둥이 소수 쌍(p, p+2)에 속하는 번호 11개 {3,5,7,11,13,17,19,29,31,41,43}의
당첨 번호 포함 빈도 분포를 분석한다. 이론 기댓값 = 11/45×6 ≈ 1.467.

## 구현 파일

- `lotto/web/data.py`: `get_twin_prime_analysis()` 함수
- `lotto/web/routes/pages.py`: `/stats/twin-prime` 라우트
- `lotto/web/templates/twin_prime.html`: Bootstrap 5 템플릿 (bg-info 테마)
- `lotto/web/templates/base.html`: 네비게이션 항목 추가
- `tests/test_twin_prime.py`: 10개 테스트
