import { useState } from "react";
import api, { errorText } from "../api";

export default function TriggerModal({ onClose, onSaved }) {
  const [form, setForm] = useState({ key: "", name: "", description: "" });
  const [error, setError] = useState("");
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const save = async (e) => {
    e.preventDefault();
    try {
      await api.post("/admin/triggers/", form);
      onSaved();
    } catch (err) {
      setError(errorText(err));
    }
  };

  return (
    <div className="modal-bg" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={save}>
        <h2>New trigger</h2>
        <label>Name<input value={form.name} onChange={set("name")} placeholder="Cart abandoned" required /></label>
        <label>Key (used in code)
          <input value={form.key} onChange={set("key")} placeholder="cart_abandoned" pattern="[a-z0-9_-]+" required />
        </label>
        <label>When it fires<input value={form.description} onChange={set("description")} /></label>
        <div className="hint">The website code calls <code>fire_trigger("{form.key || "key"}", user)</code> for this row.</div>
        {error && <div className="alert error">{error}</div>}
        <div className="row end">
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn primary">Create</button>
        </div>
      </form>
    </div>
  );
}
