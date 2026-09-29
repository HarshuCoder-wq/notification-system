import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import api, { errorText } from "../api";
import { useAuth } from "../auth";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const u = await login(form.username, form.password);
      navigate(u.is_staff ? "/admin" : "/");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const forgot = async () => {
    const email = window.prompt("Enter your registered email");
    if (!email) return;
    try {
      const r = await api.post("/auth/password-reset/", { email });
      setInfo(r.data.detail);
    } catch (err) {
      setError(errorText(err));
    }
  };

  return (
    <div className="card auth">
      <h1>Log in</h1>
      <p className="muted">Logging in fires the <b>Login</b> trigger.</p>
      <form onSubmit={submit}>
        <label>Username or email
          <input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
        </label>
        <label>Password
          <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
        </label>
        {error && <div className="alert error">{error}</div>}
        {info && <div className="alert ok">{info}</div>}
        <button className="btn primary full" disabled={busy}>{busy ? "Logging in…" : "Log in"}</button>
      </form>
      <div className="row between small">
        <button className="link" onClick={forgot}>Forgot password?</button>
        <Link to="/register">Create account</Link>
      </div>
    </div>
  );
}
