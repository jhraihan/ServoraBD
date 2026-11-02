import { keepPreviousData, useQuery } from "@tanstack/react-query";
import PropTypes from "prop-types";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { providers } from "../api/endpoints";
import LocationSelect from "../components/LocationSelect";
import { ProviderCard } from "../components/domain";
import { Button, ErrorMessage, PageHeader, SkeletonList, Spinner } from "../components/ui";
import { TRUST_TIER, TRUST_TIER_LABEL } from "../constants/domain";
import { flattenAreas, useAllServices, useLocationTree } from "../hooks/useCatalogue";
import { formatDate, plural, toDateInputValue } from "../lib/format";

const PAGE_SIZE = 10;

const FILTER_KEYS = ["service", "location", "tier", "min_trust", "verified_only", "available_on", "ordering"];

function FilterChip({ label, onRemove }) {
  return (
    <button
      type="button"
      onClick={onRemove}
      className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 py-1.5 pr-2 pl-3 text-sm font-medium text-brand-800 ring-1 ring-brand-200 transition ring-inset hover:bg-brand-100"
    >
      {label}
      <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <path d="M6 6l8 8M14 6l-8 8" strokeLinecap="round" />
      </svg>
      <span className="sr-only">— remove this filter</span>
    </button>
  );
}

FilterChip.propTypes = {
  label: PropTypes.string.isRequired,
  onRemove: PropTypes.func.isRequired,
};

export default function ProviderSearch() {
  const [params, setParams] = useSearchParams();
  const { data: services } = useAllServices();
  const { data: tree } = useLocationTree();
  const [filtersOpen, setFiltersOpen] = useState(false);

  const filters = Object.fromEntries(FILTER_KEYS.map((k) => [k, params.get(k) ?? ""]));
  const page = Number(params.get("page") ?? 1);

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ["provider-search", filters, page],
    queryFn: () => providers.search({ ...filters, page, page_size: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  });

  function update(key, value) {
    const next = new URLSearchParams(params);
    if (value === "" || value === null || value === false) next.delete(key);
    else next.set(key, String(value));
    if (key === "location" && !value && next.get("ordering") === "distance") next.delete("ordering");
    next.delete("page");
    setParams(next);
  }

  function clearAll() {
    setParams(new URLSearchParams());
  }

  function goToPage(n) {
    const next = new URLSearchParams(params);
    next.set("page", String(n));
    setParams(next);
    window.scrollTo({ top: 0 });
  }

  function showResults() {
    setFiltersOpen(false);
    document.getElementById("search-results")?.scrollIntoView({ block: "start" });
  }

  const selectedService = (services ?? []).find((s) => String(s.id) === filters.service);
  const siblings = selectedService
    ? (services ?? []).filter(
        (s) => s.categoryId === selectedService.categoryId && s.id !== selectedService.id,
      )
    : [];
  const areaLabel = flattenAreas(tree).find((a) => String(a.id) === filters.location)?.label;
  const activeCount = FILTER_KEYS.filter((k) => k !== "ordering" && filters[k]).length;
  const totalPages = data ? Math.max(1, Math.ceil(data.count / PAGE_SIZE)) : 1;

  const chips = [
    filters.service && { key: "service", label: selectedService?.name ?? "Service" },
    filters.location && { key: "location", label: areaLabel ?? "Area" },
    filters.available_on && { key: "available_on", label: `Free on ${formatDate(filters.available_on)}` },
    filters.tier && { key: "tier", label: TRUST_TIER_LABEL[filters.tier] ?? filters.tier },
    filters.min_trust && { key: "min_trust", label: `Trust ${filters.min_trust}+` },
    filters.verified_only && { key: "verified_only", label: "ID verified only" },
  ].filter(Boolean);

  return (
    <>
      <PageHeader
        title={selectedService ? `${selectedService.name} providers` : "Browse providers"}
        subtitle="Ranked by trust — measured from real jobs, not self-reported."
      />

      {selectedService && siblings.length > 0 && (
        <div className="mb-5 -mx-4 overflow-x-auto px-4 pb-1">
          <div className="flex gap-2">
            <span className="chip chip-active">{selectedService.name}</span>
            {siblings.map((s) => (
              <Link key={s.id} to={`/providers?service=${s.id}`} className="chip chip-idle">
                {s.name}
              </Link>
            ))}
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={() => setFiltersOpen((v) => !v)}
        aria-expanded={filtersOpen}
        aria-controls="search-filters"
        className="mb-4 flex w-full items-center justify-between rounded-2xl bg-white/85 px-4 py-3 text-sm font-semibold text-slate-800 ring-1 ring-slate-200 backdrop-blur-xl lg:hidden"
      >
        <span>Filters{activeCount > 0 && ` (${activeCount} active)`}</span>
        <svg viewBox="0 0 20 20" className={`h-5 w-5 transition-transform ${filtersOpen ? "rotate-180" : ""}`} fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="m5 8 5 5 5-5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <aside id="search-filters" className={`card h-fit space-y-4 p-4 lg:sticky lg:top-24 lg:block ${filtersOpen ? "" : "hidden"}`} aria-label="Filters">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink">Refine results</h2>
            {activeCount > 0 && (
              <button type="button" onClick={clearAll} className="text-sm font-semibold text-brand-700 hover:text-brand-800">
                Clear all
              </button>
            )}
          </div>
          <div>
            <label htmlFor="f-service" className="label">Service</label>
            <select id="f-service" className="input" value={filters.service} onChange={(e) => update("service", e.target.value)}>
              <option value="">Any service</option>
              {(services ?? []).map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="f-location" className="label">Area</label>
            <LocationSelect
              id="f-location"
              value={filters.location ? Number(filters.location) : null}
              onChange={(v) => update("location", v)}
            />
          </div>
          <div>
            <label htmlFor="f-date" className="label">Available on</label>
            <input id="f-date" type="date" className="input" min={toDateInputValue(new Date())} value={filters.available_on} onChange={(e) => update("available_on", e.target.value)} />
          </div>
          <div>
            <label htmlFor="f-tier" className="label">Trust tier</label>
            <select id="f-tier" className="input" value={filters.tier} onChange={(e) => update("tier", e.target.value)}>
              <option value="">Any tier</option>
              {[TRUST_TIER.TRUSTED_PRO, TRUST_TIER.ESTABLISHED, TRUST_TIER.RISING, TRUST_TIER.NEW].map((t) => (
                <option key={t} value={t}>{TRUST_TIER_LABEL[t]}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="f-sort" className="label">Sort by</label>
            <select id="f-sort" className="input" value={filters.ordering} onChange={(e) => update("ordering", e.target.value)}>
              <option value="">Highest trust</option>
              <option value="price">Lowest price</option>
              <option value="distance" disabled={!filters.location}>
                {filters.location ? "Nearest" : "Nearest (choose an area first)"}
              </option>
            </select>
          </div>
          <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300 accent-brand-700"
              checked={filters.verified_only === "true"}
              onChange={(e) => update("verified_only", e.target.checked ? "true" : "")}
            />
            Identity-verified only
          </label>
          <Button className="w-full lg:hidden" onClick={showResults}>
            {data ? `Show ${plural(data.count, "provider")}` : "Show providers"}
          </Button>
        </aside>

        <section id="search-results" aria-live="polite" className="scroll-mt-24">
          {chips.length > 0 && (
            <div className="mb-4 flex flex-wrap items-center gap-2">
              {chips.map((chip) => (
                <FilterChip key={chip.key} label={chip.label} onRemove={() => update(chip.key, "")} />
              ))}
              {chips.length > 1 && (
                <button type="button" onClick={clearAll} className="px-2 py-1.5 text-sm font-semibold text-slate-700 hover:text-brand-800">
                  Clear all
                </button>
              )}
            </div>
          )}

          <ErrorMessage error={error} onRetry={refetch} className="mb-4" />
          {isLoading ? (
            <SkeletonList count={3} itemClassName="h-44" />
          ) : !data ? null : data.results.length === 0 ? (
            <div className="card p-6">
              <h2 className="section-title">No one covers this yet</h2>
              <p className="mt-2 text-sm text-slate-600">
                {activeCount > 1
                  ? "Try removing a filter, or post a request and let providers come to you."
                  : "Post a request and every matching provider nearby will see it."}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button to={`/request-service${filters.service ? `?service=${filters.service}` : ""}`}>
                  Post a request
                </Button>
                {activeCount > 0 && (
                  <Button variant="secondary" onClick={clearAll}>
                    Clear filters
                  </Button>
                )}
              </div>
              {siblings.length > 0 && (
                <div className="mt-6 border-t border-slate-200 pt-4">
                  <p className="text-sm font-semibold text-ink">Related services with providers</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {siblings.slice(0, 6).map((s) => (
                      <Link key={s.id} to={`/providers?service=${s.id}`} className="chip chip-idle">
                        {s.name}
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <>
              <p className="mb-3 flex items-center gap-2 text-sm text-slate-600">
                {plural(data.count, "provider")}
                {isFetching && (
                  <span className="inline-flex items-center gap-1.5 text-brand-700">
                    <Spinner small label="Updating results" /> Updating…
                  </span>
                )}
              </p>
              <div className={`space-y-3 transition-opacity ${isFetching ? "opacity-60" : ""}`}>
                {data.results.map((p) => (
                  <ProviderCard key={p.id} provider={p} serviceId={filters.service || undefined} />
                ))}
              </div>
              {(data.next || data.previous) && (
                <nav className="mt-6 flex items-center justify-between gap-3" aria-label="Pages">
                  <Button variant="secondary" disabled={!data.previous} onClick={() => goToPage(page - 1)}>Previous</Button>
                  <span className="text-sm text-slate-600">Page {page} of {totalPages}</span>
                  <Button variant="secondary" disabled={!data.next} onClick={() => goToPage(page + 1)}>Next</Button>
                </nav>
              )}
            </>
          )}
        </section>
      </div>
    </>
  );
}
