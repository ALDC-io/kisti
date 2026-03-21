/**
 * Zeus Voice Configuration — Available TTS voices.
 *
 * Piper voices (server-side, high quality):
 *   Require a TTS endpoint that accepts { text, rate, voice } and
 *   returns audio. Voice ID maps to Piper model files on the server.
 *
 * Browser voices (client-side, fallback):
 *   Uses Web Speech API — available voices vary by browser/OS.
 */

export interface VoiceOption {
  id: string;
  name: string;
  description: string;
  gender: "female" | "male";
  accent: string;
  engine: "piper" | "browser";
  /** Piper model filename (without path) */
  piperModel?: string;
  /** Browser voice name hint (matched against speechSynthesis.getVoices()) */
  browserVoiceHint?: string;
}

export const VOICES: VoiceOption[] = [
  // Piper voices (server-side)
  {
    id: "alba",
    name: "Alba",
    description: "Refined British female",
    gender: "female",
    accent: "British",
    engine: "piper",
    piperModel: "en_GB-alba-medium.onnx",
  },
  {
    id: "amy",
    name: "Amy",
    description: "Clear American female",
    gender: "female",
    accent: "American",
    engine: "piper",
    piperModel: "en_US-amy-medium.onnx",
  },
  {
    id: "lessac",
    name: "Lessac",
    description: "Professional American male",
    gender: "male",
    accent: "American",
    engine: "piper",
    piperModel: "en_US-lessac-medium.onnx",
  },
  // Browser fallback voices
  {
    id: "browser-female",
    name: "System Female",
    description: "Browser default female voice",
    gender: "female",
    accent: "System",
    engine: "browser",
    browserVoiceHint: "female",
  },
  {
    id: "browser-male",
    name: "System Male",
    description: "Browser default male voice",
    gender: "male",
    accent: "System",
    engine: "browser",
    browserVoiceHint: "male",
  },
];

export const DEFAULT_VOICE_ID = "alba";

/**
 * Find the best matching browser SpeechSynthesis voice.
 */
export function findBrowserVoice(hint: string): SpeechSynthesisVoice | null {
  const voices = speechSynthesis.getVoices();
  if (!voices.length) return null;

  const lower = hint.toLowerCase();

  // Try exact name match first
  const exact = voices.find((v) => v.name.toLowerCase().includes(lower));
  if (exact) return exact;

  // Try gender-based match
  if (lower === "female") {
    return (
      voices.find((v) => /female|samantha|victoria|karen|moira|fiona/i.test(v.name)) ||
      voices.find((v) => v.lang.startsWith("en")) ||
      voices[0]
    );
  }
  if (lower === "male") {
    return (
      voices.find((v) => /male|daniel|alex|thomas|james/i.test(v.name)) ||
      voices.find((v) => v.lang.startsWith("en")) ||
      voices[0]
    );
  }

  // Fallback: first English voice
  return voices.find((v) => v.lang.startsWith("en")) || voices[0];
}

/**
 * Get available voices (filters to only voices the current environment supports).
 */
export function getAvailableVoices(hasPiperServer: boolean): VoiceOption[] {
  if (hasPiperServer) {
    return VOICES; // All voices available
  }
  // No Piper — browser voices only
  return VOICES.filter((v) => v.engine === "browser");
}
