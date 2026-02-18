import { NextRequest, NextResponse } from "next/server";

const KISTI_VOICE_INSTRUCTIONS =
  "You are KiSTI, a young female AI co-driver with a subtle Japanese accent. " +
  "Speak clearly and confidently, like a motorsport engineer briefing a driver. " +
  "Keep a calm, professional tone with slight warmth.";

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
      voice: "nova",
      input: text,
      instructions: KISTI_VOICE_INSTRUCTIONS,
      response_format: "mp3",
      speed: 1.05,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    return NextResponse.json(
      { error: "TTS API error", detail: err },
      { status: res.status }
    );
  }

  const audio = await res.arrayBuffer();
  return new NextResponse(audio, {
    headers: {
      "Content-Type": "audio/mpeg",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
