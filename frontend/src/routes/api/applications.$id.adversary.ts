import { createFileRoute } from "@tanstack/react-router";
import { runAdversary } from "@/lib/applications-data";

export const Route = createFileRoute("/api/applications/$id/adversary")({
  server: {
    handlers: {
      POST: async ({ params }) => {
        const app = runAdversary(params.id);
        if (!app) return new Response("Not found or memo missing", { status: 404 });
        return Response.json(app);
      },
    },
  },
});
