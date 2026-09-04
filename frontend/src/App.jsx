import {
  ClipboardList,
  DatabaseZap,
  Download,
  Flame,
  GitBranch,
  GitCompare,
  History,
  ScrollText,
  Settings as SettingsIcon,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { createRoot } from "react-dom/client";
import BatchResults from "./components/BatchResults";
import FindingCard from "./components/FindingCard";
import HistoryPanel from "./components/HistoryPanel";
import PlanDiff from "./components/PlanDiff";
import PlanFlame from "./components/PlanFlame";
import PlanTable from "./components/PlanTable";
import PlanTree from "./components/PlanTree";
import SettingsPanel from "./components/SettingsPanel";
import { analyzeBatchLog, analyzePlan, comparePlans, downloadTextFile, exportMarkdown } from "./lib/api";
import { getSaveByDefault, setSaveByDefault } from "./lib/settings";
import "./style.css";

const sample = `[
  {
    "Plan": {
      "Node Type": "Nested Loop",
      "Plan Rows": 100,
      "Actual Rows": 50000,
      "Actual Total Time": 1000.4,
      "Actual Loops": 1,
      "Plans": [
        {
          "Node Type": "Seq Scan",
          "Relation Name": "orders",
          "Alias": "orders",
          "Plan Rows": 100,
          "Actual Rows": 50000,
          "Actual Total Time": 900.5,
          "Actual Loops": 1,
          "Rows Removed by Filter": 100000,
          "Shared Read Blocks": 12000,
          "Filter": "(status = 'pending'::text)"
        },
        {
          "Node Type": "Index Scan",
          "Relation Name": "customers",
          "Index Name": "customers_pkey",
          "Plan Rows": 1,
          "Actual Rows": 1,
          "Actual Total Time": 0.05,
          "Actual Loops": 50000,
          "Index Cond": "(id = orders.customer_id)"
        }
      ]
    },
    "Planning Time": 2.1,
    "Execution Time": 1000.4
  }
]`;

function App() {
  const [planText, setPlanText] = useState(sample);
  const [query, setQuery] = useState("EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON) SELECT ...");
  const [result, setResult] = useState(null);
  const [activeTab, setActiveTab] = useState("advisor");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [save, setSave] = useState(getSaveByDefault());
  const [label, setLabel] = useState("");
  const [showSettings, setShowSettings] = useState(false);

  const [baselinePlanText, setBaselinePlanText] = useState("");
  const [currentPlanText, setCurrentPlanText] = useState("");
  const [compareResult, setCompareResult] = useState(null);
  const [comparing, setComparing] = useState(false);
  const [compareError, setCompareError] = useState("");

  const [logText, setLogText] = useState("");
  const [batchResult, setBatchResult] = useState(null);
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchError, setBatchError] = useState("");

  async function run() {
    setLoading(true);
    setError("");
    try {
      const data = await analyzePlan(planText, query, { save, label: label || null });
      setResult(data);
      setActiveTab("advisor");
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  async function doExport() {
    setExporting(true);
    setError("");
    try {
      const markdown = result ? await exportMarkdown(planText, query) : null;
      if (markdown) downloadTextFile(`pgplanadvisor-report-${Date.now()}.md`, markdown);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setExporting(false);
    }
  }

  function toggleSave(checked) {
    setSave(checked);
    setSaveByDefault(checked);
  }

  async function runCompare() {
    setComparing(true);
    setCompareError("");
    try {
      const data = await comparePlans(
        { planText: baselinePlanText, query: "" },
        { planText: currentPlanText, query: "" }
      );
      setCompareResult(data);
    } catch (e) {
      setCompareError(String(e.message || e));
    } finally {
      setComparing(false);
    }
  }

  async function runBatch() {
    setBatchLoading(true);
    setBatchError("");
    try {
      const data = await analyzeBatchLog(logText);
      setBatchResult(data);
    } catch (e) {
      setBatchError(String(e.message || e));
    } finally {
      setBatchLoading(false);
    }
  }

  return (
    <main>
      <header className="topbar">
        <div>
          <div className="brand">
            <DatabaseZap size={34} /> pgPlanAdvisor
          </div>
          <p>PostgreSQL EXPLAIN ANALYZE advisor for DBAs: paste plan, explain bottlenecks, visualize the tree.</p>
        </div>
        <div className="topbar-right">
          <div className="command">
            Recommended: <code>EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON)</code>
          </div>
          <button className="icon-btn" title="Settings" onClick={() => setShowSettings(true)}>
            <SettingsIcon size={18} />
          </button>
        </div>
      </header>

      {showSettings && <SettingsPanel onClose={() => setShowSettings(false)} />}

      <section className="layout">
        <aside className="input-card">
          <h2>
            <ClipboardList size={20} /> Paste Plan
          </h2>
          <label>SQL or notes</label>
          <textarea className="query" value={query} onChange={(e) => setQuery(e.target.value)} />

          <label>EXPLAIN output</label>
          <textarea className="plan" value={planText} onChange={(e) => setPlanText(e.target.value)} />

          <div className="save-row">
            <label className="checkbox-label">
              <input type="checkbox" checked={save} onChange={(e) => toggleSave(e.target.checked)} />
              Save to history
            </label>
            {save && (
              <input
                className="label-input"
                placeholder="Optional label"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
              />
            )}
          </div>

          <button onClick={run} disabled={loading}>
            <Sparkles size={18} /> {loading ? "Explaining..." : "Explain Plan"}
          </button>
          {error && <pre className="error">{error}</pre>}
        </aside>

        <section className="workspace">
          <nav className="tabs">
            <button className={activeTab === "advisor" ? "active" : ""} onClick={() => setActiveTab("advisor")}>
              Advisor
            </button>
            <button className={activeTab === "tree" ? "active" : ""} onClick={() => setActiveTab("tree")}>
              <GitBranch size={16} /> Tree Visualizer
            </button>
            <button className={activeTab === "raw" ? "active" : ""} onClick={() => setActiveTab("raw")}>
              Raw JSON
            </button>
            <button className={activeTab === "flame" ? "active" : ""} onClick={() => setActiveTab("flame")}>
              <Flame size={16} /> Flame
            </button>
            <button className={activeTab === "compare" ? "active" : ""} onClick={() => setActiveTab("compare")}>
              <GitCompare size={16} /> Compare
            </button>
            <button className={activeTab === "batch" ? "active" : ""} onClick={() => setActiveTab("batch")}>
              <ScrollText size={16} /> Batch Log
            </button>
            <button className={activeTab === "history" ? "active" : ""} onClick={() => setActiveTab("history")}>
              <History size={16} /> History
            </button>
            {result && (
              <button className="ghost-btn export-btn" onClick={doExport} disabled={exporting}>
                <Download size={14} /> {exporting ? "Exporting..." : "Export Markdown"}
              </button>
            )}
          </nav>

          {!result && !["history", "compare", "batch"].includes(activeTab) && (
            <div className="hero panel">
              <h1>Explain PostgreSQL plans beautifully.</h1>
              <p>Paste DBA output from EXPLAIN ANALYZE and pgPlanAdvisor will highlight bottlenecks, checks, and remediation ideas.</p>
            </div>
          )}

          {result && activeTab === "advisor" && (
            <>
              <div className="summary panel">
                <h1>{result.summary}</h1>
                <p>
                  Execution: {result.total_runtime_ms.toFixed(2)} ms · Planning: {result.planning_time_ms.toFixed(2)} ms
                  {result.saved && <span className="saved-pill">Saved to history</span>}
                </p>
              </div>
              <PlanTable nodes={result.nodes} />
              <div className="panel">
                <h2>DBA Checklist</h2>
                <ul className="checklist">
                  {result.investigation_checklist.map((x, i) => (
                    <li key={i}>{x}</li>
                  ))}
                </ul>
              </div>
              {result.top_findings.map((f, i) => (
                <FindingCard finding={f} key={i} />
              ))}
            </>
          )}

          {result && activeTab === "tree" && <PlanTree nodes={result.nodes} />}

          {result && activeTab === "raw" && (
            <div className="panel">
              <h2>Normalized Plan JSON</h2>
              <pre className="json">{JSON.stringify(result.normalized_plan, null, 2)}</pre>
            </div>
          )}

          {result && activeTab === "flame" && <PlanFlame nodes={result.nodes} totalRuntimeMs={result.total_runtime_ms} />}
          {!result && activeTab === "flame" && (
            <div className="hero panel">
              <h1>Nothing to show yet.</h1>
              <p>Explain a plan first, then this tab shows a proportional view of where its time actually goes.</p>
            </div>
          )}

          {activeTab === "compare" && (
            <>
              <div className="panel">
                <h2>Compare two plans</h2>
                <p className="hint">Paste a baseline (before) and current (after) EXPLAIN plan to see what changed.</p>
                <div className="compare-inputs">
                  <div>
                    <label>Baseline plan</label>
                    <textarea
                      className="plan compare-textarea"
                      value={baselinePlanText}
                      onChange={(e) => setBaselinePlanText(e.target.value)}
                      placeholder="Paste the 'before' EXPLAIN output"
                    />
                  </div>
                  <div>
                    <label>Current plan</label>
                    <textarea
                      className="plan compare-textarea"
                      value={currentPlanText}
                      onChange={(e) => setCurrentPlanText(e.target.value)}
                      placeholder="Paste the 'after' EXPLAIN output"
                    />
                  </div>
                </div>
                <button
                  className="primary-btn"
                  onClick={runCompare}
                  disabled={comparing || !baselinePlanText.trim() || !currentPlanText.trim()}
                >
                  <GitCompare size={16} /> {comparing ? "Comparing..." : "Compare Plans"}
                </button>
                {compareError && <pre className="error">{compareError}</pre>}
              </div>
              {compareResult && <PlanDiff comparison={compareResult} />}
            </>
          )}

          {activeTab === "batch" && (
            <>
              <div className="panel">
                <h2>Analyze an auto_explain log</h2>
                <p className="hint">
                  Paste captured log output containing one or more <code>duration: ... ms  plan:</code> entries
                  (from <code>auto_explain</code> with <code>log_analyze</code> on) to analyze all of them at once.
                </p>
                <textarea
                  className="plan"
                  value={logText}
                  onChange={(e) => setLogText(e.target.value)}
                  placeholder="Paste auto_explain log output here"
                />
                <button className="primary-btn" onClick={runBatch} disabled={batchLoading || !logText.trim()}>
                  <ScrollText size={16} /> {batchLoading ? "Analyzing..." : "Analyze Log"}
                </button>
                {batchError && <pre className="error">{batchError}</pre>}
              </div>
              {batchResult && <BatchResults data={batchResult} />}
            </>
          )}

          {activeTab === "history" && (
            <HistoryPanel
              onLoad={(loaded) => {
                setResult(loaded);
                setActiveTab("advisor");
              }}
            />
          )}
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
