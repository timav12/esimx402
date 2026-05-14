/**
 * 03 — IoT device crossing borders, no ops console.
 *
 * A trail camera, shipping container sensor, or logistics tracker moves
 * between countries (rail, sea, road freight). Each border crossing needs new
 * local data — no central ops console can predict the schedule.
 *
 * Pattern: GPS-driven geofence trigger → autonomous x402 purchase → onboard
 * eSIM activation. Treasury wallet topped up remotely once per quarter.
 *
 * Skeleton for embedded Node (Pi-class hardware running modern Node). Wire
 * your own GPS, wallet, and modem control.
 */

import { Client } from '../src/index.js';

declare function getCurrentCountry(): Promise<string>;
declare function hasLocalData(): Promise<boolean>;
declare function walletSend(payTo: string, amount: string, chain: string, asset: string): Promise<void>;
declare function modemInstallESim(qrCodeData: string): Promise<void>;

async function main(): Promise<void> {
  const client = new Client();
  let lastCountry: string | null = null;

  for (;;) {
    const country = await getCurrentCountry();

    if (country !== lastCountry && !(await hasLocalData())) {
      console.log(`Crossed into ${country} — provisioning eSIM autonomously`);

      const plans = await client.listPlans(country);
      // 3GB / 15-day plan is a reasonable default for IoT telemetry.
      const plan = plans.find((p) => p.dataGb >= 3 && p.validityDays >= 15) ?? plans[0]!;

      const invoice = await client.createOrder(plan.id);
      await walletSend(invoice.payTo, invoice.amount, invoice.chain, invoice.asset);

      const esim = await client.waitForESim(invoice.orderId, { timeoutMs: 120_000 });
      await modemInstallESim(esim.qrCodeData);

      console.log(`Online in ${country} — $${plan.priceUsd.toFixed(2)} spent from treasury`);
      lastCountry = country;
    }

    await new Promise((r) => setTimeout(r, 60_000));  // poll GPS once a minute
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
