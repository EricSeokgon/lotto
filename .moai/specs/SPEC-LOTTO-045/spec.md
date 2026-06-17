---
id: SPEC-LOTTO-045
version: 0.1.0
status: completed
created: 2026-06-02
updated: 2026-06-02
author: ircp
priority: high
---

# SPEC-LOTTO-045: mypy 사전 부채 483건 정리

## 개요

lotto 저장소에는 mypy `strict` 모드 기준 483건의 사전 타입 오류가 누적되어 있다.
이 부채로 인해 MoAI PreToolUse 품질 게이트(전체 저장소 mypy 실행)가 모든 커밋을
차단하며, 신규 코드가 깨끗하더라도 게이트 우회(GIT_BIN 변수 분리)가 필요했다.

본 SPEC은 **런타임 동작을 전혀 바꾸지 않고** mypy 오류를 0건으로 정리하여
품질 게이트가 정상 통과하도록 한다.

## 배경 (오류 분류 — 483건)

| 분류 | 코드 | 건수 | 위치 |
|------|------|------|------|
| 테스트 미주석 함수 | `no-untyped-def` | 396 | tests/*.py |
| 테스트 미주석 호출 | `no-untyped-call` | 41 | tests/*.py |
| 재노출 미선언 접근 | `attr-defined` | 24 | tests/*.py |
| 제네릭 타입 인자 누락 | `type-arg` | 8 | tests/*.py |
| dotenv shim / 생성자 | `misc` | 3 | config.py, tests |
| 스텁 없는 임포트 | `import-untyped` | 3 | pdf_report.py, scheduler.py |
| Optional union 접근 | `union-attr` | 2 | purchases.py, tests |
| Any 반환 | `no-any-return` | 2 | scheduler.py, tests |
| 인자 타입 | `arg-type` | 2 | tests |
| 미사용 ignore | `unused-ignore` | 1 | tests |
| 인덱싱 불가 | `index` | 1 | tests |

대부분(437건+)은 출하되지 않는 테스트 코드의 타입 미주석으로,
테스트 모듈에 대한 mypy 엄격도 완화가 표준 관행이다.

## EARS 요구사항

### Ubiquitous (상시)

- **REQ-MYPY-001**: The system SHALL pass `mypy .` with zero errors under the configured
  strictness, producing "Success: no issues found".
- **REQ-MYPY-002**: The change SHALL NOT alter any runtime behavior; all 1087 existing
  tests SHALL continue to pass.

### Event-driven (이벤트 기반)

- **REQ-MYPY-003**: When a developer runs the MoAI PreToolUse quality gate (full-repo mypy),
  the gate SHALL pass without requiring the `git commit` pattern workaround.

### State-driven (상태 기반)

- **REQ-MYPY-004**: While analyzing test modules (`tests.*`), mypy SHALL relax
  untyped-definition strictness so test code is not required to carry full annotations,
  while still type-checking the bodies (`check_untyped_defs = True`).

### Unwanted (금지)

- **REQ-MYPY-005**: The change SHALL NOT introduce any `# type: ignore` that mypy reports
  as `unused-ignore` (warn_unused_ignores remains enabled).
- **REQ-MYPY-006**: The change SHALL NOT weaken strictness for production code (`lotto/`).

### Optional (선택)

- **REQ-MYPY-007**: Where third-party libraries lack type stubs (fpdf, apscheduler),
  the system MAY suppress `import-untyped` via per-module `ignore_missing_imports`.

## 인수 기준

acceptance.md 참조.

## 범위 밖 (Out of Scope)

- 테스트 코드 전수 타입 주석 작성 (mypy.ini override로 대체)
- 프로덕션 코드 로직 변경
- 신규 테스트 추가
