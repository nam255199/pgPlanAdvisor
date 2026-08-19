import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { DatabaseZap, GitBranch, ClipboardList, Sparkles } from "lucide-react";
import { analyzePlan } from "./lib/api";
import FindingCard from "./components/FindingCard";
import PlanTable from "./components/PlanTable";
import PlanTree from "./components/PlanTree";
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

  async function run() {
    setLoading(true);
    setError("");
    try {
      const data = await analyzePlan(planText, query);
      setResult(data);
      setActiveTab("advisor");
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <header className="topbar">
        <div>
          <div className="brand"><DatabaseZap size={34} /> pgPlanAdvisor</div>
          <p>PostgreSQL EXPLAIN ANALYZE advisor for DBAs: paste plan, explain bottlenecks, visualize the tree.</p>
        </div>
        <div className="command">
          Recommended: <code>EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON)</code>
        </div>
      </header>

      <section className="layout">
        <aside className="input-card">
          <h2><ClipboardList size={20}/> Paste Plan</h2>
          <label>SQL or notes</label>
          <textarea className="query" value={query} onChange={e => setQuery(e.target.value)} />

          <label>EXPLAIN output</label>
          <textarea className="plan" value={planText} onChange={e => setPlanText(e.target.value)} />

          <button onClick={run} disabled={loading}>
            <Sparkles size={18}/> {loading ? "Explaining..." : "Explain Plan"}
          </button>
          {error && <pre className="error">{error}</pre>}
        </aside>

        <section className="workspace">
          <nav className="tabs">
            <button className={activeTab === "advisor" ? "active" : ""} onClick={() => setActiveTab("advisor")}>Advisor</button>
            <button className={activeTab === "tree" ? "active" : ""} onClick={() => setActiveTab("tree")}><GitBranch size={16}/> Tree Visualizer</button>
            <button className={activeTab === "raw" ? "active" : ""} onClick={() => setActiveTab("raw")}>Raw JSON</button>
          </nav>

          {!result && (
            <div className="hero panel">
              <h1>Explain PostgreSQL plans beautifully.</h1>
              <p>Paste DBA output from EXPLAIN ANALYZE and pgPlanAdvisor will highlight bottlenecks, checks, and remediation ideas.</p>
            </div>
          )}

          {result && activeTab === "advisor" && (
            <>
              <div className="summary panel">
                <h1>{result.summary}</h1>
                <p>Execution: {result.total_runtime_ms} ms · Planning: {result.planning_time_ms} ms</p>
              </div>
              <PlanTable nodes={result.nodes} />
              <div className="panel">
                <h2>DBA Checklist</h2>
                <ul className="checklist">{result.investigation_checklist.map((x, i) => <li key={i}>{x}</li>)}</ul>
              </div>
              {result.top_findings.map((f, i) => <FindingCard finding={f} key={i} />)}
            </>
          )}

          {result && activeTab === "tree" && <PlanTree nodes={result.nodes} />}

          {result && activeTab === "raw" && (
            <div className="panel">
              <h2>Normalized Plan JSON</h2>
              <pre className="json">{JSON.stringify(result.normalized_plan, null, 2)}</pre>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
