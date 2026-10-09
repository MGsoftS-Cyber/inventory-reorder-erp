import React, { useState } from "react";

export default function AuthScreen({ onSubmit, busy, error }) {
  const [registering, setRegistering] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  return (
    <main className="auth-layout">
      <section className="auth-intro">
        <span className="logo">◫ Inventory & Reorder ERP</span>
        <p className="eyebrow">UNDERSTAND WHAT DRIVES YOUR RESULTS</p>
        <h1>
          Understand your stock.
          <br />
          Order with confidence.
        </h1>
        <p>
          Connect stock and demand. Review reorder suggestions, manage
          purchasing, and keep clear records of every assumption.
        </p>
        <div className="intro-features">
          <span>Inventory coverage</span>
          <span>Reorder analytics</span>
          <span>Purchase receiving</span>
        </div>
      </section>
      <section className="auth-card">
        <h2>{registering ? "Create your account" : "Welcome back"}</h2>
        <p className="muted">
          Keep your inventory and purchase records private.
        </p>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit(registering, { email, password });
          }}
        >
          <label htmlFor="email">
            Email
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label htmlFor="password">
            Password
            <input
              id="password"
              aria-label="Password"
              aria-describedby="password-help"
              type="password"
              autoComplete={registering ? "new-password" : "current-password"}
              minLength={12}
              maxLength={128}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <small id="password-help">Use at least 12 characters.</small>
          <button disabled={busy}>
            {busy ? "Please wait…" : registering ? "Create account" : "Sign in"}
          </button>
        </form>
        <button
          className="text-button"
          disabled={busy}
          onClick={() => setRegistering(!registering)}
        >
          {registering
            ? "Already have an account? Sign in"
            : "New here? Create an account"}
        </button>
        <small>No default account or password is included.</small>
      </section>
    </main>
  );
}
