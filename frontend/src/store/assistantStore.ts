import { create } from "zustand";

import type { VoiceArtifact } from "../api/voice";

export type AssistantTurnRole = "user" | "assistant" | "system";

export interface AssistantTurn {
  id: string;
  role: AssistantTurnRole;
  text: string;
  artifacts: VoiceArtifact[];
  createdAt: number;
}

interface AssistantState {
  turns: AssistantTurn[];
  appendTurn: (turn: Omit<AssistantTurn, "id" | "createdAt">) => string;
  clear: () => void;
}

function nextId(): string {
  return `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export const useAssistantStore = create<AssistantState>((set) => ({
  turns: [],
  appendTurn: (turn) => {
    const id = nextId();
    set((state) => ({
      turns: [...state.turns, { id, createdAt: Date.now(), ...turn }],
    }));
    return id;
  },
  clear: () => set({ turns: [] }),
}));
