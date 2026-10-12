import { useMemo, useRef, useState, type ReactNode } from "react";
import { useColumnPrefs } from "./useColumnPrefs";

export interface ColumnDef<T> {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
  sortable?: boolean;
  sortValue?: (row: T) => string | number;
  defaultVisible?: boolean;
  defaultWidth?: number;
  minWidth?: number;
}

interface DataTableProps<T> {
  tableId: string;
  columns: ColumnDef<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  onRowActivate?: (row: T) => void;
  onRowContextMenu?: (row: T, e: React.MouseEvent) => void;
  getRowClassName?: (row: T) => string | undefined;
  leadingIcon?: (row: T) => ReactNode;
  emptyMessage?: string;
}

type SortDirection = "asc" | "desc";

export default function DataTable<T>({
  tableId,
  columns,
  rows,
  rowKey,
  onRowActivate,
  onRowContextMenu,
  getRowClassName,
  leadingIcon,
  emptyMessage = "Nothing to show.",
}: DataTableProps<T>) {
  const { isVisible, toggleVisible, widths, setWidth, resetColumns } = useColumnPrefs(tableId, columns);
  const [sort, setSort] = useState<{ key: string; direction: SortDirection } | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | number | null>(null);
  const [showColumnMenu, setShowColumnMenu] = useState(false);
  const resizing = useRef<{ key: string; startX: number; startWidth: number } | null>(null);

  const visibleColumns = columns.filter((c) => isVisible(c.key));

  const sortedRows = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.sortValue) return rows;
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = col.sortValue!(a);
      const bv = col.sortValue!(b);
      const cmp = typeof av === "number" && typeof bv === "number" ? av - bv : String(av).localeCompare(String(bv));
      return sort.direction === "asc" ? cmp : -cmp;
    });
    return copy;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, sort]);

  const onHeaderClick = (col: ColumnDef<T>) => {
    if (!col.sortable) return;
    setSort((prev) => {
      if (prev?.key !== col.key) return { key: col.key, direction: "asc" };
      return { key: col.key, direction: prev.direction === "asc" ? "desc" : "asc" };
    });
  };

  const onResizeStart = (key: string, e: React.MouseEvent) => {
    resizing.current = { key, startX: e.clientX, startWidth: widths[key] ?? 160 };
    const onMove = (ev: MouseEvent) => {
      if (!resizing.current) return;
      const delta = ev.clientX - resizing.current.startX;
      setWidth(resizing.current.key, resizing.current.startWidth + delta);
    };
    const onUp = () => {
      resizing.current = null;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  return (
    <div className="data-table-wrapper">
      <div className="data-table-toolbar">
        <button className="data-table-gear" onClick={() => setShowColumnMenu((v) => !v)} title="Columns">
          ⚙ Columns
        </button>
        {showColumnMenu && (
          <div className="data-table-column-menu">
            {columns.map((col) => (
              <label key={col.key}>
                <input type="checkbox" checked={isVisible(col.key)} onChange={() => toggleVisible(col.key)} />
                {col.header}
              </label>
            ))}
            <button className="secondary" onClick={resetColumns}>
              Reset widths
            </button>
          </div>
        )}
      </div>
      <div className="data-table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              {leadingIcon && <th style={{ width: 32 }} />}
              {visibleColumns.map((col) => (
                <th
                  key={col.key}
                  style={{ width: widths[col.key] ?? col.defaultWidth ?? 160, minWidth: col.minWidth ?? 60 }}
                  onClick={() => onHeaderClick(col)}
                  className={col.sortable ? "sortable" : undefined}
                >
                  {col.header}
                  {sort?.key === col.key && (sort.direction === "asc" ? " ▲" : " ▼")}
                  <span className="col-resize-handle" onMouseDown={(e) => onResizeStart(col.key, e)} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.length === 0 && (
              <tr>
                <td colSpan={visibleColumns.length + (leadingIcon ? 1 : 0)} className="data-table-empty">
                  {emptyMessage}
                </td>
              </tr>
            )}
            {sortedRows.map((row) => {
              const key = rowKey(row);
              const selected = key === selectedKey;
              return (
                <tr
                  key={key}
                  className={[selected ? "selected" : "", getRowClassName?.(row) ?? ""].filter(Boolean).join(" ")}
                  onClick={() => setSelectedKey(key)}
                  onDoubleClick={() => onRowActivate?.(row)}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    setSelectedKey(key);
                    onRowContextMenu?.(row, e);
                  }}
                >
                  {leadingIcon && <td>{leadingIcon(row)}</td>}
                  {visibleColumns.map((col) => (
                    <td key={col.key} style={{ width: widths[col.key] ?? col.defaultWidth ?? 160 }}>
                      {col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key] ?? "")}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
