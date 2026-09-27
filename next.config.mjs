const securityHeaders=[
  {key:'X-Content-Type-Options',value:'nosniff'},
  {key:'X-Frame-Options',value:'DENY'},
  {key:'Referrer-Policy',value:'strict-origin-when-cross-origin'},
  {key:'Permissions-Policy',value:'camera=(), geolocation=(), payment=(), microphone=(self)'},
  {key:'Content-Security-Policy',value:"frame-ancestors 'none'; base-uri 'self'; object-src 'none'"},
];

const nextConfig={
  async headers(){
    return [{source:'/:path*',headers:securityHeaders}];
  },
};

export default nextConfig;
