import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { errorText } from "../api";
import { useAuth } from "../auth";

export default function Register() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ first_name: "", username: "", email: "", phone: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await register(form);
      navigate("/");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card auth">
      <h1>Create account</h1>
      <form onSubmit={submit}>
        <label>Full name<input value={form.first_name} onChange={set("first_name")} required /></label>
        <label>Username<input value={form.username} onChange={set("username")} required /></label>
        <label>Email<input type="email" value={form.email} onChange={set("email")} required /></label>
        <label>WhatsApp number (with country code)
          <input placeholder="919876543210" value={form.phone} onChange={set("phone")} />
        </label>
        <label>Password<input type="password" value={form.password} onChange={set("password")} required minLength={6} /></label>
        {error && <div className="alert error">{error}</div>}
        <button className="btn primary full" disabled={busy}>{busy ? "Creating…" : "Sign up"}</button>
      </form>
      <p className="small">Already have an account? <Link to="/login">Log in</Link></p>
    </div>
  );
}
