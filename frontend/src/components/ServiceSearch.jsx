import PropTypes from "prop-types";
import { useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useServiceSearch } from "../hooks/useCatalogue";

const POPULAR = ["AC not cooling", "Pipe leak", "Fan", "Deep cleaning", "Wi-Fi"];

export default function ServiceSearch({ tone = "light", autoFocus = false, placeholder, onNavigate }) {
  const navigate = useNavigate();
  const [term, setTerm] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const boxRef = useRef(null);
  const inputId = useId();
  const listId = useId();
  const { matches, isEmpty, isLoading } = useServiceSearch(term);
  const visible = matches.slice(0, 6);
  const dark = tone === "dark";
  const expanded = open && Boolean(term.trim());

  useEffect(() => setActive(0), [term]);

  useEffect(() => {
    function onClickAway(event) {
      if (boxRef.current && !boxRef.current.contains(event.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickAway);
    return () => document.removeEventListener("mousedown", onClickAway);
  }, []);

  function go(service) {
    setOpen(false);
    setTerm("");
    onNavigate?.();
    navigate(`/providers?service=${service.id}`);
  }

  function onKeyDown(event) {
    if (!open || !visible.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => (i + 1) % visible.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => (i - 1 + visible.length) % visible.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      go(visible[active]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  function submit(event) {
    event.preventDefault();
    if (visible.length) go(visible[active] ?? visible[0]);
    else if (term.trim()) navigate(`/services?q=${encodeURIComponent(term.trim())}`);
  }

  return (
    <div ref={boxRef} className="relative">
      <form onSubmit={submit} role="search">
        <label htmlFor={inputId} className="sr-only">
          Search for a service or a problem
        </label>
        <div className="relative">
          <SearchIcon className={`pointer-events-none absolute top-1/2 left-4 h-5 w-5 -translate-y-1/2 ${dark ? "text-white/60" : "text-slate-600"}`} />
          <input
            id={inputId}
            type="search"
            autoComplete="off"
            autoFocus={autoFocus}
            value={term}
            onChange={(e) => { setTerm(e.target.value); setOpen(true); }}
            onFocus={() => setOpen(true)}
            onBlur={(e) => {
              if (!boxRef.current?.contains(e.relatedTarget)) setOpen(false);
            }}
            onKeyDown={onKeyDown}
            placeholder={placeholder ?? "Search a service or problem"}
            aria-expanded={expanded}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={expanded && visible.length ? `${listId}-${active}` : undefined}
            role="combobox"
            className={`w-full rounded-full py-3.5 pr-4 pl-12 text-base outline-none transition ${
              dark
                ? "border border-white/25 bg-white/15 text-white placeholder:text-white/60 backdrop-blur-xl focus:border-white/50 focus:bg-white/20"
                : "border border-slate-300 bg-white text-slate-900 placeholder:text-slate-600 focus:border-brand-600 focus:ring-2 focus:ring-brand-100"
            }`}
          />
        </div>
      </form>

      {expanded && (
        <div
          id={listId}
          className="absolute inset-x-0 top-full z-50 mt-2 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl"
        >
          {visible.length > 0 ? (
            <ul role="listbox" aria-label="Matching services">
              {visible.map((service, index) => (
                <li key={service.id} role="none">
                  <button
                    id={`${listId}-${index}`}
                    type="button"
                    tabIndex={-1}
                    role="option"
                    aria-selected={index === active}
                    onMouseEnter={() => setActive(index)}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => go(service)}
                    className={`flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition ${
                      index === active ? "bg-brand-50" : "bg-white"
                    }`}
                  >
                    <span>
                      <span className="block font-semibold text-ink">{service.name}</span>
                      <span className="block text-xs text-slate-600">{service.categoryName}</span>
                    </span>
                    <span className="text-xs font-semibold text-brand-700">Find providers →</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : isLoading ? (
            <p className="px-4 py-5 text-sm text-slate-600">Loading services…</p>
          ) : (
            isEmpty && (
              <div className="px-4 py-5 text-sm text-slate-600">
                <p className="font-semibold text-ink">Nothing matched “{term}”.</p>
                <p className="mt-1">Try a simpler word, or browse every service.</p>
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => { setOpen(false); onNavigate?.(); navigate("/services"); }}
                  className="mt-3 rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white"
                >
                  Browse all services
                </button>
              </div>
            )
          )}
        </div>
      )}

      {!term.trim() && tone === "dark" && (
        <div className="mt-3 flex flex-wrap gap-2">
          {POPULAR.map((word) => (
            <button
              key={word}
              type="button"
              onClick={() => { setTerm(word); setOpen(true); }}
              className="rounded-full border border-white/25 bg-white/10 px-3 py-1.5 text-xs font-semibold text-white/90 backdrop-blur-xl transition hover:bg-white/20"
            >
              {word}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

ServiceSearch.propTypes = {
  tone: PropTypes.oneOf(["light", "dark"]),
  autoFocus: PropTypes.bool,
  placeholder: PropTypes.string,
  onNavigate: PropTypes.func,
};

function SearchIcon({ className }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" className={className}>
      <circle cx="9" cy="9" r="6" />
      <path d="M13.5 13.5 17 17" strokeLinecap="round" />
    </svg>
  );
}

SearchIcon.propTypes = { className: PropTypes.string };
