/** @type {import('next').NextConfig} */
// O navegador fala sempre com /api/v1/... (mesma origem); o Next encaminha ao backend FastAPI.
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  eslint: { ignoreDuringBuilds: true },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
};
export default nextConfig;
