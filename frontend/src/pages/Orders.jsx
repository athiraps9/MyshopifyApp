import { useState } from "react";
import { api } from "../services/api.js";
import useFetch from "../hooks/useFetch.js";
import DataTable from "../components/DataTable.jsx";
import Pagination from "../components/Pagination.jsx";
import Loading from "../components/Loading.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

export default function Orders() {
  const [status, setStatus] = useState("any");
  const [pageInfo, setPageInfo] = useState("");
  const { data, loading, error } = useFetch(() => api.orders({ status, page_info: pageInfo }), [status, pageInfo]);

  return (
    <>
      <h1>Orders</h1>
      <div className="notice">
        Without the read_all_orders permission, Shopify only returns orders from the last 60 days.
      </div>
      <div className="filters">
        <select value={status} onChange={(e) => { setPageInfo(""); setStatus(e.target.value); }}>
          <option value="any">All orders</option>
          <option value="open">Open</option>
          <option value="closed">Closed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>
      {loading && <Loading />}
      <ErrorMessage message={error} />
      {data && (
        <>
          <DataTable
            rows={data.items}
            empty="No orders found."
            columns={[
              { key: "name", label: "Order" },
              { key: "created_at", label: "Date", render: (o) => (o.created_at || "").slice(0, 10) },
              { key: "item_count", label: "Items" },
              { key: "total_price", label: "Total", render: (o) => `${o.total_price} ${o.currency}` },
              { key: "financial_status", label: "Payment", render: (o) => <StatusBadge value={o.financial_status} /> },
              { key: "fulfillment_status", label: "Fulfilment", render: (o) => <StatusBadge value={o.fulfillment_status} /> },
            ]}
          />
          <Pagination page={data} onChange={setPageInfo} />
        </>
      )}
    </>
  );
}
