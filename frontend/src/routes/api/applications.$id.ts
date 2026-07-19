import { createFileRoute } from "@tanstack/react-router";
import { APPLICATIONS } from "@/lib/applications-data";

export const Route = createFileRoute("/api/applications/$id")({
  server: {
    handlers: {
      GET: async ({ params }) => {
        const app = APPLICATIONS[params.id];
        if (!app) return new Response("Not found", { status: 404 });
        return Response.json(app);
      },
    },
  },
});
