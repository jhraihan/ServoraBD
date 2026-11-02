import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { me } from "../../api/endpoints";
import { Money } from "../../components/domain";
import { ErrorMessage, PageHeader, PageLoader, SkeletonList, Stat } from "../../components/ui";
import { LEDGER_KIND_LABEL } from "../../constants/domain";
import { formatDate, formatPeriod, plural } from "../../lib/format";

const PERIODS = [
  ["month", "By month"],
  ["week", "By week"],
  ["day", "By day"],
];

export default function Earnings() {
  const [period, setPeriod] = useState("month");
  const earnings = useQuery({
    queryKey: ["earnings", period],
    queryFn: () => me.earnings({ period }),
    placeholderData: keepPreviousData,
  });
  const ledger = useQuery({ queryKey: ["ledger"], queryFn: () => me.ledger({ page_size: 50 }) });

  if (earnings.isLoading) return <PageLoader />;
  if (earnings.error && !earnings.data) return <ErrorMessage error={earnings.error} onRetry={earnings.refetch} />;

  const s = earnings.data.summary;

  return (
    <>
      <PageHeader title="Earnings" subtitle="Cash jobs: you collect the full amount and owe the platform its commission." />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Earned (gross)" value={<Money value={s.gross} />} hint={plural(s.jobs, "completed job")} />
        <Stat label="Platform commission" value={<Money value={s.commission} />} />
        <Stat label="Your net" value={<Money value={s.net} />} />
        <Stat label="You owe the platform" value={<Money value={s.outstandingPayable} />} hint={Number(s.outstandingPayable) > 0 ? "Settle via bKash or cash" : "All settled"} />
      </div>

      {s.flaggedPayments > 0 && (
        <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {s.flaggedPayments} job{s.flaggedPayments > 1 ? "s are" : " is"} under review because the amount you recorded differs
          from what the customer confirmed. It is left out of your earnings until our team resolves it.
        </div>
      )}

      <section className="mt-8">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="section-title">Over time</h2>
          <div className="flex gap-1" role="tablist">
            {PERIODS.map(([key, label]) => (
              <button key={key} type="button" role="tab" aria-selected={period === key} onClick={() => setPeriod(key)} className={`rounded-full px-3 py-1 text-sm font-medium ${period === key ? "bg-brand-700 text-white" : "bg-white text-slate-700 ring-1 ring-slate-200"}`}>
                {label}
              </button>
            ))}
          </div>
        </div>
        <ErrorMessage error={earnings.error} onRetry={earnings.refetch} className="mb-3" />
        {earnings.data.periods.length === 0 ? (
          <p className="card p-5 text-sm text-slate-600">No completed jobs yet.</p>
        ) : (
          <div className={`card overflow-x-auto transition-opacity ${earnings.isPlaceholderData ? "opacity-60" : ""}`}>
            <table className="w-full min-w-[480px] text-sm">
              <thead className="border-b border-slate-200 text-left text-xs uppercase text-slate-600">
                <tr>
                  <th scope="col" className="p-3">Period</th>
                  <th scope="col" className="p-3 text-right">Jobs</th>
                  <th scope="col" className="p-3 text-right">Gross</th>
                  <th scope="col" className="p-3 text-right">Commission</th>
                  <th scope="col" className="p-3 text-right">Net</th>
                </tr>
              </thead>
              <tbody>
                {earnings.data.periods.map((row) => (
                  <tr key={row.period} className="border-b border-slate-100 last:border-0">
                    <td className="p-3">{formatPeriod(row.period, earnings.data.period)}</td>
                    <td className="p-3 text-right tabular-nums">{row.jobs}</td>
                    <td className="p-3 text-right"><Money value={row.gross} /></td>
                    <td className="p-3 text-right text-slate-600"><Money value={row.commission} /></td>
                    <td className="p-3 text-right font-semibold"><Money value={row.net} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="mt-8">
        <h2 className="section-title mb-3">Ledger</h2>
        <ErrorMessage error={ledger.error} onRetry={ledger.refetch} className="mb-3" />
        {ledger.isLoading ? (
          <SkeletonList count={1} itemClassName="h-40" />
        ) : !ledger.data ? null : (
          <ul className="card divide-y divide-slate-100">
            {ledger.data.results.length === 0 && <li className="p-4 text-sm text-slate-600">No entries yet.</li>}
            {ledger.data.results.map((e) => (
              <li key={e.id} className="flex items-center justify-between gap-3 p-4 text-sm">
                <div>
                  <p className="font-medium text-ink">{LEDGER_KIND_LABEL[e.kind] ?? e.kind}</p>
                  <p className="text-xs text-slate-600">
                    {formatDate(e.createdAt)}
                    {e.bookingId && ` · Job #${e.bookingId}`}
                    {e.reference && ` · ${e.reference}`}
                  </p>
                </div>
                <Money value={e.amount} className={`font-semibold ${Number(e.amount) < 0 ? "text-slate-600" : "text-emerald-700"}`} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
