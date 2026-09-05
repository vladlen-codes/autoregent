import type { NextConfig } from "next";

// GitHub Pages serves this repo at https://<user>.github.io/autoregent/, a
// sub-path, not the domain root -- basePath/assetPrefix must reflect that.
// Only applied in CI (GITHUB_ACTIONS=true) so `next dev`/local `next build`
// still work at the root path.
const isGithubActions = process.env.GITHUB_ACTIONS === "true";
const repoName = "autoregent";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  basePath: isGithubActions ? `/${repoName}` : "",
  assetPrefix: isGithubActions ? `/${repoName}/` : "",
};

export default nextConfig;
