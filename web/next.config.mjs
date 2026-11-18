/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: ["host.docker.internal"],
  output: "export",
  trailingSlash: true,
};

export default nextConfig;
