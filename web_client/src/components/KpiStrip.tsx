export interface KpiTileDef {
  key: string;
  value: number | string;
  label: string;
  tone?: "default" | "warning" | "danger";
}

export default function KpiStrip({ tiles }: { tiles: KpiTileDef[] }) {
  return (
    <div className="kpi-strip">
      {tiles.map((t) => (
        <div key={t.key} className={"kpi-tile" + (t.tone ? ` kpi-tile-${t.tone}` : "")}>
          <div className="kpi-tile-value">{t.value}</div>
          <div className="kpi-tile-label">{t.label}</div>
        </div>
      ))}
    </div>
  );
}
