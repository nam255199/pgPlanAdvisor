import React from "react";

function childMap(nodes) {
  const map = {};
  nodes.forEach(n => {
    const parent = n.parent_id || "root";
    map[parent] = map[parent] || [];
    map[parent].push(n);
  });
  return map;
}

function relationLabel(node) {
  if (node.relation && node.alias) return `${node.relation} ${node.alias}`;
  if (node.relation) return node.relation;
  if (node.index_name) return `index ${node.index_name}`;
  return "plan node";
}

function NodeBox({ node, children }) {
  const isHot = node.bottleneck_score > 500 || node.shared_read_blocks > 10000 || node.sort_disk_kb > 0;
  const est = node.plan_rows ? Math.max(node.actual_rows / node.plan_rows, node.plan_rows / Math.max(node.actual_rows, 1)) : 0;

  return (
    <li>
      <div className={`tree-node ${isHot ? "hot" : ""}`}>
        <div className="node-title">{node.node_type}</div>
        <div className="node-relation">{relationLabel(node)}</div>

        <div className="node-grid">
          <span>Time</span><b>{node.actual_total_time.toFixed(2)} ms</b>
          <span>Rows</span><b>{Number(node.actual_rows).toLocaleString()}</b>
          <span>Estimate</span><b>{Number(node.plan_rows).toLocaleString()}</b>
          <span>Loops</span><b>{Number(node.loops).toLocaleString()}</b>
          <span>Read blocks</span><b>{Number(node.shared_read_blocks).toLocaleString()}</b>
          <span>I/O read</span><b>{Number(node.shared_read_time).toLocaleString()} ms</b>
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
      {children.map(n => (
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
      <p className="hint">Each node now shows table/index name, condition, rows, estimates, buffers, and I/O timing.</p>
      <TreeLevel parentId="root" map={map} />
    </div>
  );
}
