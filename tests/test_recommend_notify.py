"""SPEC-LOTTO-115: 추천 번호 자동 알림 테스트."""
from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

# ──────────────────────────────────────────────
# 헬퍼 픽스처
# ──────────────────────────────────────────────

def _make_recommendation(numbers: list[int], label: str = "고빈도", desc: str = "설명") -> dict[str, Any]:  # noqa: E501
    return {"numbers": numbers, "strategy_label": label, "strategy_desc": desc}


def _make_settings(**kwargs: Any) -> Any:
    """테스트용 settings 객체(MagicMock)를 반환합니다."""
    s = MagicMock()
    s.notify_recommend_count = kwargs.get("notify_recommend_count", 0)
    s.notify_webhook_url = kwargs.get("notify_webhook_url", "")
    s.notify_smtp_host = kwargs.get("notify_smtp_host", "")
    s.notify_email_to = kwargs.get("notify_email_to", "")
    s.notify_email_from = kwargs.get("notify_email_from", "")
    s.notify_smtp_port = kwargs.get("notify_smtp_port", 587)
    s.notify_smtp_user = kwargs.get("notify_smtp_user", "")
    s.notify_smtp_pass = kwargs.get("notify_smtp_pass", "")
    return s


def _make_draws(last_drw_no: int = 1000) -> list[Any]:
    """마지막 drwNo가 last_drw_no 인 DrawResult 목록(MagicMock)을 반환합니다."""
    d = MagicMock()
    d.drwNo = last_drw_no
    return [d]


# ──────────────────────────────────────────────
# _format_recommend_payload 단위 테스트
# ──────────────────────────────────────────────

def test_format_recommend_payload_basic() -> None:
    """drw_no 가 있으면 payload에 회차 라벨과 번호가 포함돼야 한다."""
    from lotto.web.notifier import _format_recommend_payload

    recs = [_make_recommendation([1, 7, 14, 21, 35, 42], "고빈도")]
    payload = _format_recommend_payload(recs, next_drw_no=1001)

    assert "1001회차" in payload["text"]
    assert "1 7 14 21 35 42" in payload["text"]
    assert "고빈도" in payload["text"]


def test_format_recommend_payload_no_drw() -> None:
    """next_drw_no=None 이면 '다음 회차'가 라벨로 사용돼야 한다."""
    from lotto.web.notifier import _format_recommend_payload

    recs = [_make_recommendation([2, 4, 6, 8, 10, 12])]
    payload = _format_recommend_payload(recs, next_drw_no=None)

    assert "다음 회차" in payload["text"]


# ──────────────────────────────────────────────
# send_webhook_recommend 단위 테스트
# ──────────────────────────────────────────────

def test_send_webhook_recommend_no_url() -> None:
    """Webhook URL이 비어있으면 False를 반환해야 한다."""
    import lotto.web.notifier as notifier_mod

    s = _make_settings(notify_webhook_url="")
    with patch.object(notifier_mod, "settings", s):
        result = notifier_mod.send_webhook_recommend([], next_drw_no=None)

    assert result is False


def test_send_webhook_recommend_success() -> None:
    """httpx.post 가 200 을 반환하면 True를 반환해야 한다."""
    import lotto.web.notifier as notifier_mod

    s = _make_settings(notify_webhook_url="https://hooks.example.com/test")
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    recs = [_make_recommendation([1, 2, 3, 4, 5, 6])]
    with patch.object(notifier_mod, "settings", s), patch("httpx.post", return_value=mock_resp):
        result = notifier_mod.send_webhook_recommend(recs, next_drw_no=1001)

    assert result is True


def test_send_webhook_recommend_non_2xx() -> None:
    """httpx.post 가 500 을 반환하면 False를 반환해야 한다 (예외 없음)."""
    import lotto.web.notifier as notifier_mod

    s = _make_settings(notify_webhook_url="https://hooks.example.com/test")
    mock_resp = MagicMock()
    mock_resp.status_code = 500

    recs = [_make_recommendation([1, 2, 3, 4, 5, 6])]
    with patch.object(notifier_mod, "settings", s), patch("httpx.post", return_value=mock_resp):
        result = notifier_mod.send_webhook_recommend(recs, next_drw_no=1001)

    assert result is False


def test_send_webhook_recommend_exception() -> None:
    """httpx.post 가 예외를 발생시켜도 False를 반환해야 한다 (예외 전파 없음)."""
    import lotto.web.notifier as notifier_mod

    s = _make_settings(notify_webhook_url="https://hooks.example.com/test")
    recs = [_make_recommendation([1, 2, 3, 4, 5, 6])]

    with patch.object(notifier_mod, "settings", s):  # noqa: SIM117
        with patch("httpx.post", side_effect=ConnectionError("timeout")):
            result = notifier_mod.send_webhook_recommend(recs, next_drw_no=1001)

    assert result is False


# ──────────────────────────────────────────────
# send_email_recommend 단위 테스트
# ──────────────────────────────────────────────

def test_send_email_recommend_no_smtp() -> None:
    """SMTP 호스트가 비어있으면 False를 반환해야 한다."""
    import lotto.web.notifier as notifier_mod

    s = _make_settings(notify_smtp_host="", notify_email_to="to@x.com", notify_email_from="from@x.com")  # noqa: E501
    recs = [_make_recommendation([1, 2, 3, 4, 5, 6])]

    with patch.object(notifier_mod, "settings", s):
        result = notifier_mod.send_email_recommend(recs, next_drw_no=1001)

    assert result is False


# ──────────────────────────────────────────────
# notify_recommendations 통합 단위 테스트
# ──────────────────────────────────────────────

def test_notify_recommendations_count_zero() -> None:
    """notify_recommend_count=0 이면 즉시 [] 를 반환해야 한다."""
    import lotto.web.notifier as notifier_mod

    s = _make_settings(notify_recommend_count=0)
    draws = _make_draws()

    with patch.object(notifier_mod, "settings", s):
        result = notifier_mod.notify_recommendations(draws)

    assert result == []


def test_notify_recommendations_no_draws() -> None:
    """draws 가 빈 리스트이면 즉시 [] 를 반환해야 한다."""
    import lotto.web.notifier as notifier_mod

    s = _make_settings(notify_recommend_count=3)
    with patch.object(notifier_mod, "settings", s):
        result = notifier_mod.notify_recommendations([])

    assert result == []


def test_notify_recommendations_no_webhook_no_email() -> None:
    """Webhook/Email 둘 다 미설정 시 채널 발사 없이 [] 를 반환해야 한다."""
    import lotto.web.notifier as notifier_mod

    s = _make_settings(notify_recommend_count=3, notify_webhook_url="", notify_smtp_host="")
    draws = _make_draws()

    mock_stats = MagicMock()
    mock_rec = MagicMock()
    mock_rec.numbers = [1, 2, 3, 4, 5, 6]
    mock_rec.strategy_label = "균형"
    mock_rec.strategy_desc = "설명"
    mock_recommender = MagicMock()
    mock_recommender.recommend.return_value = [mock_rec, mock_rec, mock_rec]

    with patch.object(notifier_mod, "settings", s):  # noqa: SIM117
        with patch("lotto.web.data.get_stats", return_value=mock_stats):
            with patch("lotto.recommender.LottoRecommender", return_value=mock_recommender):
                result = notifier_mod.notify_recommendations(draws)

    assert result == []


def test_notify_recommendations_webhook_sends() -> None:
    """Webhook 설정 시 send_webhook_recommend 가 호출되고 결과가 반환돼야 한다."""
    import lotto.web.notifier as notifier_mod

    s = _make_settings(
        notify_recommend_count=3,
        notify_webhook_url="https://hooks.example.com/test",
        notify_smtp_host="",
    )
    draws = _make_draws()

    mock_stats = MagicMock()
    mock_rec = MagicMock()
    mock_rec.numbers = [1, 2, 3, 4, 5, 6]
    mock_rec.strategy_label = "고빈도"
    mock_rec.strategy_desc = "설명"
    mock_recommender = MagicMock()
    mock_recommender.recommend.return_value = [mock_rec, mock_rec, mock_rec]

    with patch.object(notifier_mod, "settings", s):  # noqa: SIM117
        with patch("lotto.web.data.get_stats", return_value=mock_stats):
            with patch("lotto.recommender.LottoRecommender", return_value=mock_recommender):
                with patch.object(notifier_mod, "send_webhook_recommend", return_value=True) as mock_send:  # noqa: E501
                    result = notifier_mod.notify_recommendations(draws)

    mock_send.assert_called_once()
    assert len(result) == 1
    assert result[0]["channel"] == "webhook"
    assert result[0]["ok"] is True


# ──────────────────────────────────────────────
# config.py 단위 테스트
# ──────────────────────────────────────────────

def test_config_notify_recommend_count_default(tmp_path: "pytest.TempPathFactory") -> None:
    """환경 변수도 user_settings.json도 없을 때 기본값 0이어야 한다."""
    import importlib

    import lotto.config as _config

    # 빈 tmp 디렉토리를 data_dir로 지정하면 user_settings.json이 없어 기본값 적용됨
    original_count = os.environ.pop("LOTTO_NOTIFY_RECOMMEND_COUNT", None)
    original_data_dir = os.environ.pop("LOTTO_DATA_DIR", None)
    try:
        os.environ["LOTTO_DATA_DIR"] = str(tmp_path)
        importlib.reload(_config)
        assert _config.settings.notify_recommend_count == 0
    finally:
        if original_count is not None:
            os.environ["LOTTO_NOTIFY_RECOMMEND_COUNT"] = original_count
        if original_data_dir is not None:
            os.environ["LOTTO_DATA_DIR"] = original_data_dir
        elif "LOTTO_DATA_DIR" in os.environ:
            del os.environ["LOTTO_DATA_DIR"]
        importlib.reload(_config)


def test_config_notify_recommend_count_env() -> None:
    """LOTTO_NOTIFY_RECOMMEND_COUNT=5 이면 settings.notify_recommend_count == 5 이어야 한다."""
    import importlib

    import lotto.config as _config

    with patch.dict(os.environ, {"LOTTO_NOTIFY_RECOMMEND_COUNT": "5"}, clear=False):
        importlib.reload(_config)
        assert _config.settings.notify_recommend_count == 5

    # 복원 (다른 테스트 오염 방지)
    importlib.reload(_config)


# ──────────────────────────────────────────────
# API 엔드포인트 테스트
# ──────────────────────────────────────────────

def test_api_test_recommend_no_data() -> None:
    """GET /api/settings/test-recommend: 데이터 없으면 503."""
    from fastapi.testclient import TestClient

    from lotto.web.app import app

    client = TestClient(app, raise_server_exceptions=False)
    with patch("lotto.web.data.get_draws", return_value=None):
        response = client.post("/api/settings/test-recommend")

    assert response.status_code == 503


def test_api_test_recommend_no_webhook() -> None:
    """GET /api/settings/test-recommend: Webhook 미설정 시 400."""
    from fastapi.testclient import TestClient

    import lotto.config as _config
    import lotto.web.notifier as notifier_mod
    from lotto.web.app import app

    original_settings = _config.settings

    try:
        import dataclasses
        new_settings = dataclasses.replace(original_settings, notify_webhook_url="")
        _config.settings = new_settings
        notifier_mod.settings = new_settings

        draws = _make_draws()
        client = TestClient(app, raise_server_exceptions=False)
        with patch("lotto.web.data.get_draws", return_value=draws):
            response = client.post("/api/settings/test-recommend")
    finally:
        _config.settings = original_settings
        notifier_mod.settings = original_settings

    assert response.status_code == 400
