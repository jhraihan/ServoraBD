import PropTypes from "prop-types";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useToastStore } from "../store/toast";

const BUTTON_VARIANTS = {
  primary: "bg-ink text-white hover:bg-brand-900 disabled:bg-ink/50",
  secondary: "border border-slate-300 bg-white/80 text-slate-800 backdrop-blur-xl hover:bg-white disabled:text-slate-400",
  ghost: "text-brand-700 hover:bg-brand-50 disabled:text-slate-400",
  danger: "bg-rose-600 text-white hover:bg-rose-700 disabled:bg-rose-600/50",
};

const BUTTON_SIZES = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-5 py-2.5 text-sm",
  lg: "px-6 py-3.5 text-base",
};

export function Button({
  children, variant = "primary", size = "md", loading = false, disabled = false, to,
  className = "", type = "button", ...rest
}) {
  const classes = [
    "inline-flex items-center justify-center gap-2 rounded-full font-semibold transition-colors disabled:cursor-not-allowed",
    BUTTON_VARIANTS[variant],
    BUTTON_SIZES[size],
    className,
  ].join(" ");

  if (to && !disabled && !loading) {
    return (
      <Link to={to} className={classes}>
        {children}
      </Link>
    );
  }

  return (
    <button type={type} className={classes} {...rest} disabled={loading || disabled}>
      {loading && <Spinner small />}
      {children}
    </button>
  );
}

Button.propTypes = {
  children: PropTypes.node.isRequired,
  variant: PropTypes.oneOf(Object.keys(BUTTON_VARIANTS)),
  size: PropTypes.oneOf(Object.keys(BUTTON_SIZES)),
  loading: PropTypes.bool,
  disabled: PropTypes.bool,
  to: PropTypes.string,
  className: PropTypes.string,
  type: PropTypes.oneOf(["button", "submit"]),
};

export function Spinner({ small = false, label = "Loading" }) {
  const size = small ? "h-4 w-4 border-2" : "h-8 w-8 border-[3px]";
  return (
    <span role="status" aria-label={label} className="inline-flex">
      <span className={`${size} animate-spin rounded-full border-current border-t-transparent opacity-70`} />
    </span>
  );
}

Spinner.propTypes = {
  small: PropTypes.bool,
  label: PropTypes.string,
};

export function PageLoader() {
  return (
    <div className="flex justify-center py-20 text-brand-700">
      <Spinner />
    </div>
  );
}

export function SkeletonList({ count = 3, itemClassName = "h-28", className = "space-y-3" }) {
  return (
    <div className={className}>
      <span role="status" className="sr-only">Loading</span>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} aria-hidden="true" className={`card motion-safe:animate-pulse ${itemClassName}`} />
      ))}
    </div>
  );
}

SkeletonList.propTypes = {
  count: PropTypes.number,
  itemClassName: PropTypes.string,
  className: PropTypes.string,
};

export function ErrorMessage({ error, onRetry, className = "" }) {
  if (!error) return null;
  const message = typeof error === "string" ? error : error.message;
  return (
    <div role="alert" className={`flex flex-wrap items-center justify-between gap-x-4 gap-y-1 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800 ${className}`}>
      <span>{message}</span>
      {onRetry && (
        <button type="button" onClick={() => onRetry()} className="font-semibold underline underline-offset-2 hover:text-rose-950">
          Try again
        </button>
      )}
    </div>
  );
}

ErrorMessage.propTypes = {
  error: PropTypes.oneOfType([PropTypes.string, PropTypes.instanceOf(Error)]),
  onRetry: PropTypes.func,
  className: PropTypes.string,
};

export function EmptyState({ title, body, action }) {
  return (
    <div className="card flex flex-col items-center px-6 py-12 text-center">
      <p className="text-base font-semibold text-ink">{title}</p>
      {body && <p className="mt-1.5 max-w-sm text-sm text-slate-600">{body}</p>}
      {action && <div className="mt-5 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  );
}

EmptyState.propTypes = {
  title: PropTypes.string.isRequired,
  body: PropTypes.string,
  action: PropTypes.node,
};

export function ConfirmAction({ label, prompt, confirmLabel, onConfirm, loading = false }) {
  const [asking, setAsking] = useState(false);

  if (!asking) {
    return (
      <Button variant="ghost" size="sm" onClick={() => setAsking(true)}>
        {label}
      </Button>
    );
  }

  return (
    <span
      role="group"
      aria-label={prompt}
      className="inline-flex flex-wrap items-center gap-2"
      onKeyDown={(e) => e.key === "Escape" && setAsking(false)}
    >
      <span className="text-sm font-medium text-slate-700">{prompt}</span>
      <Button variant="danger" size="sm" loading={loading} onClick={onConfirm}>
        {confirmLabel}
      </Button>
      <Button variant="secondary" size="sm" onClick={() => setAsking(false)} autoFocus>
        Keep
      </Button>
    </span>
  );
}

ConfirmAction.propTypes = {
  label: PropTypes.string.isRequired,
  prompt: PropTypes.string.isRequired,
  confirmLabel: PropTypes.string.isRequired,
  onConfirm: PropTypes.func.isRequired,
  loading: PropTypes.bool,
};

export function PasswordInput({ id, ...rest }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input id={id} type={visible ? "text" : "password"} className="input pr-20" {...rest} />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-pressed={visible}
        aria-controls={id}
        className="absolute top-1/2 right-2 -translate-y-1/2 rounded-full px-3 py-1.5 text-sm font-semibold text-brand-700 hover:bg-brand-50"
      >
        {visible ? "Hide" : "Show"}
        <span className="sr-only"> password</span>
      </button>
    </div>
  );
}

PasswordInput.propTypes = { id: PropTypes.string.isRequired };

const TOAST_TONES = {
  good: "bg-ink text-white",
  bad: "bg-rose-700 text-white",
};

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);
  return (
    <div role="status" className="on-dark pointer-events-none fixed inset-x-0 top-20 z-50 flex flex-col items-center gap-2 px-4">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={dismiss} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onDismiss }) {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), 4500);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  return (
    <div className={`pointer-events-auto flex w-full max-w-sm items-center justify-between gap-3 rounded-2xl py-3 pr-2 pl-4 text-sm font-medium shadow-2xl motion-safe:animate-toast-in ${TOAST_TONES[toast.tone] ?? TOAST_TONES.good}`}>
      <span>{toast.message}</span>
      <button type="button" onClick={() => onDismiss(toast.id)} className="rounded-full p-1.5 text-white/80 hover:bg-white/10 hover:text-white">
        <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M5 5l10 10M15 5 5 15" strokeLinecap="round" />
        </svg>
        <span className="sr-only">Dismiss</span>
      </button>
    </div>
  );
}

ToastItem.propTypes = {
  toast: PropTypes.shape({
    id: PropTypes.number.isRequired,
    message: PropTypes.string.isRequired,
    tone: PropTypes.string,
  }).isRequired,
  onDismiss: PropTypes.func.isRequired,
};

const BADGE_TONES = {
  good: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  info: "bg-sky-50 text-sky-800 ring-sky-200",
  warn: "bg-amber-50 text-amber-800 ring-amber-200",
  bad: "bg-rose-50 text-rose-800 ring-rose-200",
  muted: "bg-slate-100 text-slate-700 ring-slate-200",
  brand: "bg-brand-50 text-brand-800 ring-brand-200",
};

export function Badge({ children, tone = "muted" }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${BADGE_TONES[tone]}`}>
      {children}
    </span>
  );
}

Badge.propTypes = {
  children: PropTypes.node.isRequired,
  tone: PropTypes.oneOf(Object.keys(BADGE_TONES)),
};

export function Field({ label, htmlFor, error, hint, children }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="label">
        {label}
      </label>
      {children}
      {hint && !error && <p className="mt-1 text-xs text-slate-600">{hint}</p>}
      {error && <p className="mt-1 text-xs font-medium text-rose-700">{error}</p>}
    </div>
  );
}

Field.propTypes = {
  label: PropTypes.string.isRequired,
  htmlFor: PropTypes.string.isRequired,
  error: PropTypes.string,
  hint: PropTypes.string,
  children: PropTypes.node.isRequired,
};

export function PageHeader({ title, subtitle, action }) {
  useDocumentTitle(title);
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="page-title">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-600">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

PageHeader.propTypes = {
  title: PropTypes.string.isRequired,
  subtitle: PropTypes.string,
  action: PropTypes.node,
};

export function Stat({ label, value, hint }) {
  return (
    <div className="card p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-600">{label}</p>
      <p className="mt-1 text-2xl font-bold text-ink">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-slate-600">{hint}</p>}
    </div>
  );
}

Stat.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.node.isRequired,
  hint: PropTypes.string,
};
