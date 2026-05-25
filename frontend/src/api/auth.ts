import { api } from "./axios";
import type { LoginRequest, LoginResponse, RegisterRequest } from "../types/api";

export async function login(payload: LoginRequest): Promise<LoginResponse> {
  const response = await api.post<LoginResponse>("/auth/login", payload);
  return response.data;
}

export async function register(payload: RegisterRequest): Promise<LoginResponse> {
  const response = await api.post<LoginResponse>("/auth/register", payload);
  return response.data;
}
