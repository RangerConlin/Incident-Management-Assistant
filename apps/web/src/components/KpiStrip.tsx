export interface KpiTileDef {
  key: string;
  value: number | string;
  label: string;
  /** CSS color (e.g. a statusVar .bg, or a literal) for the left accent bar. */
  accent?: string;
}

export default function KpiStrip({ tiles }: { tiles: KpiTileDef[] }) {
  return (
    <div className="kpi-strip">
      {tiles.map((t) => (
        <div
          key={t.key}
          className="kpi-tile"
          style={t.accent ? { borderLeftColor: t.accent } : undefined}
        >
          <div className="kpi-tile-value">{t.value}</div>
          <div className="kpi-tile-label">{t.label}</div>
        </div>
      ))}
    </div>
  );
}
