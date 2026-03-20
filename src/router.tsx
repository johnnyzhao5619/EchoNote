import { createRouter } from "@tanstack/react-router";
import { routeTree } from "./routeTree.gen";

export const router = createRouter({
  routeTree,
  defaultPreload: "intent",
});

// 类型注册（TanStack Router 类型安全要求）
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
