# SPEC-LOTTO-027 인수 조건

## Given / When / Then 시나리오

### AC-1: 설정 페이지 렌더링 (REQ-SET-001)

- **Given** 웹 서버가 실행 중일 때
- **When** 브라우저에서 `GET /settings`에 접속하면
- **Then** HTTP 200과 함께 알림·스케줄러 설정 현황을 보여주는 HTML 페이지가 렌더링된다.

### AC-2: 설정 상태 API - 활성 상태 (REQ-SET-002)

- **Given** `LOTTO_NOTIFY_WEBHOOK_URL`, 이메일, 스케줄러 cron이 환경 변수로 설정된 상태에서
- **When** `GET /api/settings`를 호출하면
- **Then** `webhook_enabled=true`, `email_enabled=true`, `scheduler_enabled=true`와 함께
  마스킹된 `webhook_url_masked`, `email_to_masked`, `collect_cron`, `notify_threshold`가 반환된다.

### AC-3: 민감 값 마스킹 (REQ-SET-003)

- **Given** Webhook URL이 `https://discord.com/api/webhooks/123456/abcdef`로 설정된 상태에서
- **When** `GET /api/settings`를 호출하면
- **Then** `webhook_url_masked`는 앞 10자(`https://di`) + `****` 형태이며,
  전체 URL과 SMTP 비밀번호는 응답 어디에도 평문으로 포함되지 않는다.

### AC-4: Webhook 테스트 발송 성공 (REQ-SET-004)

- **Given** Webhook URL이 설정되어 있고 발송이 정상 동작하는 상태에서
- **When** `POST /api/settings/test-webhook`을 호출하면
- **Then** 테스트 메시지가 발송되고 `{ "sent": true }`(또는 성공 표시)가 반환된다.

### AC-5: 이메일 테스트 발송 성공 (REQ-SET-005)

- **Given** 수신 이메일과 SMTP 설정이 되어 있는 상태에서
- **When** `POST /api/settings/test-email`을 호출하면
- **Then** 테스트 이메일이 발송되고 성공 결과가 반환된다.

### AC-6: 미설정 채널 테스트 거부 (REQ-SET-006)

- **Given** Webhook URL이 설정되지 않은 상태에서
- **When** `POST /api/settings/test-webhook`을 호출하면
- **Then** 발송을 시도하지 않고 `{ "sent": false, "reason": "not_configured" }`(또는 HTTP 400)이 반환된다.

## 엣지 케이스 (Edge Cases)

### EC-1: 모든 설정 미존재 - 빈 상태 (REQ-SET-007)

- **Given** 알림·스케줄러 관련 환경 변수가 하나도 설정되지 않은 상태에서
- **When** `GET /settings` 페이지에 접속하거나 `GET /api/settings`를 호출하면
- **Then** 오류 없이 모든 `*_enabled=false`, 마스킹 값은 빈 문자열, `notify_threshold=0`이 반환되고,
  페이지에는 "설정된 항목이 없습니다" 빈 상태가 표시된다.

### EC-2: 테스트 발송 중 네트워크/SMTP 오류 (REQ-SET-008)

- **Given** Webhook URL은 설정되어 있으나 외부 발송이 실패하는 상태에서
- **When** `POST /api/settings/test-webhook`을 호출하면
- **Then** 예외가 전파되지 않고 `{ "sent": false, "reason": "<오류 요약>" }`이 반환되며 페이지가 깨지지 않는다.

### EC-3: 짧은 값 마스킹

- **Given** Webhook URL이 10자 미만이거나 이메일 로컬파트가 매우 짧은 경우
- **When** `GET /api/settings`를 호출하면
- **Then** 원본 일부가 그대로 노출되지 않도록 더 강하게 마스킹된 값이 반환된다.

### EC-4: 일부만 설정된 혼합 상태

- **Given** Webhook은 설정되었으나 이메일은 미설정인 상태에서
- **When** `GET /api/settings`를 호출하면
- **Then** `webhook_enabled=true`, `email_enabled=false`가 각각 독립적으로 정확히 반영된다.

### EC-5: 설정값 변경 시도 차단

- **Given** API가 읽기 전용 설정만 제공하는 상태에서
- **When** 설정값을 변경하는 별도 엔드포인트를 호출하려 하면
- **Then** 해당 기능이 존재하지 않으며(Exclusions), 설정은 환경 변수로만 관리됨이 보장된다.

## Definition of Done

- [ ] `get_settings_status()` 및 마스킹 헬퍼 구현 + 단위 테스트 통과
- [ ] `/api/settings`, `/api/settings/test-webhook`, `/api/settings/test-email` 동작 및 통합 테스트 통과
- [ ] `GET /settings` 페이지 렌더링 및 빈 상태 처리 확인
- [ ] 민감 값 마스킹 검증 (전체 URL/이메일/비밀번호 미노출)
- [ ] 미설정 시 테스트 거부, 발송 실패 시 안전 처리 검증
- [ ] 테스트 커버리지 85% 이상 (발송 함수는 mock 처리)
- [ ] 기존 706개 테스트 회귀 없음

## 품질 게이트 (Quality Gate)

- ruff lint 통과, 타입/런타임 오류 0
- 신규 함수에 한국어 docstring 및 주석 (code_comments: ko)
- 발송 테스트는 외부 호출 mock 처리 (실제 발송 금지)
- TRUST 5: Tested(85%+), Readable, Unified, Secured(민감 정보 마스킹), Trackable
