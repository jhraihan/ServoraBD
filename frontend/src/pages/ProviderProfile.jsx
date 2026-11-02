import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { providers } from "../api/endpoints";
import { Money, Stars } from "../components/domain";
import { TrustBreakdown } from "../components/Trust";
import { Badge, Button, ErrorMessage, PageLoader } from "../components/ui";
import { COMPARE_LIMIT, PRICE_FLAG_LABEL, TRUST_TIER, WEEKDAYS } from "../constants/domain";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { formatDate, formatTime, toDateInputValue } from "../lib/format";
import { useCompareStore } from "../store/compare";

function BackLink() {
  const navigate = useNavigate();
  const canGoBack = (window.history.state?.idx ?? 0) > 0;
  return (
    <Link
      to="/providers"
      onClick={(e) => {
        if (!canGoBack) return;
        e.preventDefault();
        navigate(-1);
      }}
      className="block text-center text-sm font-semibold text-brand-700 hover:text-brand-800"
    >
      ← Back to providers
    </Link>
  );
}

export default function ProviderProfile() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const preferredService = params.get("service");
  const today = toDateInputValue(new Date());

  const detail = useQuery({ queryKey: ["provider", id], queryFn: () => providers.detail(id) });
  const trust = useQuery({ queryKey: ["provider-trust", id], queryFn: () => providers.trust(id) });
  const reviews = useQuery({ queryKey: ["provider-reviews", id], queryFn: () => providers.reviews(id) });
  const calendar = useQuery({
    queryKey: ["provider-calendar", id],
    queryFn: () => providers.calendar(id, { start: today, days: 7 }),
  });
  const providerId = Number(id);
  const inCompare = useCompareStore((s) => s.ids.includes(providerId));
  const compareFull = useCompareStore((s) => s.ids.length >= COMPARE_LIMIT);
  const toggleCompare = useCompareStore((s) => s.toggle);
  useDocumentTitle(detail.data?.displayName);

  if (detail.isLoading) return <PageLoader />;
  if (detail.error) {
    return (
      <div className="mx-auto max-w-md space-y-4">
        <ErrorMessage error={detail.error} onRetry={detail.refetch} />
        <BackLink />
      </div>
    );
  }

  const p = detail.data;
  const bookable = p.offerings.filter((o) => o.isActive);
  const firstName = p.displayName.split(" ")[0];
  const underReview = trust.data?.tier === TRUST_TIER.UNDER_REVIEW;
  const blockedReason = !p.isAcceptingWork
    ? `${firstName} is not taking new jobs right now. You can still post a request for every provider nearby.`
    : bookable.length === 0
      ? `${firstName} has not listed any services yet.`
      : underReview
        ? "Booking is paused while this provider's record is reviewed."
        : null;
  const requestLink = `/request-service?provider=${p.id}${preferredService ? `&service=${preferredService}` : ""}`;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px] lg:grid-rows-[auto_auto_auto_auto_1fr]">
        <header className="card p-5 lg:col-start-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="page-title">{p.displayName}</h1>
            {!p.identityVerified && <Badge tone="warn">Identity not yet verified</Badge>}
            {!p.isAcceptingWork && <Badge tone="muted">Not taking jobs right now</Badge>}
          </div>
          <p className="mt-1 text-sm text-slate-600">
            {p.experienceYears > 0 ? `${p.experienceYears} years of experience` : "Experience not stated"}
            {p.serviceAreas.length > 0 && ` · Serves ${p.serviceAreas.map((a) => a.location?.name).join(", ")}`}
          </p>
          {p.bio && <p className="mt-3 whitespace-pre-line text-slate-700">{p.bio}</p>}
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <Button to={requestLink} size="lg" disabled={Boolean(blockedReason)}>
              Request {firstName}
            </Button>
            <Button
              variant="secondary"
              size="lg"
              onClick={() => toggleCompare(providerId)}
              disabled={!inCompare && compareFull}
              aria-pressed={inCompare}
            >
              {inCompare ? "Comparing" : "Compare"}
            </Button>
          </div>
          {blockedReason && (
            <p className="mt-3 text-sm text-slate-600">
              {blockedReason}{" "}
              <Link
                to={`/request-service${preferredService ? `?service=${preferredService}` : ""}`}
                className="font-semibold text-brand-700 hover:text-brand-800"
              >
                Post an open request
              </Link>
            </p>
          )}
          {!inCompare && compareFull && (
            <p className="mt-2 text-xs text-slate-600">
              You are already comparing {COMPARE_LIMIT} providers. <Link to="/compare" className="font-semibold text-brand-700">Open comparison</Link>
            </p>
          )}
        </header>

        <aside className="space-y-4 lg:sticky lg:top-24 lg:col-start-2 lg:row-span-5 lg:row-start-1 lg:self-start">
          {trust.isLoading && <PageLoader />}
          <ErrorMessage error={trust.error} onRetry={trust.refetch} />
          {trust.data && <TrustBreakdown trust={trust.data} />}
          <BackLink />
        </aside>

        <section className="card p-5 lg:col-start-1" aria-labelledby="prices-heading">
          <h2 id="prices-heading" className="section-title">Services and prices</h2>
          {bookable.length === 0 ? (
            <p className="mt-2 text-sm text-slate-600">No services listed yet.</p>
          ) : (
            <ul className="mt-3 divide-y divide-slate-100">
              {bookable.map((o) => {
                const highlighted = String(o.serviceId) === preferredService;
                return (
                  <li key={o.id} className={`flex items-center justify-between gap-3 py-3 ${highlighted ? "-mx-3 rounded-2xl bg-brand-50 px-3" : ""}`}>
                    <div>
                      <p className="font-medium text-ink">
                        {o.service?.name}
                        {highlighted && <span className="ml-2 text-xs font-semibold text-brand-800">What you searched for</span>}
                      </p>
                      {o.priceFlag && o.priceFlag !== "normal" && (
                        <p className={`text-xs ${o.priceFlag === "high" ? "text-amber-700" : "text-sky-700"}`}>
                          {PRICE_FLAG_LABEL[o.priceFlag]}
                        </p>
                      )}
                    </div>
                    <Money value={o.price} className="text-lg font-bold text-ink" />
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section className="card p-5 lg:col-start-1" aria-labelledby="availability-heading">
          <h2 id="availability-heading" className="section-title">Availability this week</h2>
          {calendar.isLoading ? (
            <PageLoader />
          ) : (
            <>
              <ErrorMessage error={calendar.error} onRetry={calendar.refetch} className="mt-3" />
              <ul className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                {(calendar.data ?? []).map((day) => {
                  const isToday = day.date === today;
                  return (
                    <li key={day.date} className={`rounded-2xl border p-3 text-sm ${day.windows.length ? "border-brand-200 bg-brand-50" : "border-slate-200 bg-slate-50 text-slate-600"} ${isToday ? "ring-2 ring-brand-600" : ""}`}>
                      <p className="font-semibold">
                        {isToday ? "Today" : WEEKDAYS[(new Date(`${day.date}T00:00:00`).getDay() + 6) % 7].slice(0, 3)}, {formatDate(day.date).split(" ").slice(0, 2).join(" ")}
                      </p>
                      {day.windows.length ? (
                        day.windows.map((w) => (
                          <p key={w.startTime} className="text-xs text-brand-800">{formatTime(w.startTime)}–{formatTime(w.endTime)}</p>
                        ))
                      ) : (
                        <p className="text-xs">Unavailable</p>
                      )}
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </section>

        {p.workPhotos.length > 0 && (
          <section className="card p-5 lg:col-start-1" aria-labelledby="photos-heading">
            <h2 id="photos-heading" className="section-title">Recent work</h2>
            <ul className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
              {p.workPhotos.map((photo) => (
                <li key={photo.id}>
                  <a href={photo.image} target="_blank" rel="noreferrer" className="group block overflow-hidden rounded-2xl">
                    <img
                      src={photo.image}
                      alt={photo.caption || `Work by ${p.displayName}`}
                      loading="lazy"
                      className="aspect-square w-full object-cover transition group-hover:scale-105"
                    />
                  </a>
                  {photo.caption && <p className="mt-1 text-xs text-slate-600">{photo.caption}</p>}
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="card p-5 lg:col-start-1 lg:self-start" aria-labelledby="reviews-heading">
          <h2 id="reviews-heading" className="section-title">
            Reviews {reviews.data?.count ? `(${reviews.data.count})` : ""}
          </h2>
          <p className="mt-1 text-xs text-slate-600">Only customers with a completed job can review. Reviews are revealed once both sides have rated.</p>
          <ErrorMessage error={reviews.error} onRetry={reviews.refetch} className="mt-3" />
          {reviews.data?.results.length === 0 && <p className="mt-3 text-sm text-slate-600">No published reviews yet.</p>}
          <ul className="mt-2 divide-y divide-slate-100">
            {(reviews.data?.results ?? []).map((r) => (
              <li key={r.id} className="py-4">
                <div className="flex items-center justify-between">
                  <Stars value={r.rating} />
                  <span className="text-xs text-slate-600">{formatDate(r.createdAt)}</span>
                </div>
                <p className="mt-1 text-sm font-medium text-ink">{r.customerName}</p>
                {r.comment && <p className="mt-1 text-sm text-slate-700">{r.comment}</p>}
                {r.reply && (
                  <div className="mt-2 rounded-2xl bg-slate-50 p-3 text-sm">
                    <p className="text-xs font-semibold text-slate-600">Reply from {p.displayName}</p>
                    <p className="mt-0.5 text-slate-700">{r.reply.body}</p>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
    </div>
  );
}
