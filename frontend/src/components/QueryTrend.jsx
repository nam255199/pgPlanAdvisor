import { useEffect, useState } from "react";
import { fetchHistory } from "../lib/api";
import { formatMs } from "../lib/format";

const WIDTH = 320;
const HEIGHT = 64;
const PAD = 6;

export default function QueryTrend({ fingerprint, onClose }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    fetchHistory({ limit: 50, fingerprint })
      .then((data) => {
        if (cancelled) return;
        // Oldest first, so the sparkline reads left-to-right chronologically.
        setItems([...data.items].reverse());
      })
      .catch((e) => {
        if (!cancelled) setError(String(e.message || e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [fingerprint]);

  if (loading) return <p className="hint">Loading trend...</p>;
  if (error) return <pre className="error">{error}</pre>;
  if (items.length < 2) {
    return <p className="hint">Not enough saved runs of this query yet to show a trend.</p>;
  }

  const times = items.map((i) => i.total_runtime_ms);
  const min = Math.min(...times);
  const max = Math.max(...times);
  const range = max - min || 1;

  const points = items.map((item, i) => {
    const x = PAD + (i / (items.length - 1)) * (WIDTH - PAD * 2);
    const y = HEIGHT - PAD - ((item.total_runtime_ms - min) / range) * (HEIGHT - PAD * 2);
    return { x, y, item };
  });

  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const last = points[points.length - 1];

  return (
    <div className="query-trend">
      <div className="panel-header-row">
        <h4>Runtime trend ({items.length} runs)</h4>
        {onClose && (
          <button className="ghost-btn" onClick={onClose}>
            Close
          </button>
        )}
      </div>
      <svg width={WIDTH} height={HEIGHT} className="sparkline">
        <path d={path} fill="none" stroke="#60a5fa" strokeWidth="2" />
        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={i === points.length - 1 ? 3.5 : 2.5} fill="#60a5fa" />
        ))}
      </svg>
      <div className="query-trend-range">
        <span>{formatMs(min)}</span>
        <span>latest: {formatMs(last.item.total_runtime_ms)}</span>
        <span>{formatMs(max)}</span>
      </div>
    </div>
  );
}
