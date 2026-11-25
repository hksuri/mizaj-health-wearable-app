export type ChartSpec = {
  type: "line" | "bar" | "scatter";
  title: string;
  x: { field: string; label: string; kind: string };
  y: { label: string };
  series: { name: string; points: { x: string | number; y: number }[] }[];
};

export type ToolChip = {
  id: string;
  name: string;
  args: unknown;
  ok?: boolean;
  summary?: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  tools?: ToolChip[];
  chart?: ChartSpec;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export async function streamChat(
  message: string,
  sessionId: string | null,
  onEvent: (event: string, data: unknown) => void,
): Promise<string | null> {
  const res = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  if (!res.ok || !res.body) {
    const detail = await res.text();
    throw new Error(detail || `HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let nextSession: string | null = sessionId;
  let eventName = "message";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n");
    buffer = parts.pop() ?? "";
    for (const line of parts) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        const raw = line.slice(5).trim();
        try {
          const data = JSON.parse(raw) as unknown;
          onEvent(eventName, data);
          if (
            eventName === "session" &&
            data &&
            typeof data === "object" &&
            "session_id" in data
          ) {
            nextSession = String((data as { session_id: string }).session_id);
          }
        } catch {
          // ignore malformed chunk
        }
        eventName = "message";
      }
    }
  }
  return nextSession;
}
