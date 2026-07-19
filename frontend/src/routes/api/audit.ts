import { createFileRoute } from "@tanstack/react-router";
import { listAudit } from "@/lib/applications-data";

export const Route = createFileRoute("/api/audit")({
  server: {
    handlers: {
      GET: async ({ request }) => {
        const url = new URL(request.url);
        const appId = url.searchParams.get("application_id") ?? undefined;
        return Response.json({ audit: listAudit(appId) });
      },
    },
  },
});
