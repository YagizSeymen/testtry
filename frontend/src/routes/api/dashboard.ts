import { createFileRoute } from "@tanstack/react-router";
import { FOUNDERS } from "@/lib/dashboard-data";

export const Route = createFileRoute("/api/dashboard")({
  server: {
    handlers: {
      GET: async () => {
        return Response.json({
          founders: [...FOUNDERS].sort((a, b) => b.score - a.score),
          generated_at: new Date().toISOString(),
        });
      },
    },
  },
});
