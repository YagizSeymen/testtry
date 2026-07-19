import { createFileRoute } from "@tanstack/react-router";
import { listQueue } from "@/lib/applications-data";

export const Route = createFileRoute("/api/decisions/queue")({
  server: {
    handlers: {
      GET: async () => Response.json({ queue: listQueue() }),
    },
  },
});
