import { useState } from "react";
import { Link } from "react-router-dom";
import { applyTheme, getStoredTheme, type ThemeName } from "../../styles/statusColors";
import "./workspaces.css";
export default function CustomizationPage() {
  const [theme, setTheme] = useState(getStoredTheme());
  return <section className="workspace-page"><h1>UI Customization</h1><p>Appearance preferences apply to this browser.</p>
    <label className="field">Theme<select value={theme} onChange={e => { const value = e.target.value as ThemeName; applyTheme(value); setTheme(value); }}><option value="dark">Dark</option><option value="light">Light</option></select></label>
    <h2>Table layout</h2><p>Use Columns above each board to choose visible fields and reset widths. Drag column borders to resize. Each board remembers its layout in this browser.</p>
    <Link to="/connection">Connection settings</Link>
  </section>;
}
