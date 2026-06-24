import { useEffect, useRef, useState } from "react";
import { Bot, CheckCircle2, Download, Edit3, FileText, Loader2, Mic, Send, Sparkles, Square, Trash2, User, XCircle } from "lucide-react";

import { getApiErrorMessage } from "../api/axios";
import { askAssistant, fetchArtifactBlob, type VoiceArtifact, type VoiceAskResponse } from "../api/voice";
import { ASSISTANT_SCENARIOS, SUGGESTED_OPENERS, type AssistantScenarioGroup } from "../data/assistantScenarios";
import { useVoiceStream } from "../hooks/useVoiceStream";
import { useAssistantStore } from "../store/assistantStore";

function ArtifactPill({ artifact }: { artifact: VoiceArtifact }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (artifact.type !== "pdf" || !artifact.download_url) return null;

  async function handleDownload() {
    if (!artifact.download_url) return;
    setError(null);
    setBusy(true);
    try {
      const blob = await fetchArtifactBlob(artifact.download_url);
      const url = URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={() => void handleDownload()}
        disabled={busy}
        className="inline-flex items-center gap-2 self-start rounded-md border border-teal-200 bg-teal-50 px-3 py-1.5 text-xs font-semibold text-teal-800 transition hover:bg-teal-100 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
        <span>{artifact.title ?? "PDF report"}</span>
        {!busy ? <Download className="h-3.5 w-3.5" /> : null}
      </button>
      {error ? <p className="text-[11px] text-red-600">{error}</p> : null}
    </div>
  );
}

export default function AssistantPage() {
  const turns = useAssistantStore((state) => state.turns);
  const appendTurn = useAssistantStore((state) => state.appendTurn);
  const clear = useAssistantStore((state) => state.clear);

  const [input, setInput] = useState("");
  const [askInFlight, setAskInFlight] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<VoiceAskResponse["pending_action"]>(null);

  const { state: voiceState, error: voiceError, latestResponse, startCall, endCall, stopCall } = useVoiceStream();
  const voiceBusy = voiceState === "listening" || voiceState === "thinking" || voiceState === "speaking" || voiceState === "connecting";
  const assistantThinking = askInFlight || voiceState === "thinking";

  const transcriptRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const node = transcriptRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [turns.length, assistantThinking]);

  useEffect(() => {
    if (latestResponse) {
      setPendingAction(latestResponse.pending_action ?? null);
    }
  }, [latestResponse]);

  const isEmpty = turns.length === 0;

  async function submit(prompt: string) {
    const text = prompt.trim();
    if (!text || assistantThinking) return;
    setAskError(null);
    appendTurn({ role: "user", text, artifacts: [] });
    setInput("");
    setAskInFlight(true);
    try {
      const response = await askAssistant(text);
      appendTurn({
        role: "assistant",
        text: response.answer ?? "",
        artifacts: response.artifacts ?? [],
      });
      setPendingAction(response.pending_action ?? null);
    } catch (err) {
      const message = getApiErrorMessage(err);
      setAskError(message);
      appendTurn({ role: "system", text: `Error: ${message}`, artifacts: [] });
    } finally {
      setAskInFlight(false);
    }
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submit(input);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit(input);
    }
  }

  function handleVoicePress(event: React.PointerEvent<HTMLButtonElement>) {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    void startCall();
  }

  function handleVoiceRelease(event: React.PointerEvent<HTMLButtonElement>) {
    event.preventDefault();
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      // Pointer capture may already be released on touch cancellation.
    }
    endCall();
  }

  function handleEditPending() {
    if (!pendingAction) return;
    setInput(pendingAction.confirmation_message ?? "");
  }

  const statusLabel = askInFlight || voiceState === "thinking"
    ? "Understanding"
    : pendingAction && pendingAction.missing_fields.length === 0
      ? "Waiting for confirmation"
      : voiceState === "listening"
        ? "Listening"
        : voiceState === "speaking"
          ? "Speaking"
          : "Ready";

  return (
    <section className="panel grid h-[calc(100dvh-7rem)] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden p-0">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-teal-700 text-white">
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-950">Factory Assistant</h1>
            <p className="text-xs text-slate-500">Speak or type an update. Status: <span className="font-semibold text-teal-700">{statusLabel}</span></p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onPointerDown={handleVoicePress}
            onPointerUp={handleVoiceRelease}
            onPointerCancel={handleVoiceRelease}
            disabled={askInFlight || voiceState === "thinking" || voiceState === "speaking" || voiceState === "connecting"}
            className={
              voiceState === "listening"
                ? "inline-flex min-h-12 select-none items-center gap-2 rounded-md bg-red-600 px-4 text-sm font-semibold text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-60"
                : "inline-flex min-h-12 select-none items-center gap-2 rounded-md bg-teal-700 px-4 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-60"
            }
            style={{ touchAction: "none" }}
            aria-label="Hold to speak"
          >
            {voiceState === "thinking" || voiceState === "speaking" || voiceState === "connecting" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mic className="h-4 w-4" />}
            <span>{voiceState === "listening" ? "Release to send" : "Hold to speak"}</span>
            {voiceBusy ? (
              <span className="rounded-full bg-white/20 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
                {voiceState}
              </span>
            ) : null}
          </button>
          {voiceState === "listening" || voiceState === "speaking" ? (
            <button
              type="button"
              onClick={stopCall}
              className="inline-flex min-h-12 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-100"
            >
              <Square className="h-4 w-4" />
              Stop
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => {
              setPendingAction(null);
              clear();
            }}
            disabled={isEmpty}
            className="inline-flex min-h-12 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Clear conversation"
          >
            <Trash2 className="h-4 w-4" />
            Clear
          </button>
        </div>
      </header>

      <div className="grid min-h-0 grid-cols-1 overflow-hidden lg:grid-cols-[minmax(0,1fr)_320px]">
        <div
          ref={transcriptRef}
          className="min-h-0 overflow-y-auto bg-slate-50/40 px-4 py-5 sm:px-5"
        >
          {isEmpty ? (
            <div className="mx-auto max-w-2xl rounded-lg border border-dashed border-slate-300 bg-white px-5 py-8 text-center shadow-sm">
              <Sparkles className="mx-auto h-6 w-6 text-teal-700" />
              <p className="mt-2 text-sm font-semibold text-slate-900">
                Ask anything about your factory — POs, fabric, dispatch, contractors, quality, alerts.
              </p>
              <p className="mt-1 text-xs text-slate-500">Try one of these to get started:</p>
              <div className="mt-3 flex flex-wrap justify-center gap-2">
                {SUGGESTED_OPENERS.map((p: string) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => void submit(p)}
                    className="rounded-full border border-teal-200 bg-white px-3 py-1 text-xs font-semibold text-teal-800 transition hover:bg-teal-50"
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-4">
              {turns.map((turn) => (
                <div key={turn.id} className={turn.role === "user" ? "flex justify-end" : "flex justify-start"}>
                  <div className={`flex max-w-[85%] gap-2 ${turn.role === "user" ? "flex-row-reverse" : ""}`}>
                    <div
                      className={
                        turn.role === "user"
                          ? "flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-teal-700 text-white"
                          : turn.role === "assistant"
                          ? "flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-700"
                          : "flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-800"
                      }
                    >
                      {turn.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                    </div>
                    <div
                      className={
                        turn.role === "user"
                          ? "rounded-2xl rounded-tr-sm bg-teal-700 px-3.5 py-2 text-sm text-white shadow-sm"
                          : turn.role === "assistant"
                          ? "rounded-2xl rounded-tl-sm bg-white px-3.5 py-2 text-sm text-slate-800 shadow-sm ring-1 ring-slate-200"
                          : "rounded-2xl bg-amber-50 px-3.5 py-2 text-sm text-amber-900 shadow-sm ring-1 ring-amber-200"
                      }
                    >
                      <p className="whitespace-pre-wrap break-words leading-relaxed">{turn.text || "…"}</p>
                      {turn.artifacts.length > 0 ? (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {turn.artifacts.map((artifact, index) => (
                            <ArtifactPill key={`${turn.id}-${index}`} artifact={artifact} />
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </div>
                </div>
              ))}
              {assistantThinking ? (
                <div className="flex justify-start">
                  <div className="flex max-w-[85%] gap-2">
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-700">
                      <Bot className="h-4 w-4" />
                    </div>
                    <div className="inline-flex items-center gap-2 rounded-2xl rounded-tl-sm bg-white px-3.5 py-2 text-sm italic text-slate-500 shadow-sm ring-1 ring-slate-200">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Thinking…
                    </div>
                  </div>
                </div>
              ) : null}
              {pendingAction && pendingAction.missing_fields.length === 0 ? (
                <div className="flex justify-start">
                  <div className="flex max-w-[92%] gap-2">
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-teal-100 text-teal-800">
                      <Bot className="h-4 w-4" />
                    </div>
                    <div className="rounded-xl border border-teal-200 bg-white p-3 text-sm shadow-sm">
                      <p className="font-semibold text-slate-950">Confirm update</p>
                      <p className="mt-1 text-slate-700">{pendingAction.confirmation_message ?? "Confirm this update?"}</p>
                      {pendingAction.po_number ? <p className="mt-1 text-xs font-semibold text-teal-700">Affected PO: {pendingAction.po_number}</p> : null}
                      <div className="mt-3 grid grid-cols-3 gap-2">
                        <button type="button" onClick={() => void submit("confirm")} className="inline-flex min-h-11 items-center justify-center gap-1 rounded-md bg-teal-700 px-3 text-xs font-semibold text-white">
                          <CheckCircle2 className="h-4 w-4" /> Confirm
                        </button>
                        <button type="button" onClick={handleEditPending} className="inline-flex min-h-11 items-center justify-center gap-1 rounded-md border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700">
                          <Edit3 className="h-4 w-4" /> Edit
                        </button>
                        <button type="button" onClick={() => void submit("cancel")} className="inline-flex min-h-11 items-center justify-center gap-1 rounded-md border border-red-200 bg-red-50 px-3 text-xs font-semibold text-red-700">
                          <XCircle className="h-4 w-4" /> Cancel
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </div>

        <aside className="hidden min-h-0 flex-col border-l border-slate-200 bg-white lg:flex">
          <div className="border-b border-slate-200 px-4 py-3">
            <p className="text-sm font-semibold text-slate-900">Common questions</p>
            <p className="text-xs text-slate-500">Tap to send</p>
          </div>
          <div className="sidebar-scroll min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
            {ASSISTANT_SCENARIOS.map((group: AssistantScenarioGroup) => (
              <div key={group.id} className="space-y-2">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{group.title}</p>
                  <p className="mt-0.5 text-[11px] text-slate-500">{group.description}</p>
                </div>
                <div className="flex flex-col gap-1.5">
                  {group.prompts.map((prompt: string) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => void submit(prompt)}
                      disabled={assistantThinking}
                      className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-left text-xs leading-snug text-slate-700 transition hover:border-teal-300 hover:bg-teal-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </aside>
      </div>

      <div className="border-t border-slate-200 bg-white">
        {askError || voiceError ? (
          <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800">
            {askError ?? voiceError}
          </div>
        ) : null}
        <form onSubmit={handleSubmit} className="flex items-end gap-2 px-4 py-3 pb-[max(env(safe-area-inset-bottom),0.75rem)]">
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything — e.g. 'Generate today's dispatch PDF'"
            rows={1}
            className="field max-h-32 min-h-12 flex-1 resize-none py-3 text-base leading-snug"
            disabled={assistantThinking}
          />
          <button
            type="submit"
            className="primary-button inline-flex min-h-12 items-center gap-2 px-4"
            disabled={!input.trim() || assistantThinking}
          >
            <Send className="h-4 w-4" />
            Send
          </button>
        </form>
      </div>
    </section>
  );
}
