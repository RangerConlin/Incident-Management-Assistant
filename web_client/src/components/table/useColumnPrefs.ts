import { useCallback, useEffect, useState } from "react";
import type { ColumnDef } from "./DataTable";

interface StoredPrefs {
  visible: string[];
  widths: Record<string, number>;
}

function storageKey(tableId: string): string {
  return `sarapp.table.${tableId}`;
}

function loadPrefs(tableId: string): StoredPrefs | null {
  try {
    const raw = localStorage.getItem(storageKey(tableId));
    return raw ? (JSON.parse(raw) as StoredPrefs) : null;
  } catch {
    return null;
  }
}

function savePrefs(tableId: string, prefs: StoredPrefs): void {
  try {
    localStorage.setItem(storageKey(tableId), JSON.stringify(prefs));
  } catch {
    // best-effort only — table just won't remember prefs across reloads
  }
}

export function useColumnPrefs<T>(tableId: string, columns: ColumnDef<T>[]) {
  const defaults = (): StoredPrefs => ({
    visible: columns.filter((c) => c.defaultVisible !== false).map((c) => c.key),
    widths: Object.fromEntries(columns.map((c) => [c.key, c.defaultWidth ?? 160])),
  });

  const [prefs, setPrefs] = useState<StoredPrefs>(() => loadPrefs(tableId) ?? defaults());

  useEffect(() => {
    savePrefs(tableId, prefs);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefs]);

  const isVisible = useCallback((key: string) => prefs.visible.includes(key), [prefs.visible]);

  const toggleVisible = useCallback((key: string) => {
    setPrefs((p) =>
      p.visible.includes(key)
        ? { ...p, visible: p.visible.filter((k) => k !== key) }
        : { ...p, visible: [...p.visible, key] }
    );
  }, []);

  const setWidth = useCallback((key: string, width: number) => {
    setPrefs((p) => ({ ...p, widths: { ...p.widths, [key]: Math.max(40, width) } }));
  }, []);

  const resetColumns = useCallback(() => setPrefs(defaults()), [columns]);

  return { isVisible, toggleVisible, widths: prefs.widths, setWidth, resetColumns };
}
