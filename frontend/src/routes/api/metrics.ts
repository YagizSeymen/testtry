import { createFileRoute } from "@tanstack/react-router";
import { computeMetrics } from "@/lib/applications-data";

export const Route = createFileRoute("/api/metrics")({
  server: {
    handlers: {
      GET: async () => Response.json(computeMetrics()),
    },
  },
});
