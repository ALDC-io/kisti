"use client";

import { useState, useEffect } from "react";
import { DriverDisplayState } from "@/lib/driverTelemetry";
import DriverStatusBar from "./DriverStatusBar";
import DriverSoftkeyBar, { DriverMode } from "./DriverSoftkeyBar";
import StreetMode from "./StreetMode";
import TrackMode from "./TrackMode";
import VideoMode from "./VideoMode";
import LogMode from "./LogMode";
import SettingsMode from "./SettingsMode";

interface DriverDisplayProps {
  state: DriverDisplayState;
}

export default function DriverDisplay({ state }: DriverDisplayProps) {
  const [mode, setMode] = useState<DriverMode>("STREET");

  // Keyboard shortcuts (1-5)
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      const modes: DriverMode[] = ["STREET", "TRACK", "VIDEO", "LOG", "SETTINGS"];
      const idx = parseInt(e.key) - 1;
      if (idx >= 0 && idx < modes.length) {
        setMode(modes[idx]);
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  return (
    <div
      className="flex w-full flex-col overflow-hidden rounded-lg"
      style={{
        aspectRatio: "5 / 3",
        backgroundColor: "var(--driver-bg)",
        border: "1px solid var(--driver-chrome-dark)",
        maxHeight: 480,
      }}
      role="region"
      aria-label="Driver gauge cluster display"
    >
      <DriverStatusBar
        mode={mode}
        gpsFixed={true}
        logging={true}
        networkConnected={state.cloudSync.status !== "OFFLINE"}
      />

      <div className="relative flex-1 overflow-hidden">
        {mode === "STREET" && <StreetMode state={state} />}
        {mode === "TRACK" && <TrackMode state={state} />}
        {mode === "VIDEO" && <VideoMode state={state} />}
        {mode === "LOG" && <LogMode />}
        {mode === "SETTINGS" && (
          <SettingsMode
            gpsFixed={true}
            networkConnected={state.cloudSync.status !== "OFFLINE"}
          />
        )}
      </div>

      <DriverSoftkeyBar activeMode={mode} onModeChange={setMode} />
    </div>
  );
}
