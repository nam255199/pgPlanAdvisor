import { useEffect, useMemo, useState } from "react";
import { formatCount, formatMs, relationLabel } from "../lib/format";

const ROW_HEIGHT = 34;
const MIN_WIDTH_PCT = 0.4; // keep tiny nodes clickable instead of disappearing

function buildChildMap(nodes) {
  const map = {};
  nodes.forEach((n) => {
    const parent = n.parent_id || "root";
    map[parent] = map[parent] || [];
    map[parent].push(n);
  });
  return map;
}

// Icicle layout: each node's width is its share of its parent's width,
// weighted by bottleneck_score (actual_total_time * loops, which already
// includes time spent in descendants - the same metric EXPLAIN itself
// reports cumulatively, so this is standard flamegraph-style self+children
// sizing without needing to subtract child time out by hand).
function layout(nodes, totalRuntimeMs) {
  const map = buildChildMap(nodes);
  const roots = map.root || [];
  const boxes = [];
  let maxDepth = 0;

  function place(node, xStart, xWidth, depth) {
    maxDepth = Math.max(maxDepth, depth);
    boxes.push({ node, x: xStart, width: Math.max(xWidth, 0), depth });

    const children = map[node.id] || [];
    if (!children.length) return;
    const childTotal = children.reduce((sum, c) => sum + Math.max(c.bottleneck_score, 0), 0);
    let offset = xStart;
    children.forEach((c) => {
      const share = childTotal > 0 ? Math.max(c.bottleneck_score, 0) / childTotal : 1 / children.length;
      const w = xWidth * share;
      place(c, offset, w, depth + 1);
      offset += w;
    });
  }

  const rootBasis = totalRuntimeMs > 0 ? totalRuntimeMs : roots.reduce((s, r) => s + r.bottleneck_score, 0) || 1;
  let offset = 0;
  roots.forEach((r) => {
    const share = Math.min(Math.max(r.bottleneck_score, 0) / rootBasis, 1);
    const w = 100 * (share || 1 / roots.length);
    place(r, offset, w, 0);
    offset += w;
  });

  return { boxes, maxDepth };
}

function colorFor(pctOfTotal) {
  const t = Math.min(Math.max(pctOfTotal / 100, 0), 1);
  const hue = 210 - t * 210; // blue (cool, cheap) -> red (hot, expensive)
  return `hsl(${hue}, 65%, 42%)`;
}

export default function PlanFlame({ nodes, totalRuntimeMs }) {
  const [selected, setSelected] = useState(null);
  const { boxes, maxDepth } = useMemo(() => layout(nodes, totalRuntimeMs), [nodes, totalRuntimeMs]);

  useEffect(() => {
    setSelected(null);
  }, [nodes]);

  return (
    <div className="panel flame-panel">
      <h2>Cost / Time Proportions</h2>
      <p className="hint">
        Each row is a depth level; each block's width is its share of total execution time (self + descendants).
        Click a block for details.
      </p>
      <div className="flame-chart" style={{ height: (maxDepth + 1) * ROW_HEIGHT }}>
        {boxes.map((box) => {
          const pct = totalRuntimeMs > 0 ? (box.node.bottleneck_score / totalRuntimeMs) * 100 : 0;
          const isSelected = selected?.id === box.node.id;
          return (
            <button
              key={box.node.id}
              className={`flame-block ${isSelected ? "selected" : ""}`}
              style={{
                left: `${box.x}%`,
                width: `${Math.max(box.width, MIN_WIDTH_PCT)}%`,
                top: box.depth * ROW_HEIGHT,
                background: colorFor(pct),
              }}
              title={`${box.node.node_type} - ${relationLabel(box.node)} - ${formatMs(box.node.actual_total_time)} (${pct.toFixed(1)}% of total)`}
              onClick={() => setSelected(box.node)}
            >
              {box.width > 6 && <span>{box.node.node_type}</span>}
            </button>
          );
        })}
      </div>

      {selected && (
        <div className="flame-detail">
          <h3>{selected.node_type}</h3>
          <div className="node-relation">{relationLabel(selected)}</div>
          <div className="node-grid">
            <span>Time</span>
            <b>{formatMs(selected.actual_total_time)}</b>
            <span>Share of total</span>
            <b>{totalRuntimeMs > 0 ? `${((selected.bottleneck_score / totalRuntimeMs) * 100).toFixed(1)}%` : "-"}</b>
            <span>Rows</span>
            <b>{formatCount(selected.actual_rows)}</b>
            <span>Estimate</span>
            <b>{formatCount(selected.plan_rows)}</b>
            <span>Loops</span>
            <b>{formatCount(selected.loops)}</b>
          </div>
          {selected.condition && <div className="node-filter">{selected.condition}</div>}
        </div>
      )}
    </div>
  );
}
