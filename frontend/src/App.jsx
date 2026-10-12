import { useCallback, useEffect, useRef, useState } from "react";
import { api, downloadNeedsReviewCsv } from "./api.js";
import LineItemsPanel from "./components/LineItemsPanel.jsx";
import OrgSwitcher from "./components/OrgSwitcher.jsx";
import SectionNav from "./components/SectionNav.jsx";
import TransactionsTable from "./components/TransactionsTable.jsx";
import UploadCard from "./components/UploadCard.jsx";
import "./styles.css";

export default function App() {
  const [org, setOrg] = useState("northwind");
  const [transactions, setTransactions] = useState([]);
  const [lineItems, setLineItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);
  const [tab, setTab] = useState(() => {
    const initial = window.location.hash.replace("#", "");
    return ["upload", "transactions", "line-items"].includes(initial)
      ? initial
      : "upload";
  });
  const prevTab = useRef(tab);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [txs, items] = await Promise.all([
        api.listTransactions(org),
        api.listLineItems(org),
      ]);
      setTransactions(txs);
      setLineItems(items);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [org]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const onHashChange = () => {
      const next = window.location.hash.replace("#", "");
      if (["upload", "transactions", "line-items"].includes(next)) setTab(next);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    if (loading) return;
    if (prevTab.current === tab) return;
    prevTab.current = tab;
    const el = document.getElementById(tab);
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }, [tab, loading]);
  async function handleExport() {
    setExporting(true);
    try {
      await downloadNeedsReviewCsv(org);
    } catch (e) {
      setError(e.message);
    } finally {
      setExporting(false);
    }
  }

  function handleUploaded() {
    refresh();
  }

  return (
    <main className="page">
      <header className="header">
        <h1>AlphaCapMatch — Capital call reconciliation</h1>
        <OrgSwitcher org={org} onChange={setOrg} />
      </header>
      <SectionNav
        active={tab}
        transactionCount={transactions.length}
        lineItemCount={lineItems.length}
      />
      <div hidden={tab !== "upload"}>
        <UploadCard org={org} onImported={handleUploaded} />
      </div>
      {loading && <p className="muted">Loading…</p>}
      {!loading && error && (
        <div className="card">
          <p className="error">{error}</p>
          <button className="btn" onClick={refresh}>Retry</button>
        </div>
      )}
      {!loading && !error && (
        <>
          <section
            className="card"
            id="transactions"
            hidden={tab !== "transactions" && tab !== "upload"}
          >
            <div className="row section-head">
              <h2>Transactions ({transactions.length})</h2>
              <button className="btn" disabled={exporting} onClick={handleExport}>
                {exporting ? "Downloading…" : "Download CSV"}
              </button>
            </div>
            <TransactionsTable org={org} rows={transactions} onChanged={refresh} />
          </section>
          <section
            className="card"
            id="line-items"
            hidden={tab !== "line-items" && tab !== "upload"}
          >
            <h2>Capital call allocations</h2>
            <LineItemsPanel items={lineItems} />
          </section>
        </>
      )}
    </main>
  );
}
