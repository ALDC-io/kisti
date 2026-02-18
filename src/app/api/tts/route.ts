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

  const res = await fetch("https://api.openai.com/v1/audio/speech", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "gpt-4o-mini-tts",
      voice: "ash",
      input: text,
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
