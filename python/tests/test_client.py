"""
Mocked tests for the eSIMx402 Python client.

Uses pytest-httpx so we don't hit the real API in CI. Exercises the three
state transitions a real caller cares about:
  1. list_plans → 200 with plans array
  2. create_order → 402 with payment headers parsed into an Invoice
  3. wait_for_esim → polls until DELIVERED, returns ESim
"""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from esimx402 import (
    Client,
    OrderStatus,
    PaymentExpired,
    OrderFailed,
)


BASE = "https://api.example.com"


def test_list_plans(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{BASE}/api/v1/x402/plans?country=JP",
        json={"plans": [
            {"id": "JP_5GB_30D", "country": "Japan", "country_code": "JP",
             "data_gb": 5.0, "validity_days": 30, "price_usd": 6.21},
        ]},
    )
    with Client(base_url=BASE) as c:
        plans = c.list_plans(country="JP")
    assert len(plans) == 1
    assert plans[0].id == "JP_5GB_30D"
    assert plans[0].price_usd == 6.21


def test_create_order_returns_invoice(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{BASE}/api/v1/x402/order",
        method="POST",
        status_code=402,
        json={"order_id": "ord_abc"},
        headers={
            "x-payto": "0x742d35cc6634c053",
            "x-amount": "6.21",
            "x-asset": "USDC",
            "x-chain": "polygon",
            "x-expires": "2026-05-14T15:00:00Z",
        },
    )
    with Client(base_url=BASE) as c:
        inv = c.create_order(plan_id="JP_5GB_30D")
    assert inv.order_id == "ord_abc"
    assert inv.pay_to == "0x742d35cc6634c053"
    assert inv.amount == "6.21"
    assert inv.chain == "polygon"
    assert inv.asset == "USDC"


def test_create_order_unexpected_status_raises(httpx_mock: HTTPXMock) -> None:
    """Server returning 200 instead of 402 is a contract violation — raise."""
    from esimx402 import APIError

    httpx_mock.add_response(
        url=f"{BASE}/api/v1/x402/order",
        method="POST",
        status_code=200,
        json={"order_id": "ord_zzz"},
    )
    with Client(base_url=BASE) as c:
        with pytest.raises(APIError):
            c.create_order(plan_id="JP_5GB_30D")


def test_wait_for_esim_polls_until_delivered(httpx_mock: HTTPXMock) -> None:
    # Two PROVISIONING responses, then DELIVERED.
    for _ in range(2):
        httpx_mock.add_response(
            url=f"{BASE}/api/v1/x402/order/ord_abc",
            json={"order_id": "ord_abc", "status": "provisioning", "plan_id": "JP_5GB_30D"},
        )
    httpx_mock.add_response(
        url=f"{BASE}/api/v1/x402/order/ord_abc",
        json={
            "order_id": "ord_abc",
            "status": "delivered",
            "plan_id": "JP_5GB_30D",
            "esim": {
                "iccid": "8910300000123456789",
                "qr_code_data": "LPA:1$smdp.example.com$ACTIVATION-CODE",
                "qr_image_url": "https://example.com/qr.png",
                "activation_link": "https://esimsetup.apple.com/...",
            },
        },
    )

    with Client(base_url=BASE) as c:
        esim = c.wait_for_esim("ord_abc", poll_interval=0.01)

    assert esim.iccid == "8910300000123456789"
    assert esim.qr_image_url == "https://example.com/qr.png"


def test_wait_for_esim_raises_on_expired(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{BASE}/api/v1/x402/order/ord_abc",
        json={"order_id": "ord_abc", "status": "expired", "plan_id": "JP_5GB_30D"},
    )
    with Client(base_url=BASE) as c:
        with pytest.raises(PaymentExpired):
            c.wait_for_esim("ord_abc", poll_interval=0.01)


def test_wait_for_esim_raises_on_failed(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{BASE}/api/v1/x402/order/ord_abc",
        json={"order_id": "ord_abc", "status": "failed", "plan_id": "JP_5GB_30D"},
    )
    with Client(base_url=BASE) as c:
        with pytest.raises(OrderFailed):
            c.wait_for_esim("ord_abc", poll_interval=0.01)


def test_order_status_enum_covers_real_states() -> None:
    """If the server adds a new status the client doesn't recognise, fail loudly
    in parsing — better than silently treating it as success."""
    assert OrderStatus("delivered") == OrderStatus.DELIVERED
    assert OrderStatus("pending_payment") == OrderStatus.PENDING_PAYMENT
    with pytest.raises(ValueError):
        OrderStatus("totally_made_up_status")
