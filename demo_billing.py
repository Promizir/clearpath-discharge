"""Exercise the billing worker independently before adding it to the workflow."""

import asyncio

from agents import check_billing


async def main() -> None:
    result = await check_billing("PT-402")
    print("Billing check:", result.status)
    for item in result.discrepancies:
        print(
            f"{item.item_id}: used={item.used_quantity}, "
            f"billed={item.billed_quantity}, difference={item.quantity_difference:+d}"
        )
    print("Comparison only: the bill has not been changed.")


if __name__ == "__main__":
    asyncio.run(main())
