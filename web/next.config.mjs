/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: ["host.docker.internal"],
  output: "export",
};

export default nextConfig;
