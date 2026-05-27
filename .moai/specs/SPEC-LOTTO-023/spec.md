---
id: SPEC-LOTTO-023
version: 0.1.0
status: approved
created: 2026-05-27
updated: 2026-05-27
author: ircp
priority: medium
issue_number: null
---

# SPEC-LOTTO-023: 주간 자동 수집 스케줄러

## HISTORY

- 2026-05-27 v0.1.0: 최초 작성

## 메타데이터

| 항목 | 값 |
|------|-----|
| 도메인 | 자동화 |
| 영향 범위 | CLI, API |
| 의존 SPEC | SPEC-LOTTO-001 |

## 배경 및 목적

로또 추첨은 매주 토요일에 진행된다.
현재는 사용자가 수동으로 `collect` 명령을 실행해야 새 데이터가 수집된다.
백그라운드 스케줄러를 내장하여 웹 서버 실행 시 자동으로 주간 수집이 이루어지면
데이터를 항상 최신 상태로 유지할 수 있다.

## 요구사항

### REQ-SCHED-001: APScheduler 기반 스케줄러

- `apscheduler` 라이브러리 추가 (`pyproject.toml` 의존성)
- FastAPI lifespan에서 스케줄러 시작/종료
- 매주 토요일 21:10 KST 자동 증분 수집 (`collect` + `update_prizes`)
- 수집 완료 후 `invalidate_cache()` 호출

### REQ-SCHED-002: 스케줄 설정 외부화

- 환경 변수 `LOTTO_SCHEDULE_ENABLED` (기본 `true`) — 스케줄러 활성화 여부
- 환경 변수 `LOTTO_SCHEDULE_CRON` (기본 `"0 21 * * 6"`) — cron 표현식
- 환경 변수 `LOTTO_SCHEDULE_TZ` (기본 `"Asia/Seoul"`) — 타임존

### REQ-SCHED-003: 스케줄 상태 API

- `GET /api/scheduler/status` — 다음 실행 예정 시각, 마지막 실행 결과, 활성화 여부 반환
- `POST /api/scheduler/trigger` — 즉시 수집 수동 트리거 (관리자용)

### REQ-SCHED-004: 웹 UI 표시

- 인덱스 페이지 "다음 자동 수집 예정" 텍스트 표시
- 스케줄 비활성화 시 숨김

## 인수 조건

- 웹 서버 종료 시 스케줄러 정상 종료 (graceful shutdown)
- `LOTTO_SCHEDULE_ENABLED=false` 시 스케줄러 미시작
- 동시 실행 방지 (이미 수집 중이면 스킵)
- 테스트: 스케줄러 초기화, 트리거 API 단위 테스트
