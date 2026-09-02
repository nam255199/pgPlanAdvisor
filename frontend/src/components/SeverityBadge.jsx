export default function SeverityBadge({ severity }) {
  return <span className={`severity ${severity}`}>{severity}</span>;
}
