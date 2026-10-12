import { useState } from "react";
import { api, money, ruleLabel, statusLabel } from "../api.js";

export default function TransactionsTable({ org, rows, onChanged }) {
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");
  const [openHistory, setOpenHistory] = useState(null);
  const [histories, setHistories] = useState({});

  async function run(key, fn) {
    setBusyId(key);
    setError("");
    try {
      await fn();
      onChanged();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyId(null);
    }
  }

  async function toggleHistory(tx) {
    if (openHistory === tx.id) {
      setOpenHistory(null);
      return;
    }
    setBusyId(`h${tx.id}`);
    setError("");
    try {
      const entries = await api.transactionHistory(org, tx.id);
      setHistories((prev) => ({ ...prev, [tx.id]: entries }));
      setOpenHistory(tx.id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyId(null);
    }
  }

  if (rows.length === 0)
    return <p className="muted">No transactions yet. Upload a CSV to begin.</p>;

  return (
    <>
      {error && <p className="error">{error}</p>}
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Description</th>
            <th>Amount</th>
            <th>Status</th>
            <th>Suggestion</th>
            <th>Reason</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((tx) => {
            const reasonMatch = tx.matches.find((m) => m.reason);
            return (
            <tr key={tx.id}>
              <td>{tx.date}</td>
              <td>{tx.description}</td>
              <td className="num">{money(tx.amount)}</td>
              <td>
                <span className={`pill ${tx.status}`}>{statusLabel(tx.status)}</span>
              </td>
              <td>
                {tx.matches.length === 0 && <span className="muted">—</span>}
                {tx.matches.map((m) => (
                  <div key={m.id} className="match">
                    <strong>
                      {m.investor_name} ({m.line_item_reference})
                    </strong>
                    <span className={`pill ${m.status}`}>{statusLabel(m.status)}</span>
                    {m.status === "proposed" &&
                      (tx.status === "suggested" ||
                        tx.status === "needs_review") && (
                        <div className="row">
                          <button
                            className="btn-approve"
                            disabled={busyId !== null}
                            onClick={() =>
                              run(`a${m.id}`, () => api.approveMatch(org, m.id))
                            }
                          >
                            {busyId === `a${m.id}` ? "…" : "Approve"}
                          </button>
                          <button
                            className="btn-reject"
                            disabled={busyId !== null}
                            onClick={() =>
                              run(`r${m.id}`, () => api.rejectMatch(org, m.id))
                            }
                          >
                            {busyId === `r${m.id}` ? "…" : "Reject"}
                          </button>
                        </div>
                      )}
                  </div>
                ))}
              </td>
              <td className="reason">
                {reasonMatch?.reason || tx.reason || "—"}{" "}
                {reasonMatch && (
                  <span className="ruletag">{ruleLabel(reasonMatch.rule)}</span>
                )}
              </td>
              <td>
                {(tx.status === "suggested" || tx.status === "needs_review") && (
                  <button
                    className="btn"
                    disabled={busyId !== null}
                    onClick={() =>
                      run(`i${tx.id}`, () => api.ignoreTransaction(org, tx.id))
                    }
                  >
                    {busyId === `i${tx.id}` ? "…" : "Ignore"}
                  </button>
                )}{" "}
                {tx.status === "ignored" && tx.type === "credit" && (
                  <button
                    className="btn"
                    disabled={busyId !== null}
                    onClick={() =>
                      run(`u${tx.id}`, () => api.unignoreTransaction(org, tx.id))
                    }
                  >
                    {busyId === `u${tx.id}` ? "…" : "Un-ignore"}
                  </button>
                )}{" "}
                <button
                  className="btn"
                  disabled={busyId !== null}
                  onClick={() => toggleHistory(tx)}
                >
                  {openHistory === tx.id ? "Hide history" : "History"}
                </button>
                {openHistory === tx.id && (
                  <ul className="history">
                    {(histories[tx.id] || []).map((h) => (
                      <li key={h.id}>
                        {h.action}: {h.message}
                      </li>
                    ))}
                  </ul>
                )}
              </td>
            </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}
