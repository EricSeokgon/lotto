# SPEC-LOTTO-115: 추천 번호 자동 알림

## 메타데이터

- **SPEC ID**: SPEC-LOTTO-115
- **제목**: 추천 번호 자동 알림
- **상태**: completed
- **생성일**: 2026-06-23
- **완료일**: 2026-06-23

## 개요

주간 수집 스케줄러가 당첨 결과를 수집한 후, 다음 회차 추천 번호를 자동으로 Webhook/이메일로 발송하는 기능을 구현한다.

## 기존 동작

`scheduler.py`의 `_scheduled_collect_job()`이 주간으로 실행되어 데이터를 수집한 후 `notifier.notify(draw_info)`를 호출하여 **당첨 결과**를 발송한다.

## 목표

수집 완료 후 **다음 회차 추천 번호**를 Webhook/이메일로 추가 발송한다.

## 요구사항 (EARS 형식)

### REQ-REC-001: 추천 개수 설정
WHEN 사용자가 `notify_recommend_count`를 0보다 크게 설정하면,
THE SYSTEM SHALL 수집 완료 후 해당 개수(최대 10)의 추천 번호를 생성한다.

### REQ-REC-002: 스케줄러 연동
WHEN 주간 수집 작업이 완료되면,
THE SYSTEM SHALL 당첨 결과 알림 직후 추천 번호 알림을 발송한다.

### REQ-REC-003: Webhook 발송
WHEN Webhook URL이 설정되어 있고 `notify_recommend_count > 0`이면,
THE SYSTEM SHALL 추천 번호 목록을 Webhook으로 발송하고 실패 시 False를 반환한다 (예외 전파 없음).

### REQ-REC-004: 이메일 발송
WHEN SMTP 설정이 완료되어 있고 `notify_recommend_count > 0`이면,
THE SYSTEM SHALL 추천 번호 목록을 HTML 형식으로 이메일 발송한다.

### REQ-REC-005: 테스트 엔드포인트
WHEN 사용자가 `POST /api/settings/test-recommend`를 호출하면,
THE SYSTEM SHALL 즉시 추천 번호 알림을 테스트 발송하고 결과를 반환한다.

### REQ-REC-006: UI 설정
WHEN 사용자가 설정 화면을 열면,
THE SYSTEM SHALL 추천 번호 알림 개수(0~10) 입력 필드와 테스트 버튼을 표시한다.

### REQ-REC-007: 비활성 기본값
WHEN `notify_recommend_count`가 0(기본값)이면,
THE SYSTEM SHALL 추천 번호 알림을 발송하지 않는다.

## 인수 기준

- [x] `notify_recommend_count = 0`(기본값)이면 `notify_recommendations()`는 `[]` 반환
- [x] `notify_recommend_count > 0`이고 Webhook URL이 설정되면 Webhook 발송 시도
- [x] Webhook 발송 실패 시 예외가 외부로 전파되지 않음
- [x] `POST /api/settings/test-recommend`: 데이터 없으면 503, Webhook 미설정이면 400
- [x] 설정 화면에 `notify_recommend_count` 입력 필드(0~10) 표시
- [x] 환경 변수 `LOTTO_NOTIFY_RECOMMEND_COUNT`로 설정 가능
- [x] `user_settings.json` 파일로 설정 가능
- [x] 15개 테스트 통과 (2921 → 2936)

## 구현 노트

### 변경 파일
- `lotto/config.py`: `Settings.notify_recommend_count: int = 0` 추가
- `lotto/web/notifier.py`: `_format_recommend_payload`, `send_webhook_recommend`, `send_email_recommend`, `notify_recommendations`, `is_webhook_configured` 함수 추가
- `lotto/web/routes/api.py`: `NotifySettingsUpdate` 모델에 필드 추가, `POST /api/settings/test-recommend` 엔드포인트 추가
- `lotto/web/scheduler.py`: `_notifier.notify_recommendations(refreshed)` 호출 추가
- `lotto/web/templates/settings.html`: 추천 번호 알림 개수 입력 UI 추가
- `tests/test_recommend_notify.py`: 15개 테스트 신규 작성

### 핵심 설계
- `notify_recommendations(draws)`: `notify_recommend_count == 0`이면 즉시 `[]` 반환 (비활성화)
- `LottoRecommender(draws).recommend(count=min(count,10))`: 최대 10개 추천
- 각 채널(Webhook/이메일) 실패는 독립적으로 처리 — 하나 실패해도 다른 채널 발송 계속
- `@MX:ANCHOR`: `notify_recommendations()` 함수 (scheduler에서 호출)
