# SPEC-LOTTO-027 구현 계획

## 기술 접근 (Technical Approach)

환경 변수에서 알림(SPEC-LOTTO-025)·스케줄러(SPEC-LOTTO-023) 설정을 읽어
활성화 여부와 마스킹된 값을 조립하는 설정 조회 계층을 추가한다.
설정값은 읽기 전용으로만 노출하며, 마스킹 헬퍼로 민감 정보를 가린다.
테스트 발송은 기존 `notifier.py`의 Webhook/이메일 발송 함수를 재사용하되,
"설정 미존재"와 "발송 실패"를 구분하여 응답한다. 페이지는 `/api/settings`를
호출해 상태를 렌더링하고, 테스트 버튼은 POST 엔드포인트를 호출한다.

## 구현 단계 (Phases)

### Phase 1: 설정 조회 + 마스킹 (우선순위 High)

- `lotto/web/notifier.py` (또는 신규 `lotto/web/settings.py`)
  - `get_settings_status() -> dict`: 환경 변수 읽어 REQ-SET-002 구조 조립
  - `_mask_url(url) -> str`: 앞 10자 + `****`
  - `_mask_email(email) -> str`: 로컬파트 일부 + `****@domain`
  - 미설정 항목은 `enabled=False` + 빈 문자열로 처리

### Phase 2: API 엔드포인트 (우선순위 High)

- `lotto/web/routes/api.py`
  - `GET /api/settings`: `get_settings_status()` 반환
  - `POST /api/settings/test-webhook`: Webhook 미설정 시 거부(REQ-SET-006),
    설정 시 테스트 메시지 발송 후 성공/실패 반환(REQ-SET-004, REQ-SET-008)
  - `POST /api/settings/test-email`: 이메일 미설정 시 거부, 설정 시 테스트 발송

### Phase 3: 설정 페이지 (우선순위 Medium)

- `lotto/web/routes/pages.py`
  - `GET /settings`: 설정 페이지 렌더링
- `lotto/web/templates/settings.html` (신규)
  - 알림/스케줄러 설정 상태 카드 (활성 여부 + 마스킹 값)
  - Webhook/이메일 테스트 버튼 (설정 있을 때만 활성)
  - 빈 상태 메시지 (REQ-SET-007)
  - 테스트 결과 토스트/알림 표시
- 네비게이션에 `/settings` 링크 추가 (기존 레이아웃 템플릿 수정)

## 생성/수정 파일 (Files)

| 구분 | 경로 | 작업 |
|------|------|------|
| 수정 | `lotto/web/notifier.py` | 설정 상태 조회 + 마스킹 헬퍼, 테스트 발송 래퍼 |
| 수정 | `lotto/web/routes/api.py` | `/api/settings`, `/test-webhook`, `/test-email` 추가 |
| 수정 | `lotto/web/routes/pages.py` | `GET /settings` 라우트 추가 |
| 생성 | `lotto/web/templates/settings.html` | 설정 현황 페이지 |
| 수정 | `lotto/web/templates/*base/layout*` | 네비게이션 링크 추가 |
| 생성 | `tests/test_settings_page.py` | 마스킹/상태/테스트 발송 단위·통합 테스트 |

## 위험 요소 (Risks)

- 마스킹 길이가 짧은 값(10자 미만 URL, 짧은 이메일)에서 노출 위험 → 길이가 짧으면 더 강하게 마스킹.
- 테스트 발송이 실제 외부로 나가므로 테스트 코드에서는 발송 함수를 mock 처리.
- 인증이 없으므로 테스트 엔드포인트 남용 가능성 → 본 SPEC 범위 밖(운영 환경 네트워크 제어로 처리), 문서에 명시.

## 의존성 (Dependencies)

- 신규 외부 패키지 없음.
- 기존 `notifier.py`의 Webhook/SMTP 발송 로직 재사용 (SPEC-LOTTO-025).
