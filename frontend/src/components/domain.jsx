import PropTypes from "prop-types";
import { useState } from "react";
import { Link } from "react-router-dom";

import {
  BOOKING_STATE_LABEL, BOOKING_STATE_TONE, COMPARE_LIMIT, REQUEST_STATE_LABEL,
} from "../constants/domain";
import { formatDateTime, formatDuration, formatMoney } from "../lib/format";
import { useCompareStore } from "../store/compare";
import { Badge } from "./ui";
import { TrustBadge } from "./Trust";
import {
  bookingEventShape, bookingStateType, moneyType, providerSummaryShape,
} from "./propShapes";

export function Money({ value, className = "" }) {
  return <span className={`tabular-nums ${className}`}>{formatMoney(value)}</span>;
}

Money.propTypes = { value: moneyType, className: PropTypes.string };

export function BookingStateBadge({ state }) {
  return <Badge tone={BOOKING_STATE_TONE[state] ?? "muted"}>{BOOKING_STATE_LABEL[state] ?? state}</Badge>;
}

BookingStateBadge.propTypes = { state: bookingStateType.isRequired };

export function RequestStateBadge({ state }) {
  const tone = { open: "warn", accepted: "good", withdrawn: "muted", expired: "muted" }[state];
  return <Badge tone={tone ?? "muted"}>{REQUEST_STATE_LABEL[state] ?? state}</Badge>;
}

RequestStateBadge.propTypes = { state: PropTypes.string.isRequired };

export function Stars({ value, size = "md" }) {
  const cls = size === "sm" ? "h-3.5 w-3.5" : "h-5 w-5";
  return (
    <span className="inline-flex" aria-label={`${value} out of 5 stars`} role="img">
      {[1, 2, 3, 4, 5].map((n) => (
        <svg key={n} viewBox="0 0 20 20" fill="currentColor" className={`${cls} ${n <= value ? "text-amber-400" : "text-slate-200"}`} aria-hidden="true">
          <path d="M9.05 2.93c.3-.92 1.6-.92 1.9 0l1.4 4.3h4.5c.97 0 1.37 1.24.59 1.81l-3.64 2.64 1.39 4.28c.3.93-.76 1.7-1.54 1.13L10 14.45l-3.64 2.64c-.79.57-1.84-.2-1.54-1.13l1.39-4.28-3.64-2.64c-.78-.57-.38-1.81.59-1.81h4.5l1.4-4.3z" />
        </svg>
      ))}
    </span>
  );
}

Stars.propTypes = {
  value: PropTypes.number.isRequired,
  size: PropTypes.oneOf(["sm", "md"]),
};

const RATING_WORDS = ["", "Poor", "Fair", "Good", "Very good", "Excellent"];

export function StarInput({ value, onChange, label, name }) {
  const [hover, setHover] = useState(0);
  const shown = hover || value;
  return (
    <fieldset>
      <legend className="label">{label}</legend>
      <div className="flex items-center gap-1" role="radiogroup" aria-label={label} onMouseLeave={() => setHover(0)}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={value === n}
            aria-label={`${n} star${n > 1 ? "s" : ""}`}
            title={RATING_WORDS[n]}
            data-testid={`${name}-${n}`}
            onClick={() => onChange(value === n ? 0 : n)}
            onMouseEnter={() => setHover(n)}
            onFocus={() => setHover(n)}
            onBlur={() => setHover(0)}
            className="rounded-lg p-1 transition hover:bg-amber-50 motion-safe:hover:scale-110"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className={`h-8 w-8 transition-colors ${n <= shown ? (hover && n > value ? "text-amber-300" : "text-amber-400") : "text-slate-200"}`} aria-hidden="true">
              <path d="M9.05 2.93c.3-.92 1.6-.92 1.9 0l1.4 4.3h4.5c.97 0 1.37 1.24.59 1.81l-3.64 2.64 1.39 4.28c.3.93-.76 1.7-1.54 1.13L10 14.45l-3.64 2.64c-.79.57-1.84-.2-1.54-1.13l1.39-4.28-3.64-2.64c-.78-.57-.38-1.81.59-1.81h4.5l1.4-4.3z" />
            </svg>
          </button>
        ))}
        <span aria-hidden="true" className="ml-2 min-w-[5.5rem] text-sm font-semibold text-slate-700">
          {RATING_WORDS[shown]}
        </span>
      </div>
    </fieldset>
  );
}

StarInput.propTypes = {
  value: PropTypes.number.isRequired,
  onChange: PropTypes.func.isRequired,
  label: PropTypes.string.isRequired,
  name: PropTypes.string.isRequired,
};

const AVATAR_GRADIENTS = [
  "from-emerald-400 to-teal-600",
  "from-sky-400 to-indigo-600",
  "from-amber-400 to-orange-600",
  "from-violet-400 to-purple-600",
  "from-rose-400 to-pink-600",
  "from-cyan-400 to-blue-600",
];

export function ProviderAvatar({ name, score, size = 52 }) {
  const initials = name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
  const hue = [...name].reduce((a, c) => a + c.charCodeAt(0), 0) % AVATAR_GRADIENTS.length;
  const pct = Math.max(0, Math.min(100, Math.round(Number(score ?? 0))));
  const r = size / 2 - 3;
  const circumference = 2 * Math.PI * r;

  return (
    <span className="relative inline-flex shrink-0" style={{ width: size, height: size }}>
      <svg
        viewBox={`0 0 ${size} ${size}`}
        className="absolute inset-0 -rotate-90"
        aria-hidden="true"
      >
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(18,38,26,0.10)" strokeWidth="3" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="currentColor"
          className="text-brand-600"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - pct / 100)}
        />
      </svg>
      <span
        className={`m-[7px] flex flex-1 items-center justify-center rounded-full bg-gradient-to-br ${AVATAR_GRADIENTS[hue]} text-sm font-bold text-white`}
      >
        {initials}
      </span>
    </span>
  );
}

ProviderAvatar.propTypes = {
  name: PropTypes.string.isRequired,
  score: moneyType,
  size: PropTypes.number,
};

export function ProviderCard({ provider, serviceId }) {
  const inCompare = useCompareStore((s) => s.ids.includes(provider.id));
  const compareFull = useCompareStore((s) => s.ids.length >= COMPARE_LIMIT);
  const toggle = useCompareStore((s) => s.toggle);
  const areas = provider.serviceAreas.map((a) => a.location?.name).filter(Boolean);
  const profileLink = serviceId ? `/providers/${provider.id}?service=${serviceId}` : `/providers/${provider.id}`;

  const fast = provider.medianResponseSeconds != null && provider.medianResponseSeconds <= 1800;
  const proven = provider.jobsCompleted >= 20;

  return (
    <article className="card flex flex-col gap-4 p-5 transition hover:-translate-y-0.5 sm:flex-row sm:items-start" data-testid="provider-card">
      <div className="flex-1">
        <div className="flex items-start gap-3">
          <ProviderAvatar name={provider.displayName} score={provider.trustScore} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <Link to={profileLink} className="text-lg font-semibold text-ink hover:text-brand-700">
                {provider.displayName}
              </Link>
              {!provider.identityVerified && <Badge tone="warn">Unverified</Badge>}
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              <TrustBadge score={provider.trustScore} tier={provider.trustTier} />
              {fast && <Badge tone="good">Fast replies</Badge>}
              {proven && <Badge tone="good">{provider.jobsCompleted} jobs done</Badge>}
            </div>
          </div>
        </div>
        <dl className="mt-3 grid grid-cols-3 gap-2 text-sm">
          <div>
            <dt className="text-xs text-slate-600">Jobs done</dt>
            <dd className="font-semibold tabular-nums text-ink">{provider.jobsCompleted}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-600">Cancelled</dt>
            <dd className="font-semibold tabular-nums text-ink">{provider.jobsCancelled}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-600">Replies in</dt>
            <dd className="font-semibold text-ink">{formatDuration(provider.medianResponseSeconds)}</dd>
          </div>
        </dl>
        {areas.length > 0 && <p className="mt-3 text-xs text-slate-600">Serves {areas.join(", ")}</p>}
      </div>
      <div className="flex flex-row items-center justify-between gap-3 border-t border-slate-100 pt-4 sm:flex-col sm:items-end sm:border-0 sm:pt-0">
        <div className="sm:text-right">
          {provider.fromPrice && (
            <>
              <p className="text-xs text-slate-600">From</p>
              <Money value={provider.fromPrice} className="text-xl font-bold text-ink" />
            </>
          )}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => toggle(provider.id)}
            disabled={!inCompare && compareFull}
            className="rounded-2xl border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
            aria-pressed={inCompare}
          >
            {inCompare ? "Comparing" : "Compare"}
          </button>
          <Link to={profileLink} className="rounded-2xl bg-brand-700 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-800">
            View
          </Link>
        </div>
      </div>
    </article>
  );
}

ProviderCard.propTypes = {
  provider: providerSummaryShape.isRequired,
  serviceId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
};

const ACTOR_LABEL = { customer: "Customer", provider: "Provider", admin: "Admin", system: "System" };

export function BookingTimeline({ events }) {
  if (!events.length) return null;
  return (
    <ol className="relative ml-2 border-l-2 border-slate-200">
      {events.map((event) => (
        <li key={event.id} className="mb-5 ml-5 last:mb-0">
          <span className="absolute -left-[7px] mt-1.5 h-3 w-3 rounded-full border-2 border-white bg-brand-600" />
          <p className="text-sm font-semibold text-ink">{BOOKING_STATE_LABEL[event.toState] ?? event.toState}</p>
          <p className="text-xs text-slate-600">
            {ACTOR_LABEL[event.actor] ?? event.actor} · {formatDateTime(event.createdAt)}
          </p>
          {event.reason && <p className="mt-1 text-sm text-slate-600">“{event.reason}”</p>}
          {event.metadata?.final_price && (
            <p className="mt-1 text-sm text-slate-600">Recorded amount: <Money value={event.metadata.final_price} /></p>
          )}
        </li>
      ))}
    </ol>
  );
}

BookingTimeline.propTypes = { events: PropTypes.arrayOf(bookingEventShape).isRequired };
