---
id: SPEC-LOTTO-027
version: 0.1.0
status: completed
created: 2026-05-29
updated: 2026-05-29
author: ircp
priority: medium
issue_number: null
---

# SPEC-LOTTO-027: 웹 설정 관리 페이지

## HISTORY

- 2026-05-29 v0.1.0: 최초 작성

## 메타데이터

| 항목 | 값 |
|------|-----|
| 도메인 | 설정 / 운영 |
| 영향 범위 | API, 웹 페이지 (`/settings`) |
| 의존 SPEC | SPEC-LOTTO-023(스케줄러), SPEC-LOTTO-025(알림) |

## 배경 및 목적

SPEC-LOTTO-023(자동 수집 스케줄러)과 SPEC-LOTTO-025(조건부 알림)는
모두 환경 변수로 설정되며, 현재는 설정이 올바르게 적용되었는지
브라우저에서 확인할 방법이 없다. 운영자는 서버에 접속해 환경 변수를
직접 확인해야 하고, 알림 채널이 실제로 동작하는지 테스트하기도 번거롭다.

본 SPEC은 `/settings` 페이지를 추가하여 알림·스케줄러 설정의 활성화 여부를
한눈에 확인하고, Webhook/이메일을 즉석에서 테스트 발송할 수 있게 한다.
설정값 자체는 마스킹하여 노출하지 않으며, 값을 저장/변경하는 기능은 제공하지 않는다
(설정은 환경 변수로만 관리). 별도 인증은 두지 않는다.

## 요구사항 (EARS)

### REQ-SET-001: 설정 페이지 (Ubiquitous)

`GET /settings` 요청 시,
시스템은 SHALL 알림 및 스케줄러 설정 현황을 표시하는 HTML 페이지를 반환한다.

### REQ-SET-002: 설정 상태 API (Ubiquitous)

`GET /api/settings` 요청 시,
시스템은 SHALL 현재 설정 상태를 다음 구조로 반환한다 (실제 값은 마스킹).

- `webhook_enabled: bool` — Webhook URL 설정 여부
- `webhook_url_masked: str` — Webhook URL 앞 10자 + `****` (미설정 시 빈 문자열)
- `email_enabled: bool` — 수신 이메일 설정 여부
- `email_to_masked: str` — 수신 이메일 마스킹 (예: `ab****@domain`)
- `scheduler_enabled: bool` — 스케줄러 활성화 여부
- `collect_cron: str` — 수집 cron 표현식 (미설정 시 빈 문자열)
- `notify_threshold: int` — 알림 임계값 (원), 미설정 시 0

### REQ-SET-003: 민감 값 마스킹 (Unwanted Behavior)

시스템은 SHALL NOT Webhook URL 전체, 이메일 주소 전체,
SMTP 비밀번호 등 민감 정보를 평문으로 응답하지 않는다.
URL/이메일은 앞부분 일부만 노출하고 나머지는 `****`로 가린다.

### REQ-SET-004: Webhook 테스트 발송 (Event-Driven)

WHEN `POST /api/settings/test-webhook` 요청이 들어오고 Webhook URL이 설정되어 있으면,
시스템은 SHALL 테스트 메시지를 해당 Webhook으로 발송하고
전송 성공/실패 결과를 반환한다.

### REQ-SET-005: 이메일 테스트 발송 (Event-Driven)

WHEN `POST /api/settings/test-email` 요청이 들어오고 이메일 수신 설정이 되어 있으면,
시스템은 SHALL 테스트 이메일을 발송하고 전송 성공/실패 결과를 반환한다.

### REQ-SET-006: 미설정 시 테스트 거부 (Unwanted Behavior)

IF 테스트 요청 시 해당 채널(Webhook 또는 이메일) 설정이 없으면,
THEN 시스템은 SHALL 발송을 시도하지 않고, 설정이 없음을 알리는 명확한 응답
(예: HTTP 400 또는 `{ "sent": false, "reason": "not_configured" }`)을 반환한다.

### REQ-SET-007: 빈 상태 표시 (State-Driven)

WHILE 알림·스케줄러 설정이 모두 비어 있는 상태에서는,
시스템은 SHALL 오류 대신 "설정된 항목이 없습니다" 빈 상태를 표시한다.

### REQ-SET-008: 테스트 발송 실패 처리 (Unwanted Behavior)

IF 테스트 발송 중 네트워크/SMTP 오류가 발생하면,
THEN 시스템은 SHALL 예외를 전파하지 않고 실패 사유를 담은 응답을 반환하며,
페이지가 깨지지 않도록 한다.

## Exclusions (What NOT to Build)

- 설정값을 페이지에서 저장하거나 변경하는 기능은 제공하지 않는다 (환경 변수 전용).
- 로그인/인증/권한 제어는 포함하지 않는다.
- 민감 값(전체 URL, SMTP 비밀번호)을 노출하는 기능은 제공하지 않는다.
- 테스트 발송 이력을 영구 저장하는 기능은 포함하지 않는다 (즉석 발송 결과만 반환).
- 다중 Webhook/다중 수신자 관리 기능은 포함하지 않는다.

## 제약 조건 (Constraints)

- 언어/런타임: Python 3.11
- 저장소: DB 사용 안 함. 설정은 환경 변수, 기타 데이터는 기존 CSV/JSON 파일.
- 설정 읽기 전용: 페이지/ API는 설정을 변경하지 않는다.
- 기존 `lotto/web/notifier.py`의 Webhook/이메일 발송 로직을 재사용한다.
- 프론트엔드: Jinja2 템플릿 (기존 페이지 스타일 재사용).
