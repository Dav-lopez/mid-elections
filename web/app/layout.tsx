import type { ReactNode } from 'react';
export const metadata = { title: 'CivicPulse | Elections', description: 'Source-aware election information across countries' };
export default function RootLayout({children}:{children:ReactNode}) { return <html lang="en"><body style={{fontFamily:'system-ui',margin:0,background:'#f5f8fc',color:'#14233b'}}>{children}</body></html>; }
