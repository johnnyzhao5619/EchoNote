import { useEffect } from "react";
import { RouterProvider } from "@tanstack/react-router";
import { ThemeProvider } from "@/components/providers/ThemeProvider";
import { ModelRequiredDialog } from "@/components/models/ModelRequiredDialog";
import { useModelsStore } from "@/store/models";
import { router } from "./router";

export function App() {
  const setupModelListeners = useModelsStore((s) => s._setupListeners);

  useEffect(() => {
    const cleanup = setupModelListeners();
    return cleanup;
  }, []);

  return (
    <ThemeProvider>
      <RouterProvider router={router} />
      <ModelRequiredDialog />
    </ThemeProvider>
  );
}
