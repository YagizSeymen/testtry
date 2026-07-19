import { createFileRoute } from "@tanstack/react-router";
import { FOUNDERS } from "@/lib/dashboard-data";
import { PROFILES } from "@/lib/founder-profiles";

export const Route = createFileRoute("/api/founders/$id")({
  server: {
    handlers: {
      GET: async ({ params }) => {
        const founder = FOUNDERS.find((f) => f.id === params.id);
        const profile = PROFILES[params.id];
        if (!founder || !profile) {
          return new Response("Not found", { status: 404 });
        }
        return Response.json({ founder, profile });
      },
    },
  },
});
