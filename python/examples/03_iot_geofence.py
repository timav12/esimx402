"""
03 — IoT device crossing borders, no ops console.

A trail camera, shipping container sensor, or logistics tracker moves
between countries (rail, sea, road freight). Each border crossing needs new
local data — no central ops console can predict the schedule.

Pattern: GPS-driven geofence trigger → autonomous x402 purchase → onboard
eSIM activation. Treasury wallet topped up remotely once per quarter.

Skeleton for embedded Python (Raspberry Pi-class). Wire your own GPS,
wallet, and modem control.
"""

from __future__ import annotations

import time

from esimx402 import Client


def get_current_country() -> str:
    """Read latest GPS fix → country code via offline lookup table."""
    raise NotImplementedError


def has_local_data() -> bool:
    """Does the modem currently have an active data plan in the current country?"""
    raise NotImplementedError


def wallet_send(pay_to: str, amount: str, chain: str, asset: str) -> None:
    """Self-custodial signer on the device. Stores private key in TPM or
    similar; never leaves the device."""
    raise NotImplementedError


def modem_install_esim(qr_code_data: str) -> None:
    """Activate the new eSIM profile on the device modem."""
    raise NotImplementedError


def main() -> None:
    client = Client()
    last_country: str | None = None

    while True:
        country = get_current_country()

        if country != last_country and not has_local_data():
            print(f"Crossed into {country} — provisioning eSIM autonomously")

            plans = client.list_plans(country=country)
            # 3GB / 15-day plan is a reasonable default for IoT telemetry.
            plan = next((p for p in plans if p.data_gb >= 3 and p.validity_days >= 15), plans[0])

            invoice = client.create_order(plan_id=plan.id)
            wallet_send(invoice.pay_to, invoice.amount, invoice.chain, invoice.asset)

            esim = client.wait_for_esim(invoice.order_id, timeout=120)
            modem_install_esim(esim.qr_code_data)

            print(f"Online in {country} — ${plan.price_usd:.2f} spent from treasury")
            last_country = country

        time.sleep(60)  # poll GPS once a minute


if __name__ == "__main__":
    main()
