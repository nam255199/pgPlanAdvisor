import { formatCount, formatMs, relationLabel } from "../lib/format";

export default function PlanTable({ nodes }) {
  return (
    <div className="panel">
      <h2>Expensive Nodes</h2>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Node</th>
              <th>Table / Index</th>
              <th>Actual Time</th>
              <th>Rows</th>
              <th>Estimate</th>
              <th>Read Blocks</th>
              <th>I/O Read</th>
              <th>Condition</th>
            </tr>
          </thead>
          <tbody>
            {nodes.slice(0, 30).map((n) => (
              <tr key={n.path}>
                <td>
                  <strong>{n.node_type}</strong>
                </td>
                <td>{relationLabel(n)}</td>
                <td>{formatMs(n.actual_total_time)}</td>
                <td>{formatCount(n.actual_rows)}</td>
                <td>{formatCount(n.plan_rows)}</td>
                <td>{formatCount(n.shared_read_blocks)}</td>
                <td>{formatMs(n.shared_read_time)}</td>
                <td className="cond">{n.condition || n.sort_method || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
