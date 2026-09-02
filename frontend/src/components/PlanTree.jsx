import { estimateErrorRatio, formatCount, formatMs, relationLabel } from "../lib/format";

function childMap(nodes) {
  const map = {};
  nodes.forEach((n) => {
    const parent = n.parent_id || "root";
    map[parent] = map[parent] || [];
    map[parent].push(n);
  });
  return map;
}

function NodeBox({ node, children }) {
  const isHot = node.bottleneck_score > 500 || node.shared_read_blocks > 10000 || node.sort_disk_kb > 0;
  const est = estimateErrorRatio(node);

  return (
    <li>
      <div className={`tree-node ${isHot ? "hot" : ""}`}>
        <div className="node-title">{node.node_type}</div>
        <div className="node-relation">{relationLabel(node)}</div>

        <div className="node-grid">
          <span>Time</span>
          <b>{formatMs(node.actual_total_time)}</b>
          <span>Rows</span>
          <b>{formatCount(node.actual_rows)}</b>
          <span>Estimate</span>
          <b>{formatCount(node.plan_rows)}</b>
          <span>Loops</span>
          <b>{formatCount(node.loops)}</b>
          <span>Read blocks</span>
          <b>{formatCount(node.shared_read_blocks)}</b>
          <span>I/O read</span>
          <b>{formatMs(node.shared_read_time)}</b>
        </div>

        {est >= 10 && <div className="node-warning">Estimate error: {est.toFixed(1)}x</div>}
        {node.index_name && <div className="node-pill">Index: {node.index_name}</div>}
        {node.sort_method && <div className="node-pill">Sort: {node.sort_method}</div>}
        {node.condition && <div className="node-filter">{node.condition}</div>}
      </div>
      {children}
    </li>
  );
}

function TreeLevel({ parentId, map }) {
  const children = map[parentId] || [];
  if (!children.length) return null;

  return (
    <ul className="tree">
      {children.map((n) => (
        <NodeBox node={n} key={n.id}>
          <TreeLevel parentId={n.id} map={map} />
        </NodeBox>
      ))}
    </ul>
  );
}

export default function PlanTree({ nodes }) {
  const map = childMap(nodes);
  return (
    <div className="panel tree-panel">
      <h2>Plan Tree Visualizer</h2>
      <p className="hint">Each node shows table/index name, condition, rows, estimates, buffers, and I/O timing.</p>
      <TreeLevel parentId="root" map={map} />
    </div>
  );
}
