/**
 * 01 — Buy an eSIM end-to-end.
 *
 * The simplest possible flow: pick a country, find the cheapest plan, request
 * the order, pay the on-chain invoice, get back a QR code.
 *
 * Run:
 *   npx tsx examples/01-buy-esim.ts JP
 *
 * Bring your own wallet — `pay()` below is a placeholder you must implement
 * against your wallet stack (ethers, viem, web3.js, a hardware signer, etc.).
 */

import { Client, type Invoice } from '../src/index.js';

async function pay(invoice: Invoice): Promise<void> {
  // Example with viem for Polygon USDC (sketch — wire your own keys):
  //
  //   import { createWalletClient, http, parseUnits } from 'viem';
  //   import { polygon } from 'viem/chains';
  //
  //   const wallet = createWalletClient({
  //     account: privateKeyToAccount(PRIVATE_KEY),
  //     chain: polygon,
  //     transport: http(),
  //   });
  //
  //   const hash = await wallet.writeContract({
  //     address: USDC_POLYGON,
  //     abi: ERC20_ABI,
  //     functionName: 'transfer',
  //     args: [invoice.payTo, parseUnits(invoice.amount, 6)],
  //   });
  throw new Error(
    `Implement on-chain payment of ${invoice.amount} ${invoice.asset} ` +
    `on ${invoice.chain} to ${invoice.payTo}`,
  );
}

async function main(country: string): Promise<void> {
  const client = new Client();

  // 1. Find the cheapest plan for the country
  const plans = await client.listPlans(country);
  if (plans.length === 0) {
    console.error(`No plans available for ${country}`);
    process.exit(1);
  }
  const plan = plans.reduce((a, b) => (a.priceUsd < b.priceUsd ? a : b));
  console.log(`Selected: ${plan.id} (${plan.dataGb}GB / ${plan.validityDays}d / $${plan.priceUsd.toFixed(2)})`);

  // 2. Request the order — server replies 402 with on-chain payment details
  const invoice = await client.createOrder(plan.id);
  console.log(`Pay ${invoice.amount} ${invoice.asset} on ${invoice.chain} → ${invoice.payTo}`);

  // 3. Pay it (bring your own wallet)
  await pay(invoice);

  // 4. Wait for eSIM provisioning
  const esim = await client.waitForESim(invoice.orderId);
  console.log(`eSIM ready: ${esim.qrImageUrl}`);
  if (esim.activationLink) console.log(`Activation link: ${esim.activationLink}`);
}

main(process.argv[2] ?? 'JP').catch((err) => {
  console.error(err);
  process.exit(1);
});
