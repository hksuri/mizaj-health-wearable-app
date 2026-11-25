"use client";

import { useState, type FormEvent } from "react";

import { ChartPanel } from "@/components/ChartPanel";
import { ThemeToggle } from "@/components/ThemeToggle";
import {
  streamChat,
  type ChartSpec,
  type ChatMessage,
  type ToolChip,
} from "@/lib/chat";

export function ChatApp() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setError(null);
    setBusy(true);

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
    };
    const assistantId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      userMsg,
      { id: assistantId, role: "assistant", content: "", tools: [] },
    ]);

    let tools: ToolChip[] = [];
    let chart: ChartSpec | undefined;

    try {
      const nextSession = await streamChat(text, sessionId, (event, data) => {
        if (event === "text_delta" && data && typeof data === "object" && "text" in data) {
          const chunk = String((data as { text: string }).text);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + chunk } : m,
            ),
          );
        }
        if (event === "tool_call" && data && typeof data === "object") {
          const d = data as { id: string; name: string; args: unknown };
          tools = [...tools, { id: d.id, name: d.name, args: d.args }];
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, tools: [...tools] } : m)),
          );
        }
        if (event === "tool_result" && data && typeof data === "object") {
          const d = data as { id: string; ok: boolean; summary: string };
          tools = tools.map((t) =>
            t.id === d.id ? { ...t, ok: d.ok, summary: d.summary } : t,
          );
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, tools: [...tools] } : m)),
          );
        }
        if (event === "chart") {
          chart = data as ChartSpec;
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, chart } : m)),
          );
        }
        if (event === "error" && data && typeof data === "object" && "message" in data) {
          setError(String((data as { message: string }).message));
        }
      });
      if (nextSession) setSessionId(nextSession);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-[var(--m-bg)] text-[var(--m-text)]">
      <div
        aria-hidden
        className="pointer-events-none absolute -left-40 -top-52 h-[640px] w-[640px] rounded-full bg-[var(--m-blob-a)] blur-[100px]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-56 -right-44 h-[620px] w-[620px] rounded-full bg-[var(--m-blob-b)] blur-[110px]"
      />

      <div className="relative mx-auto flex min-h-screen max-w-5xl flex-col px-4 py-6 md:px-8">
        <header className="mb-4 flex items-center justify-between gap-3">
          <div>
            <div className="text-xs font-medium tracking-[0.14em] text-[var(--m-faint)] uppercase">
              Mizaj
            </div>
            <h1 className="text-[15px] font-semibold tracking-tight">Health trends</h1>
          </div>
          <ThemeToggle />
        </header>

        <main className="flex flex-1 flex-col overflow-hidden rounded-[18px] border border-[var(--m-hair)] bg-[var(--m-glass)] shadow-[var(--m-shadow)] backdrop-blur-[24px]">
          <div className="flex-1 space-y-4 overflow-y-auto p-5">
            {messages.length === 0 && (
              <p className="max-w-md text-[var(--m-muted)]">
                Ask about steps, sleep, or resting heart rate. Answers stream with tool
                activity and charts when useful.
              </p>
            )}
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex flex-col gap-2 ${m.role === "user" ? "items-end" : "items-start"}`}
              >
                {m.role === "user" ? (
                  <div className="max-w-[80%] rounded-[14px_14px_4px_14px] border border-[var(--m-hair)] bg-[var(--m-sel)] px-3.5 py-2.5">
                    {m.content}
                  </div>
                ) : (
                  <>
                    {m.tools && m.tools.length > 0 && (
                      <div className="w-full max-w-xl overflow-hidden rounded-xl border border-[var(--m-hair)] bg-[var(--m-glass2)]">
                        <div className="border-b border-[var(--m-hair)] px-3 py-2 text-xs text-[var(--m-muted)]">
                          {m.tools.length} tool call{m.tools.length === 1 ? "" : "s"}
                        </div>
                        <ul className="divide-y divide-[var(--m-hair)] font-mono text-xs">
                          {m.tools.map((t) => (
                            <li key={t.id} className="flex gap-2 px-3 py-2">
                              <span className="font-medium text-[var(--m-text)]">{t.name}</span>
                              <span className="truncate text-[var(--m-faint)]">
                                {t.summary ?? "…"}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {m.content && (
                      <div className="max-w-[90%] text-[14.5px] leading-relaxed whitespace-pre-wrap">
                        {m.content}
                      </div>
                    )}
                    {m.chart && <ChartPanel chart={m.chart} />}
                  </>
                )}
              </div>
            ))}
          </div>

          <form
            onSubmit={onSubmit}
            className="border-t border-[var(--m-hair)] bg-[var(--m-glass2)] p-3"
          >
            {error && (
              <div className="mb-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">
                {error}
              </div>
            )}
            <div className="flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about your trends…"
                disabled={busy}
                className="min-w-0 flex-1 rounded-xl border border-[var(--m-hair)] bg-[var(--m-bg)] px-3.5 py-3 text-sm text-[var(--m-text)] outline-none placeholder:text-[var(--m-faint)] focus:border-[var(--m-accent)]"
              />
              <button
                type="submit"
                disabled={busy || !input.trim()}
                className="rounded-xl bg-[var(--m-accent)] px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
              >
                {busy ? "…" : "Send"}
              </button>
            </div>
          </form>
        </main>
      </div>
    </div>
  );
}
