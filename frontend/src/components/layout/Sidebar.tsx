import { NavLink } from "react-router-dom";
import {
  BarChart3,
  ShoppingCart,
  Bell,
  Link2,
  GitCompare,
  Newspaper,
  Menu,
  X,
  Terminal,
  Brain,
} from "lucide-react";
import { useState } from "react";

const navItems = [
  { to: "/", label: "Portfolio", icon: BarChart3 },
  { to: "/orders", label: "Orders", icon: ShoppingCart },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/brokers", label: "Brokers", icon: Link2 },
  { to: "/comparison", label: "Comparison", icon: GitCompare },
  { to: "/news", label: "News", icon: Newspaper },
  { to: "/predictions", label: "AI Predictions", icon: Brain },
  { to: "/nerd-stats", label: "Nerd Stats", icon: Terminal },
];

export function Sidebar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        aria-label={mobileOpen ? "Close navigation" : "Open navigation"}
        className="fixed top-3 left-3 z-50 md:hidden inline-flex items-center justify-center rounded-md p-2 bg-background border shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      {/* Overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-56 border-r bg-background transition-transform md:static md:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-14 items-center border-b px-4">
          <span className="text-sm font-semibold">Navigation</span>
        </div>
        <nav className="flex flex-col gap-1 p-2" aria-label="Main navigation">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  isActive
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                }`
              }
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
    </>
  );
}
