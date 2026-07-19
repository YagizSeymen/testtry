/** @type {import('next').NextConfig} */
const staticExport = process.env.STATIC_EXPORT === "true";

const nextConfig = staticExport
  ? { output: "export" }
  : {
      async rewrites() {
        return [{ source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" }];
      }
    };

export default nextConfig;
