// src/hooks/useLlmStream.ts
// Monitor Tauri events llm:token / llm:done / llm:error, aggregate to useLlmStore by task_id.
// Call once at app startup (in root route component).

import { useEffect } from "react";
import { listen, UnlistenFn } from "@tauri-apps/api/event";
import { useLlmStore } from "@/store/llm";

interface TokenPayload {
  task_id: string;
  token: string;
}

interface LlmTaskResult {
  task_id: string;
  document_id: string;
  result_text: string;
  asset_role: string;
  asset_id: string;
  completed_at: number;
}

interface LlmErrorPayload {
  task_id: string;
  error: string;
}

export function useLlmStream() {
  const { appendToken, setDone, setError, setCancelled } = useLlmStore();

  useEffect(() => {
    const cleanups: UnlistenFn[] = [];

    (async () => {
      const unToken = await listen<TokenPayload>("llm:token", (event) => {
        appendToken(event.payload.task_id, event.payload.token);
      });
      cleanups.push(unToken);

      const unDone = await listen<LlmTaskResult>("llm:done", (event) => {
        setDone(event.payload.task_id, event.payload.result_text);
      });
      cleanups.push(unDone);

      const unError = await listen<LlmErrorPayload>("llm:error", (event) => {
        if (event.payload.error.toLowerCase().startsWith("cancelled")) {
          setCancelled(event.payload.task_id);
        } else {
          setError(event.payload.task_id, event.payload.error);
        }
      });
      cleanups.push(unError);
    })();

    return () => {
      cleanups.forEach((fn) => fn());
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
}
