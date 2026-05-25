import { useMutation } from "@tanstack/react-query";

import { login, register } from "../api/auth";
import { useAuthStore } from "../store/authStore";
import type { LoginRequest, RegisterRequest } from "../types/api";

export function useLogin() {
  const setSession = useAuthStore((state) => state.setSession);

  return useMutation({
    mutationFn: (payload: LoginRequest) => login(payload),
    onSuccess: (data) => {
      setSession(data.access_token, data.user);
    },
  });
}

export function useRegister() {
  const setSession = useAuthStore((state) => state.setSession);

  return useMutation({
    mutationFn: (payload: RegisterRequest) => register(payload),
    onSuccess: (data) => {
      setSession(data.access_token, data.user);
    },
  });
}
