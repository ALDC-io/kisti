/**
 * Zeus Voice Waveform Components
 *
 * Reusable voice visualization for any Zeus Chat implementation.
 *
 * Quick start:
 *   import VoiceWaveform from "@/components/voice/VoiceWaveform";
 *   import { useVoicePlayback } from "@/components/voice/useVoicePlayback";
 *
 *   function ChatWidget() {
 *     const { speak, isPlaying, envelope } = useVoicePlayback({
 *       ttsEndpoint: "/api/tts",
 *     });
 *
 *     return (
 *       <div>
 *         <VoiceWaveform
 *           envelope={envelope}
 *           isPlaying={isPlaying}
 *           palette="rose"        // or "blue", "green", "amber", "custom"
 *           width={240}
 *           height={140}
 *         />
 *         <button onClick={() => speak("Hello from Zeus.")}>Speak</button>
 *         <button onClick={() => speak("Alert detected!", "critical")}>Alert</button>
 *       </div>
 *     );
 *   }
 *
 * Available palettes:
 *   - rose: cherry blossom (KiSTI default)
 *   - blue: cool/corporate
 *   - green: nature/health
 *   - amber: warm/energy
 *   - custom: provide customColors prop
 *
 * Urgency levels affect speech rate:
 *   - normal: 1.1x (composed)
 *   - alert: 0.7x (firm)
 *   - critical: 0.6x (urgent)
 */

export { default as VoiceWaveform } from "./VoiceWaveform";
export { useVoicePlayback } from "./useVoicePlayback";
export type { WaveformPalette } from "./VoiceWaveform";
