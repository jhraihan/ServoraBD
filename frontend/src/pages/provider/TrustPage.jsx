import { useQuery } from "@tanstack/react-query";

import { me, providers } from "../../api/endpoints";
import { TrustBadge, TrustBreakdown } from "../../components/Trust";
import { Button, EmptyState, ErrorMessage, PageHeader, PageLoader } from "../../components/ui";
import { useSession } from "../../hooks/useSession";
import { formatDateTime } from "../../lib/format";

const ADVICE = {
  f1_verification: "Upload both sides of your NID and a trade certificate on your profile page. Verification is the fastest way to raise your score.",
  f2_volume: "Complete more jobs. Every early job counts for a lot; the effect tapers off after about 100.",
  f3_completion: "Finish the jobs you accept. Accepting and then not completing drags this down sharply.",
  f4_cancellation: "Avoid cancelling, especially at short notice. A cancellation within 4 hours of the job costs four times more than one made a day ahead, and old cancellations fade over six months.",
  f5_response: "Reply to requests quickly — within 5 minutes scores full marks. Pause “Taking new jobs” when you are busy rather than leaving requests unanswered.",
  f6_reviews: "Do careful work and rate your customers after each job — their review of you is only published once you have rated them.",
};

const TRIGGER_LABEL = {
  booking_completed: "Job completed",
  booking_cancelled: "Job cancelled",
  review_changed: "Review published",
  verification_decided: "Verification reviewed",
  dispute_changed: "Dispute updated",
  nightly_batch: "Daily refresh",
  manual: "Recalculated",
};

export default function TrustPage() {
  const { user } = useSession();
  const trust = useQuery({
    queryKey: ["provider-trust", String(user.providerId)],
    queryFn: () => providers.trust(user.providerId),
    enabled: Boolean(user.providerId),
  });
  const history = useQuery({ queryKey: ["trust-history"], queryFn: me.trustHistory });

  if (trust.isLoading) return <PageLoader />;
  if (trust.error) return <ErrorMessage error={trust.error} onRetry={trust.refetch} />;
  if (!trust.data) {
    return (
      <>
        <PageHeader title="Your trust score" />
        <EmptyState
          title="No trust score yet"
          body="Finish setting up your provider profile and your score will appear here."
          action={<Button to="/provider/profile">Set up profile</Button>}
        />
      </>
    );
  }

  const weakest = [...trust.data.factors].sort((a, b) => a.score - b.score).slice(0, 2);

  return (
    <>
      <PageHeader title="Your trust score" subtitle="Exactly what customers see, and how to improve it." />
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          <TrustBreakdown trust={trust.data} />
          <section className="card p-5">
            <h2 className="section-title">Where you can gain the most</h2>
            <ul className="mt-3 space-y-3">
              {weakest.map((f) => (
                <li key={f.key} className="rounded-2xl bg-slate-50 p-4">
                  <p className="text-sm font-semibold text-ink">
                    {f.label} · {Math.round(f.score)}/100
                  </p>
                  <p className="mt-1 text-sm text-slate-600">{ADVICE[f.key]}</p>
                </li>
              ))}
            </ul>
          </section>
        </div>

        <section className="card h-fit p-5">
          <h2 className="section-title">History</h2>
          <ErrorMessage error={history.error} />
          <ul className="mt-3 divide-y divide-slate-100">
            {(history.data?.results ?? []).map((s) => (
              <li key={s.id} className="flex items-center justify-between py-2.5 text-sm">
                <div>
                  <p className="text-ink">{TRIGGER_LABEL[s.trigger] ?? s.trigger}</p>
                  <p className="text-xs text-slate-600">{formatDateTime(s.createdAt)}</p>
                </div>
                <TrustBadge score={s.score} tier={s.tier} />
              </li>
            ))}
            {history.data?.results.length === 0 && <li className="py-3 text-sm text-slate-600">No history yet.</li>}
          </ul>
        </section>
      </div>
    </>
  );
}
