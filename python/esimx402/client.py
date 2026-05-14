"""
eSIMx402 client — sync + async variants, same surface.

The protocol over the wire (see https://esimx402.com/docs for the canonical spec):

  GET  /api/v1/x402/plans?country=JP             →  list of plans (no auth)
  POST /api/v1/x402/order  { "plan_id": "..." }  →  402 + payment headers
  GET  /api/v1/x402/order/{id}                   →  current status; 200 when delivered

The client itself does NOT sign or send the on-chain transaction — bring
your own wallet. We just hand back an `Invoice` with the destination, amount,
chain, and asset; you pay through whatever wallet stack you already use.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.esimahora.com"
DEFAULT_TIMEOUT = 30.0


# ─── Domain types ──────────────────────────────────────────────────────────


class OrderStatus(str, Enum):
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    PROVISIONING = "provisioning"
    DELIVERED = "delivered"
    EXPIRED = "expired"
    REFUNDED = "refunded"
    FAILED = "failed"


@dataclass(frozen=True)
class Plan:
    id: str
    country: str
    country_code: str
    data_gb: float
    validity_days: int
    price_usd: float
    raw: dict[str, Any]


@dataclass(frozen=True)
class Invoice:
    """A 402 Payment Required response — what the caller must pay before fulfilment."""

    order_id: str
    pay_to: str        # on-chain destination address
    amount: str        # decimal string, exact (don't float-round)
    asset: str         # USDC | USDT
    chain: str         # polygon | ton
    expires_at: str    # ISO-8601


@dataclass(frozen=True)
class ESim:
    iccid: str
    qr_code_data: str
    qr_image_url: str
    activation_link: str | None


@dataclass(frozen=True)
class Order:
    id: str
    status: OrderStatus
    plan_id: str
    esim: ESim | None
    invoice: Invoice | None
    raw: dict[str, Any]


# ─── Exceptions ────────────────────────────────────────────────────────────


class APIError(RuntimeError):
    """Unexpected HTTP response from the server."""

    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"eSIMx402 API error {status}: {body[:200]}")
        self.status = status
        self.body = body


class PaymentExpired(RuntimeError):
    """The 402 invoice expired before payment landed on-chain."""


class OrderFailed(RuntimeError):
    """The order fulfilment failed after payment. Refund is automatic."""

    def __init__(self, order: Order) -> None:
        super().__init__(f"Order {order.id} failed with status {order.status}")
        self.order = order


# ─── Shared parsing helpers ────────────────────────────────────────────────


def _parse_plan(d: dict[str, Any]) -> Plan:
    return Plan(
        id=str(d["id"]),
        country=str(d.get("country", "")),
        country_code=str(d.get("country_code", "")),
        data_gb=float(d.get("data_gb", 0.0)),
        validity_days=int(d.get("validity_days", 0)),
        price_usd=float(d.get("price_usd", 0.0)),
        raw=d,
    )


def _parse_invoice_from_headers(headers: httpx.Headers, order_id: str) -> Invoice:
    return Invoice(
        order_id=order_id,
        pay_to=headers["x-payto"],
        amount=headers["x-amount"],
        asset=headers["x-asset"],
        chain=headers["x-chain"],
        expires_at=headers.get("x-expires", ""),
    )


def _parse_order(d: dict[str, Any]) -> Order:
    esim = None
    if e := d.get("esim"):
        esim = ESim(
            iccid=e["iccid"],
            qr_code_data=e["qr_code_data"],
            qr_image_url=e["qr_image_url"],
            activation_link=e.get("activation_link"),
        )
    return Order(
        id=str(d["order_id"]),
        status=OrderStatus(d["status"]),
        plan_id=str(d.get("plan_id", "")),
        esim=esim,
        invoice=None,
        raw=d,
    )


# ─── Sync client ───────────────────────────────────────────────────────────


class Client:
    """Synchronous client. For asyncio code, see `AsyncClient`."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        http: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=timeout)
        self._owns_http = http is None

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    # ─ Public API ─

    def list_plans(self, country: str | None = None) -> list[Plan]:
        params = {"country": country} if country else None
        r = self._http.get(f"{self.base_url}/api/v1/x402/plans", params=params)
        if not r.is_success:
            raise APIError(r.status_code, r.text)
        return [_parse_plan(p) for p in r.json().get("plans", [])]

    def create_order(self, plan_id: str, callback_url: str | None = None) -> Invoice:
        """POST /order — server responds 402 with the on-chain invoice."""
        body: dict[str, Any] = {"plan_id": plan_id}
        if callback_url:
            body["callback_url"] = callback_url
        r = self._http.post(f"{self.base_url}/api/v1/x402/order", json=body)
        if r.status_code != 402:
            raise APIError(r.status_code, r.text)
        order_id = r.json().get("order_id") or r.headers.get("x-order-id", "")
        return _parse_invoice_from_headers(r.headers, str(order_id))

    def get_order(self, order_id: str) -> Order:
        r = self._http.get(f"{self.base_url}/api/v1/x402/order/{order_id}")
        if not r.is_success:
            raise APIError(r.status_code, r.text)
        return _parse_order(r.json())

    def wait_for_esim(
        self,
        order_id: str,
        timeout: float = 120.0,
        poll_interval: float = 2.0,
    ) -> ESim:
        """Block until the order is DELIVERED, or raise on terminal failure."""
        deadline = time.monotonic() + timeout
        terminal_failures = {
            OrderStatus.EXPIRED,
            OrderStatus.REFUNDED,
            OrderStatus.FAILED,
        }
        while True:
            order = self.get_order(order_id)
            if order.status == OrderStatus.DELIVERED and order.esim:
                return order.esim
            if order.status == OrderStatus.EXPIRED:
                raise PaymentExpired(f"Invoice {order_id} expired before payment")
            if order.status in terminal_failures:
                raise OrderFailed(order)
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Order {order_id} still {order.status} after {timeout}s"
                )
            time.sleep(poll_interval)


# ─── Async client ──────────────────────────────────────────────────────────


class AsyncClient:
    """Async-await variant. Same surface as `Client`, all methods awaitable."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = http or httpx.AsyncClient(timeout=timeout)
        self._owns_http = http is None

    async def __aenter__(self) -> AsyncClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def list_plans(self, country: str | None = None) -> list[Plan]:
        params = {"country": country} if country else None
        r = await self._http.get(f"{self.base_url}/api/v1/x402/plans", params=params)
        if not r.is_success:
            raise APIError(r.status_code, r.text)
        return [_parse_plan(p) for p in r.json().get("plans", [])]

    async def create_order(self, plan_id: str, callback_url: str | None = None) -> Invoice:
        body: dict[str, Any] = {"plan_id": plan_id}
        if callback_url:
            body["callback_url"] = callback_url
        r = await self._http.post(f"{self.base_url}/api/v1/x402/order", json=body)
        if r.status_code != 402:
            raise APIError(r.status_code, r.text)
        order_id = r.json().get("order_id") or r.headers.get("x-order-id", "")
        return _parse_invoice_from_headers(r.headers, str(order_id))

    async def get_order(self, order_id: str) -> Order:
        r = await self._http.get(f"{self.base_url}/api/v1/x402/order/{order_id}")
        if not r.is_success:
            raise APIError(r.status_code, r.text)
        return _parse_order(r.json())

    async def wait_for_esim(
        self,
        order_id: str,
        timeout: float = 120.0,
        poll_interval: float = 2.0,
    ) -> ESim:
        import asyncio
        deadline = time.monotonic() + timeout
        terminal_failures = {OrderStatus.EXPIRED, OrderStatus.REFUNDED, OrderStatus.FAILED}
        while True:
            order = await self.get_order(order_id)
            if order.status == OrderStatus.DELIVERED and order.esim:
                return order.esim
            if order.status == OrderStatus.EXPIRED:
                raise PaymentExpired(f"Invoice {order_id} expired before payment")
            if order.status in terminal_failures:
                raise OrderFailed(order)
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Order {order_id} still {order.status} after {timeout}s"
                )
            await asyncio.sleep(poll_interval)
