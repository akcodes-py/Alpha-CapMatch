const LINKS = [
  { id: "upload", label: "Upload" },
  { id: "transactions", label: "Transactions" },
  { id: "line-items", label: "Allocations" },
];

export default function SectionNav({ active, transactionCount, lineItemCount }) {
  const counts = { transactions: transactionCount, "line-items": lineItemCount };
  return (
    <nav aria-label="Page sections" className="pagenav">
      {LINKS.map(({ id, label }) => (
        <a
          key={id}
          href={`#${id}`}
          className={active === id ? "active" : ""}
          aria-current={active === id ? "location" : undefined}
        >
          {label}
          {counts[id] !== undefined && ` (${counts[id]})`}
        </a>
      ))}
    </nav>
  );
}
