import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../services/api.js";
import useFetch from "../hooks/useFetch.js";
import Loading from "../components/Loading.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import DataTable from "../components/DataTable.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

function Profile({ customerId }) {
  const [refresh, setRefresh] = useState(0);
  const [formError, setFormError] = useState("");
  const [note, setNote] = useState({ channel: "phone", summary: "" });
  const [followUp, setFollowUp] = useState({ title: "", due_date: "" });

  const profile = useFetch(() => api.crmCustomer(customerId), [customerId]);
  const notes = useFetch(() => api.interactions(customerId), [customerId, refresh]);
  const tasks = useFetch(() => api.followUps({ shopify_customer_id: customerId }), [customerId, refresh]);

  const save = (action) => async (e) => {
    e.preventDefault();
    setFormError("");
    try {
      await action();
      setRefresh((n) => n + 1);
    } catch (err) {
      setFormError(err.message);
    }
  };

  if (profile.loading) return <Loading />;
  if (profile.error) return <ErrorMessage message={profile.error} />;
  const c = profile.data.shopify;

  return (
    <>
      <div className="card">
        <h2>{c.name}</h2>
        <p>{c.email} - {c.orders_count} orders - {c.total_spent} spent</p>
        <p className="muted">Shopify customer ID {c.id}</p>
      </div>
      <div className="notice">Do not record prescriptions or health details in CRM notes.</div>
      <ErrorMessage message={formError} />

      <h3>Interactions</h3>
      <form className="stack" onSubmit={save(async () => {
        await api.addInteraction(customerId, note);
        setNote({ ...note, summary: "" });
      })}>
        <select value={note.channel} onChange={(e) => setNote({ ...note, channel: e.target.value })}>
          {["phone", "email", "in_person", "chat", "other"].map((c) => <option key={c} value={c}>{c.replace("_", " ")}</option>)}
        </select>
        <textarea required maxLength={2000} placeholder="What was discussed?" value={note.summary}
          onChange={(e) => setNote({ ...note, summary: e.target.value })} />
        <button type="submit">Add interaction</button>
      </form>
      {notes.data && (
        <DataTable rows={notes.data} empty="No interactions yet." columns={[
          { key: "created_at", label: "When", render: (n) => n.created_at.slice(0, 16).replace("T", " ") },
          { key: "channel", label: "Channel" },
          { key: "summary", label: "Summary" },
        ]} />
      )}

      <h3>Follow-ups</h3>
      <form className="row" onSubmit={save(async () => {
        await api.addFollowUp({ shopify_customer_id: Number(customerId), ...followUp });
        setFollowUp({ title: "", due_date: "" });
      })}>
        <input required placeholder="Follow-up title" value={followUp.title}
          onChange={(e) => setFollowUp({ ...followUp, title: e.target.value })} />
        <input required type="date" value={followUp.due_date}
          onChange={(e) => setFollowUp({ ...followUp, due_date: e.target.value })} />
        <button type="submit">Add follow-up</button>
      </form>
      {tasks.data && (
        <DataTable rows={tasks.data} empty="No follow-ups yet." columns={[
          { key: "title", label: "Title" },
          { key: "due_date", label: "Due" },
          { key: "status", label: "Status", render: (t) => <StatusBadge value={t.status} /> },
        ]} />
      )}
    </>
  );
}

export default function CRM() {
  const [params, setParams] = useSearchParams();
  const [idInput, setIdInput] = useState("");
  const selected = params.get("customer");
  const list = useFetch(() => api.crmCustomers(), []);

  return (
    <>
      <h1>CRM</h1>
      <p className="muted">Notes and follow-ups are stored in our database; customer details come live from Shopify.</p>
      <div className="split">
        <div>
          <form className="row" onSubmit={(e) => { e.preventDefault(); idInput && setParams({ customer: idInput.trim() }); }}>
            <input placeholder="Shopify customer ID" value={idInput} onChange={(e) => setIdInput(e.target.value)} />
            <button type="submit">Open</button>
          </form>
          {list.loading && <Loading />}
          <ErrorMessage message={list.error} />
          {list.data?.map((c) => (
            <button key={c.id} className={`list-item ${String(c.shopify_customer_id) === selected ? "active" : ""}`}
              onClick={() => setParams({ customer: c.shopify_customer_id })}>
              {c.display_name || c.shopify_customer_id}
            </button>
          ))}
        </div>
        <div>{selected ? <Profile key={selected} customerId={selected} /> : <p className="muted">Pick a customer, or open one by Shopify ID (or from the Customers page).</p>}</div>
      </div>
    </>
  );
}
