from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE_LOGO = ROOT / "assets" / "branding" / "arc_horizon_icon.png"
ANDROID_RES = ROOT / "android" / "app" / "src" / "main" / "res"
IOS_APP_ICON = ROOT / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset"
WINDOWS_RES = ROOT / "windows" / "runner" / "resources"
WEB = ROOT / "web"
CANVAS_BG = "#17324D"


def fitted_logo(size: int, *, inset: float = 0.08, round_icon: bool = False) -> Image.Image:
    if not SOURCE_LOGO.exists():
        raise FileNotFoundError(f"Missing source logo: {SOURCE_LOGO}")

    source = Image.open(SOURCE_LOGO).convert("RGBA")
    source.thumbnail((int(size * (1 - inset)), int(size * (1 - inset))), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (size, size), CANVAS_BG)
    x = (size - source.width) // 2
    y = (size - source.height) // 2
    canvas.alpha_composite(source, (x, y))

    if round_icon:
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
        rounded = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        rounded.paste(canvas, (0, 0), mask)
        return rounded

    return canvas


def save_android_icons() -> None:
    densities = {
        "mipmap-mdpi": 48,
        "mipmap-hdpi": 72,
        "mipmap-xhdpi": 96,
        "mipmap-xxhdpi": 144,
        "mipmap-xxxhdpi": 192,
    }
    for folder, size in densities.items():
        target_dir = ANDROID_RES / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        fitted_logo(size, inset=0.0).save(target_dir / "ic_launcher.png")
        fitted_logo(size, inset=0.08, round_icon=True).save(target_dir / "ic_launcher_round.png")


def save_web_icons() -> None:
    icons_dir = WEB / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)
    fitted_logo(32, inset=0.0).save(WEB / "favicon.png")
    fitted_logo(192, inset=0.0).save(icons_dir / "Icon-192.png")
    fitted_logo(512, inset=0.0).save(icons_dir / "Icon-512.png")
    fitted_logo(192, inset=0.08).save(icons_dir / "Icon-maskable-192.png")
    fitted_logo(512, inset=0.08).save(icons_dir / "Icon-maskable-512.png")


def save_ios_icons() -> None:
    sizes = {
        "Icon-App-20x20@1x.png": 20,
        "Icon-App-20x20@2x.png": 40,
        "Icon-App-20x20@3x.png": 60,
        "Icon-App-29x29@1x.png": 29,
        "Icon-App-29x29@2x.png": 58,
        "Icon-App-29x29@3x.png": 87,
        "Icon-App-40x40@1x.png": 40,
        "Icon-App-40x40@2x.png": 80,
        "Icon-App-40x40@3x.png": 120,
        "Icon-App-60x60@2x.png": 120,
        "Icon-App-60x60@3x.png": 180,
        "Icon-App-76x76@1x.png": 76,
        "Icon-App-76x76@2x.png": 152,
        "Icon-App-83.5x83.5@2x.png": 167,
        "Icon-App-1024x1024@1x.png": 1024,
    }
    for filename, size in sizes.items():
        fitted_logo(size, inset=0.0).convert("RGB").save(IOS_APP_ICON / filename)


def save_windows_icon() -> None:
    WINDOWS_RES.mkdir(parents=True, exist_ok=True)
    fitted_logo(256, inset=0.0).save(
        WINDOWS_RES / "app_icon.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


if __name__ == "__main__":
    save_android_icons()
    save_web_icons()
    save_ios_icons()
    save_windows_icon()
