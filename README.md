# esimx402

[![PyPI](https://img.shields.io/pypi/v/esimx402?label=pypi%20esimx402)](https://pypi.org/project/esimx402/)
[![npm](https://img.shields.io/npm/v/esimx402?label=npm%20esimx402)](https://www.npmjs.com/package/esimx402)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python tests](https://github.com/timav12/esimx402/actions/workflows/test-python.yml/badge.svg)](https://github.com/timav12/esimx402/actions/workflows/test-python.yml)
[![Node tests](https://github.com/timav12/esimx402/actions/workflows/test-node.yml/badge.svg)](https://github.com/timav12/esimx402/actions/workflows/test-node.yml)

Production [x402 protocol](https://www.x402.org) clients for buying travel eSIM data — Python and TypeScript/JavaScript.

No account. No API key. Pay on-chain in USDC or USDT (Polygon or TON). Built for AI agents, IoT devices, and autonomous workflows.

→ Live API: <https://esimx402.com>
→ Docs: <https://esimx402.com/docs>

## Why x402 for eSIM?

Traditional eSIM-reseller APIs require KYC, a sales contract, an API key, and a credit card on file. That works for human-operated SaaS. It fails for AI agents and unattended devices.

x402 replaces the entire account + auth + billing stack with a single HTTP flow:

```
POST /api/v1/x402/order { "plan_id": "JP_5GB_30D" }
←  402 Payment Required
   x-payto: 0x742d35cc6634c053...
   x-amount: 6.21
   x-chain: polygon
   x-asset: USDC

[ your wallet sends 6.21 USDC on Polygon to that address ]

GET /api/v1/x402/order/{id}
←  200 OK
   { iccid, qr_code_data, qr_image_url, activation_link }
```

That's it. No webhook configuration, no API-key rotation, no minimum commitment. Pay only for the eSIMs you actually order.

## Quick start

### Python

```bash
pip install esimx402
```

```python
from esimx402 import Client

with Client() as client:
    plans = client.list_plans(country="JP")
    invoice = client.create_order(plan_id=plans[0].id)
    # pay invoice from your wallet
    esim = client.wait_for_esim(invoice.order_id)
    print(esim.qr_image_url)
```

Full Python docs: [python/README.md](python/README.md) · [PyPI](https://pypi.org/project/esimx402/)

### Node / TypeScript

```bash
npm install esimx402
```

```ts
import { Client } from 'esimx402';

const client = new Client();
const plans = await client.listPlans('JP');
const invoice = await client.createOrder(plans[0].id);
// pay invoice from your wallet
const esim = await client.waitForESim(invoice.orderId);
console.log(esim.qrImageUrl);
```

Full Node docs: [node/README.md](node/README.md) · [npm](https://www.npmjs.com/package/esimx402)

## Use cases

- **AI travel agents** (LangChain, AgentKit, Bedrock AgentCore) provisioning data for booked trips
- **VPS / bot failover** when primary uplink dies — autonomous purchase + modem swap in 30 s
- **IoT devices crossing borders** — logistics trackers, agricultural sensors, drones
- **Privacy-first travel users** — no email, no card, just an on-chain transfer
- **Multi-agent platforms** — coordinator agent pays for connectivity used by sub-agents

Each language ships three runnable example skeletons under `python/examples/` and `node/examples/`.

## Wallet support

The client deliberately stays out of the signing path. Bring your own. Any wallet stack that can send a standard ERC-20 transfer works:

| Stack | Polygon | TON |
|---|---|---|
| viem / wagmi / ethers (JS) | ✅ | — |
| web3.py (Python) | ✅ | — |
| @ton/ton (JS) | — | ✅ |
| pytonlib (Python) | — | ✅ |
| Coinbase Wallet SDK | ✅ | — |
| Hardware wallets (Ledger, Trezor) | ✅ | partial |

If your wallet can sign and submit a USDC/USDT transfer on Polygon or USDT on TON, you're done.

## Errors

| Exception | When |
|---|---|
| `APIError` | Server returned an unexpected HTTP status |
| `PaymentExpired` | Invoice expired before payment landed on-chain (30-min default window) |
| `OrderFailed` | Server received payment but couldn't fulfill — automatic on-chain refund within 5 min |

## Status

| | |
|---|---|
| Version | 0.1.0 (initial release) |
| API stability | Beta. Minor breaking changes possible until 1.0, documented in CHANGELOG |
| Chains in production | Polygon (USDC, USDT), TON (USDT) |
| Coverage | 179 countries, 2,500+ plans |
| Uptime target | 99.5% |

## Links

- API documentation: <https://esimx402.com/docs>
- Quickstart guide: <https://esimx402.com/quickstart>
- Use cases: <https://esimx402.com/use-cases>
- Pricing: <https://esimx402.com/pricing>
- Engineering blog: <https://esimx402.com/blog>
- Issues + Discussions: <https://github.com/timav12/esimx402/issues>
- Contact: `dev@esimx402.com`

## Related

- Consumer site (Spanish-language end-user UX): <https://esimahora.com>
- B2B Teams (invoiced billing, multi-seat): <https://esimteams.com>

## License

[MIT](LICENSE). Use, fork, modify, embed in commercial products freely. Attribution appreciated but not required.
