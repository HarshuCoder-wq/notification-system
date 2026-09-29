import { useEffect, useState } from "react";
import api, { errorText } from "../api";
import { useAuth } from "../auth";
import { isSubscribed, onSubscriptionChange, subscribe } from "../push";

export default function Home() {
  const { user, setUser } = useAuth();
  const [pushOn, setPushOn] = useState(false);
  const [phone, setPhone] = useState(user.phone || "");
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    isSubscribed().then(setPushOn);
    onSubscriptionChange((p) => p.then(setPushOn));
  }, []);

  const flash = (type, text) => {
    setMsg({ type, text });
    setTimeout(() => setMsg(null), 5000);
  };

  const enablePush = async () => {
    try {
      const ok = await subscribe();
      setPushOn(ok);
      flash(ok ? "ok" : "error", ok ? "Browser notifications enabled ✅" : "Permission was not granted");
    } catch (e) {
      flash("error", e.message);
    }
  };

  const savePhone = async () => {
    try {
      const r = await api.patch("/auth/me/", { phone });
      setUser(r.data);
      flash("ok", "Phone saved");
    } catch (e) {
      flash("error", errorText(e));
    }
  };

  const placeOrder = async () => {
    try {
      const r = await api.post("/orders/", { amount: 499 });
      flash("ok", `Order ${r.data.order_id} placed — "Order placed" trigger fired`);
    } catch (e) {
      flash("error", errorText(e));
    }
  };

  return (
    <div className="stack">
      <div className="card">
        <h1>Hi {user.first_name || user.username} 👋</h1>
        <p className="muted">This is the demo website. Actions here fire triggers, and the admin decides which channels send what.</p>
        {msg && <div className={`alert ${msg.type}`}>{msg.text}</div>}
      </div>

      <div className="grid3">
        <div className="card">
          <h3>🌐 Web Push</h3>
          <p className="muted small">Allow browser notifications so this user can receive web push.</p>
          {pushOn ? <span className="badge on">Subscribed</span> : <button className="btn primary" onClick={enablePush}>Enable notifications</button>}
        </div>
        <div className="card">
          <h3>💬 WhatsApp</h3>
          <p className="muted small">Number with country code. In sandbox it must be in Meta's test recipient list.</p>
          <div className="row">
            <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="919876543210" />
            <button className="btn" onClick={savePhone}>Save</button>
          </div>
        </div>
        <div className="card">
          <h3>✉️ Email</h3>
          <p className="muted small">Emails go to:</p>
          <b>{user.email}</b>
        </div>
      </div>

      <div className="card">
        <h3>Fire a trigger from the website</h3>
        <div className="row wrap">
          <button className="btn primary" onClick={placeOrder}>🛒 Place demo order</button>
          <span className="muted small">Login / Logout fire automatically. Inactivity triggers run from the hourly job.</span>
        </div>
      </div>
    </div>
  );
}
