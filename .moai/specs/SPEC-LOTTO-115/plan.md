# SPEC-LOTTO-115 구현 계획

## 구현 전략

단일 패스 구현 — 5개 파일 수정 + 테스트 파일 신규 작성

## 구현 단계

1. `lotto/config.py` — `notify_recommend_count` 필드 추가
2. `lotto/web/notifier.py` — 추천 번호 알림 함수 4개 추가
3. `lotto/web/scheduler.py` — 스케줄러에 `notify_recommendations()` 호출 추가
4. `lotto/web/routes/api.py` — 설정 모델 업데이트 + 테스트 엔드포인트 추가
5. `lotto/web/templates/settings.html` — UI 추가
6. `tests/test_recommend_notify.py` — 15개 테스트 작성

## 완료 기준

- 모든 테스트 통과 (2921 → 2936)
- Python 3.9 호환성 유지
