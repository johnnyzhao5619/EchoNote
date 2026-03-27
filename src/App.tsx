import { useEffect } from "react";
import { RouterProvider } from "@tanstack/react-router";
import { ThemeProvider } from "@/components/providers/ThemeProvider";
import { ModelRequiredDialog } from "@/components/models/ModelRequiredDialog";
import { useModelsStore } from "@/store/models";
import { useTranscriptionStore } from "@/store/transcription";
import { router } from "./router";

export function App() {
  const setupModelListeners = useModelsStore((s) => s._setupListeners);
  const checkFfmpeg = useTranscriptionStore((state) => state.checkFfmpeg);

  useEffect(() => {
    const cleanup = setupModelListeners();
    return cleanup;
  }, []);

  useEffect(() => {
    void checkFfmpeg();
  }, [checkFfmpeg]);

  return (
    <ThemeProvider>
      <RouterProvider router={router} />
      <ModelRequiredDialog />
    </ThemeProvider>
  );
}
