/** Application workflows use an HTTP adapter; financial and stock rules live in Python. */
import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, setCsrfToken } from "./api";
import AuthScreen from "./components/AuthScreen";
import "./styles.css";
const money = (v) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
    Number(v),
  );
const number = (v) =>
  v == null
    ? "No demand"
    : Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 });
function Field({ label, children }) {
  return (
    <label>
      {label}
      {children}
    </label>
  );
}
function App() {
  const [user, U] = useState(null),
    [busy, B] = useState(false),
    [error, E] = useState(""),
    [message, M] = useState(""),
    [tab, T] = useState("Overview"),
    [suppliers, S] = useState([]),
    [warehouses, W] = useState([]),
    [products, P] = useState([]),
    [balances, Q] = useState([]),
    [moves, G] = useState([]),
    [orders, O] = useState([]),
    [analyses, A] = useState([]),
    [performance, F] = useState([]),
    [warehouse, H] = useState(""),
    [result, R] = useState(null),
    [lookback, L] = useState(90),
    [csv, C] = useState(""),
    [preview, V] = useState(null),
    [edit, J] = useState(null);
  async function load() {
    const data = await Promise.all(
      [
        "/suppliers",
        "/warehouses",
        "/products",
        "/balances",
        "/movements",
        "/purchase-orders",
        "/analyses",
        "/supplier-performance",
      ].map((p) => api("/v1" + p)),
    );
    S(data[0]);
    W(data[1]);
    P(data[2]);
    Q(data[3]);
    G(data[4]);
    O(data[5]);
    A(data[6]);
    F(data[7]);
    H((old) => old || data[1][0]?.id || "");
  }
  async function task(fn) {
    B(true);
    E("");
    M("");
    try {
      await fn();
    } catch (e) {
      E(e.message);
    } finally {
      B(false);
    }
  }
  async function write(path, body) {
    return api("/v1" + path, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
  }
  useEffect(() => {
    api("/auth/session")
      .then(async (s) => {
        U(s.user);
        setCsrfToken(s.csrf_token);
        await load();
      })
      .catch(() => {});
  }, []);
  async function auth(registering, body) {
    await task(async () => {
      let s = await api("/auth/" + (registering ? "register" : "login"), {
        method: "POST",
        body: JSON.stringify(body),
      });
      U(s.user);
      setCsrfToken(s.csrf_token);
      await load();
    });
  }
  function submit(event, fn) {
    event.preventDefault();
    const form = event.currentTarget;
    const d = Object.fromEntries(new FormData(form));
    task(async () => {
      await fn(d);
      await load();
      form.reset();
      M("Saved successfully. Review the updated records below.");
    });
  }
  const productName = (id) => products.find((p) => p.id === id)?.name || id;
  const whName = (id) => warehouses.find((w) => w.id === id)?.name || id;
  const supplierName = (id) =>
    suppliers.find((s) => s.id === id)?.name || "Unassigned";
  const selects = (list, label, name) => (
    <Field label={label}>
      <select aria-label={label} name={name} required>
        <option value="">Choose {label.toLowerCase()}</option>
        {list.map((x) => (
          <option key={x.id} value={x.id}>
            {x.name}
          </option>
        ))}
      </select>
    </Field>
  );
  if (!user) return <AuthScreen onSubmit={auth} busy={busy} error={error} />;
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <span>▦</span>
          <div>
            InventoryIQ<small>Inventory & reorder ERP</small>
          </div>
        </div>
        <nav>
          {[
            "Overview",
            "Catalog",
            "Stock",
            "Purchasing",
            "Demand imports",
            "Reports",
          ].map((x) => (
            <button
              key={x}
              className={tab === x ? "active" : ""}
              onClick={() => T(x)}
            >
              {x}
            </button>
          ))}
        </nav>
        <div className="account">
          <small>{user.email}</small>
          <button
            onClick={() =>
              task(async () => {
                await api("/auth/logout", { method: "POST" });
                U(null);
                setCsrfToken("");
              })
            }
          >
            Sign out
          </button>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <p className="eyebrow">OPERATIONS / {tab.toUpperCase()}</p>
            <h1>
              {tab === "Overview"
                ? "Keep the right stock at the right time"
                : tab}
            </h1>
            <p className="muted">
              Clear inventory decisions, traceable stock movements, and
              reviewable purchases.
            </p>
          </div>
          <div className="warehouse-select">
            <Field label="Active warehouse">
              <select
                aria-label="Active warehouse"
                value={warehouse}
                onChange={(e) => H(e.target.value)}
              >
                <option value="">Select warehouse</option>
                {warehouses.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        </header>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {message && (
          <p className="success" role="status">
            {message}
          </p>
        )}
        {busy && (
          <p className="muted" role="status">
            Saving or loading…
          </p>
        )}
        {tab === "Overview" && (
          <>
            <section className="card">
              <div className="section-head">
                <div>
                  <h2>Replenishment analysis</h2>
                  <p className="muted">
                    Suggestions require review. Creating a purchase order does
                    not contact a supplier.
                  </p>
                </div>
                {!products.length && (
                  <button
                    disabled={busy}
                    onClick={() =>
                      task(async () => {
                        let d = await write("/demo");
                        H(d.warehouse_id);
                        await load();
                        M(d.message);
                      })
                    }
                  >
                    Load demo data
                  </button>
                )}
              </div>
              <div className="controls">
                <Field label="Sales lookback days">
                  <input
                    aria-label="Sales lookback days"
                    type="number"
                    min="7"
                    max="730"
                    value={lookback}
                    onChange={(e) => L(Number(e.target.value))}
                  />
                </Field>
                <button
                  disabled={busy || !warehouse}
                  onClick={() =>
                    task(async () => {
                      R(
                        await write("/analyses", {
                          warehouse_id: warehouse,
                          lookback_days: lookback,
                          slow_days: 30,
                        }),
                      );
                      await load();
                    })
                  }
                >
                  Run inventory analysis
                </button>
              </div>
            </section>
            {result ? (
              <>
                <div className="metrics">
                  {[
                    ["Products", result.results.summary.product_count],
                    ["Need reorder", result.results.summary.reorder_count],
                    ["Slow-moving", result.results.summary.slow_count],
                    [
                      "Estimated stock value",
                      money(result.results.summary.estimated_stock_value),
                    ],
                  ].map(([k, v]) => (
                    <div className="metric" key={k}>
                      <small>{k}</small>
                      <strong>{v}</strong>
                    </div>
                  ))}
                </div>
                <section className="card">
                  <div className="section-head">
                    <div>
                      <h2>Recommended replenishment</h2>
                      <p className="muted">
                        Saved {result.inputs.as_of} ·{" "}
                        {whName(result.inputs.warehouse_id)} ·{" "}
                        {result.inputs.lookback_days} calendar days
                      </p>
                    </div>
                    <span className="pill">
                      Estimated order cost{" "}
                      {money(result.results.summary.estimated_order_cost)}
                    </span>
                  </div>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          {[
                            "Product",
                            "Stock",
                            "Incoming",
                            "Days coverage",
                            "ABC",
                            "Order qty",
                            "Action",
                          ].map((x) => (
                            <th key={x}>{x}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {result.results.products.map((x) => (
                          <tr key={x.product_id}>
                            <td>
                              <b>{x.name}</b>
                              <small>{x.sku}</small>
                            </td>
                            <td>{number(x.stock)}</td>
                            <td>{number(x.incoming)}</td>
                            <td>{number(x.coverage_days)}</td>
                            <td>
                              <span className={"badge " + x.abc}>{x.abc}</span>
                            </td>
                            <td>{number(x.suggested_order)}</td>
                            <td>
                              <button
                                className="small"
                                disabled={
                                  busy ||
                                  Number(x.suggested_order) <= 0 ||
                                  !x.supplier_id
                                }
                                onClick={() =>
                                  task(async () => {
                                    const expected = new Date();
                                    expected.setDate(
                                      expected.getDate() + x.lead_days,
                                    );
                                    const date = [
                                      expected.getFullYear(),
                                      String(expected.getMonth() + 1).padStart(
                                        2,
                                        "0",
                                      ),
                                      String(expected.getDate()).padStart(
                                        2,
                                        "0",
                                      ),
                                    ].join("-");
                                    await write("/purchase-orders", {
                                      supplier_id: x.supplier_id,
                                      warehouse_id: result.inputs.warehouse_id,
                                      expected_date: date,
                                      lines: [
                                        {
                                          product_id: x.product_id,
                                          quantity: x.suggested_order,
                                          unit_cost: x.unit_cost,
                                        },
                                      ],
                                    });
                                    await load();
                                    T("Purchasing");
                                    M(
                                      "Purchase order created for review. No external message was sent.",
                                    );
                                  })
                                }
                              >
                                Create order
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
                <section className="card">
                  <h2>How suggestions are calculated</h2>
                  <div className="grid three">
                    <div>
                      <h3>1 · Measure demand</h3>
                      <p>
                        Sold units divided by every calendar day in the selected
                        window, including zero-sales days.
                      </p>
                    </div>
                    <div>
                      <h3>2 · Check inventory position</h3>
                      <p>
                        On-hand stock plus open purchase quantities. Review
                        overdue deliveries before relying on them.
                      </p>
                    </div>
                    <div>
                      <h3>3 · Round the order</h3>
                      <p>
                        Cover lead time, safety days and the review cycle. Apply
                        the minimum quantity and pack size.
                      </p>
                    </div>
                  </div>
                  <p className="muted">
                    Observed sales can understate demand during stockouts. Stock
                    value uses current standard cost; turnover is a
                    units/current-stock proxy.
                  </p>
                </section>
              </>
            ) : (
              <section className="empty card">
                <h2>Start with your catalog or demo data</h2>
                <p>
                  Create a warehouse, supplier and products. Record stock,
                  import historical demand, then run your first analysis.
                </p>
              </section>
            )}
          </>
        )}
        {tab === "Catalog" && (
          <>
            <div className="grid two">
              <section className="card">
                <h2>New supplier</h2>
                <form
                  onSubmit={(e) => submit(e, (d) => write("/suppliers", d))}
                >
                  <Field label="Supplier name">
                    <input
                      name="name"
                      aria-label="Supplier name"
                      required
                      maxLength={120}
                    />
                  </Field>
                  <Field label="Supplier email">
                    <input
                      name="email"
                      aria-label="Supplier email"
                      type="email"
                    />
                  </Field>
                  <button disabled={busy}>Save supplier</button>
                </form>
              </section>
              <section className="card">
                <h2>New warehouse</h2>
                <form
                  onSubmit={(e) => submit(e, (d) => write("/warehouses", d))}
                >
                  <Field label="Warehouse name">
                    <input
                      name="name"
                      aria-label="Warehouse name"
                      required
                      maxLength={120}
                    />
                  </Field>
                  <button disabled={busy}>Save warehouse</button>
                </form>
                <p className="muted">
                  {warehouses.map((w) => w.name).join(" · ") ||
                    "No warehouses yet"}
                </p>
              </section>
            </div>
            <section className="card">
              <h2>{edit ? "Edit product" : "New product"}</h2>
              <form
                key={edit?.id || "new"}
                onSubmit={(e) =>
                  submit(e, async (d) => {
                    const fields = [
                      "lead_days",
                      "safety_days",
                      "review_days",
                      "pack_size",
                      "minimum_order",
                    ];
                    fields.forEach((k) => (d[k] = Number(d[k])));
                    d.supplier_id = d.supplier_id || null;
                    if (edit) {
                      await api("/v1/products/" + edit.id, {
                        method: "PATCH",
                        headers: { "Idempotency-Key": crypto.randomUUID() },
                        body: JSON.stringify(d),
                      });
                      J(null);
                    } else await write("/products", d);
                  })
                }
              >
                <div className="grid three">
                  {[
                    ["SKU", "sku", "text", "", true],
                    ["Product name", "name", "text", "", true],
                    ["Unit", "unit", "text", "unit", true],
                    ["Unit cost (USD)", "unit_cost", "number", "0", true],
                    [
                      "Selling price (USD)",
                      "selling_price",
                      "number",
                      "0",
                      true,
                    ],
                    ["Lead days", "lead_days", "number", 7, true],
                    ["Safety days", "safety_days", "number", 7, true],
                    ["Review days", "review_days", "number", 7, true],
                    ["Pack size", "pack_size", "number", 1, true],
                    ["Minimum order", "minimum_order", "number", 1, true],
                  ].map(([label, name, type, val, required]) => (
                    <Field label={label} key={name}>
                      <input
                        aria-label={label}
                        name={name}
                        type={type}
                        step={
                          ["unit_cost", "selling_price"].includes(name)
                            ? ".0001"
                            : "1"
                        }
                        min={type === "number" ? 0 : undefined}
                        defaultValue={edit?.[name] ?? val}
                        required={required}
                      />
                    </Field>
                  ))}
                  <Field label="Product supplier">
                    <select
                      aria-label="Product supplier"
                      name="supplier_id"
                      defaultValue={edit?.supplier_id || ""}
                    >
                      <option value="">Unassigned</option>
                      {suppliers.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                </div>
                <button disabled={busy}>Save product</button>
                {edit && (
                  <button
                    className="text-button"
                    onClick={() => J(null)}
                    type="button"
                  >
                    Cancel editing
                  </button>
                )}
              </form>
            </section>
            <section className="card">
              <h2>Product catalog</h2>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>SKU</th>
                      <th>Name</th>
                      <th>Supplier</th>
                      <th>Cost</th>
                      <th>Lead time</th>
                      <th>Edit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {products.map((p) => (
                      <tr key={p.id}>
                        <td>{p.sku}</td>
                        <td>{p.name}</td>
                        <td>{supplierName(p.supplier_id)}</td>
                        <td>{money(p.unit_cost)}</td>
                        <td>{p.lead_days} days</td>
                        <td>
                          <button className="text-button" onClick={() => J(p)}>
                            Edit {p.sku}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
        {tab === "Stock" && (
          <>
            <section className="card">
              <h2>Record stock movement</h2>
              <p className="muted">
                Receipts add stock. Sales and issues remove it. A sale also
                records demand at the current selling price. Transfers update
                both warehouses together.
              </p>
              <form
                onSubmit={(e) =>
                  submit(e, (d) => {
                    d.destination_id = d.destination_id || null;
                    return write("/movements", d);
                  })
                }
              >
                <div className="grid three">
                  {selects(products, "Movement product", "product_id")}
                  {selects(warehouses, "Source warehouse", "warehouse_id")}
                  <Field label="Movement type">
                    <select aria-label="Movement type" name="kind">
                      {[
                        "receipt",
                        "sale",
                        "issue",
                        "adjustment_in",
                        "adjustment_out",
                        "transfer",
                      ].map((x) => (
                        <option key={x}>{x}</option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Quantity">
                    <input
                      name="quantity"
                      aria-label="Quantity"
                      type="number"
                      min=".0001"
                      step=".0001"
                      required
                    />
                  </Field>
                  <Field label="Transfer destination">
                    <select
                      aria-label="Transfer destination"
                      name="destination_id"
                    >
                      <option value="">For transfers only</option>
                      {warehouses.map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Movement note">
                    <input
                      name="note"
                      aria-label="Movement note"
                      required
                      maxLength={500}
                    />
                  </Field>
                </div>
                <button disabled={busy}>Post stock movement</button>
              </form>
            </section>
            <div className="grid two">
              <section className="card">
                <h2>Stock balances</h2>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Product</th>
                        <th>Warehouse</th>
                        <th>Quantity</th>
                      </tr>
                    </thead>
                    <tbody>
                      {balances.map((x) => (
                        <tr key={x.product_id + x.warehouse_id}>
                          <td>{productName(x.product_id)}</td>
                          <td>{whName(x.warehouse_id)}</td>
                          <td>{number(x.quantity)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
              <section className="card">
                <h2>Movement history</h2>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Product</th>
                        <th>Type</th>
                        <th>Change</th>
                        <th>Note</th>
                      </tr>
                    </thead>
                    <tbody>
                      {moves.slice(0, 100).map((x) => (
                        <tr key={x.id}>
                          <td>{productName(x.product_id)}</td>
                          <td>{x.kind}</td>
                          <td>{number(x.quantity_delta)}</td>
                          <td>{x.note}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          </>
        )}
        {tab === "Purchasing" && (
          <>
            <section className="card">
              <h2>Create purchase order</h2>
              <form
                onSubmit={(e) =>
                  submit(e, (d) =>
                    write("/purchase-orders", {
                      supplier_id: d.supplier_id,
                      warehouse_id: d.warehouse_id,
                      expected_date: d.expected_date,
                      lines: [
                        {
                          product_id: d.product_id,
                          quantity: d.quantity,
                          unit_cost: d.unit_cost,
                        },
                      ],
                    }),
                  )
                }
              >
                <div className="grid three">
                  {selects(suppliers, "Order supplier", "supplier_id")}
                  {selects(warehouses, "Receiving warehouse", "warehouse_id")}
                  {selects(products, "Order product", "product_id")}
                  <Field label="Order quantity">
                    <input
                      aria-label="Order quantity"
                      name="quantity"
                      type="number"
                      min=".0001"
                      step=".0001"
                      required
                    />
                  </Field>
                  <Field label="Order unit cost">
                    <input
                      aria-label="Order unit cost"
                      name="unit_cost"
                      type="number"
                      min="0"
                      step=".0001"
                      required
                    />
                  </Field>
                  <Field label="Expected delivery">
                    <input
                      aria-label="Expected delivery"
                      name="expected_date"
                      type="date"
                      required
                    />
                  </Field>
                </div>
                <button disabled={busy}>Create purchase order</button>
              </form>
            </section>
            {orders.map((order) => (
              <section className="card" key={order.id}>
                <div className="section-head">
                  <div>
                    <h2>
                      {supplierName(order.supplier_id)}{" "}
                      <span className="pill">{order.status}</span>
                    </h2>
                    <p className="muted">
                      {whName(order.warehouse_id)} · expected{" "}
                      {order.expected_date} · {order.id.slice(0, 8)}
                    </p>
                  </div>
                  {["ordered", "partial"].includes(order.status) && (
                    <button
                      className="text-button"
                      disabled={busy}
                      onClick={() =>
                        task(async () => {
                          await write(
                            "/purchase-orders/" + order.id + "/cancel",
                          );
                          await load();
                          M(
                            "Unreceived quantities cancelled. Previously received stock remains.",
                          );
                        })
                      }
                    >
                      Cancel remaining order
                    </button>
                  )}
                </div>
                {order.lines.map((line) => (
                  <div className="order-line" key={line.id}>
                    <p>
                      <b>{productName(line.product_id)}</b> · ordered{" "}
                      {number(line.quantity)} · received {number(line.received)}
                    </p>
                    {["ordered", "partial"].includes(order.status) &&
                      Number(line.received) < Number(line.quantity) && (
                        <form
                          onSubmit={(e) =>
                            submit(e, (d) =>
                              write(
                                "/purchase-orders/" + order.id + "/receive",
                                {
                                  lines: [
                                    { line_id: line.id, quantity: d.quantity },
                                  ],
                                },
                              ),
                            )
                          }
                        >
                          <Field
                            label={"Receive quantity " + line.id.slice(0, 8)}
                          >
                            <input
                              aria-label={
                                "Receive quantity " + line.id.slice(0, 8)
                              }
                              name="quantity"
                              type="number"
                              min=".0001"
                              max={
                                Number(line.quantity) - Number(line.received)
                              }
                              step=".0001"
                              defaultValue={
                                Number(line.quantity) - Number(line.received)
                              }
                              required
                            />
                          </Field>
                          <button disabled={busy}>Receive stock</button>
                        </form>
                      )}
                  </div>
                ))}
              </section>
            ))}
            <section className="card">
              <h2>Supplier receipt performance</h2>
              <p className="muted">
                Observed lead time averages receipt events, including partial
                receipts. It does not replace the configured product lead time.
              </p>
              {performance.map((x) => (
                <p key={x.supplier_id}>
                  <b>{x.name}</b> · {x.receipt_count} receipts · average{" "}
                  {x.average_receipt_lead_days ?? "unavailable"} days ·{" "}
                  {x.overdue_open_orders} overdue orders
                </p>
              ))}
            </section>
          </>
        )}
        {tab === "Demand imports" && (
          <section className="card">
            <h2>Import historical demand</h2>
            <p>
              CSV header: <code>date,sku,quantity,revenue</code>. Imported rows
              support analytics and never change physical stock. Avoid importing
              sales already posted through stock movements.
            </p>
            <Field label="Demand CSV">
              <input
                aria-label="Demand CSV"
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => {
                  const file = e.target.files[0];
                  if (file)
                    task(async () => {
                      if (file.size > 500000)
                        throw Error("Maximum CSV size is 500 KB.");
                      const text = await file.text();
                      C(text);
                      V(
                        await write("/imports/demand/preview", {
                          csv_text: text,
                        }),
                      );
                    });
                }}
              />
            </Field>
            {preview && (
              <div className="import-preview">
                <h3>Import review</h3>
                <p>{preview.rows.length} valid rows</p>
                {preview.errors.map((x, i) => (
                  <p className="error" key={i}>
                    Row {x.row}: {x.message}
                  </p>
                ))}
                <button
                  disabled={busy || !preview.valid || !warehouse}
                  onClick={() =>
                    task(async () => {
                      const response = await write("/imports/demand/apply", {
                        csv_text: csv,
                        warehouse_id: warehouse,
                      });
                      M(response.message);
                      V(null);
                      await load();
                    })
                  }
                >
                  Apply demand import
                </button>
              </div>
            )}
            <p className="muted">
              Identical file bytes for the same warehouse are imported once.
              Changed or overlapping files require your review to prevent
              double-counting.
            </p>
          </section>
        )}
        {tab === "Reports" && (
          <section className="card">
            <h2>Saved inventory analyses</h2>
            <p className="muted">
              Each result stores the exact assumptions and data used. Changes to
              stock or product settings do not alter these reports.
            </p>
            {analyses.map((a) => (
              <div className="saved" key={a.id}>
                <div>
                  <b>{whName(a.inputs.warehouse_id)}</b>
                  <small>
                    {a.inputs.as_of} · {a.inputs.lookback_days} days ·{" "}
                    {a.results.summary.reorder_count} reorder suggestions
                  </small>
                </div>
                <button
                  className="text-button"
                  onClick={() => {
                    R(a);
                    T("Overview");
                  }}
                >
                  Open analysis
                </button>
                <a href={"/api/v1/analyses/" + a.id + "/report"}>JSON report</a>
                <a href={"/api/v1/analyses/" + a.id + "/report?format=csv"}>
                  CSV report
                </a>
              </div>
            ))}
          </section>
        )}
        <footer>
          InventoryIQ v1.0 · Single-currency USD estimates · No orders are sent
          automatically
        </footer>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")).render(<App />);
