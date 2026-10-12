import { useEffect, useRef } from "react";

export interface ContextMenuItem {
  label: string;
  onClick: () => void;
  danger?: boolean;
  disabled?: boolean;
}

export interface ContextMenuSection {
  title?: string;
  items: ContextMenuItem[];
}

interface RowContextMenuProps {
  position: { x: number; y: number } | null;
  sections: ContextMenuSection[];
  onClose: () => void;
}

export default function RowContextMenu({ position, sections, onClose }: RowContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!position) return;
    const onDocClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [position, onClose]);

  if (!position) return null;

  return (
    <div
      ref={ref}
      className="row-context-menu"
      style={{ position: "fixed", top: position.y, left: position.x, zIndex: 1000 }}
    >
      {sections.map((section, i) => (
        <div key={i} className="row-context-menu-section">
          {section.title && <div className="row-context-menu-title">{section.title}</div>}
          {section.items.map((item) => (
            <button
              key={item.label}
              className={item.danger ? "danger" : undefined}
              disabled={item.disabled}
              onClick={() => {
                item.onClick();
                onClose();
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}
