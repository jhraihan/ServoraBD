import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import PropTypes from "prop-types";
import { useState } from "react";

import { me } from "../../api/endpoints";
import { Money } from "../../components/domain";
import { Badge, Button, ConfirmAction, ErrorMessage, Field, PageHeader, PageLoader } from "../../components/ui";
import { PRICE_FLAG_LABEL, WEEKDAYS } from "../../constants/domain";
import { flattenAreas, useAllServices, useLocationTree } from "../../hooks/useCatalogue";
import { toast } from "../../store/toast";

const DOCUMENT_TYPES = [
  ["nid_front", "NID — front"],
  ["nid_back", "NID — back"],
  ["trade_certificate", "Trade certificate"],
  ["address_proof", "Address proof"],
];

const STATUS_TONE = { pending: "warn", approved: "good", rejected: "bad" };
const STATUS_LABEL = { pending: "In review", approved: "Approved", rejected: "Rejected" };

export default function ProfileSetup() {
  const profile = useQuery({ queryKey: ["my-profile"], queryFn: me.profile });

  if (profile.isLoading) return <PageLoader />;
  if (profile.error) return <ErrorMessage error={profile.error} onRetry={profile.refetch} />;

  const p = profile.data;
  const checklist = [
    ["Add at least one service", p.offerings.length > 0, "section-services"],
    ["Choose the areas you serve", p.serviceAreas.length > 0, "section-areas"],
    ["Set your weekly hours", p.availability.length > 0, "section-hours"],
    ["Verify your identity", p.identityVerified, "section-verification"],
  ];
  const done = checklist.filter(([, ok]) => ok).length;

  return (
    <>
      <PageHeader title="Your profile" subtitle="Customers only find you once services and areas are set." />

      <div className="card mb-6 p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-semibold text-ink">Profile setup · {done} of {checklist.length} done</p>
          {done === checklist.length && <Badge tone="good">Ready for customers</Badge>}
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100" aria-hidden="true">
          <div className="h-full rounded-full bg-brand-600 transition-all duration-500" style={{ width: `${(done / checklist.length) * 100}%` }} />
        </div>
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {checklist.map(([label, ok, target]) => (
            <li key={label}>
              <a
                href={`#${target}`}
                className={`flex items-center gap-2 rounded-lg px-2 py-1 text-sm hover:bg-white/70 ${ok ? "text-emerald-700" : "font-medium text-slate-700"}`}
              >
                <span aria-hidden="true">{ok ? "✓" : "○"}</span>
                {label}
                {!ok && <span className="ml-auto text-xs font-semibold text-brand-700">Do it →</span>}
              </a>
            </li>
          ))}
        </ul>
      </div>

      <div className="space-y-6">
        <BasicInfo profile={p} />
        <Offerings offerings={p.offerings} />
        <ServiceAreas
          key={p.serviceAreas.map((a) => a.locationId).join(",")}
          selectedIds={p.serviceAreas.map((a) => a.locationId)}
        />
        <WeeklyHours windows={p.availability} />
        <Verification />
      </div>
    </>
  );
}

function useProfileRefresh() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["my-profile"] });
    queryClient.invalidateQueries({ queryKey: ["provider-dashboard"] });
  };
}

function BasicInfo({ profile }) {
  const refresh = useProfileRefresh();
  const [form, setForm] = useState({
    displayName: profile.displayName,
    bio: profile.bio,
    experienceYears: profile.experienceYears,
  });
  const save = useMutation({
    mutationFn: () => me.updateProfile(form),
    onSuccess: () => {
      refresh();
      toast("Profile saved.");
    },
  });

  return (
    <section className="card p-5">
      <h2 className="section-title">About you</h2>
      <form className="mt-4 space-y-4" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
        <div className="grid gap-4 sm:grid-cols-[1fr_160px]">
          <Field label="Display name" htmlFor="p-name">
            <input id="p-name" className="input" value={form.displayName} onChange={(e) => setForm({ ...form, displayName: e.target.value })} required />
          </Field>
          <Field label="Years of experience" htmlFor="p-exp">
            <input id="p-exp" type="number" min="0" max="70" className="input" value={form.experienceYears} onChange={(e) => setForm({ ...form, experienceYears: e.target.value === "" ? "" : Number(e.target.value) })} />
          </Field>
        </div>
        <Field label="About your work" htmlFor="p-bio">
          <textarea id="p-bio" className="input" rows={3} value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} />
        </Field>
        <ErrorMessage error={save.error} />
        <div className="flex items-center gap-3">
          <Button type="submit" loading={save.isPending}>Save</Button>
        </div>
      </form>
    </section>
  );
}

BasicInfo.propTypes = {
  profile: PropTypes.shape({
    displayName: PropTypes.string.isRequired,
    bio: PropTypes.string,
    experienceYears: PropTypes.number,
  }).isRequired,
};

function Offerings({ offerings }) {
  const refresh = useProfileRefresh();
  const { data: services } = useAllServices();
  const [serviceId, setServiceId] = useState("");
  const [price, setPrice] = useState("");

  const add = useMutation({
    mutationFn: () => me.addOffering({ serviceId: Number(serviceId), price }),
    onSuccess: () => {
      setServiceId("");
      setPrice("");
      refresh();
      toast("Service added.");
    },
  });
  const toggle = useMutation({
    mutationFn: (o) => me.updateOffering(o.id, { isActive: !o.isActive }),
    onSuccess: (_data, o) => {
      refresh();
      toast(o.isActive ? "Service paused. Customers will not see it." : "Service is live again.");
    },
  });
  const remove = useMutation({
    mutationFn: (id) => me.removeOffering(id),
    onSuccess: () => {
      refresh();
      toast("Service removed.");
    },
  });

  const offered = new Set(offerings.map((o) => o.serviceId));
  const chosen = (services ?? []).find((s) => String(s.id) === serviceId);
  const outsideRange = chosen?.priceMin && chosen?.priceMax && price !== "" && (Number(price) < Number(chosen.priceMin) || Number(price) > Number(chosen.priceMax));

  return (
    <section id="section-services" className="card scroll-mt-24 p-5">
      <h2 className="section-title">Services and prices</h2>
      <ul className="mt-3 divide-y divide-slate-100">
        {offerings.length === 0 && <li className="py-3 text-sm text-slate-600">No services yet.</li>}
        {offerings.map((o) => (
          <li key={o.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
            <div>
              <p className={`font-medium ${o.isActive ? "text-ink" : "text-slate-600 line-through"}`}>{o.service?.name}</p>
              {o.priceFlag && <p className="text-xs text-slate-600">{PRICE_FLAG_LABEL[o.priceFlag]}</p>}
            </div>
            <div className="flex items-center gap-2">
              <Money value={o.price} className="font-semibold text-ink" />
              <Button variant="ghost" size="sm" loading={toggle.isPending && toggle.variables?.id === o.id} onClick={() => toggle.mutate(o)}>{o.isActive ? "Pause" : "Resume"}</Button>
              <ConfirmAction
                label="Remove"
                prompt="Remove this service?"
                confirmLabel="Yes, remove"
                loading={remove.isPending && remove.variables === o.id}
                onConfirm={() => remove.mutate(o.id)}
              />
            </div>
          </li>
        ))}
      </ul>
      <form className="mt-4 grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-[1fr_140px_auto] sm:items-end" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
        <Field label="Add a service" htmlFor="o-service" hint={chosen?.priceMin ? `Typical ৳${chosen.priceMin}–৳${chosen.priceMax}` : undefined}>
          <select id="o-service" className="input" value={serviceId} onChange={(e) => setServiceId(e.target.value)} required>
            <option value="">Choose…</option>
            {(services ?? []).filter((s) => !offered.has(s.id)).map((s) => (
              <option key={s.id} value={s.id}>{s.name} — {s.categoryName}</option>
            ))}
          </select>
        </Field>
        <Field label="Your price (৳)" htmlFor="o-price">
          <input id="o-price" type="number" min="0" step="1" className="input" value={price} onChange={(e) => setPrice(e.target.value)} required />
        </Field>
        <Button type="submit" loading={add.isPending}>Add</Button>
      </form>
      {outsideRange && (
        <p className="mt-2 text-xs text-amber-800" aria-live="polite">
          This is outside the typical range, so customers will see it flagged as {Number(price) > Number(chosen.priceMax) ? "above" : "below"} typical price.
        </p>
      )}
      <ErrorMessage error={add.error || toggle.error || remove.error} className="mt-3" />
    </section>
  );
}

Offerings.propTypes = { offerings: PropTypes.arrayOf(PropTypes.object).isRequired };

function ServiceAreas({ selectedIds }) {
  const refresh = useProfileRefresh();
  const { data: tree } = useLocationTree();
  const [selected, setSelected] = useState(new Set(selectedIds));
  const save = useMutation({
    mutationFn: () => me.setServiceAreas([...selected]),
    onSuccess: () => {
      refresh();
      toast("Areas saved.");
    },
  });
  const rows = flattenAreas(tree).filter((r) => r.level === "thana");
  const dirty = selected.size !== selectedIds.length || selectedIds.some((id) => !selected.has(id));

  function flip(id) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <section id="section-areas" className="card scroll-mt-24 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="section-title">Areas you serve</h2>
        <span className="text-sm text-slate-600">{selected.size} selected</span>
      </div>
      <p className="mt-1 text-sm text-slate-600">Choosing a thana covers every area inside it.</p>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {rows.map((r) => (
          <label key={r.id} className={`choice flex items-center gap-2 px-3 py-2 text-sm ${selected.has(r.id) ? "choice-on" : "choice-off"}`}>
            <input type="checkbox" className="sr-only" checked={selected.has(r.id)} onChange={() => flip(r.id)} />
            <span aria-hidden="true" className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] ${selected.has(r.id) ? "border-brand-600 bg-brand-600 text-white" : "border-slate-400"}`}>
              {selected.has(r.id) && "✓"}
            </span>
            {r.label}
          </label>
        ))}
      </div>
      <ErrorMessage error={save.error} className="mt-3" />
      <div className="mt-4 flex items-center gap-3">
        <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!dirty}>Save areas</Button>
        {dirty && <span className="text-sm font-medium text-amber-800">Unsaved changes</span>}
      </div>
    </section>
  );
}

ServiceAreas.propTypes = { selectedIds: PropTypes.arrayOf(PropTypes.number).isRequired };

function WeeklyHours({ windows }) {
  const refresh = useProfileRefresh();
  const [days, setDays] = useState(() =>
    WEEKDAYS.map((_, weekday) => {
      const existing = windows.find((w) => w.weekday === weekday);
      return { weekday, on: Boolean(existing), startTime: existing?.startTime ?? "09:00", endTime: existing?.endTime ?? "18:00" };
    }),
  );
  const save = useMutation({
    mutationFn: () => me.setAvailability(days.filter((d) => d.on)),
    onSuccess: () => {
      refresh();
      toast("Hours saved.");
    },
  });

  function patch(weekday, fields) {
    setDays((all) => all.map((d) => (d.weekday === weekday ? { ...d, ...fields } : d)));
  }

  const template = days.find((d) => d.on);
  const invalid = days.filter((d) => d.on && d.endTime <= d.startTime);

  function copyToAll() {
    setDays((all) => all.map((d) => ({ ...d, on: true, startTime: template.startTime, endTime: template.endTime })));
  }

  return (
    <section id="section-hours" className="card scroll-mt-24 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="section-title">Weekly hours</h2>
        {template && (
          <Button variant="ghost" size="sm" onClick={copyToAll}>
            Use {WEEKDAYS[template.weekday]}&apos;s hours every day
          </Button>
        )}
      </div>
      <ul className="mt-3 divide-y divide-slate-100">
        {days.map((d) => (
          <li key={d.weekday} className="flex flex-wrap items-center gap-3 py-2.5">
            <label className="flex w-36 items-center gap-2 text-sm font-medium text-slate-700">
              <input type="checkbox" className="h-4 w-4 accent-brand-700" checked={d.on} onChange={(e) => patch(d.weekday, { on: e.target.checked })} />
              {WEEKDAYS[d.weekday]}
            </label>
            {d.on ? (
              <div className="flex items-center gap-2 text-sm">
                <input type="time" aria-label={`${WEEKDAYS[d.weekday]} start`} className="input w-32 py-1.5" value={d.startTime} onChange={(e) => patch(d.weekday, { startTime: e.target.value })} />
                <span>to</span>
                <input type="time" aria-label={`${WEEKDAYS[d.weekday]} end`} className="input w-32 py-1.5" value={d.endTime} onChange={(e) => patch(d.weekday, { endTime: e.target.value })} />
              </div>
            ) : (
              <span className="text-sm text-slate-600">Off</span>
            )}
          </li>
        ))}
      </ul>
      {invalid.length > 0 && (
        <p className="mt-3 text-sm font-medium text-rose-700" role="alert">
          End time must be after start time on {invalid.map((d) => WEEKDAYS[d.weekday]).join(", ")}.
        </p>
      )}
      <ErrorMessage error={save.error} className="mt-3" />
      <div className="mt-4 flex items-center gap-3">
        <Button onClick={() => save.mutate()} loading={save.isPending} disabled={invalid.length > 0}>Save hours</Button>
      </div>
    </section>
  );
}

WeeklyHours.propTypes = { windows: PropTypes.arrayOf(PropTypes.object).isRequired };

function Verification() {
  const queryClient = useQueryClient();
  const docs = useQuery({ queryKey: ["my-verification"], queryFn: me.verification });
  const [documentType, setDocumentType] = useState("nid_front");
  const [file, setFile] = useState(null);
  const [inputKey, setInputKey] = useState(0);
  const upload = useMutation({
    mutationFn: () => me.uploadVerification({ documentType, file }),
    onSuccess: () => {
      setFile(null);
      setInputKey((k) => k + 1);
      queryClient.invalidateQueries({ queryKey: ["my-verification"] });
      toast("Document uploaded. We will review it soon.");
    },
  });
  const tooBig = file && file.size > 5 * 1024 * 1024;

  return (
    <section id="section-verification" className="card scroll-mt-24 p-5">
      <h2 className="section-title">Verification</h2>
      <p className="mt-1 text-sm text-slate-600">
        Both sides of your NID verify your identity; a trade certificate verifies your skill. Documents are stored privately and deleted 90 days after review.
      </p>
      <ul className="mt-3 divide-y divide-slate-100">
        {(docs.data ?? []).map((d) => (
          <li key={d.id} className="flex items-center justify-between py-2.5 text-sm">
            <span>{d.documentTypeLabel}</span>
            <span className="flex items-center gap-2">
              {d.rejectionReason && <span className="text-xs text-rose-700">{d.rejectionReason}</span>}
              <Badge tone={STATUS_TONE[d.status]}>{STATUS_LABEL[d.status] ?? d.status}</Badge>
            </span>
          </li>
        ))}
      </ul>
      <form className="mt-4 grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-[200px_1fr_auto] sm:items-end" onSubmit={(e) => { e.preventDefault(); upload.mutate(); }}>
        <Field label="Document" htmlFor="v-type">
          <select id="v-type" className="input" value={documentType} onChange={(e) => setDocumentType(e.target.value)}>
            {DOCUMENT_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </Field>
        <Field label="File (JPEG, PNG or PDF, max 5 MB)" htmlFor="v-file">
          <input key={inputKey} id="v-file" type="file" accept="image/jpeg,image/png,application/pdf" className="input py-2" onChange={(e) => setFile(e.target.files?.[0] ?? null)} required />
        </Field>
        <Button type="submit" loading={upload.isPending} disabled={!file || tooBig}>Upload</Button>
      </form>
      {tooBig && (
        <p className="mt-2 text-sm font-medium text-rose-700" role="alert">
          That file is {(file.size / (1024 * 1024)).toFixed(1)} MB. Please choose one under 5 MB.
        </p>
      )}
      <ErrorMessage error={upload.error || docs.error} className="mt-3" />
    </section>
  );
}
