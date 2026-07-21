/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Transpile the workspace packages consumed as source.
  transpilePackages: ["@ayf/ui", "@ayf/shared", "@ayf/config"],
  output: "standalone",
};

export default nextConfig;
