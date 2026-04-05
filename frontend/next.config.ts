import type { NextConfig } from "next";

function normalizeUrl(value: string | undefined): string | null {
  if (!value) {
    return null;
  }

  return value.endsWith("/") ? value.slice(0, -1) : value;
}

const backendUrl =
  normalizeUrl(process.env.NEXT_PUBLIC_API_BASE_URL) ??
  normalizeUrl(process.env.API_BASE_URL) ??
  "https://finmind-production-23fd.up.railway.app";

const nextConfig: NextConfig = {
  devIndicators: false,
  allowedDevOrigins: ["192.168.0.7"],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
