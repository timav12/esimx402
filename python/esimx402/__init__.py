"""
esimx402 — Python client for the eSIMx402 x402 protocol API.

Quickstart:

    from esimx402 import Client

    client = Client()  # uses production API by default

    # 1. Discover plans
    plans = client.list_plans(country="JP")

    # 2. Request order — server returns 402 with payment details
    invoice = client.create_order(plan_id=plans[0].id)
    print(f"Pay {invoice.amount} {invoice.asset} on {invoice.chain} to {invoice.pay_to}")

    # 3. Pay the invoice from your wallet (bring your own signer)
    your_wallet.send(invoice.pay_to, invoice.amount, invoice.chain, invoice.asset)

    # 4. Poll until eSIM is provisioned (5-15s typical)
    esim = client.wait_for_esim(invoice.order_id)
    print(esim.qr_image_url)

Full docs: https://esimx402.com/docs
"""

from .client import (
    Client,
    AsyncClient,
    Plan,
    Invoice,
    ESim,
    Order,
    OrderStatus,
    APIError,
    PaymentExpired,
    OrderFailed,
)

__all__ = [
    "Client",
    "AsyncClient",
    "Plan",
    "Invoice",
    "ESim",
    "Order",
    "OrderStatus",
    "APIError",
    "PaymentExpired",
    "OrderFailed",
]

__version__ = "0.1.0"
