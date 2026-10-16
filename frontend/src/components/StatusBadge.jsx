export default function StatusBadge({ value }) {
  return <span className={`badge ${value || ""}`}>{(value || "-").replaceAll("_", " ")}</span>;
}
