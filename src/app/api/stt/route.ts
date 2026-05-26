import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const key = process.env.OPENAI_API_KEY;
  if (!key) {
    return NextResponse.json({ error: "STT not configured" }, { status: 503 });
  }

  const formData = await req.formData();
  const audio = formData.get("audio");
  if (!audio || !(audio instanceof Blob)) {
    return NextResponse.json({ error: "No audio provided" }, { status: 400 });
  }

  const apiForm = new FormData();
  apiForm.append("file", audio, "recording.webm");
  apiForm.append("model", "whisper-1");
  apiForm.append("language", "en");

  const res = await fetch("https://api.openai.com/v1/audio/transcriptions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${key}`,
    },
    body: apiForm,
  });

  if (!res.ok) {
    const err = await res.text();
    return NextResponse.json(
      { error: "STT API error", detail: err },
      { status: res.status }
    );
  }

  const data = await res.json();
  return NextResponse.json({ text: data.text });
}
