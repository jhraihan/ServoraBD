import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { providers, requests } from "../api/endpoints";
import LocationSelect from "../components/LocationSelect";
import { Money } from "../components/domain";
import { Button, ErrorMessage, Field, PageHeader } from "../components/ui";
import { flattenAreas, useAllServices, useLocationTree } from "../hooks/useCatalogue";
import {
  dhakaLocalToIso, formatDate, formatTime, toDateInputValue, toTimeInputValue,
} from "../lib/format";

const DRAFT_KEY = "servorabd-request-draft";

const SLOTS = [
  { id: "morning", label: "Morning", start: "09:00", end: "12:00" },
  { id: "midday", label: "Midday", start: "12:00", end: "15:00" },
  { id: "afternoon", label: "Afternoon", start: "15:00", end: "18:00" },
  { id: "evening", label: "Evening", start: "18:00", end: "21:00" },
];

const STEPS = ["The job", "Where and when", "Confirm"];

const EMPTY = {
  serviceId: null,
  locationId: null,
  address: "",
  description: "",
  date: "",
  slot: "morning",
  targetProviderId: null,
};

function loadDraft() {
  try {
    return { ...EMPTY, ...JSON.parse(sessionStorage.getItem(DRAFT_KEY) ?? "{}") };
  } catch {
    return { ...EMPTY };
  }
}

function tomorrow() {
  return toDateInputValue(new Date(Date.now() + 24 * 60 * 60 * 1000));
}

function slotStarted(slot, date) {
  return date === toDateInputValue(new Date()) && slot.start <= toTimeInputValue(new Date());
}

export default function RequestService() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [draft, setDraft] = useState(() => {
    const saved = loadDraft();
    const service = params.get("service");
    const provider = params.get("provider");
    return {
      ...saved,
      serviceId: service ? Number(service) : saved.serviceId,
      targetProviderId: provider ? Number(provider) : saved.targetProviderId,
      date: saved.date || tomorrow(),
    };
  });
  const [step, setStep] = useState(0);
  const [offeredProviderId] = useState(() => draft.targetProviderId);

  const { data: services } = useAllServices();
  const { data: tree } = useLocationTree();

  useEffect(() => {
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  }, [draft]);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [step]);

  const target = useQuery({
    queryKey: ["provider", String(offeredProviderId)],
    queryFn: () => providers.detail(offeredProviderId),
    enabled: Boolean(offeredProviderId),
  });

  const matches = useQuery({
    queryKey: ["provider-search", { service: draft.serviceId, location: draft.locationId }],
    queryFn: () => providers.search({ service: draft.serviceId, location: draft.locationId, page_size: 3 }),
    enabled: Boolean(draft.serviceId && draft.locationId),
  });

  const submit = useMutation({
    mutationFn: () => {
      const slot = SLOTS.find((s) => s.id === draft.slot);
      return requests.create({
        serviceId: draft.serviceId,
        locationId: draft.locationId,
        address: draft.address,
        description: draft.description,
        preferredStart: dhakaLocalToIso(draft.date, slot.start),
        preferredEnd: dhakaLocalToIso(draft.date, slot.end),
        targetProviderId: draft.targetProviderId,
      });
    },
    onSuccess: (created) => {
      sessionStorage.removeItem(DRAFT_KEY);
      navigate("/my-requests", { replace: true, state: { created: created.id } });
    },
  });

  const service = useMemo(
    () => (services ?? []).find((s) => s.id === draft.serviceId),
    [services, draft.serviceId],
  );
  const area = flattenAreas(tree).find((a) => a.id === draft.locationId);
  const slot = SLOTS.find((s) => s.id === draft.slot);
  const targetOffering = target.data?.offerings.find((o) => o.serviceId === draft.serviceId);

  function update(fields) {
    setDraft((d) => ({ ...d, ...fields }));
  }

  function pickDate(date) {
    const fields = { date };
    if (slotStarted(slot, date)) {
      const open = SLOTS.find((s) => !slotStarted(s, date));
      if (open) fields.slot = open.id;
    }
    update(fields);
  }

  const today = toDateInputValue(new Date());
  const descriptionLength = draft.description.trim().length;
  const todayIsFull = SLOTS.every((s) => slotStarted(s, today));
  const blockers = [
    [
      !draft.serviceId && "Choose a service.",
      descriptionLength < 10 && "Describe the problem in at least 10 characters.",
    ],
    [
      !draft.locationId && "Choose your area.",
      draft.address.trim().length < 5 && "Add your full address.",
      (!draft.date || draft.date < today) && "Pick today or a later date.",
      draft.date === today && slotStarted(slot, draft.date) && "That time has already started today. Pick a later time or another day.",
    ],
    [],
  ][step].filter(Boolean);
  const canContinue = blockers.length === 0;

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Request a service" subtitle={`Step ${step + 1} of ${STEPS.length} · ${STEPS[step]}`} />

      <ol className="mb-6 grid grid-cols-3 gap-2">
        {STEPS.map((label, i) => (
          <li key={label}>
            <button
              type="button"
              disabled={i >= step}
              onClick={() => setStep(i)}
              aria-current={i === step ? "step" : undefined}
              className="group w-full text-left disabled:cursor-default"
            >
              <span className={`block h-1.5 rounded-full transition-colors ${i <= step ? "bg-brand-600" : "bg-slate-200"}`} />
              <span className={`mt-1.5 block text-xs font-semibold ${i === step ? "text-ink" : i < step ? "text-brand-700 group-hover:underline" : "text-slate-600"}`}>
                {i + 1}. {label}
              </span>
            </button>
          </li>
        ))}
      </ol>

      <form
        className="card space-y-5 p-5 sm:p-6"
        onSubmit={(e) => {
          e.preventDefault();
          if (step < STEPS.length - 1) setStep(step + 1);
          else submit.mutate();
        }}
      >
        {step === 0 && (
          <>
            <Field label="What do you need done?" htmlFor="rs-service">
              <select id="rs-service" className="input" value={draft.serviceId ?? ""} onChange={(e) => update({ serviceId: Number(e.target.value) || null })} required>
                <option value="">Choose a service</option>
                {(services ?? []).map((s) => (
                  <option key={s.id} value={s.id}>{s.name} — {s.categoryName}</option>
                ))}
              </select>
            </Field>
            <Field
              label="Describe the problem"
              htmlFor="rs-description"
              hint={`What is wrong, and anything the provider should bring.${descriptionLength < 10 ? ` At least 10 characters${descriptionLength ? ` (${10 - descriptionLength} to go)` : ""}.` : ""}`}
            >
              <textarea id="rs-description" className="input" rows={4} value={draft.description} onChange={(e) => update({ description: e.target.value })} placeholder="e.g. The bedroom AC runs but does not cool. It is a 1.5 ton split unit." required />
            </Field>
          </>
        )}

        {step === 1 && (
          <>
            <Field label="Area" htmlFor="rs-location">
              <LocationSelect id="rs-location" value={draft.locationId} onChange={(v) => update({ locationId: v })} placeholder="Choose your area" required />
            </Field>
            <Field label="Full address" htmlFor="rs-address" hint="Only shared with the provider who accepts your job.">
              <textarea id="rs-address" className="input" rows={2} value={draft.address} onChange={(e) => update({ address: e.target.value })} placeholder="House, road, flat, landmark" required />
            </Field>
            <Field label="Date" htmlFor="rs-date">
              <div className="flex flex-wrap items-center gap-2">
                <input id="rs-date" type="date" className="input w-auto min-w-0 flex-1" min={today} value={draft.date} onChange={(e) => pickDate(e.target.value)} required />
                {[["Today", today], ["Tomorrow", tomorrow()]].map(([label, value]) => (
                  <button
                    key={label}
                    type="button"
                    aria-pressed={draft.date === value}
                    disabled={value === today && todayIsFull}
                    onClick={() => pickDate(value)}
                    className={`chip disabled:cursor-not-allowed disabled:opacity-50 ${draft.date === value ? "chip-active" : "chip-idle"}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </Field>
            <fieldset>
              <legend className="label">Preferred time</legend>
              <div className="grid grid-cols-2 gap-2">
                {SLOTS.map((s) => {
                  const started = slotStarted(s, draft.date);
                  const tone = started
                    ? "cursor-not-allowed border-dashed border-slate-300 bg-slate-50 text-slate-600"
                    : draft.slot === s.id ? "choice-on" : "choice-off";
                  return (
                    <label key={s.id} className={`choice p-3 text-sm ${tone}`}>
                      <input type="radio" name="slot" value={s.id} checked={draft.slot === s.id} disabled={started} onChange={() => update({ slot: s.id })} className="sr-only" />
                      <span className="block font-semibold">{s.label}</span>
                      <span className="text-xs">{started ? "Already started today" : `${formatTime(s.start)} – ${formatTime(s.end)}`}</span>
                    </label>
                  );
                })}
              </div>
            </fieldset>
          </>
        )}

        {step === 2 && (
          <>
            <fieldset className="space-y-2">
              <legend className="label">Who should see this request?</legend>
              {offeredProviderId && target.data && (
                <label className={`flex cursor-pointer gap-3 rounded-2xl border p-4 ${draft.targetProviderId ? "border-brand-600 bg-brand-50" : "border-slate-300"}`}>
                  <input type="radio" name="who" checked={Boolean(draft.targetProviderId)} onChange={() => update({ targetProviderId: offeredProviderId })} />
                  <span>
                    <span className="block font-semibold text-ink">Only {target.data.displayName}</span>
                    <span className="text-sm text-slate-600">
                      {targetOffering ? <>Their price for this: <Money value={targetOffering.price} /></> : "They do not list this service — they may decline."}
                    </span>
                  </span>
                </label>
              )}
              <label className={`flex cursor-pointer gap-3 rounded-2xl border p-4 ${!draft.targetProviderId ? "border-brand-600 bg-brand-50" : "border-slate-300"}`}>
                <input type="radio" name="who" checked={!draft.targetProviderId} onChange={() => update({ targetProviderId: null })} />
                <span>
                  <span className="block font-semibold text-ink">All matching providers in {area?.label ?? "your area"}</span>
                  <span className="text-sm text-slate-600">
                    {matches.data ? `${matches.data.count} provider${matches.data.count === 1 ? "" : "s"} can see it. The first to accept gets the job.` : "The first provider to accept gets the job."}
                  </span>
                </span>
              </label>
            </fieldset>

            <dl className="divide-y divide-slate-100 rounded-2xl bg-slate-50/70 px-4 text-sm">
              {[
                ["Service", service?.name, 0],
                ["Problem", draft.description, 0],
                ["Area", area?.label, 1],
                ["Address", draft.address, 1],
                ["When", `${formatDate(draft.date)}, ${slot.label.toLowerCase()} (${formatTime(slot.start)}–${formatTime(slot.end)})`, 1],
              ].map(([k, v, target]) => (
                <div key={k} className="grid grid-cols-[90px_1fr] gap-2 py-2.5 sm:grid-cols-[110px_1fr]">
                  <dt className="text-slate-600">{k}</dt>
                  <dd className="flex items-start justify-between gap-3">
                    <span className="min-w-0 whitespace-pre-line break-words text-ink">{v}</span>
                    <button type="button" onClick={() => setStep(target)} className="shrink-0 text-xs font-semibold text-brand-700 hover:text-brand-800">
                      Edit<span className="sr-only"> {k.toLowerCase()}</span>
                    </button>
                  </dd>
                </div>
              ))}
            </dl>
          </>
        )}

        <ErrorMessage error={submit.error} />

        {!canContinue && (
          <p className="text-sm text-slate-600" aria-live="polite">
            <span className="font-semibold text-ink">To continue:</span> {blockers.join(" ")}
          </p>
        )}

        <div className="flex justify-between gap-3 pt-2">
          <Button variant="secondary" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>
            Back
          </Button>
          <Button type="submit" disabled={!canContinue} loading={submit.isPending}>
            {step === STEPS.length - 1 ? "Send request" : "Continue"}
          </Button>
        </div>
      </form>
    </div>
  );
}
