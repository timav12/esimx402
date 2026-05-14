/**
 * Mocked tests for the eSIMx402 Node client.
 *
 * Uses node's built-in test runner (`node --test`) — no jest, no vitest.
 * fetch is replaced with a hand-rolled stub per-test for clean isolation.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  Client,
  OrderStatus,
  PaymentExpired,
  OrderFailed,
  APIError,
} from './client.js';

const BASE = 'https://api.example.com';

function mockFetch(handlers: Array<(url: string) => Response>): typeof fetch {
  let i = 0;
  return async (url: string | URL | Request) => {
    const handler = handlers[i++];
    if (!handler) throw new Error(`mockFetch: no handler for call ${i} (${url})`);
    return handler(typeof url === 'string' ? url : url.toString());
  };
}

function jsonResponse(status: number, body: unknown, extraHeaders: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', ...extraHeaders },
  });
}

test('listPlans returns parsed plans', async () => {
  const client = new Client({
    baseUrl: BASE,
    fetch: mockFetch([
      () => jsonResponse(200, {
        plans: [{
          id: 'JP_5GB_30D',
          country: 'Japan',
          country_code: 'JP',
          data_gb: 5,
          validity_days: 30,
          price_usd: 6.21,
        }],
      }),
    ]),
  });

  const plans = await client.listPlans('JP');
  assert.equal(plans.length, 1);
  assert.equal(plans[0]!.id, 'JP_5GB_30D');
  assert.equal(plans[0]!.priceUsd, 6.21);
});

test('createOrder parses 402 + headers into Invoice', async () => {
  const client = new Client({
    baseUrl: BASE,
    fetch: mockFetch([
      () => jsonResponse(402, { order_id: 'ord_abc' }, {
        'x-payto': '0x742d35cc6634c053',
        'x-amount': '6.21',
        'x-asset': 'USDC',
        'x-chain': 'polygon',
        'x-expires': '2026-05-14T15:00:00Z',
      }),
    ]),
  });

  const inv = await client.createOrder('JP_5GB_30D');
  assert.equal(inv.orderId, 'ord_abc');
  assert.equal(inv.payTo, '0x742d35cc6634c053');
  assert.equal(inv.amount, '6.21');
  assert.equal(inv.asset, 'USDC');
  assert.equal(inv.chain, 'polygon');
});

test('createOrder throws on non-402 status (contract violation)', async () => {
  const client = new Client({
    baseUrl: BASE,
    fetch: mockFetch([() => jsonResponse(200, { order_id: 'ord_zzz' })]),
  });
  await assert.rejects(() => client.createOrder('JP_5GB_30D'), APIError);
});

test('waitForESim polls until delivered', async () => {
  const provisioning = () => jsonResponse(200, {
    order_id: 'ord_abc',
    status: 'provisioning',
    plan_id: 'JP_5GB_30D',
  });
  const delivered = () => jsonResponse(200, {
    order_id: 'ord_abc',
    status: 'delivered',
    plan_id: 'JP_5GB_30D',
    esim: {
      iccid: '8910300000123456789',
      qr_code_data: 'LPA:1$smdp.example.com$ACTIVATION',
      qr_image_url: 'https://example.com/qr.png',
      activation_link: 'https://esimsetup.apple.com/...',
    },
  });

  const client = new Client({
    baseUrl: BASE,
    fetch: mockFetch([provisioning, provisioning, delivered]),
  });

  const esim = await client.waitForESim('ord_abc', { pollIntervalMs: 1, timeoutMs: 1_000 });
  assert.equal(esim.iccid, '8910300000123456789');
  assert.equal(esim.qrImageUrl, 'https://example.com/qr.png');
});

test('waitForESim throws PaymentExpired on expired status', async () => {
  const client = new Client({
    baseUrl: BASE,
    fetch: mockFetch([
      () => jsonResponse(200, { order_id: 'ord_abc', status: 'expired', plan_id: 'JP_5GB_30D' }),
    ]),
  });
  await assert.rejects(
    () => client.waitForESim('ord_abc', { pollIntervalMs: 1, timeoutMs: 1_000 }),
    PaymentExpired,
  );
});

test('waitForESim throws OrderFailed on failed status', async () => {
  const client = new Client({
    baseUrl: BASE,
    fetch: mockFetch([
      () => jsonResponse(200, { order_id: 'ord_abc', status: 'failed', plan_id: 'JP_5GB_30D' }),
    ]),
  });
  await assert.rejects(
    () => client.waitForESim('ord_abc', { pollIntervalMs: 1, timeoutMs: 1_000 }),
    OrderFailed,
  );
});

test('OrderStatus enum value-equality', () => {
  assert.equal(OrderStatus.Delivered, 'delivered');
  assert.equal(OrderStatus.PendingPayment, 'pending_payment');
});
