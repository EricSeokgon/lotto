# SPEC-LOTTO-045 인수 기준

## AC-1: mypy 0건 (REQ-MYPY-001)

- **Given** lotto 저장소 루트
- **When** `cd /home/sklee/moai/lotto && /home/sklee/.local/bin/mypy .` 실행
- **Then** `Success: no issues found in 109 source files` 출력, 종료 코드 0

검증 결과: PASS — "Success: no issues found in 109 source files"

## AC-2: 전체 테스트 통과 (REQ-MYPY-002)

- **Given** 변경된 코드베이스
- **When** `PYTHONPATH=/home/sklee/moai/lotto /home/sklee/.local/bin/pytest --tb=short -q` 실행
- **Then** 기존 1087개 테스트 전부 통과, 신규 실패/스킵 없음

검증 결과: PASS — 1087 passed, 96.33% coverage (660.28s)

## AC-3: 품질 게이트 통과 (REQ-MYPY-003)

- **Given** MoAI PreToolUse 품질 게이트(전체 저장소 mypy)
- **When** 커밋 시도
- **Then** 사전 부채 483건이 0건이 되어 게이트가 차단 없이 통과
  (GIT_BIN 우회는 본 SPEC 커밋 자체에만 잔존; 본 변경 이후로는 불필요)

## AC-4: 테스트 모듈 본문 타입 검사 유지 (REQ-MYPY-004)

- **Given** `[mypy-conftest,test_*...]` override
- **When** mypy 실행
- **Then** `check_untyped_defs = True`로 테스트 본문은 계속 타입 검사됨
  (단순 무시가 아니라 미주석 시그니처 강제만 완화)

## AC-5: unused-ignore 0건 (REQ-MYPY-005)

- **Given** `warn_unused_ignores = True` 유지
- **When** mypy 실행
- **Then** 추가한 `# type: ignore`가 `unused-ignore`로 보고되지 않음
  (재노출로 불필요해진 기존 ignore 4건 제거 완료)

검증 결과: PASS — unused-ignore 0건

## AC-6: 프로덕션 strict 유지 (REQ-MYPY-006)

- **Given** `lotto/` 프로덕션 코드
- **When** mypy 실행
- **Then** 전역 `strict = True` 정책 유지, override는 테스트 모듈에만 적용

## AC-7: ruff 클린 (보조)

- **Given** 변경된 .py 파일
- **When** `ruff check <changed files>` 실행
- **Then** All checks passed!

검증 결과: PASS — All checks passed!
