import { createFileRoute } from "@tanstack/react-router";
import { listApplications } from "@/lib/applications-data";

export const Route = createFileRoute("/api/applications")({
  server: {
    handlers: {
      GET: async () => Response.json({ applications: listApplications() }),
    },
  },
});
