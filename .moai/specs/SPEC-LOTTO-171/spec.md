# SPEC-LOTTO-171: 반소수 포함 분포 분석

## 메타데이터

| 항목 | 값 |
|------|-----|
| SPEC ID | SPEC-LOTTO-171 |
| 제목 | 반소수(Semiprime) 포함 분포 분석 |
| 상태 | DONE |
| 우선순위 | Medium |
| 생성일 | 2026-06-30 |

## 개요

소인수가 정확히 2개(중복 허용)인 반소수 15개 {4,6,9,10,14,15,21,22,25,26,33,34,35,38,39}의
당첨 번호 포함 빈도 분포를 분석한다. 이론 기댓값 = 15/45×6 = 2.0.

## 구현 파일

- `lotto/web/data.py`: `get_semiprime_analysis()` 함수
- `lotto/web/routes/pages.py`: `/stats/semiprime` 라우트
- `lotto/web/templates/semiprime.html`: Bootstrap 5 템플릿 (bg-secondary 테마)
- `lotto/web/templates/base.html`: 네비게이션 항목 추가
- `tests/test_semiprime.py`: 10개 테스트
