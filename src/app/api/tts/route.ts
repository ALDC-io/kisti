import { NextRequest, NextResponse } from "next/server";

const KISTI_VOICE_INSTRUCTIONS =
  "You are KiSTI, an intelligent vehicle AI. " +
  "Speak with precise enunciation, calm authority, and dry wit. " +
  "Cultured and composed with perfect diction. Protective of the driver. " +
  "Brisk, efficient pacing — not slow, not rushed. Like a sharp motorsport engineer " +
  "on the radio during a session. Clipped consonants, no filler words. " +
  "Speak with a neutral international English accent, not American.";

export async function POST(req: NextRequest) {
  const key = process.env.OPENAI_API_KEY;
  if (!key) {
    return NextResponse.json({ error: "TTS not configured" }, { status: 503 });
  }

  const { text } = await req.json();
  if (!text || typeof text !== "string" || text.length > 4096) {
    return NextResponse.json({ error: "Invalid text" }, { status: 400 });
  }

  // Expand abbreviations for natural speech
  const spoken = text
    .replace(/\bFL\b/g, "Front-Left")
    .replace(/\bFR\b/g, "Front-Right")
    .replace(/\bRL\b/g, "Rear-Left")
    .replace(/\bRR\b/g, "Rear-Right")
    .replace(/\bEGT\b/g, "E.G.T.")
    .replace(/\bAFR\b/g, "air-fuel ratio")
    .replace(/\bPSI\b/g, "P.S.I.")
    .replace(/\bFMIC\b/g, "front-mount intercooler")
    .replace(/\bDCCD\b/g, "D.C.C.D.")
    .replace(/\bAWD\b/g, "all-wheel drive")
    .replace(/\bWHP\b/g, "wheel horsepower")
    .replace(/\bMAF\b/g, "mass airflow sensor")
    .replace(/\bECU\b/g, "E.C.U.")
    .replace(/\bCAN\b/g, "can")
    .replace(/°F/g, " degrees Fahrenheit")
    .replace(/°C/g, " degrees Celsius")
    .replace(/km\/h/g, "kilometers per hour")
    .replace(/\bkm\b/g, "kilometers");

  const res = await fetch("https://api.openai.com/v1/audio/speech", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "gpt-4o-mini-tts",
      voice: "ash",
      input: spoken,
      instructions: KISTI_VOICE_INSTRUCTIONS,
      response_format: "pcm",
      speed: 1.1,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    return NextResponse.json(
      { error: "TTS API error", detail: err },
      { status: res.status }
    );
  }

  // Stream raw PCM (24kHz, 16-bit, mono) to the client for immediate playback
  return new NextResponse(res.body as ReadableStream, {
    headers: {
      "Content-Type": "application/octet-stream",
      "X-Audio-Format": "pcm-24000-16bit-mono",
    },
  });
}
