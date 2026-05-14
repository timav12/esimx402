"""
01 — Buy an eSIM end-to-end.

The simplest possible flow: pick a country, find the cheapest plan, request
the order, pay the on-chain invoice, get back a QR code.

Run:
    python 01_buy_esim.py JP   # buy data for Japan

Bring your own wallet — this example uses a placeholder `pay()` function that
you must implement against your wallet stack (web3.py, ethers.js, a hardware
wallet, etc.). The library deliberately stays out of the signing path.
"""

from __future__ import annotations

import sys

from esimx402 import Client, Invoice


def pay(invoice: Invoice) -> None:
    """Implement against your wallet of choice.

    Example with web3.py for Polygon USDC (sketch — wire your own keys):

        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))
        usdc = w3.eth.contract(address=USDC_POLYGON, abi=ERC20_ABI)
        tx = usdc.functions.transfer(
            invoice.pay_to,
            int(float(invoice.amount) * 10**6),  # USDC has 6 decimals
        ).build_transaction({"from": MY_ADDRESS, "nonce": w3.eth.get_transaction_count(MY_ADDRESS)})
        signed = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
        w3.eth.send_raw_transaction(signed.rawTransaction)
    """
    raise NotImplementedError(
        f"Implement on-chain payment of {invoice.amount} {invoice.asset} "
        f"on {invoice.chain} to {invoice.pay_to}"
    )


def main(country: str) -> int:
    with Client() as client:
        # 1. Find the cheapest plan for the country
        plans = client.list_plans(country=country)
        if not plans:
            print(f"No plans available for {country}")
            return 1
        plan = min(plans, key=lambda p: p.price_usd)
        print(f"Selected: {plan.id} ({plan.data_gb}GB / {plan.validity_days}d / ${plan.price_usd:.2f})")

        # 2. Request the order — server replies 402 with on-chain payment details
        invoice = client.create_order(plan_id=plan.id)
        print(f"Pay {invoice.amount} {invoice.asset} on {invoice.chain} → {invoice.pay_to}")

        # 3. Pay it (bring your own wallet)
        pay(invoice)

        # 4. Wait for eSIM provisioning
        esim = client.wait_for_esim(invoice.order_id)
        print(f"eSIM ready: {esim.qr_image_url}")
        if esim.activation_link:
            print(f"Activation link: {esim.activation_link}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "JP"))
