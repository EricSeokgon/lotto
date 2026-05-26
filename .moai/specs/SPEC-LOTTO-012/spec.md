# SPEC-LOTTO-012: /api/health 헬스체크 엔드포인트

## 목표

운영 모니터링 도구(Prometheus, UptimeRobot, k8s liveness probe 등)가
사용할 수 있는 GET /api/health 엔드포인트를 추가한다.

## 요구사항

### REQ-HLT-001: 엔드포인트 경로
- `GET /api/health`
- 인증 불필요 (공개 엔드포인트)
- Content-Type: application/json

### REQ-HLT-002: 응답 구조

```json
{
  "status": "ok",
  "uptime_seconds": 123.45,
  "data": {
    "csv_exists": true,
    "csv_rows": 1150,
    "stats_exists": true,
    "last_sync": "2024-01-15"
  },
  "version": "1.0.0"
}
```

필드 정의:
- `status`: "ok" (항상 200 응답 시) / "degraded" (데이터 파일 없을 때)
- `uptime_seconds`: 앱 시작 시각부터 현재까지 경과 초 (float)
- `data.csv_exists`: `data/draws.csv` 존재 여부 (bool)
- `data.csv_rows`: CSV 행 수 (int, 파일 없으면 0)
- `data.stats_exists`: `data/stats.json` 존재 여부 (bool)
- `data.last_sync`: last_sync.json의 날짜 문자열 (없으면 null)
- `version`: pyproject.toml의 project.version 값

### REQ-HLT-003: status 결정 로직
- csv_exists AND stats_exists → "ok"
- 그 외 → "degraded"
- HTTP 응답 코드는 항상 200 (모니터링 도구 호환성)

### REQ-HLT-004: uptime 계산
- 앱 lifespan startup 시점을 모듈 변수로 저장
- `datetime.datetime.now()` - startup_time

### REQ-HLT-005: version 조회
- importlib.metadata.version("lotto") 사용
- 실패 시 "unknown" 반환

## 구현 위치

- `lotto/web/routes/api.py`: `GET /api/health` 엔드포인트 추가
- `lotto/web/app.py`: lifespan에서 startup_time 기록 (api 모듈에 저장)
- Pydantic 응답 모델: `HealthDataResponse`, `HealthResponse`

## 테스트

- `tests/test_web_api.py` 또는 신규 파일에 추가
- status="ok" 케이스 (csv + stats 모두 존재)
- status="degraded" 케이스 (파일 없음)
- uptime_seconds > 0 검증
- version 필드 존재 검증

## 성공 기준

- [ ] `GET /api/health` 200 응답
- [ ] Pydantic 모델로 응답 스키마 검증
- [ ] 419 기존 테스트 회귀 없음
- [ ] ruff check 통과
- [ ] 새 테스트 ≥ 3개
