import { NextResponse } from 'next/server';

export async function GET() {
  const devMode = process.env.NEXT_PUBLIC_DEV_MODE === 'true' || process.env.DEV_MODE === 'true';
  
  return NextResponse.json({
    websocket_debug: devMode,
    quick_login: devMode,
    dev_mode: devMode
  });
}
