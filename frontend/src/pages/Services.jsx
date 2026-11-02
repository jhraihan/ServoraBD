import PropTypes from "prop-types";
import { useMemo } from "react";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";

import CategoryIcon from "../components/CategoryIcon";
import { Money } from "../components/domain";
import { Button, EmptyState, ErrorMessage, SkeletonList } from "../components/ui";
import { categoryTheme } from "../constants/categories";
import { matchServices, useAllServices, useCategories } from "../hooks/useCatalogue";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { plural } from "../lib/format";

function ServiceCard({ service, theme }) {
  return (
    <li className="group relative overflow-hidden rounded-3xl border border-white/70 bg-white/85 p-4 shadow-[0_10px_34px_-24px_rgba(18,38,26,0.5)] backdrop-blur-xl transition hover:-translate-y-0.5 hover:shadow-[0_18px_40px_-22px_rgba(18,38,26,0.45)]">
      <span
        aria-hidden="true"
        className={`absolute -top-10 -right-8 h-24 w-24 rounded-full bg-gradient-to-br ${theme.gradient} opacity-20 blur-2xl transition group-hover:opacity-35`}
      />
      <div className="relative flex items-start gap-3">
        <span
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br ${theme.gradient} text-white shadow-lg ${theme.glow}`}
        >
          <CategoryIcon name={service.categoryIcon} className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-ink">{service.name}</p>
          <p className="mt-0.5 text-xs font-medium" style={{ color: theme.accent }}>
            {service.categoryName}
          </p>
          <p className="mt-2 text-sm text-slate-600">
            {service.priceMin && service.priceMax ? (
              <>
                Typically <Money value={service.priceMin} className="font-semibold text-ink" />
                {" – "}
                <Money value={service.priceMax} className="font-semibold text-ink" />
              </>
            ) : (
              "Quoted after a visit"
            )}
          </p>
        </div>
      </div>
      <div className="relative mt-3 flex gap-2">
        <Link
          to={`/providers?service=${service.id}`}
          className="flex-1 rounded-full bg-ink px-4 py-2.5 text-center text-sm font-semibold text-white transition hover:bg-brand-900"
        >
          Find providers
        </Link>
        <Link
          to={`/request-service?service=${service.id}`}
          className="rounded-full border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-white"
        >
          Request
        </Link>
      </div>
    </li>
  );
}

ServiceCard.propTypes = {
  service: PropTypes.object.isRequired,
  theme: PropTypes.object.isRequired,
};

export function Services() {
  const categories = useCategories();
  const { data: services, isLoading, error, refetch } = useAllServices();
  const [params, setParams] = useSearchParams();
  const active = params.get("category") ?? "";
  const query = params.get("q") ?? "";

  const inCategory = useMemo(() => {
    const rows = services ?? [];
    return active ? rows.filter((s) => s.categorySlug === active) : rows;
  }, [services, active]);
  const visible = useMemo(() => matchServices(inCategory, query), [inCategory, query]);
  const elsewhere = active && query.trim() ? matchServices(services, query).length - visible.length : 0;

  function setParam(key, value) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }

  const activeCategory = (categories.data ?? []).find((c) => c.slug === active);
  useDocumentTitle(activeCategory ? activeCategory.name : "Services");

  return (
    <>
      <div className="mb-5 min-h-[4.5rem]">
        <h1 className="page-title">
          {activeCategory ? activeCategory.name : "Every service"}
        </h1>
        <p className="mt-1.5 text-slate-600">
          {activeCategory
            ? activeCategory.description
            : "Every service we cover, one tap from a provider."}
        </p>
        <div className="relative mt-5 max-w-xl">
          <label htmlFor="service-filter" className="sr-only">
            Filter services
          </label>
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" className="pointer-events-none absolute top-1/2 left-4 h-5 w-5 -translate-y-1/2 text-slate-600">
            <circle cx="9" cy="9" r="6" />
            <path d="M13.5 13.5 17 17" strokeLinecap="round" />
          </svg>
          <input
            id="service-filter"
            type="search"
            autoComplete="off"
            className="input rounded-full pl-12"
            placeholder="Filter by name or problem, e.g. “leak”"
            value={query}
            onChange={(e) => setParam("q", e.target.value)}
          />
        </div>
      </div>

      <div className="sticky top-16 z-10 -mx-4 mb-6 bg-canvas/85 px-4 py-3 backdrop-blur-xl">
        <div className="-mx-1 overflow-x-auto px-1 pb-1">
          <div className="flex min-h-[2.75rem] gap-2" role="group" aria-label="Categories">
            <button
              type="button"
              onClick={() => setParam("category", "")}
              aria-pressed={active === ""}
              className={`chip ${active === "" ? "chip-active" : "chip-idle"}`}
            >
              All {(services ?? []).length}
            </button>
            {(categories.data ?? []).map((c) => {
              const theme = categoryTheme(c.slug);
              const on = active === c.slug;
              return (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => setParam("category", c.slug)}
                  aria-pressed={on}
                  className={`chip ${on ? "text-white shadow-lg" : "chip-idle"}`}
                  style={on ? { backgroundColor: theme.accent } : undefined}
                >
                  <CategoryIcon name={c.icon} className="h-4 w-4" />
                  {c.name}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <ErrorMessage error={error || categories.error} onRetry={() => { refetch(); categories.refetch(); }} className="mb-4" />

      {isLoading ? (
        <SkeletonList count={6} itemClassName="h-40" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" />
      ) : services && visible.length === 0 ? (
        <EmptyState
          title={query.trim() ? `No services match “${query.trim()}”` : "No services here yet"}
          body={
            elsewhere > 0
              ? `${plural(elsewhere, "match", "matches")} in other categories.`
              : "Try a different word, or post a request describing the job and providers nearby will see it."
          }
          action={
            <>
              {elsewhere > 0 && <Button onClick={() => setParam("category", "")}>Search all categories</Button>}
              {query && <Button variant="secondary" onClick={() => setParam("q", "")}>Clear search</Button>}
              {elsewhere === 0 && <Button to="/request-service">Post a request</Button>}
            </>
          }
        />
      ) : (
        <>
          <p className="mb-3 text-sm text-slate-600" aria-live="polite">
            {plural(visible.length, "service")}
            {query.trim() && ` matching “${query.trim()}”`}
            {elsewhere > 0 && (
              <>
                {" · "}
                <button type="button" onClick={() => setParam("category", "")} className="font-semibold text-brand-700 hover:text-brand-800">
                  {elsewhere} more in other categories
                </button>
              </>
            )}
          </p>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {visible.map((s) => (
              <ServiceCard key={s.id} service={s} theme={categoryTheme(s.categorySlug)} />
            ))}
          </ul>
        </>
      )}
    </>
  );
}

export function CategoryServices() {
  const { categorySlug } = useParams();
  return <Navigate to={`/services?category=${encodeURIComponent(categorySlug)}`} replace />;
}
