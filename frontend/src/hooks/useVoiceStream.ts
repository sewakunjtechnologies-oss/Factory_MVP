import { useCallback, useEffect, useRef, useState } from "react";

import { getApiErrorMessage } from "../api/axios";
import { askAssistant } from "../api/voice";
import { useAssistantStore } from "../store/assistantStore";

// Listening uses the browser's Web Speech API (SpeechRecognition). The Gemini
// brain handles reasoning + tool calls via POST /voice/ask; replies are spoken
// back through SpeechSynthesis. No audio is sent to the backend.

type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: ArrayLike<ArrayLike<{ transcript: string; confidence: number }> & { isFinal: boolean }>;
};

type SpeechRecognitionErrorLike = { error?: string; message?: string };

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((ev: SpeechRecognitionEventLike) => void) | null;
  onerror: ((ev: SpeechRecognitionErrorLike) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getSpeechRecognitionCtor(): SpeechRecognitionCtor | null {
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export type VoiceStreamState =
  | "idle"
  | "connecting"
  | "ready"
  | "speaking"   // assistant TTS is playing
  | "listening"  // mic is open, recognizing speech
  | "thinking"   // waiting on /voice/ask
  | "error";

export interface ToolEvent {
  id: number;
  name: string;
  args?: Record<string, unknown>;
  result?: unknown;
}

interface UseVoiceStreamApi {
  state: VoiceStreamState;
  error: string | null;
  toolEvents: ToolEvent[];
  startCall: () => Promise<void>;
  endCall: () => void;
}

const RECOGNITION_LANG = "en-IN";

export function useVoiceStream(): UseVoiceStreamApi {
  const [state, setState] = useState<VoiceStreamState>("idle");
  const [error, setError] = useState<string | null>(null);
  // REST /voice/ask returns one final answer — tool events are never streamed in.
  const [toolEvents] = useState<ToolEvent[]>([]);

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const activeRef = useRef(false);
  const pendingTranscriptRef = useRef("");
  const askInFlightRef = useRef(false);

  const speak = useCallback((text: string): Promise<void> => {
    return new Promise((resolve) => {
      if (!text.trim() || typeof window === "undefined" || !window.speechSynthesis) {
        resolve();
        return;
      }
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = RECOGNITION_LANG;
      utter.onend = () => resolve();
      utter.onerror = () => resolve();
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utter);
    });
  }, []);

  const stopRecognition = useCallback(() => {
    const recognition = recognitionRef.current;
    if (recognition) {
      try { recognition.onend = null; } catch { /* ignore */ }
      try { recognition.abort(); } catch { /* ignore */ }
    }
    recognitionRef.current = null;
  }, []);

  const cleanup = useCallback(() => {
    activeRef.current = false;
    stopRecognition();
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    pendingTranscriptRef.current = "";
    askInFlightRef.current = false;
  }, [stopRecognition]);

  const startRecognition = useCallback(() => {
    if (!activeRef.current) return;
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) {
      setError("Speech recognition is not supported in this browser. Use Chrome/Edge.");
      setState("error");
      activeRef.current = false;
      return;
    }
    const recognition = new Ctor();
    // continuous=false makes the browser fire `onend` automatically when the
    // user pauses speaking — which is what we use to trigger the API call.
    // With continuous=true, onend never fires until we explicitly stop, so
    // utterances just accumulate and never get sent.
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = RECOGNITION_LANG;
    recognitionRef.current = recognition;

    recognition.onstart = () => {
      if (activeRef.current && !askInFlightRef.current) setState("listening");
    };

    recognition.onresult = (event) => {
      let finalText = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const transcript = result[0]?.transcript ?? "";
        if (result.isFinal) {
          finalText += transcript;
        }
      }
      if (!finalText.trim()) return;
      pendingTranscriptRef.current = (pendingTranscriptRef.current + " " + finalText).trim();
    };

    recognition.onerror = (event) => {
      // "no-speech" and "aborted" are routine; ignore. Surface auth / network issues.
      const code = event.error ?? "";
      if (code === "not-allowed" || code === "service-not-allowed") {
        setError("Microphone permission denied.");
        setState("error");
        activeRef.current = false;
      }
    };

    recognition.onend = async () => {
      const utterance = pendingTranscriptRef.current.trim();
      pendingTranscriptRef.current = "";

      if (!activeRef.current) return;

      if (!utterance) {
        // No speech captured this segment — just resume listening.
        startRecognition();
        return;
      }

      askInFlightRef.current = true;
      setState("thinking");
      useAssistantStore.getState().appendTurn({ role: "user", text: utterance, artifacts: [] });
      try {
        const response = await askAssistant(utterance);
        const answer = response.answer ?? "";
        useAssistantStore.getState().appendTurn({
          role: "assistant",
          text: answer,
          artifacts: response.artifacts ?? [],
        });
        if (!activeRef.current) return;
        setState("speaking");
        await speak(answer);
      } catch (err) {
        if (activeRef.current) {
          setError(getApiErrorMessage(err));
          setState("error");
          activeRef.current = false;
        }
        return;
      } finally {
        askInFlightRef.current = false;
      }

      if (activeRef.current) {
        startRecognition();
      }
    };

    try {
      recognition.start();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start microphone.");
      setState("error");
      activeRef.current = false;
    }
  }, [speak]);

  const startCall = useCallback(async () => {
    if (activeRef.current) return;

    if (!getSpeechRecognitionCtor()) {
      setError("Speech recognition is not supported in this browser. Use Chrome/Edge.");
      setState("error");
      return;
    }

    setError(null);
    setState("connecting");

    try {
      // Trigger the mic permission prompt early so the user sees one explicit ask.
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
    } catch {
      setError("Microphone permission denied.");
      setState("error");
      return;
    }

    activeRef.current = true;
    setState("ready");
    startRecognition();
  }, [startRecognition]);

  const endCall = useCallback(() => {
    cleanup();
    setState("idle");
    setError(null);
  }, [cleanup]);

  useEffect(() => cleanup, [cleanup]);

  return { state, error, toolEvents, startCall, endCall };
}
