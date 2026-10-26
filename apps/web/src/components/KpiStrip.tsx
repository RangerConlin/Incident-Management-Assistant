export interface KpiTileDef {
  key: string;
  value: number | string;
  label: string;
  /** CSS color (e.g. a statusVar .bg, or a literal) for the left accent bar — and, once the count is non-zero, the tile's fill. */
  accent?: string;
}

export default function KpiStrip({ tiles }: { tiles: KpiTileDef[] }) {
  return (
    <div className="kpi-strip">
      {tiles.map((t) => {
        // Zero means nothing to act on — leave it as a quiet outlined tile.
        // Any count above that is worth noticing, so fill the tile solid.
        const filled = !!t.accent && typeof t.value === "number" && t.value > 0;
        return (
          <div
            key={t.key}
            className={"kpi-tile" + (filled ? " kpi-tile-filled" : "")}
            style={
              filled
                ? { background: t.accent, borderLeftColor: t.accent }
                : t.accent
                  ? { borderLeftColor: t.accent }
                  : undefined
            }
          >
            <div className="kpi-tile-value">{t.value}</div>
            <div className="kpi-tile-label">{t.label}</div>
          </div>
        );
      })}
    </div>
  );
}
