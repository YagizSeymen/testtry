import { createFileRoute } from "@tanstack/react-router";
import { decide } from "@/lib/applications-data";

export const Route = createFileRoute("/api/decisions/$id/decide")({
  server: {
    handlers: {
      POST: async ({ params, request }) => {
        const body = (await request.json().catch(() => ({}))) as {
          verdict?: "approved" | "rejected";
          note?: string;
        };
        if (body.verdict !== "approved" && body.verdict !== "rejected") {
          return new Response("verdict must be 'approved' or 'rejected'", { status: 400 });
        }
        const app = decide(params.id, body.verdict, body.note);
        if (!app) return new Response("Not found", { status: 404 });
        return Response.json({
          id: app.id,
          decision: app.decision,
          last_event: app.audit[app.audit.length - 1],
        });
      },
    },
  },
});
