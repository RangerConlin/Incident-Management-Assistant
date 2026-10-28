import json
import os

class SettingsManager:
    def __init__(self, filename=None):
        if filename is None:
            filename = os.environ.get("SARAPP_SETTINGS_PATH", "settings.json")
        self.filename = filename
        self.settings = {}
        self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    self.settings = json.load(f)
            except UnicodeDecodeError:
                # Backward-compat: migrate legacy cp1252/ANSI files to UTF-8
                with open(self.filename, "r", encoding="cp1252", errors="strict") as f:
                    self.settings = json.load(f)
                # write back normalized UTF-8
                with open(self.filename, "w", encoding="utf-8") as f:
                    json.dump(self.settings, f, indent=4, ensure_ascii=False)
            except json.JSONDecodeError:
                backup_path = f"{self.filename}.corrupt"
                try:
                    os.replace(self.filename, backup_path)
                    print(
                        f"Warning: Failed to decode JSON from {self.filename}. "
                        f"Saved the unreadable file to {backup_path} and resetting settings."
                    )
                except OSError as exc:
                    print(
                        f"Warning: Failed to decode JSON from {self.filename} "
                        f"and could not back it up ({exc}). Resetting settings."
                    )
                self.settings = {}
                self.save()
        else:
            self.settings = {}
            self.save()

    def save(self):
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=4, ensure_ascii=False)

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save()
