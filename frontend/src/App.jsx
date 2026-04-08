import { useCallback, useEffect, useRef, useState } from "react";

const POLL_MS = 2000;

/** Avoids `Unexpected end of JSON input` when Vite proxy returns an empty body (backend down). */
async function readJsonResponse(res) {
  const text = await res.text();
  if (!text.trim()) {
    throw new Error(
      "Empty API response — Django is probably not reachable. Run: python manage.py runserver 8001 " +
        "(or set VITE_PROXY_API to your Django URL and restart npm run dev)."
    );
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(
      `Expected JSON (HTTP ${res.status}): ${text.slice(0, 160)}${text.length > 160 ? "…" : ""}`
    );
  }
}

function terminalClass(line) {
  if (/BLOCKED|Failed|ERROR|error/i.test(line)) return "text-red-400";
  if (/Completed|passed|✓/i.test(line)) return "text-emerald-400";
  return "text-gray-300";
}

export default function App() {
  const [prompt, setPrompt] = useState("");
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);

  const [sessionId, setSessionId] = useState(null);
  const [status, setStatus] = useState(null);
  const [finalText, setFinalText] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [terminalLines, setTerminalLines] = useState([]);
  const [busy, setBusy] = useState(false);
  const [wipeBusy, setWipeBusy] = useState(false);

  const lastStatusRef = useRef(null);
  const pollRef = useRef(null);

  const appendTerminal = useCallback((line) => {
    setTerminalLines((prev) => [...prev, line]);
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const pollSession = useCallback(
    async (sid) => {
      try {
        const res = await fetch(`/api/sessions/${sid}/`);
        if (res.status === 404) {
          stopPolling();
          appendTerminal("[System] Session not found (was it wiped?).");
          setSessionId(null);
          return;
        }
        const data = await readJsonResponse(res);
        if (data.status && data.status !== lastStatusRef.current) {
          lastStatusRef.current = data.status;
          setStatus(data.status);
          appendTerminal(
            `[${new Date().toLocaleTimeString()}] STATUS → ${data.status}`
          );
        }
        if (data.status === "Completed") {
          setFinalText(data.final_rehydrated_text || "");
          setErrorMessage("");
          stopPolling();
          appendTerminal("[System] Pipeline finished successfully.");
          setBusy(false);
        } else if (data.status === "Failed") {
          setErrorMessage(data.error_message || "Unknown failure");
          setFinalText("");
          stopPolling();
          appendTerminal(
            `[System] Pipeline failed: ${data.error_message || "Unknown"}`
          );
          setBusy(false);
        }
      } catch (e) {
        stopPolling();
        appendTerminal(`[System] Poll error: ${e.message}`);
        setBusy(false);
      }
    },
    [appendTerminal, stopPolling]
  );

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const onSubmit = async (e) => {
    e.preventDefault();
    const p = prompt.trim();
    const key = apiKey.trim();
    if (!p || !key) return;

    stopPolling();
    setBusy(true);
    setSessionId(null);
    setStatus(null);
    setFinalText("");
    setErrorMessage("");
    lastStatusRef.current = null;
    setTerminalLines([]);
    appendTerminal("[System] Submitting session…");

    try {
      const res = await fetch("/api/sessions/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: p,
          provider,
          api_key: key,
        }),
      });
      const data = await readJsonResponse(res);
      if (!res.ok) {
        appendTerminal(`[System] ${JSON.stringify(data)}`);
        setBusy(false);
        return;
      }
      const sid = data.session_id;
      setSessionId(sid);
      appendTerminal(`[System] Session created — session_id=${sid}`);
      appendTerminal("[System] Polling every 2s…");

      pollRef.current = setInterval(() => {
        pollSession(sid);
      }, POLL_MS);
      pollSession(sid);
    } catch (err) {
      appendTerminal(`[System] Network error: ${err.message}`);
      setBusy(false);
    }
  };

  const onWipe = async () => {
    if (!sessionId) return;
    setWipeBusy(true);
    try {
      const res = await fetch(`/api/sessions/${sessionId}/`, {
        method: "DELETE",
      });
      if (res.status === 204) {
        appendTerminal(
          "[System] Local audit log wiped — row removed from SQLite."
        );
        stopPolling();
        setSessionId(null);
        setStatus(null);
        lastStatusRef.current = null;
      } else if (res.status === 404) {
        appendTerminal("[System] Session already absent.");
        setSessionId(null);
      } else {
        try {
          const body = await readJsonResponse(res);
          appendTerminal(`[System] Wipe failed: ${JSON.stringify(body)}`);
        } catch (e) {
          appendTerminal(`[System] Wipe failed: HTTP ${res.status} — ${e.message}`);
        }
      }
    } catch (e) {
      appendTerminal(`[System] Wipe error: ${e.message}`);
    } finally {
      setWipeBusy(false);
    }
  };

  const canSubmit = prompt.trim().length > 0 && apiKey.trim().length > 0 && !busy;
  const canWipe = Boolean(sessionId) && !wipeBusy;

  return (
    <div className="flex min-h-full flex-col bg-gray-950 text-gray-100 antialiased">
      <header className="sticky top-0 z-10 border-b border-gray-800 bg-gray-950/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 select-none items-center justify-center rounded-lg bg-sovereign-600 text-sm font-bold text-white">
              SR
            </div>
            <div>
              <h1 className="text-lg font-semibold tracking-tight text-white">
                Sovereign AI Router
              </h1>
              <p className="text-xs text-gray-500">
                Enterprise Privacy Firewall · Q-Hack 2026
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span className="inline-block h-2 w-2 animate-pulse-dot rounded-full bg-emerald-500" />
            Ollama Local · SQLite state
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        <div className="grid gap-8 lg:grid-cols-2">
          <form className="flex flex-col gap-5" onSubmit={onSubmit}>
            <div>
              <label
                htmlFor="prompt"
                className="mb-1.5 block text-sm font-medium text-gray-300"
              >
                Prompt
              </label>
              <textarea
                id="prompt"
                rows={8}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Enter your prompt — sensitive data is redacted before the cloud…"
                className="w-full resize-none rounded-lg border border-gray-700 bg-gray-900 px-4 py-3 text-sm text-gray-100 placeholder-gray-600 transition focus:border-sovereign-500 focus:outline-none focus:ring-1 focus:ring-sovereign-500/40"
              />
            </div>

            <div>
              <label
                htmlFor="provider"
                className="mb-1.5 block text-sm font-medium text-gray-300"
              >
                Cloud provider
              </label>
              <select
                id="provider"
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-2.5 text-sm text-gray-100 transition focus:border-sovereign-500 focus:outline-none focus:ring-1 focus:ring-sovereign-500/40"
              >
                <option value="openai">OpenAI</option>
                <option value="gemini">Google Gemini</option>
              </select>
            </div>

            <div>
              <label
                htmlFor="api-key"
                className="mb-1.5 block text-sm font-medium text-gray-300"
              >
                API key{" "}
                <span className="text-xs font-normal text-gray-500">
                  (browser memory only — never sent to SQLite)
                </span>
              </label>
              <div className="relative">
                <input
                  id="api-key"
                  type={showKey ? "text" : "password"}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-... or AIza..."
                  autoComplete="off"
                  className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-2.5 pr-20 text-sm text-gray-100 placeholder-gray-600 transition focus:border-sovereign-500 focus:outline-none focus:ring-1 focus:ring-sovereign-500/40"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded px-2 py-1 text-xs text-gray-400 transition hover:text-gray-200"
                >
                  {showKey ? "Hide" : "Show"}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={!canSubmit}
              className="mt-1 flex items-center justify-center gap-2 rounded-lg bg-sovereign-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-sovereign-500 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {busy ? (
                <>
                  <span
                    className="inline-block h-4 w-4 animate-spin-slow rounded-full border-2 border-white/30 border-t-white"
                    aria-hidden
                  />
                  Running pipeline…
                </>
              ) : (
                "Send through Sovereign Pipeline"
              )}
            </button>

            <button
              type="button"
              disabled={!canWipe}
              onClick={onWipe}
              className="rounded-lg border border-amber-900/60 bg-amber-950/20 px-5 py-2.5 text-sm font-medium text-amber-200/90 transition hover:bg-amber-950/40 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Wipe Local Audit Log (DELETE session)
            </button>

            <p className="rounded-lg border border-gray-800 bg-gray-900/60 p-4 text-xs leading-relaxed text-gray-400">
              <strong className="text-gray-300">Privacy:</strong> Prompts and
              mappings are stored temporarily in local{" "}
              <code className="text-sovereign-400">db.sqlite3</code> for
              pipeline state. Your cloud API key stays in RAM only. Use{" "}
              <em>Wipe Local Audit Log</em> to remove the session row from disk.
            </p>
          </form>

          <div className="flex flex-col gap-5">
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-sm font-medium text-gray-300">
                  Status Terminal
                </span>
                {status && (
                  <span className="font-mono text-xs text-sovereign-400">
                    {status}
                  </span>
                )}
              </div>
              <div className="h-64 overflow-y-auto rounded-lg border border-gray-800 bg-black p-4 font-mono text-xs leading-relaxed">
                {terminalLines.length === 0 ? (
                  <span className="text-gray-600">Waiting for input…</span>
                ) : (
                  terminalLines.map((line, i) => (
                    <div key={i} className="log-enter mb-1">
                      <span className={terminalClass(line)}>{line}</span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {errorMessage && (
              <div className="rounded-lg border border-red-900/50 bg-red-950/30 p-4 text-sm text-red-300">
                <strong>Error:</strong> {errorMessage}
              </div>
            )}

            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-300">
                Final response
              </label>
              <div className="min-h-[12rem] whitespace-pre-wrap rounded-lg border border-gray-800 bg-gray-900 p-4 text-sm leading-relaxed text-gray-200">
                {finalText ? (
                  finalText
                ) : (
                  <span className="text-gray-600">
                    Re-hydrated text appears when status is Completed…
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>

      <footer className="border-t border-gray-800 py-4 text-center text-xs text-gray-600">
        Sovereign AI Router — Exxeta Q-Hack 2026
      </footer>
    </div>
  );
}
