import { NavLink } from "react-router-dom";

const links = [
  ["/", "Dashboard"],
  ["/products", "Products"],
  ["/orders", "Orders"],
];

export default function Layout({ children }) {
  return (
    <div className="app">
      <header className="topbar">
        <strong>Pharmacy Dashboard</strong>
        <nav>
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"}>
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main>{children}</main>
    </div>
  );
}
