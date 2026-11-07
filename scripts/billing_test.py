"""Stripe sandbox billing is not implemented. This command must not contact Stripe."""

from __future__ import annotations

import sys


def main() -> int:
    print("Billing tests are not implemented.")
    print("Phase 5 must create the 1499-cent monthly price and a 14-day trial in a Stripe sandbox.")
    print("No Stripe API was called. PRODUCTION_BILLING_ENABLED must stay false.")
    print("Required later: STRIPE_SECRET_KEY (sk_test_ only), STRIPE_WEBHOOK_SECRET,")
    print("STRIPE_MONTHLY_PRICE_ID.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
