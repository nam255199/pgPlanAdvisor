import React from "react";

function rel(n) {
  if (n.relation && n.alias) return `${n.relation} ${n.alias}`;
  return n.relation || n.index_name || "-";
}

export default function PlanTable({ nodes }) {
  return (
    <div className="panel">
      <h2>Expensive Nodes</h2>
      <table>
        <thead>
          <tr>
            <th>Node</th>
            <th>Table / Index</th>
            <th>Actual Time</th>
            <th>Rows</th>
            <th>Estimate</th>
            <th>Read Blocks</th>
            <th>I/O Read ms</th>
            <th>Condition</th>
          </tr>
        </thead>
        <tbody>
          {nodes.slice(0, 30).map((n) => (
            <tr key={n.path}>
              <td><strong>{n.node_type}</strong></td>
              <td>{rel(n)}</td>
              <td>{n.actual_total_time.toFixed(2)} ms</td>
              <td>{Number(n.actual_rows).toLocaleString()}</td>
              <td>{Number(n.plan_rows).toLocaleString()}</td>
              <td>{Number(n.shared_read_blocks).toLocaleString()}</td>
              <td>{Number(n.shared_read_time).toLocaleString()}</td>
              <td className="cond">{n.condition || n.sort_method || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
