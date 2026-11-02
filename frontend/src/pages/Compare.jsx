import { useQueries } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { providers } from "../api/endpoints";
import { Money } from "../components/domain";
import { TrustBadge } from "../components/Trust";
import { Button, EmptyState, PageHeader, PageLoader } from "../components/ui";
import { COMPARE_LIMIT } from "../constants/domain";
import { formatDuration, formatPercent } from "../lib/format";
import { useCompareStore } from "../store/compare";

function yes(value) {
  return value ? (
    <span className="font-semibold text-emerald-700"><span aria-hidden="true">✓ </span>Yes</span>
  ) : (
    <span className="text-slate-600">No</span>
  );
}

function lowestPrice(c) {
  const prices = c.p.offerings.filter((o) => o.isActive).map((o) => Number(o.price));
  return prices.length ? Math.min(...prices) : null;
}

const ROWS = [
  { label: "Trust", render: (c) => <TrustBadge score={c.t.score} tier={c.t.tier} />, value: (c) => c.t.score, better: "high" },
  { label: "Identity verified", render: (c) => yes(c.t.verification.identity) },
  { label: "Trade certificate", render: (c) => yes(c.t.verification.skill) },
  { label: "Jobs completed", render: (c) => c.t.evidence.jobsCompleted, value: (c) => c.t.evidence.jobsCompleted, better: "high" },
  { label: "Completion rate", render: (c) => formatPercent(c.t.evidence.completionRate), value: (c) => c.t.evidence.completionRate, better: "high" },
  { label: "Cancellation rate", render: (c) => formatPercent(c.t.evidence.cancellationRate), value: (c) => c.t.evidence.cancellationRate, better: "low" },
  { label: "Typical response", render: (c) => formatDuration(c.t.evidence.medianResponseSeconds), value: (c) => c.t.evidence.medianResponseSeconds, better: "low" },
  {
    label: "Lowest price",
    render: (c) => {
      const price = lowestPrice(c);
      return price === null ? "—" : <Money value={price} />;
    },
    value: lowestPrice,
    better: "low",
  },
  { label: "Experience", render: (c) => (c.p.experienceYears ? `${c.p.experienceYears} yrs` : "—"), value: (c) => c.p.experienceYears || null, better: "high" },
];

function bestIds(columns, row) {
  if (!row.value || columns.length < 2) return new Set();
  const scored = columns
    .map((c) => ({ id: c.id, raw: row.value(c) }))
    .filter(({ raw }) => raw !== null && raw !== undefined && raw !== "" && !Number.isNaN(Number(raw)))
    .map(({ id, raw }) => ({ id, n: Number(raw) }));
  if (scored.length < 2) return new Set();
  const target = row.better === "high" ? Math.max(...scored.map((s) => s.n)) : Math.min(...scored.map((s) => s.n));
  if (scored.every((s) => s.n === target)) return new Set();
  return new Set(scored.filter((s) => s.n === target).map((s) => s.id));
}

export default function Compare() {
  const ids = useCompareStore((s) => s.ids);
  const toggle = useCompareStore((s) => s.toggle);
  const clear = useCompareStore((s) => s.clear);

  const details = useQueries({
    queries: ids.map((id) => ({ queryKey: ["provider", String(id)], queryFn: () => providers.detail(id) })),
  });
  const trusts = useQueries({
    queries: ids.map((id) => ({ queryKey: ["provider-trust", String(id)], queryFn: () => providers.trust(id) })),
  });

  if (ids.length === 0) {
    return (
      <>
        <PageHeader title="Compare providers" />
        <EmptyState
          title="Nothing to compare yet"
          body="Tap “Compare” on up to three providers to see them side by side."
          action={<Button to="/providers">Browse providers</Button>}
        />
      </>
    );
  }

  if (details.some((q) => q.isLoading) || trusts.some((q) => q.isLoading)) return <PageLoader />;

  const columns = ids.map((id, i) => ({ id, p: details[i].data, t: trusts[i].data })).filter((c) => c.p && c.t);
  const failed = ids.filter((id, i) => details[i].error || trusts[i].error);

  return (
    <>
      <PageHeader
        title="Compare providers"
        subtitle="The same facts, side by side. The best value in each row is highlighted."
        action={
          <div className="flex flex-wrap gap-2">
            {ids.length < COMPARE_LIMIT && <Button variant="secondary" size="sm" to="/providers">Add another</Button>}
            <Button variant="secondary" size="sm" onClick={clear}>Clear all</Button>
          </div>
        }
      />

      {failed.length > 0 && (
        <div role="alert" className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <span>{failed.length === 1 ? "One provider" : `${failed.length} providers`} could not be loaded and may no longer be listed.</span>
          <button type="button" onClick={() => failed.forEach((id) => toggle(id))} className="font-semibold underline underline-offset-2">
            Remove from comparison
          </button>
        </div>
      )}

      {columns.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[520px] text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th scope="col" className="p-4 text-left text-xs font-medium uppercase text-slate-600">Provider</th>
                {columns.map((c) => (
                  <th key={c.id} scope="col" className="p-4 text-left align-top">
                    <Link to={`/providers/${c.id}`} className="font-semibold text-ink hover:text-brand-700">{c.p.displayName}</Link>
                    <div className="mt-2 flex flex-wrap items-center gap-3">
                      <Link to={`/request-service?provider=${c.id}`} className="rounded-full bg-ink px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-900">
                        Request
                      </Link>
                      <button type="button" onClick={() => toggle(c.id)} className="text-xs font-medium text-slate-600 hover:text-rose-700">
                        Remove
                      </button>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ROWS.map((row) => {
                const best = bestIds(columns, row);
                return (
                  <tr key={row.label} className="border-b border-slate-100 last:border-0">
                    <th scope="row" className="p-4 text-left font-medium text-slate-600">{row.label}</th>
                    {columns.map((c) => (
                      <td key={c.id} className={`p-4 tabular-nums text-ink ${best.has(c.id) ? "bg-emerald-50/80" : ""}`}>
                        <span className="inline-flex flex-wrap items-center gap-1.5">
                          {row.render(c)}
                          {best.has(c.id) && (
                            <span className="rounded-full bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold tracking-wide text-emerald-800 uppercase">
                              Best
                            </span>
                          )}
                        </span>
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
