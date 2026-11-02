import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { auth } from "../api/endpoints";
import { Button, ErrorMessage, Field, PasswordInput } from "../components/ui";
import { ROLE } from "../constants/domain";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useSession } from "../hooks/useSession";
import { toast } from "../store/toast";

const RESEND_SECONDS = 30;

function landingFor(user, from) {
  if (from) return from;
  return user.activeRole === ROLE.PROVIDER ? "/provider/dashboard" : "/";
}

export function Login() {
  const { login } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  useDocumentTitle("Log in");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await login({ phone, password });
      navigate(landingFor(user, location.state?.from), { replace: true });
    } catch (err) {
      setError(err.status === 401 ? "That phone number and password do not match." : err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <div className="card p-6 sm:p-8">
        <h1 className="page-title">Welcome back</h1>
        <p className="mt-1 text-sm text-slate-600">Log in with your phone number or email.</p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <Field label="Phone number or email" htmlFor="login-phone">
            <input id="login-phone" className="input" autoComplete="username" autoCapitalize="none" spellCheck={false} placeholder="01712 345678 or you@example.com" value={phone} onChange={(e) => setPhone(e.target.value)} required />
          </Field>
          <Field label="Password" htmlFor="login-password">
            <PasswordInput id="login-password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </Field>
          <ErrorMessage error={error} />
          <Button type="submit" size="lg" loading={busy} className="w-full">Log in</Button>
        </form>
        <p className="mt-6 text-center text-sm text-slate-600">
          New to ServoraBd? <Link to="/register" className="font-semibold text-brand-700">Create an account</Link>
        </p>
      </div>
    </div>
  );
}

export function Register() {
  const { login } = useSession();
  const navigate = useNavigate();
  const [step, setStep] = useState("details");
  const [form, setForm] = useState({ fullName: "", phone: "", password: "", role: ROLE.CUSTOMER });
  const [code, setCode] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  useDocumentTitle(step === "verify" ? "Verify your phone" : "Create your account");

  useEffect(() => {
    if (cooldown <= 0) return undefined;
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  function set(key) {
    return (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  }

  async function signIn() {
    const user = await login({ phone: form.phone, password: form.password });
    navigate(user.activeRole === ROLE.PROVIDER ? "/provider/profile" : "/", { replace: true });
  }

  async function submitDetails(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await auth.register(form);
      setForm((f) => ({ ...f, phone: result.user.phone }));
      setCode("");
      if (result.otpSent) setCooldown(RESEND_SECONDS);
      setStep("verify");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function submitCode(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await auth.verifyOtp({ phone: form.phone, code });
      await signIn();
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  async function resend() {
    setError(null);
    try {
      await auth.sendOtp(form.phone);
      setCooldown(RESEND_SECONDS);
      toast(`A new code is on its way to ${form.phone}.`);
    } catch (err) {
      setError(err);
    }
  }

  async function skip() {
    setBusy(true);
    setError(null);
    try {
      await signIn();
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  if (step === "verify") {
    return (
      <div className="mx-auto max-w-md">
        <div className="card p-6 sm:p-8">
          <h1 className="page-title">Verify your phone</h1>
          <p className="mt-1 text-sm text-slate-600">We sent a 6-digit code to {form.phone}. It expires in 5 minutes.</p>
          <form onSubmit={submitCode} className="mt-6 space-y-4">
            <Field label="Verification code" htmlFor="otp-code">
              <input id="otp-code" className="input text-center text-2xl tracking-[0.5em]" inputMode="numeric" autoComplete="one-time-code" maxLength={6} pattern="\d{6}" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} required />
            </Field>
            <ErrorMessage error={error} />
            <Button type="submit" size="lg" loading={busy} className="w-full">Verify and continue</Button>
          </form>
          <div className="mt-4 flex justify-between text-sm">
            <button type="button" className="font-semibold text-brand-700 hover:text-brand-800 disabled:font-medium disabled:text-slate-600" onClick={resend} disabled={cooldown > 0}>
              {cooldown > 0 ? `Send a new code in ${cooldown}s` : "Send a new code"}
            </button>
            <button type="button" className="text-slate-600 hover:text-slate-700" onClick={skip} disabled={busy}>
              Skip for now
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md">
      <div className="card p-6 sm:p-8">
        <h1 className="page-title">Create your account</h1>
        <form onSubmit={submitDetails} className="mt-6 space-y-4">
          <fieldset>
            <legend className="label">I want to</legend>
            <div className="grid grid-cols-2 gap-2">
              {[
                [ROLE.CUSTOMER, "Hire a provider"],
                [ROLE.PROVIDER, "Offer my services"],
              ].map(([role, label]) => (
                <label key={role} className={`choice p-3 text-center text-sm font-medium ${form.role === role ? "choice-on" : "choice-off"}`}>
                  <input type="radio" name="role" value={role} checked={form.role === role} onChange={set("role")} className="sr-only" />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
          <Field label="Full name" htmlFor="reg-name">
            <input id="reg-name" className="input" autoComplete="name" value={form.fullName} onChange={set("fullName")} required />
          </Field>
          <Field label="Mobile number" htmlFor="reg-phone" error={error?.fieldError?.("phone")} hint="Bangladeshi number, e.g. 01712 345678">
            <input id="reg-phone" className="input" inputMode="tel" autoComplete="tel" value={form.phone} onChange={set("phone")} required />
          </Field>
          <Field label="Password" htmlFor="reg-password" error={error?.fieldError?.("password")} hint={form.password && form.password.length < 8 ? `At least 8 characters — ${8 - form.password.length} more to go` : "At least 8 characters"}>
            <PasswordInput id="reg-password" autoComplete="new-password" minLength={8} value={form.password} onChange={set("password")} required />
          </Field>
          {error && !error.fieldError?.("phone") && !error.fieldError?.("password") && <ErrorMessage error={error} />}
          <Button type="submit" size="lg" loading={busy} className="w-full">Create account</Button>
        </form>
        <p className="mt-6 text-center text-sm text-slate-600">
          Already have an account? <Link to="/login" className="font-semibold text-brand-700">Log in</Link>
        </p>
      </div>
    </div>
  );
}
