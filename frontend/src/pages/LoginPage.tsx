import { type FormEvent, useState } from "react";
import { Lock, LogIn } from "lucide-react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { getApiErrorMessage } from "../api/axios";
import { useLogin } from "../hooks/useAuth";
import { useAuthStore } from "../store/authStore";
import type { LoginFormValues } from "../types/forms";

export default function LoginPage() {
  const token = useAuthStore((state) => state.token);
  const loginMutation = useLogin();
  const navigate = useNavigate();
  const location = useLocation();
  const [values, setValues] = useState<LoginFormValues>({ email: "", password: "" });
  const from = (location.state as { from?: string } | null)?.from ?? "/dashboard";

  if (token) {
    return <Navigate to="/dashboard" replace />;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    loginMutation.mutate(values, {
      onSuccess: () => navigate(from, { replace: true }),
    });
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
      <section className="grid w-full max-w-5xl overflow-hidden rounded-lg border border-slate-200 bg-white shadow-soft md:grid-cols-[1fr_420px]">
        <div className="bg-slate-950 px-8 py-10 text-white md:px-10">
          <div className="flex h-11 w-11 items-center justify-center rounded-md bg-teal-500">
            <Lock className="h-5 w-5" aria-hidden="true" />
          </div>
          <h1 className="mt-8 max-w-md text-3xl font-bold leading-tight">Factory execution, without waiting for verbal updates.</h1>
          <div className="mt-8 grid max-w-lg gap-3 text-sm text-slate-300">
            <p>See what is pending, where the delay sits, who owns it, and whether shipment is at risk.</p>
            <p>Built for owners and managers who need the day’s production picture in one scan.</p>
          </div>
        </div>

        <div className="px-6 py-8 sm:px-8">
          <h2 className="text-xl font-bold text-slate-950">Sign in</h2>
          <p className="mt-1 text-sm text-slate-500">Use your factory dashboard account.</p>

          <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <label className="label" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                className="field"
                type="email"
                value={values.email}
                onChange={(event) => setValues((current) => ({ ...current, email: event.target.value }))}
                autoComplete="email"
                required
              />
            </div>
            <div className="space-y-2">
              <label className="label" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                className="field"
                type="password"
                value={values.password}
                onChange={(event) => setValues((current) => ({ ...current, password: event.target.value }))}
                autoComplete="current-password"
                required
              />
            </div>

            {loginMutation.isError ? (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {getApiErrorMessage(loginMutation.error)}
              </div>
            ) : null}

            <button type="submit" className="primary-button w-full" disabled={loginMutation.isPending}>
              <LogIn className="h-4 w-4" aria-hidden="true" />
              {loginMutation.isPending ? "Signing in" : "Login"}
            </button>
          </form>

          <p className="mt-5 text-center text-sm text-slate-500">
            Need an account?{" "}
            <Link className="font-semibold text-teal-700 hover:text-teal-800" to="/register">
              Register
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
