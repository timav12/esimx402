/**
 * 02 — Agent / VPS autonomous failover.
 *
 * A monitoring or trading bot deployed on a VPS in a remote region needs
 * fallback connectivity when its primary uplink degrades. Buying a SIM card
 * via human procurement takes hours; the failover window is seconds.
 *
 * Pattern: pre-loaded treasury wallet + health check → x402 → cellular
 * modem inserts the eSIM → service back online in ~30 seconds.
 *
 * Skeleton only — wire your own modem control + health probe.
 */

import { Client } from '../src/index.js';

declare function primaryLinkHealthy(): Promise<boolean>;
declare function detectRegion(): Promise<string>;
declare function insertESim(qrCodeData: string): Promise<void>;
declare function payFromTreasury(payTo: string, amount: string, chain: string, asset: string): Promise<void>;

async function main(): Promise<void> {
  const client = new Client();

  for (;;) {
    if (await primaryLinkHealthy()) {
      await new Promise((r) => setTimeout(r, 30_000));
      continue;
    }

    // Primary down. Buy emergency local data.
    const region = await detectRegion();  // e.g. "VN"
    console.log(`Primary down — purchasing emergency eSIM in ${region}`);

    const plans = await client.listPlans(region);
    const candidates = [...plans].sort((a, b) => a.priceUsd - b.priceUsd);
    const plan = candidates.find((p) => p.dataGb >= 1) ?? candidates[0]!;

    const invoice = await client.createOrder(plan.id);
    await payFromTreasury(invoice.payTo, invoice.amount, invoice.chain, invoice.asset);

    const esim = await client.waitForESim(invoice.orderId, { timeoutMs: 60_000 });
    await insertESim(esim.qrCodeData);
    console.log(`Failover online in ${region} (${plan.dataGb}GB / ${plan.validityDays}d)`);

    // Don't immediately re-probe — give the new uplink time to come up.
    await new Promise((r) => setTimeout(r, 60_000));
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
