/** @type {import('next').NextConfig} */
const staticExport = process.env.STATIC_EXPORT === "true";
const localApiServer = process.env.LOCAL_API_URL || "http://127.0.0.1:8000";

const nextConfig = staticExport
  ? { output: "export" }
  : process.env.VERCEL === "1"
    ? {}
    : {
      async rewrites() {
        return [{ source: "/api/:path*", destination: `${localApiServer}/api/:path*` }];
      }
    };

export default nextConfig;
