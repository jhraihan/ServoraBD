import PropTypes from "prop-types";
import { useEffect, useState } from "react";
import {
  Link, NavLink, Navigate, Outlet, useLocation, useNavigate, useNavigationType,
} from "react-router-dom";

import ServiceSearch from "./ServiceSearch";
import { Toaster } from "./ui";
import { COMPARE_LIMIT, ROLE } from "../constants/domain";
import { useSession } from "../hooks/useSession";
import { useCompareStore } from "../store/compare";

const CUSTOMER_LINKS = [
  { to: "/services", label: "Find services" },
  { to: "/my-requests", label: "My requests" },
  { to: "/my-bookings", label: "My bookings" },
];

const PROVIDER_LINKS = [
  { to: "/provider/dashboard", label: "Dashboard" },
  { to: "/provider/bookings", label: "Jobs" },
  { to: "/provider/earnings", label: "Earnings" },
  { to: "/provider/trust", label: "Trust" },
  { to: "/provider/profile", label: "Profile" },
];

const GUEST_LINKS = [
  { to: "/services", label: "Find services" },
  { to: "/providers", label: "Browse providers" },
];

function navClass({ isActive }) {
  return [
    "block rounded-lg px-3 py-2 text-sm font-medium",
    isActive ? "bg-brand-50 text-brand-800" : "text-slate-700 hover:bg-slate-100",
  ].join(" ");
}

export default function Layout() {
  const { user, isAuthenticated, isProvider, logout, switchRole } = useSession();
  const compareCount = useCompareStore((s) => s.ids.length);
  const clearCompare = useCompareStore((s) => s.clear);
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const navigationType = useNavigationType();
  const navigate = useNavigate();

  useEffect(() => {
    setOpen(false);
    if (navigationType !== "POP") window.scrollTo(0, 0);
  }, [location.pathname, navigationType]);

  useEffect(() => {
    if (!open) return undefined;
    function onKey(event) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const isHome = location.pathname === "/";
  const hasOwnSearch = isHome || location.pathname.startsWith("/services");
  const showCompareTray = !isProvider && compareCount > 0 && location.pathname.startsWith("/providers");
  const links = !isAuthenticated ? GUEST_LINKS : isProvider ? PROVIDER_LINKS : CUSTOMER_LINKS;
  const otherRole = isProvider ? ROLE.CUSTOMER : ROLE.PROVIDER;
  const canSwitch = user?.roles?.includes(otherRole);

  async function handleSwitch() {
    await switchRole(otherRole);
    navigate(otherRole === ROLE.PROVIDER ? "/provider/dashboard" : "/");
  }

  async function handleLogout() {
    await logout();
    navigate("/");
  }

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-lg focus:bg-brand-700 focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-white"
      >
        Skip to main content
      </a>
      <header className="sticky top-0 z-30 border-b border-white/50 bg-white/55 backdrop-blur-2xl backdrop-saturate-150">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
          <Link to={isProvider ? "/provider/dashboard" : "/"} className="flex items-center gap-2">
            <img src="/favicon.svg" alt="" className="h-8 w-8" />
            <span className="text-lg font-bold tracking-tight text-ink">
              Servora<span className="text-brand-700">Bd</span>
            </span>
          </Link>

          {!isProvider && (
            <div className="hidden min-w-0 flex-1 max-w-sm lg:block">
              <ServiceSearch />
            </div>
          )}

          <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
            {links.map((l) => (
              <NavLink key={l.to} to={l.to} className={navClass}>
                {l.label}
              </NavLink>
            ))}
            {!isProvider && compareCount > 0 && (
              <NavLink to="/compare" className={navClass}>
                Compare ({compareCount})
              </NavLink>
            )}
          </nav>

          <div className="hidden items-center gap-2 md:flex">
            <AccountActions
              isAuthenticated={isAuthenticated}
              name={user?.fullName}
              canSwitch={canSwitch}
              otherRole={otherRole}
              onSwitch={handleSwitch}
              onLogout={handleLogout}
            />
          </div>

          <button
            type="button"
            className="rounded-lg p-2 text-slate-700 hover:bg-slate-100 md:hidden"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls="mobile-menu"
            aria-label="Menu"
          >
            <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              {open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
            </svg>
          </button>
        </div>

        {open && (
          <div id="mobile-menu" className="border-t border-white/50 bg-white/80 px-4 py-3 backdrop-blur-2xl md:hidden">
            {!isProvider && (
              <div className="mb-3">
                <ServiceSearch onNavigate={() => setOpen(false)} />
              </div>
            )}
            <nav className="flex flex-col gap-1" aria-label="Mobile">
              {links.map((l) => (
                <NavLink key={l.to} to={l.to} className={navClass}>
                  {l.label}
                </NavLink>
              ))}
              {!isProvider && compareCount > 0 && (
                <NavLink to="/compare" className={navClass}>
                  Compare ({compareCount})
                </NavLink>
              )}
            </nav>
            <div className="mt-3 flex flex-col gap-2 border-t border-slate-100 pt-3">
              <AccountActions
                isAuthenticated={isAuthenticated}
                name={user?.fullName}
                canSwitch={canSwitch}
                otherRole={otherRole}
                onSwitch={handleSwitch}
                onLogout={handleLogout}
              />
            </div>
          </div>
        )}
      </header>

      {!isProvider && !hasOwnSearch && (
        <div className="sticky top-16 z-20 border-b border-white/50 bg-white/55 px-4 py-3 backdrop-blur-2xl backdrop-saturate-150 lg:hidden">
          <div className="mx-auto max-w-6xl">
            <ServiceSearch />
          </div>
        </div>
      )}

      <main id="main" tabIndex={-1} className="mx-auto min-h-[calc(100svh-4rem)] w-full max-w-6xl flex-1 px-4 py-6 focus:outline-none sm:py-10">
        <Outlet />
      </main>

      {showCompareTray && (
        <>
          <div aria-hidden="true" className="h-20" />
          <CompareTray count={compareCount} onClear={clearCompare} />
        </>
      )}
      <Toaster />

      <footer className="border-t border-white/50 bg-white/50 backdrop-blur-2xl">
        <div className="mx-auto max-w-6xl px-4 py-6 text-xs text-slate-600">
          ServoraBd · Verified local services in Dhaka · Trust scores are computed from recorded jobs, not self-reported.
        </div>
      </footer>
    </div>
  );
}

function CompareTray({ count, onClear }) {
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-40 flex justify-center px-4">
      <section
        aria-label="Comparison"
        className="on-dark pointer-events-auto flex items-center gap-2 rounded-full bg-ink py-2 pr-2 pl-5 text-sm text-white shadow-2xl motion-safe:animate-rise-in"
      >
        <span className="font-medium whitespace-nowrap">
          {count} of {COMPARE_LIMIT} picked
        </span>
        <button type="button" onClick={onClear} className="rounded-full px-3 py-2 text-white/80 hover:bg-white/10 hover:text-white">
          Clear
        </button>
        <Link to="/compare" className="rounded-full bg-white px-4 py-2 font-semibold whitespace-nowrap text-ink hover:bg-brand-50">
          Compare now
        </Link>
      </section>
    </div>
  );
}

CompareTray.propTypes = {
  count: PropTypes.number.isRequired,
  onClear: PropTypes.func.isRequired,
};

function AccountActions({ isAuthenticated, name, canSwitch, otherRole, onSwitch, onLogout }) {
  if (!isAuthenticated) {
    return (
      <>
        <Link to="/login" className="rounded-xl px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100">
          Log in
        </Link>
        <Link to="/register" className="rounded-xl bg-brand-700 px-4 py-2 text-center text-sm font-semibold text-white hover:bg-brand-800">
          Sign up
        </Link>
      </>
    );
  }

  return (
    <>
      <span className="truncate px-1 text-sm text-slate-600">{name}</span>
      {canSwitch && (
        <button type="button" onClick={onSwitch} className="rounded-xl border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
          Switch to {otherRole}
        </button>
      )}
      <button type="button" onClick={onLogout} className="rounded-xl px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100">
        Log out
      </button>
    </>
  );
}

AccountActions.propTypes = {
  isAuthenticated: PropTypes.bool.isRequired,
  name: PropTypes.string,
  canSwitch: PropTypes.bool,
  otherRole: PropTypes.string.isRequired,
  onSwitch: PropTypes.func.isRequired,
  onLogout: PropTypes.func.isRequired,
};

export function RequireRole({ role, children }) {
  const { isAuthenticated, user } = useSession();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  if (role && user?.activeRole !== role) {
    if (user?.roles?.includes(role)) {
      return <SwitchPrompt role={role} />;
    }
    return <Navigate to={user?.activeRole === ROLE.PROVIDER ? "/provider/dashboard" : "/"} replace />;
  }
  return children;
}

RequireRole.propTypes = {
  role: PropTypes.oneOf(Object.values(ROLE)),
  children: PropTypes.node.isRequired,
};

function SwitchPrompt({ role }) {
  const { switchRole } = useSession();
  return (
    <div className="card mx-auto max-w-md p-6 text-center">
      <p className="font-semibold text-ink">This page is for your {role} account.</p>
      <button
        type="button"
        onClick={() => switchRole(role)}
        className="mt-4 rounded-xl bg-brand-700 px-4 py-2 text-sm font-semibold text-white"
      >
        Switch to {role}
      </button>
    </div>
  );
}

SwitchPrompt.propTypes = { role: PropTypes.string.isRequired };
