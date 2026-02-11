"use client";

const HIGHLIGHT = "#E60000";
const GRAY = "#808080";
const CHROME_DARK = "#606060";

export default function LogMode() {
  return (
    <div
      className="flex h-full w-full flex-col items-center justify-center"
      style={{ backgroundColor: "#0A0A0A" }}
    >
      <div
        className="rounded-lg p-6 text-center"
        style={{ border: `1px solid ${CHROME_DARK}` }}
      >
        <h2
          className="text-lg font-bold"
          style={{ color: HIGHLIGHT }}
        >
          LOG
        </h2>
        <p className="mt-2 text-xs" style={{ color: GRAY }}>
          Data logging interface coming soon.
        </p>
        <p className="mt-1 text-[10px]" style={{ color: GRAY }}>
          Will support CAN bus recording, CSV export,
          <br />
          and cloud upload to Zeus.
        </p>
      </div>
    </div>
  );
}
