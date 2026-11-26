import { useEffect, useState, type ReactNode } from "react";

/** Wall clock that re-renders every 30 s so "starts in" and overdue flags stay honest. */
export function useNow(intervalMs = 30_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(t);
  }, [intervalMs]);
  return now;
}

export function ErrorNote({ message }: { message: string | null }) {
  return message ? <p className="error" role="alert">{message}</p> : null;
}

export function Field({ label, children, wide, htmlFor }: { label: string; children: ReactNode; wide?: boolean; htmlFor?: string }) {
  return <div className={"field" + (wide ? " pe-wide" : "")}><label htmlFor={htmlFor}>{label}</label>{children}</div>;
}

export function Definition({ rows }: { rows: [string, ReactNode][] }) {
  return <dl className="pe-defs">{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>;
}
