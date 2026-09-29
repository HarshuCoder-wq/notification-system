import { useState } from "react";
import api, { errorText } from "../api";

const LABEL = { whatsapp: "WhatsApp", email: "Email", webpush: "Web Push" };
const VARS = ["name", "email", "phone", "app_name", "date", "time", "order_id", "amount", "link"];

export default function TemplateModal({ trigger, channel, template, onClose, onSaved }) {
  const [form, setForm] = useState({
    subject: template?.subject || "",
    title: template?.title || "",
    body: template?.body || "",
    is_enabled: template?.is_enabled ?? true,
    wa_mode: template?.wa_mode || "template",
    wa_template_name: template?.wa_template_name || `nh_${trigger.key}`.replace(/-/g, "_"),
    wa_language: template?.wa_language || "en_US",
    wa_category: template?.wa_category || "UTILITY",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const insertVar = (v) => setForm({ ...form, body: `${form.body}{{${v}}}` });

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = { ...form, trigger: trigger.id, channel };
      const r = template
        ? await api.patch(`/admin/templates/${template.id}/`, payload)
        : await api.post("/admin/templates/", payload);
      onSaved(r.data);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-bg" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={save}>
        <h2>{template ? "Edit" : "Create"} {LABEL[channel]} template</h2>
        <p className="muted small">Trigger: <b>{trigger.name}</b></p>

        {channel === "email" && (
          <label>Subject<input value={form.subject} onChange={set("subject")} required /></label>
        )}
        {channel === "webpush" && (
          <>
            <label>Title<input value={form.title} onChange={set("title")} required /></label>
            <div className="hint">Platforms: <b>Web only</b> — iOS & Android are turned off.</div>
          </>
        )}
        {channel === "whatsapp" && (
          <>
            <label>Send as
              <select value={form.wa_mode} onChange={set("wa_mode")}>
                <option value="template">Approved template (needs Meta approval)</option>
                <option value="text">Free-form text (only within 24h after user messages you)</option>
              </select>
            </label>
            {form.wa_mode === "template" && (
              <div className="row">
                <label className="grow">Template name
                  <input value={form.wa_template_name} onChange={set("wa_template_name")} pattern="[a-z0-9_]+" required />
                </label>
                <label>Language
                  <input value={form.wa_language} onChange={set("wa_language")} style={{ width: 90 }} />
                </label>
                <label>Category
                  <select value={form.wa_category} onChange={set("wa_category")}>
                    <option>UTILITY</option>
                    <option>MARKETING</option>
                  </select>
                </label>
              </div>
            )}
          </>
        )}

        <label>Message body
          <textarea rows={5} value={form.body} onChange={set("body")} required />
        </label>
        <div className="vars">
          <span className="muted small">Insert variable:</span>
          {VARS.map((v) => (
            <button type="button" key={v} className="chip" onClick={() => insertVar(v)}>{`{{${v}}}`}</button>
          ))}
        </div>
        {channel === "whatsapp" && form.wa_mode === "template" && (
          <div className="hint">
            Saving submits this template to WhatsApp for approval. Variables are mapped in order to {"{{1}}, {{2}}…"}.
            Changing the template name creates a new template on Meta.
          </div>
        )}
        <label className="check"><input type="checkbox" checked={form.is_enabled} onChange={set("is_enabled")} /> Enabled</label>

        {error && <div className="alert error">{error}</div>}
        <div className="row end">
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn primary" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
        </div>
      </form>
    </div>
  );
}
