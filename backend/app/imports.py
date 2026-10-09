"""CSV demand feeds are historical observations, never physical stock adjustments."""

import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation


def preview_demand(text):
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != ["date", "sku", "quantity", "revenue"]:
        return dict(rows=[], errors=[dict(row=1, message="Required header: date,sku,quantity,revenue")], valid=False)
    rows = []
    errors = []
    for index, row in enumerate(reader, 2):
        if index > 5001:
            errors.append(dict(row=index, message="Maximum 5,000 demand rows."))
            break
        try:
            day = date.fromisoformat(row["date"])
            qty = Decimal(row["quantity"])
            revenue = Decimal(row["revenue"])
            if (
                day > date.today()
                or not qty.is_finite()
                or not revenue.is_finite()
                or qty <= 0
                or qty > Decimal("1e9")
                or revenue < 0
                or revenue > Decimal("1e12")
            ):
                raise ValueError()
            if (
                qty.as_tuple().exponent < -4
                or revenue.as_tuple().exponent < -4
                or not row["sku"]
                or len(row["sku"]) > 40
                or None in row
            ):
                raise ValueError()
            rows.append(dict(date=str(day), sku=row["sku"], quantity=str(qty), revenue=str(revenue)))
        except (ValueError, InvalidOperation, TypeError, KeyError):
            errors.append(
                dict(
                    row=index,
                    message="Invalid date, SKU, positive quantity, or nonnegative revenue (maximum four decimal places).",
                )
            )
    if not rows:
        errors.append(dict(row=1, message="Provide at least one valid demand row."))
    return dict(rows=rows, errors=errors, valid=not errors)
