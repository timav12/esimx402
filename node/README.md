# esimx402

TypeScript/JavaScript client for the [eSIMx402](https://esimx402.com) production x402 API.

Buy travel eSIM data with a single HTTP request — no account, no API key. Pay on-chain in USDC or USDT (Polygon or TON). Built for AI agents and autonomous workflows.

## Install

```bash
npm install esimx402
```

Requires Node ≥ 20 (native `fetch`).

## Quickstart

```ts
import { Client } from 'esimx402';

const client = new Client();

// 1. Discover plans for a country
const plans = await client.listPlans('JP');
const cheapest = plans.reduce((a, b) => (a.priceUsd < b.priceUsd ? a : b));

// 2. Request an order — server returns 402 with the on-chain invoice
const invoice = await client.createOrder(cheapest.id);
console.log(`Pay ${invoice.amount} ${invoice.asset} on ${invoice.chain} → ${invoice.payTo}`);

// 3. Pay it. Bring your own wallet — any sender of ERC-20 transfers works.
await yourWallet.send({
  to: invoice.payTo,
  amount: invoice.amount,
  chain: invoice.chain,
  asset: invoice.asset,
});

// 4. Wait for the eSIM (5-15 s typical)
const esim = await client.waitForESim(invoice.orderId);
console.log(esim.qrImageUrl);
```

## Three full examples

- [examples/01-buy-esim.ts](examples/01-buy-esim.ts) — basic happy path
- [examples/02-agent-failover.ts](examples/02-agent-failover.ts) — autonomous failover when the primary uplink dies
- [examples/03-iot-geofence.ts](examples/03-iot-geofence.ts) — IoT device crossing borders, no ops console

## Errors

| Exception | When |
|---|---|
| `APIError` | Server returned an unexpected HTTP status (contract violation or outage) |
| `PaymentExpired` | The 402 invoice expired before payment landed on-chain |
| `OrderFailed` | Server received payment but couldn't fulfill the order. Automatic on-chain refund within 5 min |
| Native `Error` (`'after ${ms}ms'`) | `waitForESim()` ceiling reached without DELIVERED |

## Links

- API docs: <https://esimx402.com/docs>
- Quickstart: <https://esimx402.com/quickstart>
- Pricing: <https://esimx402.com/pricing>
- Issues / questions: <https://github.com/timav12/esimx402/issues>
- Email: `dev@esimx402.com`

## License

MIT
