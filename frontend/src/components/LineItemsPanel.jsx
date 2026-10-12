import { money, statusLabel } from "../api.js";

export default function LineItemsPanel({ items }) {
  if (items.length === 0) return <p className="muted">No allocations.</p>;
  return (
    <table>
      <thead>
        <tr>
          <th>Reference</th>
          <th>Investor</th>
          <th>Called</th>
          <th>Funded</th>
          <th>Remaining</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id}>
            <td>{item.reference}</td>
            <td>{item.investor}</td>
            <td className="num">{money(item.amount_called)}</td>
            <td className="num">{money(item.amount_funded)}</td>
            <td className="num">{money(item.remaining)}</td>
            <td>
              <span className={`pill ${item.status}`}>{statusLabel(item.status)}</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
