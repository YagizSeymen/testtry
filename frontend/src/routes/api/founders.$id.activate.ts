import { createFileRoute } from "@tanstack/react-router";
import { PROFILES } from "@/lib/founder-profiles";

export const Route = createFileRoute("/api/founders/$id/activate")({
  server: {
    handlers: {
      POST: async ({ params }) => {
        const profile = PROFILES[params.id];
        if (!profile) return new Response("Not found", { status: 404 });
        return Response.json({
          founder_id: params.id,
          outreach_draft: profile.outreach_draft,
          status: "draft",
          drafted_at: new Date().toISOString(),
        });
      },
    },
  },
});
