// Small, dependency-free formatting/sorting helpers. Kept separate from
// components so they're trivial to unit test (see lib/format.test.js).

const SEVERITY_RANK = { high: 3, medium: 2, low: 1, info: 0 };

export function severityRank(severity) {
  return SEVERITY_RANK[severity] ?? 0;
}

export function sortFindingsBySeverity(findings) {
  return [...findings].sort((a, b) => {
    const rankDiff = severityRank(b.severity) - severityRank(a.severity);
    if (rankDiff !== 0) return rankDiff;
    return (b.score ?? 0) - (a.score ?? 0);
  });
}

export function formatMs(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "-";
  if (n >= 1000) return `${(n / 1000).toFixed(2)} s`;
  return `${n.toFixed(2)} ms`;
}

export function formatCount(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "-";
  return n.toLocaleString();
}

export function relationLabel(node) {
  if (node.relation && node.alias && node.relation !== node.alias) return `${node.relation} ${node.alias}`;
  if (node.relation) return node.relation;
  if (node.index_name) return `index ${node.index_name}`;
  return "plan node";
}

export function estimateErrorRatio(node) {
  if (!node.plan_rows) return 0;
  return Math.max(node.actual_rows / node.plan_rows, node.plan_rows / Math.max(node.actual_rows, 1));
}
