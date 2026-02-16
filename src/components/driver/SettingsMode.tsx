"use client";

const HIGHLIGHT = "#E60000";
const WHITE = "#FFFFFF";
const SILVER = "#D0D0D0";
const GRAY = "#808080";
const GREEN = "#00CC66";
const RED = "#FF1A1A";
const BG_PANEL = "#121212";
const CHROME_DARK = "#606060";

interface SettingsModeProps {
  gpsFixed: boolean;
  networkConnected: boolean;
}

export default function SettingsMode({ gpsFixed, networkConnected }: SettingsModeProps) {
  return (
    <div className="flex h-full w-full gap-3 p-3" style={{ backgroundColor: "#0A0A0A" }}>
      {/* Left: Branding column */}
      <div className="flex flex-1 flex-col items-center justify-center gap-3">
        <h2
          className="text-2xl font-black"
          style={{ color: HIGHLIGHT }}
        >
          KiSTI
        </h2>
        <p className="text-center text-[10px] leading-tight" style={{ color: SILVER }}>
          Knight Industries STI
        </p>

        <div className="my-1" />

        <img
          src="/assets/jetson_orin_logo.svg"
          alt="NVIDIA Jetson Orin"
          className="h-8"
          draggable={false}
        />
        <p className="text-[9px]" style={{ color: GRAY }}>
          Powered by NVIDIA Jetson Orin
        </p>

        <div className="my-1" />

        <img
          src="/assets/link_logo.svg"
          alt="Link Engine Management"
          className="h-6"
          draggable={false}
        />
        <p className="text-[9px]" style={{ color: GRAY }}>
          Link Engine Management
        </p>

        <div className="flex-1" />

        <p className="text-[9px]" style={{ color: GRAY }}>
          v0.3.0-web
        </p>
      </div>

      {/* Right: System diagnostics */}
      <div className="flex flex-1 flex-col gap-2">
        <h3
          className="text-xs font-bold"
          style={{ color: HIGHLIGHT, borderBottom: `1px solid ${CHROME_DARK}`, paddingBottom: 4 }}
        >
          SYSTEM
        </h3>

        <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-[10px]">
          <span style={{ color: GRAY }}>Platform</span>
          <span style={{ color: WHITE }}>Jetson Orin (ARM64)</span>

          <span style={{ color: GRAY }}>Display</span>
          <span style={{ color: WHITE }}>Kenwood Excelon 800x480</span>

          <span style={{ color: GRAY }}>ECU</span>
          <span style={{ color: WHITE }}>Link G4X (CAN 500kbps)</span>

          <span style={{ color: GRAY }}>Cameras</span>
          <span style={{ color: WHITE }}>4 feeds (IR/RGB/LiDAR/WX)</span>

          <span style={{ color: GRAY }}>Cloud</span>
          <span style={{ color: WHITE }}>Zeus</span>
        </div>

        <h3
          className="mt-2 text-xs font-bold"
          style={{ color: HIGHLIGHT, borderBottom: `1px solid ${CHROME_DARK}`, paddingBottom: 4 }}
        >
          STATUS
        </h3>

        <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-[10px]">
          <span style={{ color: GRAY }}>GPS</span>
          <span style={{ color: gpsFixed ? GREEN : RED }}>
            {gpsFixed ? "● Fix acquired" : "● No fix"}
          </span>

          <span style={{ color: GRAY }}>Network</span>
          <span style={{ color: networkConnected ? GREEN : RED }}>
            {networkConnected ? "● Connected" : "● Disconnected"}
          </span>

          <span style={{ color: GRAY }}>Storage</span>
          <span style={{ color: GREEN }}>● 128GB NVMe (43% used)</span>

          <span style={{ color: GRAY }}>Temp</span>
          <span style={{ color: GREEN }}>● 62°C (Jetson SoC)</span>
        </div>

        <div className="flex-1" />

        <div className="flex items-center gap-2">
          <img
            src="/assets/boost_barn_logo.png"
            alt="Boost Barn"
            className="h-4"
            draggable={false}
          />
          <span className="text-[9px]" style={{ color: GRAY }}>
            Built by Boost Barn
          </span>
        </div>
      </div>
    </div>
  );
}
