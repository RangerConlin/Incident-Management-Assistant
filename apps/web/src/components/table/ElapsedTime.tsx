import { useEffect, useState } from "react";

function formatElapsed(ms: number): string {
  if (ms < 0) ms = 0;
  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}

export default function ElapsedTime({ since }: { since: string | null }) {
  const [, setTick] = useState(0);

  useEffect(() => {
    if (!since) return;
    const interval = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(interval);
  }, [since]);

  if (!since) return <span>—</span>;
  const sinceMs = new Date(since).getTime();
  if (Number.isNaN(sinceMs)) return <span>—</span>;
  return <span>{formatElapsed(Date.now() - sinceMs)}</span>;
}
