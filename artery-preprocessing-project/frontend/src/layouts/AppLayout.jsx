import { useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Activity, BarChart3, ClipboardList, Database, FileImage, FileText,
  FolderOpen, HeartPulse, LayoutDashboard, LogOut, Menu, Shield, UserRound, Users, X,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";

const primaryNavigation = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/cases", label: "Cases", icon: FolderOpen },
  { to: "/upload", label: "Image upload", icon: FileImage, permission: "image:upload" },
  { to: "/preprocess", label: "Preprocessing", icon: Activity, permission: "image:preprocess" },
  { to: "/history", label: "Analysis history", icon: ClipboardList },
  { to: "/reports", label: "Reports", icon: FileText },
  { to: "/models", label: "Model comparison", icon: BarChart3 },
];

const administrationNavigation = [
  { to: "/dataset", label: "Dataset inspection", icon: Database, roles: ["data_scientist", "administrator"] },
  { to: "/admin/users", label: "User management", icon: Users, roles: ["administrator"] },
  { to: "/admin/audit", label: "Audit logs", icon: Shield, roles: ["administrator"] },
];

const pageTitles = [
  ["/dashboard", "Dashboard"], ["/cases/new", "Create case"], ["/cases/", "Case workspace"],
  ["/cases", "Cases"], ["/upload", "Image upload"], ["/preprocess", "Image preprocessing"],
  ["/history", "Analysis history"], ["/reports", "Reports"], ["/models", "Model comparison"],
  ["/dataset", "Dataset inspection"], ["/admin/users", "User management"],
  ["/admin/audit", "Audit logs"], ["/profile", "Profile settings"],
];

function NavItem({ item, closeMenu }) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      end={item.to === "/cases"}
      onClick={closeMenu}
      className={({ isActive }) => `app-nav-link ${isActive ? "app-nav-link-active" : ""}`}
    >
      <Icon aria-hidden="true" size={18} strokeWidth={1.8} />
      <span>{item.label}</span>
    </NavLink>
  );
}

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const title = pageTitles.find(([path]) => path === location.pathname)?.[1]
    || pageTitles.find(([path]) => path.endsWith("/") && location.pathname.startsWith(path))?.[1]
    || "Artery analysis";
  const roleLabel = (user?.role || "user").replaceAll("_", " ");
  const visiblePrimary = primaryNavigation.filter((item) => !item.permission || user?.permissions?.includes(item.permission));
  const visibleAdministration = administrationNavigation.filter((item) => item.roles.includes(user?.role));

  const onLogout = async () => {
    setLoggingOut(true);
    try {
      await logout();
      navigate("/login");
    } finally {
      setLoggingOut(false);
    }
  };

  const closeMenu = () => setMenuOpen(false);

  return (
    <div className="app-shell min-h-screen lg:grid lg:grid-cols-[260px_minmax(0,1fr)]">
      <aside className={`${menuOpen ? "block" : "hidden"} app-sidebar lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col`}>
        <Link to="/dashboard" className="app-brand" onClick={closeMenu}>
          <span className="app-brand-mark"><HeartPulse aria-hidden="true" size={23} /></span>
          <span>
            <span className="block text-[15px] font-semibold tracking-tight">Artery Analysis</span>
            <span className="mt-0.5 block text-[11px] text-slate-300">Research workspace</span>
          </span>
        </Link>

        <div className="px-4 pt-5">
          <p className="app-nav-label">Workspace</p>
          <nav aria-label="Main navigation" className="mt-2 space-y-1">
            {visiblePrimary.map((item) => <NavItem key={item.to} item={item} closeMenu={closeMenu} />)}
          </nav>
        </div>

        {visibleAdministration.length ? (
          <div className="px-4 pt-6">
            <p className="app-nav-label">Administration</p>
            <nav aria-label="Administration navigation" className="mt-2 space-y-1">
              {visibleAdministration.map((item) => <NavItem key={item.to} item={item} closeMenu={closeMenu} />)}
            </nav>
          </div>
        ) : null}

        <div className="mt-auto border-t border-white/10 p-4">
          <Link to="/profile" onClick={closeMenu} className="app-profile-link">
            <span className="app-avatar"><UserRound aria-hidden="true" size={17} /></span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium text-white">{user?.full_name || user?.email || "Signed in user"}</span>
              <span className="mt-0.5 block truncate text-xs capitalize text-slate-300">{roleLabel}</span>
            </span>
            <UserRound aria-hidden="true" size={16} className="text-slate-400" />
          </Link>
          <button type="button" className="app-logout-button mt-3" onClick={onLogout} disabled={loggingOut}>
            <LogOut aria-hidden="true" size={17} />
            {loggingOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="app-topbar">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              className="app-menu-button lg:hidden"
              aria-label={menuOpen ? "Close navigation" : "Open navigation"}
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((open) => !open)}
            >
              {menuOpen ? <X size={19} /> : <Menu size={19} />}
            </button>
            <div className="min-w-0">
              <p className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">Clinical imaging research</p>
              <h1 className="truncate text-lg font-semibold text-slate-900">{title}</h1>
            </div>
          </div>
          <div className="hidden items-center gap-3 sm:flex">
            <span className="app-role-chip capitalize">{roleLabel}</span>
            <Link to="/profile" className="app-top-profile" aria-label="Open profile settings">
              <span className="app-avatar app-avatar-light"><UserRound aria-hidden="true" size={16} /></span>
              <span className="max-w-40 truncate text-sm font-medium">{user?.full_name || user?.email}</span>
            </Link>
          </div>
        </header>

        <main id="main-content" className="app-main min-w-0">
          <div className="mx-auto w-full max-w-[1480px]"> <Outlet /> </div>
          <footer className="app-footer">
            Research prototype. Model outputs require expert review and are not a standalone diagnosis.
          </footer>
        </main>
      </div>
    </div>
  );
}
