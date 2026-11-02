import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import PropTypes from "prop-types";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { me, requests } from "../../api/endpoints";
import { Money } from "../../components/domain";
import { TrustBadge } from "../../components/Trust";
import { Button, EmptyState, ErrorMessage, PageHeader, PageLoader, SkeletonList, Spinner, Stat } from "../../components/ui";
import { formatDateTime, plural } from "../../lib/format";
import { toast } from "../../store/toast";

export default function Dashboard() {
  const queryClient = useQueryClient();
  const dashboard = useQuery({ queryKey: ["provider-dashboard"], queryFn: me.dashboard });
  const inbox = useQuery({ queryKey: ["provider-inbox"], queryFn: me.inbox, refetchInterval: 30000 });
  const toggle = useMutation({
    mutationFn: (accepting) => me.setAcceptingWork(accepting),
    onSuccess: (_data, accepting) => {
      queryClient.invalidateQueries({ queryKey: ["provider-dashboard"] });
      toast(accepting ? "You are taking new jobs again." : "Paused. You will not get new requests.");
    },
    onError: (err) => toast(err.message, "bad"),
  });

  if (dashboard.isLoading) return <PageLoader />;
  if (dashboard.error) return <ErrorMessage error={dashboard.error} onRetry={dashboard.refetch} />;

  const d = dashboard.data;

  return (
    <>
      <PageHeader
        title="Dashboard"
        action={
          <label className={`flex cursor-pointer items-center gap-3 rounded-2xl px-4 py-2 ring-1 transition has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand-700 ${d.isAcceptingWork ? "bg-emerald-50 ring-emerald-200" : "bg-white ring-slate-200"}`}>
            <span className={`h-2.5 w-2.5 rounded-full ${d.isAcceptingWork ? "bg-emerald-500" : "bg-slate-400"}`} aria-hidden="true" />
            <span className="text-sm font-medium text-slate-700">Taking new jobs</span>
            <input
              type="checkbox"
              role="switch"
              className="h-5 w-5 accent-brand-700"
              checked={d.isAcceptingWork}
              disabled={toggle.isPending}
              onChange={(e) => toggle.mutate(e.target.checked)}
            />
          </label>
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="card flex flex-col justify-between p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-600">Your trust</p>
          <div className="mt-2"><TrustBadge score={d.trust.score} tier={d.trust.tier} /></div>
          <Link to="/provider/trust" className="mt-2 text-xs font-semibold text-brand-700">See breakdown →</Link>
        </div>
        <Stat label="Open requests" value={d.openRequests} hint="In your areas" />
        <Stat label="Upcoming jobs" value={d.bookings.upcoming} hint={d.bookings.awaitingConfirm ? `${d.bookings.awaitingConfirm} awaiting customer` : undefined} />
        <Stat label="Earned this month" value={<Money value={d.earnings.thisMonth.net} />} hint={`${plural(d.earnings.thisMonth.jobs, "job")}, after commission`} />
      </div>

      {Number(d.earnings.outstandingPayable) > 0 && (
        <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          You owe <Money value={d.earnings.outstandingPayable} className="font-semibold" /> in platform commission from cash jobs.{" "}
          <Link to="/provider/earnings" className="font-semibold underline">View earnings</Link>
        </div>
      )}

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <section aria-labelledby="inbox-heading">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 id="inbox-heading" className="section-title">
              New requests{inbox.data?.length ? ` (${inbox.data.length})` : ""}
            </h2>
            <button
              type="button"
              onClick={() => inbox.refetch()}
              disabled={inbox.isFetching}
              className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-semibold text-brand-700 hover:bg-brand-50 disabled:text-slate-600"
            >
              {inbox.isFetching && <Spinner small label="Checking for requests" />}
              {inbox.isFetching ? "Checking…" : "Refresh"}
            </button>
          </div>
          <ErrorMessage error={inbox.error} onRetry={inbox.refetch} className="mb-3" />
          {inbox.isLoading ? (
            <SkeletonList count={2} itemClassName="h-40" />
          ) : !inbox.data ? null : inbox.data.length === 0 ? (
            <EmptyState
              title="No open requests right now"
              body={d.isAcceptingWork ? "New requests in your areas appear here. Replying quickly improves your trust score." : "You are paused. Turn on “Taking new jobs” to receive requests."}
            />
          ) : (
            <ul className="space-y-3">
              {inbox.data.map((r) => (
                <InboxItem key={r.id} request={r} />
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="next-heading">
          <h2 id="next-heading" className="section-title mb-3">Next jobs</h2>
          {d.bookings.next.length === 0 ? (
            <EmptyState title="Nothing scheduled" body="Accepted jobs appear here." />
          ) : (
            <ul className="space-y-3">
              {d.bookings.next.map((b) => (
                <li key={b.id}>
                  <Link to={`/provider/bookings/${b.id}`} className="card flex items-center justify-between p-4 hover:border-brand-300">
                    <div>
                      <p className="font-semibold text-ink">{b.service?.name}</p>
                      <p className="text-sm text-slate-600">{formatDateTime(b.scheduledFor)}</p>
                    </div>
                    <Money value={b.agreedPrice} className="font-semibold text-ink" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}

function InboxItem({ request }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState("");

  const respond = useMutation({
    mutationFn: (accept) => requests.respond(request.id, { accept, reason }),
    onSuccess: (booking, accept) => {
      queryClient.invalidateQueries({ queryKey: ["provider-inbox"] });
      queryClient.invalidateQueries({ queryKey: ["provider-dashboard"] });
      toast(accept ? "Job accepted. The address is now visible." : "Request declined.");
      if (booking) navigate(`/provider/bookings/${booking.id}`);
    },
    onError: () => queryClient.invalidateQueries({ queryKey: ["provider-inbox"] }),
  });

  return (
    <li className="card p-4" data-testid="inbox-item">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-ink">{request.service?.name}</p>
          <p className="text-sm text-slate-600">{request.location?.fullName} · {formatDateTime(request.preferredStart)}</p>
        </div>
        {request.kind === "direct" && <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-semibold text-brand-800">Sent to you</span>}
      </div>
      <p className="mt-2 text-sm text-slate-700">{request.description}</p>
      <p className="mt-2 text-xs text-slate-600">The exact address is shared once you accept.</p>
      <ErrorMessage error={respond.error} className="mt-3" />
      {declining ? (
        <div className="mt-3 space-y-2">
          <label htmlFor={`decline-${request.id}`} className="label">Reason (optional)</label>
          <input id={`decline-${request.id}`} className="input" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Fully booked that day" autoFocus />
          <div className="flex gap-2">
            <Button variant="danger" size="sm" loading={respond.isPending} onClick={() => respond.mutate(false)}>Decline</Button>
            <Button variant="ghost" size="sm" onClick={() => setDeclining(false)}>Back</Button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex gap-2">
          <Button size="sm" loading={respond.isPending && respond.variables === true} onClick={() => respond.mutate(true)}>Accept job</Button>
          <Button variant="secondary" size="sm" onClick={() => setDeclining(true)}>Decline</Button>
        </div>
      )}
    </li>
  );
}

InboxItem.propTypes = {
  request: PropTypes.shape({
    id: PropTypes.number.isRequired,
    kind: PropTypes.string,
    description: PropTypes.string,
    preferredStart: PropTypes.string,
    service: PropTypes.shape({ name: PropTypes.string }),
    location: PropTypes.shape({ fullName: PropTypes.string }),
  }).isRequired,
};
