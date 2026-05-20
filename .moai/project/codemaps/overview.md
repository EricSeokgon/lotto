# 아키텍처 개요

## 설계 패턴

**계층형 CLI (Layered CLI)**

```
main.py (CLI 레이어 — Typer)
├── collect  → lotto/collector.py
├── analyze  → lotto/analyzer.py
├── recommend → lotto/recommender.py
└── simulate  → lotto/simulator.py
                  └── (all modules) → lotto/models.py
```

## 시스템 경계

- **입력**: 동행복권 API (외부), CLI 인수 (사용자)
- **출력**: 터미치 stdout (Rich), data/*.csv, data/*.json
- **저장소**: 파일 기반 (데이터베이스 없음)

## 핵심 설계 원칙

1. **인과관계 안전성** — `HistoricalView`가 백테스트 시 미래 데이터 누수 방지
2. **재시도 탄력성** — `_fetch_with_retry()` 지수 백오프 (1s→2s→4s)
3. **타입 안전성** — Pydantic v2 전체 적용, mypy --strict 통과
4. **분리 관심사** — 수집/분석/추천/시뮬레이션 각각 독립 모듈
