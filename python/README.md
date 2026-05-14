# esimx402

Python client for the [eSIMx402](https://esimx402.com) production x402 API.

Buy travel eSIM data with a single HTTP request — no account, no API key. Pay on-chain in USDC or USDT (Polygon or TON). Built for AI agents and autonomous workflows.

## Install

```bash
pip install esimx402
```

## Quickstart

```python
from esimx402 import Client

with Client() as client:
    # 1. Discover plans for a country
    plans = client.list_plans(country="JP")
    cheap = min(plans, key=lambda p: p.price_usd)

    # 2. Request an order — server returns 402 with the on-chain invoice
    invoice = client.create_order(plan_id=cheap.id)
    print(f"Pay {invoice.amount} {invoice.asset} on {invoice.chain} → {invoice.pay_to}")

    # 3. Pay it. Bring your own wallet — any sender of ERC-20 transfers works.
    your_wallet.send(
        to=invoice.pay_to,
        amount=invoice.amount,
        chain=invoice.chain,
        asset=invoice.asset,
    )

    # 4. Wait for the eSIM (5-15 s typical, 30 s ceiling)
    esim = client.wait_for_esim(invoice.order_id)
    print(esim.qr_image_url)
```

Async variant: `from esimx402 import AsyncClient` — same surface, all methods `await`able.

## Three full examples

- [examples/01_buy_esim.py](examples/01_buy_esim.py) — basic happy path
- [examples/02_agent_failover.py](examples/02_agent_failover.py) — autonomous failover when the primary uplink dies
- [examples/03_iot_geofence.py](examples/03_iot_geofence.py) — IoT device crossing borders, no ops console

## Errors

| Exception | When |
|---|---|
| `APIError` | Server returned an unexpected HTTP status (contract violation or outage) |
| `PaymentExpired` | The 402 invoice expired before payment landed on-chain |
| `OrderFailed` | Server received payment but couldn't fulfill the order. Automatic on-chain refund within 5 min |
| `TimeoutError` | `wait_for_esim()` ceiling reached without the order reaching DELIVERED |

## Links

- API docs: <https://esimx402.com/docs>
- Quickstart: <https://esimx402.com/quickstart>
- Pricing: <https://esimx402.com/pricing>
- Issues / questions: <https://github.com/timav12/esimx402/issues>
- Email: `dev@esimx402.com`

## License

MIT
