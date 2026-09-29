import { useCallback, useEffect, useState } from "react";
import api, { errorText } from "../api";
import TemplateModal from "../components/TemplateModal";
import TriggerModal from "../components/TriggerModal";

const CHANNELS = [
  { key: "whatsapp", label: "WhatsApp", icon: "💬" },
  { key: "email", label: "Email", icon: "✉️" },
  { key: "webpush", label: "Web Push", icon: "🌐" },
];

function Cell({ row, channel, tpl, onEdit, onChanged, flash }) {
  const [busy, setBusy] = useState("");

  const run = async (name, fn) => {
    setBusy(name);
    try {
      await fn();
    } finally {
      setBusy("");
    }
  };

  if (!tpl) {
    return (
      <td className="cell empty">
        <button className="btn small" onClick={() => onEdit(row, channel, null)}>+ Create template</button>
      </td>
    );
  }

  const toggle = () =>
    run("toggle", async () => {
      await api.post(`/admin/templates/${tpl.id}/toggle/`);
      onChanged();
    });

  const test = () =>
    run("test", async () => {
      try {
        await api.post(`/admin/templates/${tpl.id}/test/`);
        flash("ok", `Test ${channel} sent for "${row.name}"`);
      } catch (e) {
        flash("error", `Test failed: ${errorText(e)}`);
      }
      onChanged();
    });

  const sync = () =>
    run("sync", async () => {
      try {
        const r = await api.post(`/admin/templates/${tpl.id}/sync/`);
        flash("ok", `WhatsApp status: ${r.data.wa_status}`);
      } catch (e) {
        flash("error", `Sync failed: ${errorText(e)}`);
      }
      onChanged();
    });

  const waTemplate = channel === "whatsapp" && tpl.wa_mode === "template";

  return (
    <td className={`cell ${tpl.is_enabled ? "" : "off"}`}>
      <div className="cell-head">
        <label className="switch" title="Turn on / off">
          <input type="checkbox" checked={tpl.is_enabled} onChange={toggle} disabled={busy === "toggle"} />
          <span />
        </label>
        <span className="small">{tpl.is_enabled ? "On" : "Off"}</span>
        {waTemplate && <span className={`badge ${tpl.wa_status.toLowerCase()}`}>{tpl.wa_status}</span>}
        {channel === "whatsapp" && tpl.wa_mode === "text" && <span className="badge">TEXT</span>}
      </div>
      {tpl.subject && <div className="preview-title">{tpl.subject}</div>}
      {tpl.title && <div className="preview-title">{tpl.title}</div>}
      <div className="preview">{tpl.body}</div>
      {waTemplate && <div className="muted tiny">{tpl.wa_template_name}</div>}
      {tpl.wa_last_error && <div className="tiny err-text">{tpl.wa_last_error}</div>}
      <div className="cell-actions">
        <button className="btn small" onClick={() => onEdit(row, channel, tpl)}>Edit</button>
        <button className="btn small" onClick={test} disabled={!!busy}>{busy === "test" ? "Sending…" : "Test"}</button>
        {waTemplate && <button className="btn small" onClick={sync} disabled={!!busy}>{busy === "sync" ? "…" : "Sync"}</button>}
      </div>
    </td>
  );
}

export default function Admin() {
  const [rows, setRows] = useState([]);
  const [logs, setLogs] = useState([]);
  const [editing, setEditing] = useState(null);
  const [addingTrigger, setAddingTrigger] = useState(false);
  const [msg, setMsg] = useState(null);

  const flash = (type, text) => {
    setMsg({ type, text });
    setTimeout(() => setMsg(null), 6000);
  };

  const load = useCallback(async () => {
    const [m, l] = await Promise.all([api.get("/admin/matrix/"), api.get("/admin/logs/")]);
    setRows(m.data.rows);
    setLogs(l.data);
  }, []);

  useEffect(() => {
    load().catch((e) => flash("error", errorText(e)));
  }, [load]);

  const fire = async (row) => {
    try {
      const r = await api.post(`/admin/triggers/${row.id}/fire/`);
      const summary = r.data.logs.map((l) => `${l.channel}: ${l.status}`).join(", ");
      flash(r.data.logs.some((l) => l.status === "failed") ? "error" : "ok", `${r.data.detail}${summary ? " → " + summary : ""}`);
    } catch (e) {
      flash("error", errorText(e));
    }
    load();
  };

  return (
    <div className="stack">
      <div className="row between wrap">
        <div>
          <h1>Notification Settings</h1>
          <p className="muted">Rows = triggers · Columns = channels · Each cell = one template.</p>
        </div>
        <div className="row">
          <button className="btn" onClick={load}>↻ Refresh</button>
          <button className="btn primary" onClick={() => setAddingTrigger(true)}>+ Add trigger</button>
        </div>
      </div>

      {msg && <div className={`alert ${msg.type}`}>{msg.text}</div>}

      <div className="table-wrap">
        <table className="matrix">
          <thead>
            <tr>
              <th>Trigger</th>
              {CHANNELS.map((c) => <th key={c.key}>{c.icon} {c.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td className="trigger">
                  <b>{row.name}</b>
                  <div className="muted tiny"><code>{row.key}</code></div>
                  <div className="muted small">{row.description}</div>
                  <button className="btn small ghost" onClick={() => fire(row)} title="Fire this trigger for yourself now">⚡ Fire for me</button>
                </td>
                {CHANNELS.map((c) => (
                  <Cell
                    key={c.key}
                    row={row}
                    channel={c.key}
                    tpl={row.cells[c.key]}
                    onEdit={(r, ch, t) => setEditing({ trigger: r, channel: ch, template: t })}
                    onChanged={load}
                    flash={flash}
                  />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Recent deliveries</h3>
        <div className="table-wrap">
          <table className="logs">
            <thead>
              <tr><th>Time</th><th>Trigger</th><th>Channel</th><th>User</th><th>Recipient</th><th>Status</th><th>Error</th></tr>
            </thead>
            <tbody>
              {logs.length === 0 && <tr><td colSpan={7} className="muted">No notifications yet.</td></tr>}
              {logs.map((l) => (
                <tr key={l.id}>
                  <td className="nowrap">{new Date(l.created_at).toLocaleString()}</td>
                  <td>{l.trigger_key}{l.is_test && <span className="badge">test</span>}</td>
                  <td>{l.channel}</td>
                  <td>{l.user}</td>
                  <td className="tiny">{l.recipient}</td>
                  <td><span className={`badge ${l.status === "sent" ? "approved" : "rejected"}`}>{l.status}</span></td>
                  <td className="tiny err-text">{l.error}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {editing && (
        <TemplateModal
          {...editing}
          onClose={() => setEditing(null)}
          onSaved={(t) => {
            setEditing(null);
            flash(t.wa_last_error ? "error" : "ok", t.wa_last_error ? `Saved, but WhatsApp said: ${t.wa_last_error}` : "Template saved");
            load();
          }}
        />
      )}
      {addingTrigger && (
        <TriggerModal
          onClose={() => setAddingTrigger(false)}
          onSaved={() => {
            setAddingTrigger(false);
            load();
          }}
        />
      )}
    </div>
  );
}
