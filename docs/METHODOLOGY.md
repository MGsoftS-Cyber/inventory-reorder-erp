# Inventory analytics methodology

The window ends on the server's current UTC date. Start = today - lookback + 1, inclusive. Daily demand d = observed sold units / all calendar days. Physical movements are posted now; imported historical observations do not change stock. Demand combines posted sale movements with historical CSV observations. Avoid overlapping sources.

Safety stock = d * safety_days. Reorder point = d * lead_days + safety stock. Inventory position = on_hand + unreceived quantities on ordered/partial purchase orders. Target stock = d * (lead_days + review_days) + safety stock. Trigger when d > 0 and position <= reorder point. Suggested quantity = ceil(max(target-position,minimum_order)/pack_size) * pack_size. A shortage must be positive. No sale history means no automatic order and an explanatory warning.

Example: d=3, lead=10, safety=5, review=7, stock=18, incoming=0. Safety=15; reorder point=45; target=66. Shortage=48; pack=10; suggestion=50. At cost USD20, estimated purchase cost=USD1000. If 50 units are ordered, position becomes 68 and a fresh analysis suggests zero. Receiving 20 changes stock to38 and incoming to30; position remains68. Cancelling the remaining order removes its unreceived quantities only.

ABC sorts observed revenue descending (SKU tie-break). Revenue share before each item selects A below80%, B below95%, otherwise C; the boundary-crossing item stays in the higher category. With no revenue all items are C. Slow-moving means no known sale or at least slow_days since the latest observation. Imported absent history must not be confused with proof of no demand.

Coverage = on_hand/d, null when d=0. Turnover proxy = sold units/current stock, null when stock=0. It is NOT conventional COGS/average-inventory turnover. Stock value = current quantity * current standard cost; it is NOT a statutory valuation. No depreciation, purchase-lot valuation or foreign exchange is modeled.

Incoming stock includes all open orders regardless of expected date. Review overdue orders. Supplier observed lead time is the arithmetic average of receipt-event day minus order day, including partial receipts; configured lead days are not automatically replaced. Safety days are a user policy, not a statistical service-level calculation.

Extensions: true average-inventory valuation, stockout-censored demand, variable lead-time distributions, seasonal forecasts, safety stock by service level, reservations/backorders, units of measure, expiry/batches, multi-warehouse pooling and EOQ when cost assumptions justify it.
