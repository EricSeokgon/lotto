"""SPEC-LOTTO-002: 설정 외부화 모듈.

환경 변수, 선택적 .env 파일, 기본값 순으로 설정을 결정합니다.

# @MX:ANCHOR: [AUTO] 전역 설정 진입점 — 모든 lotto 모듈의 설정 참조 단일 소스
# @MX:REASON: collector/recommender/scraper/main/web 등 다수 모듈에서 참조 (fan_in >= 3)

@MX:SPEC: SPEC-LOTTO-002 REQ-CFG-001~005
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# REQ-CFG-003: python-dotenv은 선택적 의존성. 미설치 환경에서도 정상 동작해야 함.
try:
    from dotenv import load_dotenv as _load_dotenv

    _DOTENV_AVAILABLE = True  # pragma: no cover
except ImportError:  # pragma: no cover
    _DOTENV_AVAILABLE = False

    def _load_dotenv(*_args: object, **_kwargs: object) -> bool:
        """python-dotenv 미설치 시 no-op."""
        return False


# === 기본값 정의 (REQ-CFG-004) ===
_DEFAULT_API_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={drw_no}"
_DEFAULT_DATA_DIR = "data"
_DEFAULT_WEB_HOST = "127.0.0.1"
_DEFAULT_WEB_PORT = "8000"
_DEFAULT_RECOMMENDER_WEIGHTS = "0.4,0.3,0.2,0.1"
_DEFAULT_CHECKPOINT_INTERVAL = "20"
_DEFAULT_SCRAPER_URL_1 = "https://signalfire85.tistory.com/798"
_DEFAULT_SCRAPER_URL_2 = "https://signalfire85.tistory.com/28"
# SPEC-LOTTO-003 REQ-BONUS-004: 보너스 회피 가중치 기본값 (0.0 = 비활성 → 기존 동작 보존)
_DEFAULT_BONUS_AVOIDANCE_WEIGHT = "0.0"
# SPEC-LOTTO-023 REQ-SCHED-002: 스케줄러 설정 기본값
# - 활성화 여부, 크론 표현식, 타임존
# - 기본: 매주 토요일 21:10 KST (당첨 결과 발표 직후)
_DEFAULT_SCHEDULE_ENABLED = "true"
_DEFAULT_SCHEDULE_CRON = "10 21 * * 6"
_DEFAULT_SCHEDULE_TZ = "Asia/Seoul"
# SPEC-LOTTO-025 REQ-NOTIF-001: 알림 설정 기본값
# - 임계값 0 = 비활성, webhook/email 미설정 = 비활성
# - SMTP 포트 기본 587 (TLS)
_DEFAULT_NOTIFY_PRIZE_THRESHOLD = "0"
_DEFAULT_NOTIFY_SMTP_PORT = "587"


def _parse_weights(raw: str) -> tuple[float, float, float, float]:
    """REQ-CFG-005: 콤마 구분 가중치를 4-튜플로 파싱. 실패 시 명확한 ValueError."""
    try:
        parts = [float(x.strip()) for x in raw.split(",")]
    except ValueError as exc:
        raise ValueError(
            "LOTTO_RECOMMENDER_WEIGHTS는 콤마로 구분된 4개의 float이어야 합니다. "
            f"받은 값: {raw!r}"
        ) from exc
    if len(parts) != 4:
        raise ValueError(
            "LOTTO_RECOMMENDER_WEIGHTS는 정확히 4개의 값(w_freq,w_recent,w_pair,w_consec)이 "
            f"필요합니다. 받은 값: {raw!r}"
        )
    return (parts[0], parts[1], parts[2], parts[3])


def _parse_int(raw: str, env_name: str) -> int:
    """REQ-CFG-005: 정수 파싱. 실패 시 어떤 환경 변수인지 명시."""
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(
            f"{env_name}은 정수여야 합니다. 받은 값: {raw!r}"
        ) from exc


def _parse_float(raw: str, env_name: str) -> float:
    """SPEC-LOTTO-003: float 파싱. 실패 시 어떤 환경 변수인지 명시."""
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(
            f"{env_name}은 float이어야 합니다. 받은 값: {raw!r}"
        ) from exc


@dataclass(frozen=True)
class Settings:
    """애플리케이션 전역 설정.

    모든 값은 환경 변수 -> .env -> 기본값 순으로 결정됩니다.
    """

    api_url: str
    data_dir: Path
    web_host: str
    web_port: int
    recommender_weights: tuple[float, float, float, float]
    checkpoint_interval: int
    scraper_urls: list[str] = field(default_factory=list)
    # SPEC-LOTTO-003 REQ-BONUS-004: 보너스 회피 가중치 (기본 0.0 = 비활성)
    bonus_avoidance_weight: float = 0.0
    # SPEC-LOTTO-023 REQ-SCHED-002: 주간 자동 수집 스케줄러 설정
    schedule_enabled: bool = True
    schedule_cron: str = "10 21 * * 6"
    schedule_tz: str = "Asia/Seoul"
    # SPEC-LOTTO-025 REQ-NOTIF-001: 조건부 알림 설정
    # threshold=0 또는 채널 미설정 시 알림 비활성
    notify_prize_threshold: int = 0
    notify_webhook_url: str = ""
    notify_email_to: str = ""
    notify_email_from: str = ""
    notify_smtp_host: str = ""
    notify_smtp_port: int = 587
    notify_smtp_user: str = ""
    notify_smtp_pass: str = ""


def _load_settings() -> Settings:
    """환경 변수와 (가능한 경우) .env 파일을 기반으로 Settings를 생성합니다."""
    # REQ-CFG-003: python-dotenv가 설치된 경우 프로젝트 루트의 .env를 자동 로드.
    # override=False: 이미 설정된 환경 변수가 우선 (REQ-CFG-002 (1) > (2)).
    if _DOTENV_AVAILABLE:
        _load_dotenv(override=False)

    api_url = os.environ.get("LOTTO_API_URL", _DEFAULT_API_URL)
    data_dir = Path(os.environ.get("LOTTO_DATA_DIR", _DEFAULT_DATA_DIR))
    web_host = os.environ.get("LOTTO_WEB_HOST", _DEFAULT_WEB_HOST)
    web_port = _parse_int(
        os.environ.get("LOTTO_WEB_PORT", _DEFAULT_WEB_PORT),
        "LOTTO_WEB_PORT",
    )
    recommender_weights = _parse_weights(
        os.environ.get("LOTTO_RECOMMENDER_WEIGHTS", _DEFAULT_RECOMMENDER_WEIGHTS)
    )
    checkpoint_interval = _parse_int(
        os.environ.get("LOTTO_CHECKPOINT_INTERVAL", _DEFAULT_CHECKPOINT_INTERVAL),
        "LOTTO_CHECKPOINT_INTERVAL",
    )
    scraper_urls = [
        os.environ.get("LOTTO_SCRAPER_URL_1", _DEFAULT_SCRAPER_URL_1),
        os.environ.get("LOTTO_SCRAPER_URL_2", _DEFAULT_SCRAPER_URL_2),
    ]
    # SPEC-LOTTO-003 REQ-BONUS-004: 보너스 회피 가중치 (환경 변수 또는 기본 0.0)
    bonus_avoidance_weight = _parse_float(
        os.environ.get("LOTTO_BONUS_AVOIDANCE_WEIGHT", _DEFAULT_BONUS_AVOIDANCE_WEIGHT),
        "LOTTO_BONUS_AVOIDANCE_WEIGHT",
    )
    # SPEC-LOTTO-023 REQ-SCHED-002: 스케줄러 설정 — 환경 변수 우선, 기본값 폴백
    raw_enabled = os.environ.get("LOTTO_SCHEDULE_ENABLED", _DEFAULT_SCHEDULE_ENABLED)
    schedule_enabled = raw_enabled.strip().lower() in {"true", "1", "yes", "on"}
    schedule_cron = os.environ.get("LOTTO_SCHEDULE_CRON", _DEFAULT_SCHEDULE_CRON)
    schedule_tz = os.environ.get("LOTTO_SCHEDULE_TZ", _DEFAULT_SCHEDULE_TZ)
    # SPEC-LOTTO-025 REQ-NOTIF-001: 알림 설정 — 환경 변수 우선, 기본값 폴백
    notify_prize_threshold = _parse_int(
        os.environ.get("LOTTO_NOTIFY_PRIZE_THRESHOLD", _DEFAULT_NOTIFY_PRIZE_THRESHOLD),
        "LOTTO_NOTIFY_PRIZE_THRESHOLD",
    )
    notify_webhook_url = os.environ.get("LOTTO_NOTIFY_WEBHOOK_URL", "")
    notify_email_to = os.environ.get("LOTTO_NOTIFY_EMAIL_TO", "")
    notify_email_from = os.environ.get("LOTTO_NOTIFY_EMAIL_FROM", "")
    notify_smtp_host = os.environ.get("LOTTO_NOTIFY_SMTP_HOST", "")
    notify_smtp_port = _parse_int(
        os.environ.get("LOTTO_NOTIFY_SMTP_PORT", _DEFAULT_NOTIFY_SMTP_PORT),
        "LOTTO_NOTIFY_SMTP_PORT",
    )
    notify_smtp_user = os.environ.get("LOTTO_NOTIFY_SMTP_USER", "")
    notify_smtp_pass = os.environ.get("LOTTO_NOTIFY_SMTP_PASS", "")

    return Settings(
        api_url=api_url,
        data_dir=data_dir,
        web_host=web_host,
        web_port=web_port,
        recommender_weights=recommender_weights,
        checkpoint_interval=checkpoint_interval,
        scraper_urls=scraper_urls,
        bonus_avoidance_weight=bonus_avoidance_weight,
        schedule_enabled=schedule_enabled,
        schedule_cron=schedule_cron,
        schedule_tz=schedule_tz,
        notify_prize_threshold=notify_prize_threshold,
        notify_webhook_url=notify_webhook_url,
        notify_email_to=notify_email_to,
        notify_email_from=notify_email_from,
        notify_smtp_host=notify_smtp_host,
        notify_smtp_port=notify_smtp_port,
        notify_smtp_user=notify_smtp_user,
        notify_smtp_pass=notify_smtp_pass,
    )


# 모듈 임포트 시 단일 settings 인스턴스 초기화 (REQ-CFG-001).
settings: Settings = _load_settings()
