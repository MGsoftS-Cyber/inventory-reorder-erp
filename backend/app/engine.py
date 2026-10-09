"""Pure replenishment engine; inputs are already authorized, frozen business data.

This is a transparent demand-rate model, not a trained forecast. It counts all
calendar days (including zero-sale days) and cannot observe demand lost to stockouts.
"""

from decimal import Decimal, ROUND_CEILING

ENGINE_VERSION = "1.0.0"
D = Decimal


def decimal_text(value):
    return format(value.quantize(D("0.0001")), "f")


def calculate(snapshot):
    days = snapshot["lookback_days"]
    rows = []
    for item in snapshot["products"]:
        daily = D(item["sold"]) / days
        stock, incoming = D(item["stock"]), D(item["incoming"])
        safety = daily * item["safety_days"]
        reorder_point = daily * item["lead_days"] + safety
        target = daily * (item["lead_days"] + item["review_days"]) + safety
        position = stock + incoming
        shortage = max(D(0), target - position)
        # Equality is a trigger, but zero observed demand never orders automatically.
        needed = daily > 0 and position <= reorder_point and shortage > 0
        suggestion = D(0)
        if needed:
            base = max(shortage, D(item["minimum_order"]))
            pack = D(item["pack_size"])
            suggestion = (base / pack).to_integral_value(rounding=ROUND_CEILING) * pack
        warnings = []
        if daily == 0:
            warnings.append("No sales observed: review new products, missing history, or stockout periods manually.")
        if incoming > 0:
            warnings.append(
                "Outstanding purchase quantities are included regardless of promised arrival date; check overdue orders."
            )
        rows.append(
            dict(
                product_id=item["id"],
                sku=item["sku"],
                name=item["name"],
                stock=decimal_text(stock),
                incoming=decimal_text(incoming),
                sold=item["sold"],
                revenue=item["revenue"],
                daily_demand=decimal_text(daily),
                coverage_days=decimal_text(stock / daily) if daily else None,
                safety_stock=decimal_text(safety),
                reorder_point=decimal_text(reorder_point),
                target_stock=decimal_text(target),
                suggested_order=decimal_text(suggestion),
                estimated_order_cost=decimal_text(suggestion * D(item["unit_cost"])),
                stock_value=decimal_text(stock * D(item["unit_cost"])),
                slow_moving=item["days_since_sale"] is None or item["days_since_sale"] >= snapshot["slow_days"],
                days_since_sale=item["days_since_sale"],
                turnover_proxy=decimal_text(D(item["sold"]) / stock) if stock else None,
                warnings=warnings,
                supplier_id=item["supplier_id"],
                unit_cost=item["unit_cost"],
                lead_days=item["lead_days"],
            )
        )
    total = sum((D(x["revenue"]) for x in rows), D(0))
    cumulative = D(0)
    for row in sorted(rows, key=lambda x: (-D(x["revenue"]), x["sku"])):
        # Rank by the revenue share BEFORE this item; the boundary-crossing SKU
        # stays in the higher category, with deterministic SKU tie ordering.
        share_before = cumulative / total if total else D(1)
        row["abc"] = "A" if share_before < D(".80") else "B" if share_before < D(".95") else "C"
        cumulative += D(row["revenue"])
    return dict(
        products=rows,
        summary=dict(
            product_count=len(rows),
            reorder_count=sum(D(x["suggested_order"]) > 0 for x in rows),
            slow_count=sum(x["slow_moving"] for x in rows),
            estimated_stock_value=decimal_text(sum((D(x["stock_value"]) for x in rows), D(0))),
            estimated_order_cost=decimal_text(sum((D(x["estimated_order_cost"]) for x in rows), D(0))),
            sales_revenue=decimal_text(total),
        ),
        methodology=dict(
            demand="Observed sold quantity / calendar days",
            inventory_position="On hand + outstanding purchase orders",
            order_policy="Lead time + safety days + review cycle; round upward to pack size",
            valuation="Current product standard cost estimate, not accounting valuation",
            turnover="Units sold / current stock proxy; not COGS / average inventory",
            limitations="No reservations, backorders, seasonality, lost-sales estimation or cross-warehouse pooling.",
        ),
    )
