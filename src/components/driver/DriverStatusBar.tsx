"use client";

interface DriverStatusBarProps {
  gpsFixed: boolean;
  logging: boolean;
  networkConnected: boolean;
}

export default function DriverStatusBar({
  gpsFixed,
  logging,
  networkConnected,
}: DriverStatusBarProps) {
  const now = new Date();
  const timeStr = now.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  return (
    <div
      className="flex h-10 items-center justify-between px-2"
      style={{
        backgroundColor: "var(--driver-panel)",
        borderBottom: "1px solid var(--driver-chrome-dark)",
      }}
    >
      {/* Left: Link ECU logo */}
      <div className="flex items-center gap-2">
        <img
          src="/assets/link_logo.svg"
          alt="Link ECU"
          className="h-5"
          draggable={false}
        />
      </div>

      {/* Center: clock + status dots */}
      <div className="flex items-center gap-3 text-xs font-bold">
        <span style={{ color: "var(--driver-white)" }}>{timeStr}</span>
        <span style={{ color: gpsFixed ? "var(--driver-green)" : "var(--driver-red-bright)" }}>
          ● GPS
        </span>
        <span style={{ color: logging ? "var(--driver-green)" : "var(--driver-gray)" }}>
          ● LOG
        </span>
        <span style={{ color: networkConnected ? "var(--driver-green)" : "var(--driver-red-bright)" }}>
          ● NET
        </span>
      </div>

      {/* Nvidia logo (right) */}
      <img
        src="/assets/jetson_orin_logo.svg"
        alt="NVIDIA Jetson"
        className="h-5"
        draggable={false}
      />
    </div>
  );
}
