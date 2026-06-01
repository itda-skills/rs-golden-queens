import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // 상위 디렉토리의 lockfile로 인한 workspace root 오추론을 막고 이 폴더로 고정한다.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
