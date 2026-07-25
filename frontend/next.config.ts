import path from "node:path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a minimal self-contained server bundle (.next/standalone) for a small
  // production Docker image — see frontend/Dockerfile.
  output: "standalone",
  // Pin the workspace root to this app so Next doesn't infer it from an
  // unrelated lockfile elsewhere on the machine.
  turbopack: {
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
