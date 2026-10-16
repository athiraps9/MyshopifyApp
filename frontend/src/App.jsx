import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Products from "./pages/Products.jsx";
import Orders from "./pages/Orders.jsx";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/products" element={<Products />} />
        <Route path="/customers" element={<Navigate to="/" replace />} />
        <Route path="/orders" element={<Orders />} />
        <Route path="/crm" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
