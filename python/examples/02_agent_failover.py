"""
02 — Agent / VPS autonomous failover.

A monitoring or trading bot deployed on a VPS in a remote region needs
fallback connectivity when its primary uplink degrades. Buying a SIM card
via human procurement takes hours; the failover window is seconds.

This pattern: pre-loaded treasury wallet + health check → x402 → cellular
modem inserts the eSIM → service back online in ~30 seconds.

Run as a daemon. Skeleton only — wire your own modem control + health probe.
"""

from __future__ import annotations

import time

from esimx402 import Client


def primary_link_healthy() -> bool:
    """Probe to determine whether the primary uplink is up. Replace with your
    real check — e.g. ping a known external host, check interface state,
    measure packet loss."""
    raise NotImplementedError("Implement primary-link health check")


def detect_region() -> str:
    """Where am I? Reply with an ISO 2-letter country code.
    GPS, ip-geolocation, hardcode for a fixed deployment — your call."""
    raise NotImplementedError("Implement region detection")


def insert_esim(qr_code_data: str) -> None:
    """Hand the eSIM activation string to the device's cellular modem.
    On many embedded Linux setups this means writing to ModemManager via
    DBus. On macOS/iOS you use the eSIM activation link instead."""
    raise NotImplementedError("Implement modem eSIM install")


def pay_from_treasury(pay_to: str, amount: str, chain: str, asset: str) -> None:
    """Send the on-chain payment from a pre-funded treasury wallet."""
    raise NotImplementedError("Implement on-chain payment")


def main() -> None:
    client = Client()

    while True:
        if primary_link_healthy():
            time.sleep(30)
            continue

        # Primary down. Buy emergency local data.
        region = detect_region()  # e.g. "VN"
        print(f"Primary down — purchasing emergency eSIM in {region}")

        plans = client.list_plans(country=region)
        # Prefer the smallest plan that fits a few hours of operation.
        candidates = sorted(plans, key=lambda p: p.price_usd)
        plan = next((p for p in candidates if p.data_gb >= 1), candidates[0])

        invoice = client.create_order(plan_id=plan.id)
        pay_from_treasury(invoice.pay_to, invoice.amount, invoice.chain, invoice.asset)

        esim = client.wait_for_esim(invoice.order_id, timeout=60)
        insert_esim(esim.qr_code_data)
        print(f"Failover online in {region} ({plan.data_gb}GB / {plan.validity_days}d)")

        # Don't immediately re-probe — give the new uplink time to come up.
        time.sleep(60)


if __name__ == "__main__":
    main()
