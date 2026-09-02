import { RefreshCw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { deleteHistoryItem, fetchHistory, fetchHistoryItem } from "../lib/api";
import SeverityBadge from "./SeverityBadge";

export default function HistoryPanel({ onLoad }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [disabled, setDisabled] = useState(false);

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchHistory({ limit: 50 });
      setItems(data.items);
      setDisabled(false);
    } catch (e) {
      if (e.status === 404) {
        setDisabled(true);
      } else {
        setError(String(e.message || e));
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function open(id) {
    try {
      const result = await fetchHistoryItem(id);
      onLoad(result);
    } catch (e) {
      setError(String(e.message || e));
    }
  }

  async function remove(id, ev) {
    ev.stopPropagation();
    try {
      await deleteHistoryItem(id);
      setItems((prev) => prev.filter((i) => i.id !== id));
    } catch (e) {
      setError(String(e.message || e));
    }
  }

  if (disabled) {
    return (
      <div className="panel">
        <h2>History</h2>
        <p className="hint">
          Server-side history is disabled on this backend. Set <code>PGPA_HISTORY_ENABLED=true</code> to
          enable saving and browsing past analyses.
        </p>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-header-row">
        <h2>Saved Analyses</h2>
        <button className="ghost-btn" onClick={refresh} disabled={loading}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>
      {error && <pre className="error">{error}</pre>}
      {!items.length && !loading && <p className="hint">No saved analyses yet. Check "Save to history" before running one.</p>}
      <ul className="history-list">
        {items.map((item) => (
          <li key={item.id} className="history-item" onClick={() => open(item.id)}>
            <div className="history-item-main">
              {item.top_severity && <SeverityBadge severity={item.top_severity} />}
              <div>
                <div className="history-item-title">{item.label || item.summary}</div>
                <div className="history-item-meta">
                  {new Date(item.created_at).toLocaleString()} · {item.total_runtime_ms.toFixed(1)} ms ·{" "}
                  {item.finding_count} finding(s)
                </div>
              </div>
            </div>
            <button className="icon-btn" title="Delete" onClick={(ev) => remove(item.id, ev)}>
              <Trash2 size={16} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
