import { Link } from "react-router-dom";

import CategoryIcon from "../components/CategoryIcon";
import ServiceSearch from "../components/ServiceSearch";
import { ErrorMessage, SkeletonList } from "../components/ui";
import { categoryTheme } from "../constants/categories";
import { useAllServices, useCategories } from "../hooks/useCatalogue";
import { toDateInputValue } from "../lib/format";
import HomeHero from "./HomeHero";

const PROMISES = [
  {
    title: "Trust you can read",
    body: "Verification, completion rate, cancellations and reply time — not just a star rating.",
    icon: "sparkles",
    gradient: "from-brand-500 via-brand-600 to-brand-700",
  },
  {
    title: "Price agreed up front",
    body: "The price is locked when a provider accepts, and you see the typical range first.",
    icon: "wrench",
    gradient: "from-amber-400 via-orange-400 to-amber-500",
  },
  {
    title: "Honest reviews",
    body: "Only customers with a completed job can review, and reviews stay sealed until both rate.",
    icon: "monitor",
    gradient: "from-indigo-400 via-violet-500 to-indigo-600",
  },
];

export default function Home() {
  const { data: categories, isLoading, error, refetch } = useCategories();
  const { data: services } = useAllServices();

  return (
    <div className="space-y-14">
      <HomeHero>
        <div className="mt-8 max-w-xl">
          <ServiceSearch tone="dark" placeholder="Try “AC not cooling”" />
        </div>
      </HomeHero>

      <section aria-labelledby="urgency-heading">
        <h2 id="urgency-heading" className="section-title">
          How soon do you need it?
        </h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {[
            {
              key: "today",
              title: "Today",
              body: "Someone free in the next few hours.",
              gradient: "from-rose-500 via-red-500 to-orange-500",
              to: `/providers?available_on=${toDateInputValue(new Date())}`,
            },
            {
              key: "week",
              title: "This week",
              body: "Plan it around your schedule.",
              gradient: "from-amber-400 via-orange-400 to-amber-500",
              to: "/providers",
            },
            {
              key: "quote",
              title: "Just a quote",
              body: "Compare prices before you commit.",
              gradient: "from-brand-500 via-brand-600 to-brand-700",
              to: "/request-service",
            },
          ].map((o) => (
            <Link
              key={o.key}
              to={o.to}
              className={`group relative overflow-hidden rounded-3xl bg-gradient-to-br ${o.gradient} p-5 text-white shadow-lg transition hover:-translate-y-0.5 hover:shadow-xl`}
            >
              <span
                aria-hidden="true"
                className="absolute -top-8 -right-6 h-24 w-24 rounded-full bg-white/25 blur-2xl transition group-hover:bg-white/35"
              />
              <p className="relative text-lg font-bold">{o.title}</p>
              <p className="relative mt-1 text-sm text-white/90">{o.body}</p>
              <p className="relative mt-4 text-sm font-semibold">Browse →</p>
            </Link>
          ))}
        </div>
      </section>

      <section aria-labelledby="categories-heading">
        <div className="mb-4 flex items-end justify-between gap-4">
          <h2 id="categories-heading" className="section-title">Browse by category</h2>
          <Link to="/services" className="text-sm font-semibold text-brand-700">
            {services ? `All ${services.length} services →` : "All services →"}
          </Link>
        </div>
        {isLoading && <SkeletonList count={8} itemClassName="h-32" className="grid grid-cols-2 gap-3 sm:grid-cols-4" />}
        <ErrorMessage error={error} onRetry={refetch} />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {(categories ?? []).map((c) => {
            const theme = categoryTheme(c.slug);
            return (
              <Link
                key={c.id}
                to={`/services?category=${c.slug}`}
                className="group relative overflow-hidden rounded-3xl border border-white/70 bg-white/85 p-4 shadow-[0_10px_30px_-22px_rgba(18,38,26,0.5)] backdrop-blur-xl transition hover:-translate-y-1 hover:shadow-[0_18px_38px_-20px_rgba(18,38,26,0.45)]"
              >
                <span
                  aria-hidden="true"
                  className={`absolute -top-8 -right-6 h-20 w-20 rounded-full bg-gradient-to-br ${theme.gradient} opacity-25 blur-2xl transition group-hover:opacity-45`}
                />
                <span
                  className={`relative flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br ${theme.gradient} text-white shadow-lg ${theme.glow}`}
                >
                  <CategoryIcon name={c.icon} className="h-6 w-6" />
                </span>
                <p className="relative mt-3 font-semibold text-ink">{c.name}</p>
                <p className="relative text-xs font-medium" style={{ color: theme.accent }}>
                  {c.serviceCount} services
                </p>
              </Link>
            );
          })}
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        {PROMISES.map((p) => (
          <div key={p.title} className="card p-5">
            <span
              className={`flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br ${p.gradient} text-white shadow-lg`}
            >
              <CategoryIcon name={p.icon} className="h-5 w-5" />
            </span>
            <h3 className="mt-3 font-semibold text-ink">{p.title}</h3>
            <p className="mt-1.5 text-sm text-slate-600">{p.body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
