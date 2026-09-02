import { KeyRound, X } from "lucide-react";
import { useState } from "react";
import { getApiKey, setApiKey } from "../lib/settings";

export default function SettingsPanel({ onClose }) {
  const [key, setKey] = useState(getApiKey());

  function save() {
    setApiKey(key.trim());
    onClose();
  }

  return (
    <div className="settings-backdrop" onClick={onClose}>
      <div className="settings-panel" onClick={(e) => e.stopPropagation()}>
        <div className="panel-header-row">
          <h2>
            <KeyRound size={18} /> Settings
          </h2>
          <button className="icon-btn" onClick={onClose}>
            <X size={16} />
          </button>
        </div>
        <label>API key</label>
        <input
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="Only needed if the server sets PGPA_API_KEY"
        />
        <p className="hint">
          Stored only in this browser (localStorage), sent as <code>X-API-Key</code>. Leave blank if the
          server has no API key configured.
        </p>
        <button className="primary-btn" onClick={save}>
          Save
        </button>
      </div>
    </div>
  );
}
