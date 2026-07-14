import { Outlet } from "react-router-dom";
import { useState } from "react";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

export default function AppShell() {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("sidebar-collapsed") === "true");
  const [mobileOpen, setMobileOpen] = useState(false);
  const toggle = () => {
    setCollapsed(v => {
      localStorage.setItem("sidebar-collapsed", String(!v));
      return !v;
    });
  };
  return <div className={`app-shell ${collapsed ? "sidebar-collapsed" : ""}`}>
    <Sidebar collapsed={collapsed} mobileOpen={mobileOpen} onToggle={toggle} onClose={() => setMobileOpen(false)} />
    {mobileOpen && <button className="backdrop" aria-label="Close menu" onClick={() => setMobileOpen(false)} />}
    <div className="app-main">
      <TopBar onMenu={() => setMobileOpen(true)} />
      <main className="page-content"><Outlet /></main>
    </div>
  </div>;
}
