import { type FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { KeyRound, UserPlus } from "lucide-react";

import { getApiErrorMessage } from "../api/axios";
import { useRegister } from "../hooks/useAuth";
import { useAuthStore } from "../store/authStore";
import type { RegisterFormValues } from "../types/forms";

const initialValues: RegisterFormValues = {
  full_name: "",
  email: "",
  password: "",
  confirm_password: "",
  role: "owner",
};

export default function RegisterPage() {
  const token = useAuthStore((state) => state.token);
  const registerMutation = useRegister();
  const navigate = useNavigate();
  const [values, setValues] = useState<RegisterFormValues>(initialValues);
  const [formError, setFormError] = useState<string | null>(null);

  if (token) {
    return <Navigate to="/dashboard" replace />;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    if (values.password !== values.confirm_password) {
      setFormError("Passwords do not match.");
      return;
    }

    registerMutation.mutate(
      {
        full_name: values.full_name,
        email: values.email,
        password: values.password,
        role: values.role,
      },
      {
        onSuccess: () => navigate("/dashboard", { replace: true }),
      },
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
      <section className="grid w-full max-w-5xl overflow-hidden rounded-lg border border-slate-200 bg-white shadow-soft md:grid-cols-[1fr_440px]">
        <div className="bg-slate-950 px-8 py-10 text-white md:px-10">
          <div className="flex h-11 w-11 items-center justify-center rounded-md bg-teal-500">
            <KeyRound className="h-5 w-5" aria-hidden="true" />
          </div>
          <h1 className="mt-8 max-w-md text-3xl font-bold leading-tight">Create the first factory control account.</h1>
          <div className="mt-8 grid max-w-lg gap-3 text-sm text-slate-300">
            <p>Register an owner account for full control, or a receipt-only role for allocation, verification, or dispatch work.</p>
            <p>The same JWT session powers production entry, dispatch, alerts, and PO visibility.</p>
          </div>
        </div>

        <div className="px-6 py-8 sm:px-8">
          <h2 className="text-xl font-bold text-slate-950">Register</h2>
          <p className="mt-1 text-sm text-slate-500">Create a dashboard user connected to the backend auth route.</p>

          <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <label className="label" htmlFor="full_name">
                Full Name
              </label>
              <input
                id="full_name"
                className="field"
                type="text"
                value={values.full_name}
                onChange={(event) => setValues((current) => ({ ...current, full_name: event.target.value }))}
                autoComplete="name"
                required
              />
            </div>

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
              <label className="label" htmlFor="role">
                Role
              </label>
              <select
                id="role"
                className="field"
                value={values.role}
                onChange={(event) =>
                  setValues((current) => ({
                    ...current,
                    role: event.target.value as RegisterFormValues["role"],
                  }))
                }
              >
                <option value="owner">Owner</option>
                <option value="manager">Manager</option>
              </select>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <label className="label" htmlFor="password">
                  Password
                </label>
                <input
                  id="password"
                  className="field"
                  type="password"
                  minLength={8}
                  value={values.password}
                  onChange={(event) => setValues((current) => ({ ...current, password: event.target.value }))}
                  autoComplete="new-password"
                  required
                />
              </div>

              <div className="space-y-2">
                <label className="label" htmlFor="confirm_password">
                  Confirm
                </label>
                <input
                  id="confirm_password"
                  className="field"
                  type="password"
                  minLength={8}
                  value={values.confirm_password}
                  onChange={(event) => setValues((current) => ({ ...current, confirm_password: event.target.value }))}
                  autoComplete="new-password"
                  required
                />
              </div>
            </div>

            {formError ? (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{formError}</div>
            ) : null}
            {registerMutation.isError ? (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {getApiErrorMessage(registerMutation.error)}
              </div>
            ) : null}

            <button type="submit" className="primary-button w-full" disabled={registerMutation.isPending}>
              <UserPlus className="h-4 w-4" aria-hidden="true" />
              {registerMutation.isPending ? "Creating Account" : "Create Account"}
            </button>
          </form>

          <p className="mt-5 text-center text-sm text-slate-500">
            Already have an account?{" "}
            <Link className="font-semibold text-teal-700 hover:text-teal-800" to="/login">
              Login
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
