/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: ["portal.avico78.com"],
  async rewrites() {
    return [
      {
        source: "/api/portal/:path*",
        destination: `${process.env.PORTAL_API_URL}/portal/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
