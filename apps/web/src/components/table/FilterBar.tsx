import type { ReactNode } from "react";

interface ActiveFilterChip {
  key: string;
  label: string;
}

interface FilterBarProps {
  search: string;
  onSearchChange: (value: string) => void;
  activeFilters: ActiveFilterChip[];
  onClearFilter: (key: string) => void;
  onResetAll: () => void;
  children?: ReactNode;
}

export default function FilterBar({
  search,
  onSearchChange,
  activeFilters,
  onClearFilter,
  onResetAll,
  children,
}: FilterBarProps) {
  return (
    <div className="filter-bar">
      <div className="filter-bar-row">
        <input
          type="search"
          placeholder="Search…"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          style={{ maxWidth: 240 }}
        />
        {children}
      </div>
      {activeFilters.length > 0 && (
        <div className="filter-bar-chips">
          {activeFilters.map((f) => (
            <button key={f.key} className="filter-chip" onClick={() => onClearFilter(f.key)}>
              {f.label} ✕
            </button>
          ))}
          <button className="secondary" style={{ width: "auto" }} onClick={onResetAll}>
            Reset filters
          </button>
        </div>
      )}
    </div>
  );
}
