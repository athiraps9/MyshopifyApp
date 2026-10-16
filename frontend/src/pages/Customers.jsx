import { useState } from "react";
import { api } from "../services/api.js";
import useFetch from "../hooks/useFetch.js";
import SearchBar from "../components/SearchBar.jsx";
import DataTable from "../components/DataTable.jsx";
import Pagination from "../components/Pagination.jsx";
import Loading from "../components/Loading.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";

export default function Customers() {
  const [search, setSearch] = useState("");
  const [pageInfo, setPageInfo] = useState("");
  const { data, loading, error } = useFetch(() => api.customers({ search, page_info: pageInfo }), [search, pageInfo]);

  return (
    <>
      <h1>Customers</h1>
      <SearchBar placeholder="Search name or email" onSearch={(v) => { setPageInfo(""); setSearch(v); }} />
      {loading && <Loading />}
      <ErrorMessage message={error} />
      {data && (
        <>
          <DataTable
            rows={data.items}
            empty="No customers found."
            columns={[
              { key: "name", label: "Name" },
              { key: "email", label: "Email" },
              { key: "orders_count", label: "Orders" },
              { key: "total_spent", label: "Total spent" },
            ]}
          />
          <Pagination page={data} onChange={setPageInfo} />
        </>
      )}
    </>
  );
}
