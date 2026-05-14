/**
 * eSIMx402 client — TypeScript, parity surface with the Python client.
 *
 * Wire protocol (see https://esimx402.com/docs for canonical spec):
 *   GET  /api/v1/x402/plans?country=JP             →  plans array
 *   POST /api/v1/x402/order  { "plan_id": "..." }  →  402 + payment headers
 *   GET  /api/v1/x402/order/{id}                   →  current status
 *
 * This client does NOT sign or send the on-chain transaction. Bring your own
 * wallet — the `Invoice` returned by `createOrder()` is everything you need
 * to send the payment through whatever stack you already use.
 */

const DEFAULT_BASE_URL = 'https://api.esimahora.com';
const DEFAULT_TIMEOUT_MS = 30_000;

// ─── Domain types ──────────────────────────────────────────────────────────

export enum OrderStatus {
  PendingPayment = 'pending_payment',
  Paid = 'paid',
  Provisioning = 'provisioning',
  Delivered = 'delivered',
  Expired = 'expired',
  Refunded = 'refunded',
  Failed = 'failed',
}

export interface Plan {
  readonly id: string;
  readonly country: string;
  readonly countryCode: string;
  readonly dataGb: number;
  readonly validityDays: number;
  readonly priceUsd: number;
  readonly raw: Record<string, unknown>;
}

export interface Invoice {
  readonly orderId: string;
  readonly payTo: string;
  readonly amount: string;   // decimal string — don't round-trip through float
  readonly asset: string;    // USDC | USDT
  readonly chain: string;    // polygon | ton
  readonly expiresAt: string;
}

export interface ESim {
  readonly iccid: string;
  readonly qrCodeData: string;
  readonly qrImageUrl: string;
  readonly activationLink: string | null;
}

export interface Order {
  readonly id: string;
  readonly status: OrderStatus;
  readonly planId: string;
  readonly esim: ESim | null;
  readonly raw: Record<string, unknown>;
}

// ─── Exceptions ────────────────────────────────────────────────────────────

export class APIError extends Error {
  constructor(public readonly status: number, public readonly body: string) {
    super(`eSIMx402 API error ${status}: ${body.slice(0, 200)}`);
    this.name = 'APIError';
  }
}

export class PaymentExpired extends Error {
  constructor(orderId: string) {
    super(`Invoice ${orderId} expired before payment`);
    this.name = 'PaymentExpired';
  }
}

export class OrderFailed extends Error {
  constructor(public readonly order: Order) {
    super(`Order ${order.id} failed with status ${order.status}`);
    this.name = 'OrderFailed';
  }
}

// ─── Parsing helpers ───────────────────────────────────────────────────────

function parsePlan(d: Record<string, unknown>): Plan {
  return {
    id: String(d.id),
    country: String(d.country ?? ''),
    countryCode: String(d.country_code ?? ''),
    dataGb: Number(d.data_gb ?? 0),
    validityDays: Number(d.validity_days ?? 0),
    priceUsd: Number(d.price_usd ?? 0),
    raw: d,
  };
}

function parseOrder(d: Record<string, unknown>): Order {
  const eRaw = d.esim as Record<string, unknown> | undefined;
  const esim: ESim | null = eRaw
    ? {
        iccid: String(eRaw.iccid),
        qrCodeData: String(eRaw.qr_code_data),
        qrImageUrl: String(eRaw.qr_image_url),
        activationLink: (eRaw.activation_link as string | undefined) ?? null,
      }
    : null;
  return {
    id: String(d.order_id),
    status: d.status as OrderStatus,
    planId: String(d.plan_id ?? ''),
    esim,
    raw: d,
  };
}

// ─── Internal HTTP wrapper ─────────────────────────────────────────────────

interface RequestOpts {
  method?: 'GET' | 'POST';
  body?: unknown;
  acceptStatus?: number[];     // statuses other than 200 to treat as success
  signal?: AbortSignal;
}

interface Response<T = unknown> {
  status: number;
  headers: Headers;
  body: T;
}

// ─── Client ────────────────────────────────────────────────────────────────

export interface ClientOptions {
  baseUrl?: string;
  timeoutMs?: number;
  fetch?: typeof globalThis.fetch;
}

export class Client {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly fetchFn: typeof globalThis.fetch;

  constructor(opts: ClientOptions = {}) {
    this.baseUrl = (opts.baseUrl ?? DEFAULT_BASE_URL).replace(/\/$/, '');
    this.timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.fetchFn = opts.fetch ?? globalThis.fetch.bind(globalThis);
  }

  /** List eSIM plans, optionally filtered by ISO-3166-1 alpha-2 country code. */
  async listPlans(country?: string): Promise<Plan[]> {
    const url = country
      ? `${this.baseUrl}/api/v1/x402/plans?country=${encodeURIComponent(country)}`
      : `${this.baseUrl}/api/v1/x402/plans`;
    const r = await this.request(url, {});
    const body = r.body as { plans?: Array<Record<string, unknown>> };
    return (body.plans ?? []).map(parsePlan);
  }

  /** Create an order. Server returns 402 with payment details in headers. */
  async createOrder(planId: string, callbackUrl?: string): Promise<Invoice> {
    const url = `${this.baseUrl}/api/v1/x402/order`;
    const body: Record<string, unknown> = { plan_id: planId };
    if (callbackUrl) body.callback_url = callbackUrl;
    const r = await this.request(url, { method: 'POST', body, acceptStatus: [402] });
    const rb = r.body as { order_id?: string };
    const orderId = rb.order_id ?? r.headers.get('x-order-id') ?? '';
    const required = (k: string): string => {
      const v = r.headers.get(k);
      if (!v) throw new APIError(r.status, `Missing required header ${k}`);
      return v;
    };
    return {
      orderId,
      payTo: required('x-payto'),
      amount: required('x-amount'),
      asset: required('x-asset'),
      chain: required('x-chain'),
      expiresAt: r.headers.get('x-expires') ?? '',
    };
  }

  /** Get current order state. */
  async getOrder(orderId: string): Promise<Order> {
    const url = `${this.baseUrl}/api/v1/x402/order/${encodeURIComponent(orderId)}`;
    const r = await this.request(url, {});
    return parseOrder(r.body as Record<string, unknown>);
  }

  /**
   * Poll until the order is DELIVERED, or throw on a terminal failure.
   * Default ceiling 120 s; tune for your latency requirements.
   */
  async waitForESim(
    orderId: string,
    { timeoutMs = 120_000, pollIntervalMs = 2_000 } = {},
  ): Promise<ESim> {
    const terminalFailures = new Set([
      OrderStatus.Expired,
      OrderStatus.Refunded,
      OrderStatus.Failed,
    ]);
    const deadline = Date.now() + timeoutMs;
    while (true) {
      const order = await this.getOrder(orderId);
      if (order.status === OrderStatus.Delivered && order.esim) return order.esim;
      if (order.status === OrderStatus.Expired) throw new PaymentExpired(orderId);
      if (terminalFailures.has(order.status)) throw new OrderFailed(order);
      if (Date.now() >= deadline) {
        throw new Error(`Order ${orderId} still ${order.status} after ${timeoutMs}ms`);
      }
      await new Promise((r) => setTimeout(r, pollIntervalMs));
    }
  }

  // ─ Internal ─

  private async request(url: string, opts: RequestOpts): Promise<Response> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const res = await this.fetchFn(url, {
        method: opts.method ?? 'GET',
        headers: opts.body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
        body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
        signal: opts.signal ?? controller.signal,
      });
      const accepted = new Set<number>([200, ...(opts.acceptStatus ?? [])]);
      if (!accepted.has(res.status)) {
        const text = await res.text().catch(() => '');
        throw new APIError(res.status, text);
      }
      const body = res.headers.get('content-type')?.includes('application/json')
        ? await res.json()
        : await res.text();
      return { status: res.status, headers: res.headers, body };
    } finally {
      clearTimeout(timeoutId);
    }
  }
}
