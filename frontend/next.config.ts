import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  allowedDevOrigins: ["192.168.0.7"],
  generateBuildId: async () => `build-${Date.now()}`,
  webpack: (config) => {
    if (config.cache && typeof config.cache === "object") {
      config.cache = { type: "memory" as const };
    }
    return config;
  },
  async headers() {
    return [
      {
        source: "/",
        headers: [{ key: "Cache-Control", value: "no-store" }],
      },
    ];
  },
};

export default nextConfig;
// 2026年 4月 5日 星期日 12時48分34秒 CST
