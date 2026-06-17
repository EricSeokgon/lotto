---
id: SPEC-LOTTO-025
version: 0.1.0
status: completed
created: 2026-05-27
updated: 2026-05-27
author: ircp
priority: low
issue_number: null
---

# SPEC-LOTTO-025: 조건부 알림 (Webhook / 이메일)

## HISTORY

- 2026-05-27 v0.1.0: 최초 작성

## 메타데이터

| 항목 | 값 |
|------|-----|
| 도메인 | 알림 |
| 영향 범위 | API, 설정 |
| 의존 SPEC | SPEC-LOTTO-023 |

## 배경 및 목적

자동 수집(SPEC-LOTTO-023) 이후 특정 조건(예: 1등 당첨금이 일정 금액 이상)이
충족되면 사용자에게 알림을 전송하는 기능이 필요하다.
Webhook(Discord/Slack)과 이메일(SMTP) 두 가지 채널을 지원하여
특별한 회차를 놓치지 않도록 한다.

## 요구사항

### REQ-NOTIF-001: 알림 조건 설정

환경 변수로 조건 설정:
- `LOTTO_NOTIFY_PRIZE_THRESHOLD` (기본 `0`, 비활성) — 1등 당첨금이 이 값(원) 이상일 때 알림
- `LOTTO_NOTIFY_WEBHOOK_URL` — Discord/Slack Incoming Webhook URL
- `LOTTO_NOTIFY_EMAIL_TO` — 수신 이메일 주소 (SMTP 방식)
- `LOTTO_NOTIFY_EMAIL_FROM`, `LOTTO_NOTIFY_SMTP_HOST`, `LOTTO_NOTIFY_SMTP_PORT`, `LOTTO_NOTIFY_SMTP_USER`, `LOTTO_NOTIFY_SMTP_PASS`

### REQ-NOTIF-002: Webhook 알림

- Discord/Slack Webhook URL로 HTTP POST (JSON embed)
- 알림 내용: 회차, 당첨 번호, 1등 당첨금, 당첨자 수

### REQ-NOTIF-003: 이메일 알림

- SMTP를 통해 HTML 이메일 발송
- 알림 내용: REQ-NOTIF-002와 동일

### REQ-NOTIF-004: 알림 이력 API

- `GET /api/notifications` — 최근 전송된 알림 목록 반환 (최대 50건)
- `data/notifications.json` 파일 저장

### REQ-NOTIF-005: 알림 설정 UI

- 설정 페이지(`/settings`) 또는 인덱스 하단에 알림 설정 상태 표시
- Webhook URL / 이메일 설정 여부 및 임계값 표시 (값 숨김 처리)

## 인수 조건

- 알림 조건 미설정(threshold=0, URL 없음) 시 알림 미발송
- Webhook / 이메일 각각 독립적으로 활성화 가능
- 알림 실패 시 로그 기록 후 무시 (수집 프로세스 중단 안 됨)
- 테스트: Webhook 전송 mock 테스트, 조건 판단 로직 단위 테스트
