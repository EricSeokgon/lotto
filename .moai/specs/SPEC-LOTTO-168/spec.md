# SPEC-LOTTO-168: 연속번호 분포 분석

## 메타데이터

| 항목 | 값 |
|------|-----|
| SPEC ID | SPEC-LOTTO-168 |
| 제목 | 연속번호 분포 분석 |
| 상태 | DONE |
| 우선순위 | Medium |
| 생성일 | 2026-06-30 |

## 개요

각 로또 회차 당첨 번호 중 연속된 번호 쌍(예: 7,8 또는 13,14)이 몇 개 존재하는지 분포를 분석한다.

## 구현 파일

- `lotto/web/data.py`: `get_consecutive_analysis()` 함수
- `lotto/web/routes/pages.py`: `/stats/consecutive` 라우트
- `lotto/web/templates/consecutive.html`: Bootstrap 5 템플릿
- `lotto/web/templates/base.html`: 네비게이션 항목 추가
- `tests/test_consecutive.py`: 10개 테스트
