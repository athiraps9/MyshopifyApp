import { Link } from "react-router-dom";
import { api } from "../services/api.js";
import useFetch from "../hooks/useFetch.js";
import Loading from "../components/Loading.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import DataTable from "../components/DataTable.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

export default function Dashboard() {
  const orders = useFetch(() => api.orders({ limit: 5 }), []);

  return (
    <>
      <h1>Dashboard</h1>
      <h2>Latest orders (from Shopify)</h2>
      {orders.loading && <Loading />}
      <ErrorMessage message={orders.error} />
      {orders.data && (
        <DataTable
          rows={orders.data.items}
          empty="No orders yet."
          columns={[
            { key: "name", label: "Order" },
            { key: "total_price", label: "Total", render: (o) => `${o.total_price} ${o.currency}` },
            { key: "financial_status", label: "Payment", render: (o) => <StatusBadge value={o.financial_status} /> },
            { key: "fulfillment_status", label: "Fulfilment", render: (o) => <StatusBadge value={o.fulfillment_status} /> },
          ]}
        />
      )}
      <p><Link to="/orders">See all orders</Link></p>
    </>
  );
}
