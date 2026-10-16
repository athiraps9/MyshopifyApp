import { useState } from "react";
import { api } from "../services/api.js";
import useFetch from "../hooks/useFetch.js";
import SearchBar from "../components/SearchBar.jsx";
import Pagination from "../components/Pagination.jsx";
import Loading from "../components/Loading.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";

export default function Products() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [pageInfo, setPageInfo] = useState("");
  const [categories, setCategories] = useState([]);
  const [selected, setSelected] = useState(null);

  const { data, loading, error } = useFetch(
    () =>
      api.products({ search, category, page_info: pageInfo }).then((page) => {
        // Collect the categories (product types) we have seen so far for the filter box.
        setCategories((old) => [...new Set([...old, ...page.items.map((p) => p.product_type).filter(Boolean)])]);
        return page;
      }),
    [search, category, pageInfo]
  );

  const reset = (fn) => (value) => {
    setPageInfo(""); // a new filter always starts from page 1
    fn(value);
  };

  return (
    <>
      <h1>Products</h1>
      <div className="filters">
        <SearchBar placeholder="Search by product title" onSearch={reset(setSearch)} />
        <select value={category} onChange={(e) => reset(setCategory)(e.target.value)}>
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {loading && <Loading />}
      <ErrorMessage message={error} />
      {data && (
        <>
          {!data.items.length && <p className="muted">No products found.</p>}
          <div className="cards">
            {data.items.map((p) => (
              <div className="card" key={p.id}>
                {p.image ? <img src={p.image} alt={p.title} /> : <img alt="" />}
                <h3>{p.title}</h3>
                <p className="muted">{p.product_type || "Uncategorised"}</p>
                <p>{p.price_from != null ? `From ${p.price_from}` : ""}</p>
                <div className="row">
                  <button onClick={() => api.product(p.id).then(setSelected).catch((e) => alert(e.message))}>Details</button>
                  <a className="link-btn" href={p.store_url} target="_blank" rel="noreferrer">Buy in store</a>
                </div>
              </div>
            ))}
          </div>
          <Pagination page={data} onChange={setPageInfo} />
        </>
      )}

      {selected && (
        <div className="card" style={{ marginTop: 16 }}>
          <h2>{selected.title}</h2>
          <p>{selected.description || "No description."}</p>
          <ul>
            {selected.variants.map((v) => (
              <li key={v.id}>
                {v.title} - {v.price} {v.sku ? `(SKU ${v.sku})` : ""}
              </li>
            ))}
          </ul>
          <button onClick={() => setSelected(null)}>Close</button>
        </div>
      )}
    </>
  );
}
