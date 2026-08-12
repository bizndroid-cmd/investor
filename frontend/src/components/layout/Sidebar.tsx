import { NavLink } from "react-router-dom";
import {
  BarChart3,
  Bell,
  Link2,
  Menu,
  X,
  Crosshair,
  FileText,
  Wallet,
  Settings2,
  Coins,
  Target,
  Zap,
} from "lucide-react";
import { useState } from "react";

const navItems = [
  { to: "/goals", label: "Blueprint", icon: Target },
  { to: "/", label: "The Market", icon: BarChart3 },
  { to: "/earnings", label: "Earnings", icon: Wallet },
  { to: "/etfs", label: "ETFs", icon: Coins },
  { to: "/research", label: "Research", icon: Crosshair },
  { to: "/briefing", label: "AI Copilot", icon: FileText },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/brokers", label: "Brokers", icon: Link2 },
  { to: "/settings", label: "Settings", icon: Settings2 },
];

export function Sidebar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        aria-label={mobileOpen ? "Close navigation" : "Open navigation"}
        className="fixed top-3 left-3 z-50 md:hidden btn-icon border shadow-sm bg-card"
      >
        {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      {/* Overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden animate-fade-in"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-60 border-r bg-card/95 backdrop-blur-md transition-transform duration-300 ease-out md:static md:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Logo */}
        <div className="flex h-14 items-center gap-2.5 border-b px-5">
          <div className="flex items-center justify-center h-7 w-7 rounded-lg bg-primary/10">
            <Zap className="h-4 w-4 text-primary" />
          </div>
          <span className="text-sm font-bold tracking-tight">Investor</span>
        </div>

        {/* Navigation */}
        <nav className="flex flex-col gap-0.5 p-3 mt-1" aria-label="Main navigation">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                isActive ? "nav-link nav-link-active" : "nav-link"
              }
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span className="truncate">{label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Bottom section */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t">
          <div className="flex items-center gap-2 px-2">
            <div className="h-2 w-2 rounded-full bg-success animate-pulse-soft" />
            <span className="text-[11px] text-muted-foreground">System Online</span>
          </div>
        </div>
      </aside>
    </>
  );
}
