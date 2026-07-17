import { NavLink } from "react-router-dom";
import { ChartIcon, FileIcon, HomeIcon, PlanIcon, ReviewIcon } from "../ui/Icons";

type NavigationItem = {
  to: string;
  label: string;
  icon: React.ReactNode;
  badge?: string;
};

const groups: { label: string; items: NavigationItem[] }[] = [
  {
    label: "",
    items: [{ to: "/", label: "Home", icon: <HomeIcon /> }],
  },
  {
    label: "Prepare",
    items: [
      { to: "/prepare/pdf", label: "Extract from PDF", icon: <FileIcon /> },
      { to: "/prepare/requirements", label: "Extract requirements", icon: <FileIcon /> },
      { to: "/prepare/chapters", label: "Extract chapters", icon: <FileIcon /> },
    ],
  },
  {
    label: "Analyse and compare",
    items: [
      { to: "/review/inconsistencies", label: "Compare specification versions", icon: <ReviewIcon /> },
      {
        to: "/review/ambiguities",
        label: "Check for Inconsistencies",
        icon: <ReviewIcon />,
        badge: "Unused",
      },
      {
        to: "/review/quality",
        label: "Quality checker",
        icon: <ReviewIcon />,
      },
    ],
  },
  {
    label: "Verification",
    items: [
      { to: "/verification/generate", label: "Generate vPlan", icon: <PlanIcon /> },
      { to: "/verification/vplan", label: "View vPlan", icon: <PlanIcon /> },
      { to: "/verification/edge-cases", label: "Edge cases", icon: <ReviewIcon /> },
      { to: "/verification/weak-language", label: "Weak language", icon: <ReviewIcon /> },
      { to: "/verification/coverage", label: "Check coverage", icon: <ChartIcon /> },
    ],
  },
  {
    label: "Reports",
    items: [{ to: "/reports/metrics", label: "Usage and cost", icon: <ChartIcon /> }],
  },
];

export default function Sidebar({
  collapsed,
  mobileOpen,
  onToggle,
  onClose,
}: {
  collapsed: boolean;
  mobileOpen: boolean;
  onToggle: () => void;
  onClose: () => void;
}) {
  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""} ${mobileOpen ? "mobile-open" : ""}`}>
      <div className="sidebar-brand">
        <span className="brand-mark">S</span>
        {!collapsed && (
          <span>
            <strong>Spec Workspace</strong>
            <small>Verification toolkit</small>
          </span>
        )}
      </div>

      <nav>
        {groups.map((group, index) => (
          <section className="nav-group" key={index}>
            {group.label && !collapsed && <p>{group.label}</p>}

            {group.items.map((item) => (
              <NavLink
                end={item.to === "/"}
                title={collapsed ? `${item.label}${item.badge ? ` — ${item.badge}` : ""}` : undefined}
                onClick={onClose}
                className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
                to={item.to}
                key={item.to}
              >
                <span className="nav-icon">{item.icon}</span>

                {!collapsed && (
                  <span className="nav-label">
                    <span>{item.label}</span>
                    {item.badge && <small className="nav-badge">{item.badge}</small>}
                  </span>
                )}
              </NavLink>
            ))}
          </section>
        ))}
      </nav>

      <button className="collapse-button" onClick={onToggle}>
        {collapsed ? "›" : "‹  Minimise menu"}
      </button>
    </aside>
  );
}
