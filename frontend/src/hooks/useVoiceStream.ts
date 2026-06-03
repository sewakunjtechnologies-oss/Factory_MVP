import { useCallback, useEffect, useRef, useState } from "react";

import { getApiErrorMessage } from "../api/axios";
import { askAssistant } from "../api/voice";
import { canUseNativeSpeech, recognizeWithNativeSpeech, speakWithNativeSpeech, stopNativeSpeech } from "../native/factorySpeech";
import { useAssistantStore } from "../store/assistantStore";

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
  | "speaking"
  | "listening"
  | "thinking"
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

function splitForSpeech(text: string): string[] {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (!cleaned) return [];
  const sentences = cleaned.match(/[^.!?]+[.!?]*/g) ?? [cleaned];
  const chunks: string[] = [];
  let current = "";
  sentences.forEach((sentence) => {
    const next = sentence.trim();
    if (!next) return;
    if ((current + " " + next).trim().length <= 220) {
      current = (current + " " + next).trim();
      return;
    }
    if (current) chunks.push(current);
    if (next.length <= 220) {
      current = next;
      return;
    }
    for (let index = 0; index < next.length; index += 200) {
      chunks.push(next.slice(index, index + 200));
    }
    current = "";
  });
  if (current) chunks.push(current);
  return chunks;
}

export function useVoiceStream(): UseVoiceStreamApi {
  const [state, setState] = useState<VoiceStreamState>("ready");
  const [error, setError] = useState<string | null>(null);
  const [toolEvents] = useState<ToolEvent[]>([]);

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const interimTranscriptRef = useRef("");
  const finalTranscriptRef = useRef("");
  const isListeningRef = useRef(false);
  const askInFlightRef = useRef(false);
  const shouldSubmitOnEndRef = useRef(false);
  const nativeRecognitionRef = useRef(false);
  const lastSubmittedRef = useRef("");

  const speak = useCallback(async (text: string): Promise<void> => {
    const chunks = splitForSpeech(text);
    if (chunks.length === 0) return;

    if (nativeRecognitionRef.current && await canUseNativeSpeech()) {
      try {
        await speakWithNativeSpeech(chunks.join(" "), RECOGNITION_LANG);
        return;
      } catch {
        // Fall through to browser TTS.
      }
    }

    if (typeof window === "undefined" || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();

    for (const chunk of chunks) {
      await new Promise<void>((resolve) => {
        const utter = new SpeechSynthesisUtterance(chunk);
        utter.lang = RECOGNITION_LANG;
        utter.onend = () => resolve();
        utter.onerror = () => resolve();
        window.speechSynthesis.speak(utter);
      });
    }
  }, []);

  const resetRecognitionRefs = useCallback(() => {
    interimTranscriptRef.current = "";
    finalTranscriptRef.current = "";
    shouldSubmitOnEndRef.current = false;
    isListeningRef.current = false;
  }, []);

  const stopRecognition = useCallback((abort = true) => {
    const recognition = recognitionRef.current;
    if (!recognition) return;
    try {
      if (abort) recognition.abort();
      else recognition.stop();
    } catch {
      // Browser recognition throws when already stopped; harmless.
    }
  }, []);

  const submitUtterance = useCallback(async (utterance: string) => {
    const text = utterance.replace(/\s+/g, " ").trim();
    if (!text || askInFlightRef.current) {
      setState("ready");
      return;
    }
    if (text === lastSubmittedRef.current) {
      setState("ready");
      return;
    }

    lastSubmittedRef.current = text;
    askInFlightRef.current = true;
    setError(null);
    setState("thinking");
    useAssistantStore.getState().appendTurn({ role: "user", text, artifacts: [] });

    try {
      const response = await askAssistant(text);
      const answer = (response.answer ?? "").trim() || "I found the request, but there is no spoken answer available.";
      useAssistantStore.getState().appendTurn({
        role: "assistant",
        text: answer,
        artifacts: response.artifacts ?? [],
      });
      setState("speaking");
      await speak(answer);
      setState("ready");
    } catch (err) {
      const message = getApiErrorMessage(err);
      setError(message);
      useAssistantStore.getState().appendTurn({ role: "system", text: `Error: ${message}`, artifacts: [] });
      setState("error");
      window.setTimeout(() => setState("ready"), 1200);
    } finally {
      askInFlightRef.current = false;
      window.setTimeout(() => {
        lastSubmittedRef.current = "";
      }, 800);
    }
  }, [speak]);

  const startBrowserRecognition = useCallback(() => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) {
      setError("Speech recognition is not available in this browser. Please type your question or use Chrome.");
      setState("error");
      return;
    }

    const recognition = new Ctor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = RECOGNITION_LANG;
    recognitionRef.current = recognition;

    recognition.onstart = () => {
      isListeningRef.current = true;
      setState("listening");
    };

    recognition.onresult = (event) => {
      let interim = "";
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const transcript = result[0]?.transcript ?? "";
        if (result.isFinal) {
          finalTranscriptRef.current = `${finalTranscriptRef.current} ${transcript}`.trim();
        } else {
          interim += transcript;
        }
      }
      interimTranscriptRef.current = interim.trim();
    };

    recognition.onerror = (event) => {
      const code = event.error ?? "";
      if (code === "not-allowed" || code === "service-not-allowed") {
        setError("Microphone permission denied.");
        setState("error");
      }
      if (code === "network") {
        setError("Speech recognition network service is unavailable. Please try again.");
        setState("error");
      }
    };

    recognition.onend = () => {
      recognitionRef.current = null;
      isListeningRef.current = false;
      const transcript = `${finalTranscriptRef.current} ${interimTranscriptRef.current}`.replace(/\s+/g, " ").trim();
      const shouldSubmit = shouldSubmitOnEndRef.current;
      resetRecognitionRefs();
      if (!shouldSubmit) {
        setState((current) => (current === "listening" ? "ready" : current));
        return;
      }
      void submitUtterance(transcript);
    };

    try {
      recognition.start();
    } catch (err) {
      recognitionRef.current = null;
      setError(err instanceof Error ? err.message : "Could not start microphone.");
      setState("error");
    }
  }, [resetRecognitionRefs, submitUtterance]);

  const startCall = useCallback(async () => {
    if (askInFlightRef.current || isListeningRef.current || state === "speaking") return;
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    void stopNativeSpeech();
    resetRecognitionRefs();
    setError(null);
    setState("connecting");

    if (await canUseNativeSpeech()) {
      nativeRecognitionRef.current = true;
      setState("listening");
      try {
        const utterance = await recognizeWithNativeSpeech(RECOGNITION_LANG);
        if (utterance.trim()) {
          await submitUtterance(utterance);
        } else {
          setState("ready");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not capture voice.");
        setState("error");
      }
      return;
    }

    nativeRecognitionRef.current = false;
    startBrowserRecognition();
  }, [resetRecognitionRefs, startBrowserRecognition, state, submitUtterance]);

  const endCall = useCallback(() => {
    if (nativeRecognitionRef.current) {
      void stopNativeSpeech();
      return;
    }
    if (!isListeningRef.current && !recognitionRef.current) return;
    shouldSubmitOnEndRef.current = true;
    stopRecognition(false);
  }, [stopRecognition]);

  useEffect(() => {
    return () => {
      shouldSubmitOnEndRef.current = false;
      stopRecognition(true);
      void stopNativeSpeech();
      if (typeof window !== "undefined" && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, [stopRecognition]);

  return { state, error, toolEvents, startCall, endCall };
}
