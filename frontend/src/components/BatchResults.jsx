import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import { formatMs } from "../lib/format";
import FindingCard from "./FindingCard";
import SeverityBadge from "./SeverityBadge";

function ResultRow({ result, index }) {
  const [open, setOpen] = useState(index === 0);
  const topSeverity = result.top_findings[0]?.severity;

  return (
    <div className="batch-row">
      <button className="batch-row-header" onClick={() => setOpen((v) => !v)}>
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        {topSeverity && <SeverityBadge severity={topSeverity} />}
        <span className="batch-row-summary">{result.label || result.summary}</span>
        <span className="batch-row-meta">
          {formatMs(result.total_runtime_ms)} · {result.top_findings.length} finding(s)
        </span>
      </button>
      {open && (
        <div className="batch-row-body">
          {result.top_findings.length === 0 && <p className="hint">No findings for this plan.</p>}
          {result.top_findings.map((f, i) => (
            <FindingCard finding={f} key={i} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function BatchResults({ data }) {
  const { entries_found, results, parse_errors } = data;

  return (
    <div className="panel">
      <h2>Batch results</h2>
      <p className="hint">
        {entries_found} plan(s) found in the log · {results.length} analyzed · {parse_errors.length} failed to parse.
        Sorted by total runtime, worst first.
      </p>

      {parse_errors.length > 0 && (
        <div className="batch-parse-errors">
          <h4>Parse errors</h4>
          <ul>
            {parse_errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      {results.length === 0 && parse_errors.length === 0 && (
        <p className="hint">No "duration: ... ms  plan:" entries were found in the pasted text.</p>
      )}

      <div className="batch-list">
        {results.map((r, i) => (
          <ResultRow result={r} index={i} key={r.id} />
        ))}
      </div>
    </div>
  );
}
