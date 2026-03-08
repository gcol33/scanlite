#!/usr/bin/env python3
"""Build native installers for Scanlite.

Usage:
    python build_installer.py              # bundle exe only (PyInstaller)
    python build_installer.py --msi        # Windows: bundle + .msi via WiX v4
    python build_installer.py --dmg        # macOS:   bundle + .dmg via create-dmg
    python build_installer.py --deb        # Linux:   bundle + .deb via fpm
    python build_installer.py --rpm        # Linux:   bundle + .rpm via fpm
    python build_installer.py --all        # all available for current platform
    python build_installer.py --clean      # remove build artifacts first

Prerequisites:
    pip install pyinstaller

    Windows .msi:
        winget install WiXToolset.WiXToolset   (or: dotnet tool install -g wix)

    macOS .dmg:
        brew install create-dmg

    Linux .deb/.rpm:
        sudo apt install ruby-dev build-essential && sudo gem install fpm
        (for .rpm also: sudo apt install rpm)
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
INSTALLER_DIR = ROOT / "installer"
OUTPUT = ROOT / "Output"

APP_NAME = "Scanlite"
APP_VERSION = "0.1.0"
BUNDLE_DIR = DIST / "scanlite"

# Stable GUID for WiX (regenerate if you fork)
UPGRADE_CODE = "7a3e1f4b-8c2d-4e5a-b6f7-9d0c1e2a3b4c"


# ── Helpers ──────────────────────────────────────────────────────────────

def run(cmd: list[str], **kw) -> None:
    print(f"  $ {' '.join(cmd)}")
    subprocess.check_call(cmd, **kw)


def which(name: str) -> str | None:
    return shutil.which(name)


def app_exe() -> str:
    return "scanlite.exe" if platform.system() == "Windows" else "scanlite"


def clean() -> None:
    for d in (DIST, BUILD, OUTPUT):
        if d.exists():
            shutil.rmtree(d)
            print(f"Removed {d}")
    for spec in ROOT.glob("*.spec"):
        spec.unlink()
        print(f"Removed {spec}")


# ── PyInstaller bundle ───────────────────────────────────────────────────

def bundle() -> Path:
    """Create the PyInstaller bundle. Returns the bundle directory."""
    exe = BUNDLE_DIR / app_exe()
    system = platform.system()

    # On macOS PyInstaller --windowed produces a .app bundle
    if system == "Darwin":
        app_bundle = DIST / f"{APP_NAME}.app"
        if app_bundle.exists():
            print(f"Bundle already exists at {app_bundle}, skipping PyInstaller.")
            return app_bundle
    elif exe.exists():
        print(f"Bundle already exists at {BUNDLE_DIR}, skipping PyInstaller.")
        return BUNDLE_DIR

    sep = ";" if system == "Windows" else ":"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "scanlite" if system != "Darwin" else APP_NAME,
        "--noconfirm",
        "--windowed",
        "--add-data", f"scanlite{sep}scanlite",
        "--hidden-import", "PIL._tkinter_finder",
        "--collect-all", "pytesseract",
        "--collect-all", "sv_ttk",
        str(ROOT / "scanlite" / "__main__.py"),
    ]

    if system == "Windows":
        icon = INSTALLER_DIR / "scanlite.ico"
        if icon.exists():
            cmd.extend(["--icon", str(icon)])
    elif system == "Darwin":
        icon = INSTALLER_DIR / "scanlite.icns"
        if icon.exists():
            cmd.extend(["--icon", str(icon)])
        cmd.extend([
            "--osx-bundle-identifier", "com.gcol33.scanlite",
        ])
    else:
        icon = INSTALLER_DIR / "scanlite.png"
        if icon.exists():
            cmd.extend(["--icon", str(icon)])

    print(f"Building PyInstaller bundle for {system}...")
    run(cmd)

    if system == "Darwin":
        app_bundle = DIST / f"{APP_NAME}.app"
        if not app_bundle.exists():
            print(f"ERROR: expected {app_bundle} not found")
            sys.exit(1)
        print(f"Bundle ready: {app_bundle}")
        return app_bundle

    if not exe.exists():
        print(f"ERROR: expected {exe} not found")
        sys.exit(1)

    size_mb = sum(f.stat().st_size for f in BUNDLE_DIR.rglob("*") if f.is_file()) / 1024 / 1024
    print(f"Bundle ready: {BUNDLE_DIR}  ({size_mb:.0f} MB)")
    return BUNDLE_DIR


# ── Windows .msi via WiX v4 ─────────────────────────────────────────────

def _find_wix() -> str | None:
    for name in ("wix", "wix.exe"):
        p = which(name)
        if p:
            return p
    dotnet_tools = Path.home() / ".dotnet" / "tools"
    wix_path = dotnet_tools / "wix.exe"
    if wix_path.exists():
        return str(wix_path)
    return None


def _generate_wix_file_entries(bundle_dir: Path) -> tuple[str, str]:
    """Walk the bundle dir and produce WiX v4 XML fragments.

    Returns (components_xml, component_refs_xml).
    """
    files: list[Path] = sorted(
        f.relative_to(bundle_dir) for f in bundle_dir.rglob("*") if f.is_file()
    )

    dirs: dict[str, list[Path]] = {}
    for f in files:
        d = str(f.parent).replace("/", "\\")
        if d == ".":
            d = ""
        dirs.setdefault(d, []).append(f)

    comp_lines: list[str] = []
    ref_lines: list[str] = []

    def _safe_id(prefix: str, s: str) -> str:
        """Generate a WiX-safe identifier, hashing if longer than 68 chars.

        WiX identifiers may only contain A-Z, a-z, 0-9, underscore, and period.
        """
        raw = "".join(c if c.isalnum() or c in "_." else "_" for c in s)
        candidate = f"{prefix}_{raw}"
        if len(candidate) <= 68:
            return candidate
        # Hash to keep it short but unique
        h = hashlib.md5(s.encode()).hexdigest()[:16]
        # Keep a readable prefix from the filename
        short = raw[-30:] if len(raw) > 30 else raw
        return f"{prefix}_{short}_{h}"

    # Root-level files
    for f in dirs.get("", []):
        cid = _safe_id("C", f.name)
        src = str(bundle_dir / f).replace("/", "\\")
        comp_lines.append(
            f'      <Component Id="{cid}" Guid="{uuid.uuid4()}">\n'
            f'        <File Source="{src}" />\n'
            f'      </Component>'
        )
        ref_lines.append(f'        <ComponentRef Id="{cid}" />')

    # Subdirectory files
    for d, d_files in sorted(dirs.items()):
        if d == "":
            continue
        parts = d.split("\\")
        indent = "      "
        opens = []
        closes = []
        for i, part in enumerate(parts):
            sub_id = _safe_id("D", "_".join(parts[: i + 1]))
            pad = indent + "  " * i
            opens.append(f'{pad}<Directory Id="{sub_id}" Name="{part}">')
            closes.insert(0, f"{pad}</Directory>")

        comp_lines.append("\n".join(opens))
        deep = indent + "  " * len(parts)
        for f in d_files:
            cid = _safe_id("C", str(f))
            src = str(bundle_dir / f).replace("/", "\\")
            comp_lines.append(
                f'{deep}<Component Id="{cid}" Guid="{uuid.uuid4()}">\n'
                f'{deep}  <File Source="{src}" />\n'
                f'{deep}</Component>'
            )
            ref_lines.append(f'        <ComponentRef Id="{cid}" />')
        comp_lines.append("\n".join(closes))

    return "\n".join(comp_lines), "\n".join(ref_lines)


def build_msi(bundle_dir: Path) -> None:
    wix = _find_wix()
    if not wix:
        print("ERROR: WiX v4 CLI not found.")
        print("  Install: winget install WiXToolset.WiXToolset")
        print("  Or:      dotnet tool install -g wix")
        sys.exit(1)

    print("Generating WiX source...")
    components_xml, comprefs_xml = _generate_wix_file_entries(bundle_dir)

    icon_src = INSTALLER_DIR / "scanlite.ico"
    icon_block = ""
    if icon_src.exists():
        icon_block = (
            f'    <Icon Id="ScanliteIcon" SourceFile="{icon_src}" />\n'
            f'    <Property Id="ARPPRODUCTICON" Value="ScanliteIcon" />'
        )

    wxs = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">
  <Package Name="{APP_NAME}"
           Version="{APP_VERSION}"
           Manufacturer="Gilles Colling"
           UpgradeCode="{UPGRADE_CODE}"
           Compressed="yes">

    <MajorUpgrade DowngradeErrorMessage="A newer version is already installed." />
    <MediaTemplate EmbedCab="yes" />
{icon_block}
    <StandardDirectory Id="ProgramFiles6432Folder">
      <Directory Id="INSTALLFOLDER" Name="{APP_NAME}">
{components_xml}
      </Directory>
    </StandardDirectory>

    <Feature Id="Main" Title="{APP_NAME}" Level="1">
{comprefs_xml}
    </Feature>

    <StandardDirectory Id="ProgramMenuFolder">
      <Component Id="StartMenuShortcut" Guid="{uuid.uuid4()}">
        <Shortcut Id="ScanliteShortcut"
                  Name="{APP_NAME}"
                  Target="[INSTALLFOLDER]scanlite.exe"
                  WorkingDirectory="INSTALLFOLDER" />
        <RegistryValue Root="HKCU" Key="Software\\Scanlite"
                       Name="installed" Type="integer" Value="1"
                       KeyPath="yes" />
        <RemoveFolder Id="RemoveMenuFolder" On="uninstall" />
      </Component>
    </StandardDirectory>

    <Feature Id="Shortcuts" Title="Start Menu Shortcut" Level="1">
      <ComponentRef Id="StartMenuShortcut" />
    </Feature>

  </Package>
</Wix>
"""

    OUTPUT.mkdir(exist_ok=True)
    BUILD.mkdir(exist_ok=True)
    wxs_path = BUILD / "scanlite.wxs"
    wxs_path.write_text(wxs, encoding="utf-8")

    msi_path = OUTPUT / f"Scanlite-{APP_VERSION}.msi"
    print("Compiling .msi ...")
    run([wix, "build", str(wxs_path), "-o", str(msi_path)])

    if msi_path.exists():
        size_mb = msi_path.stat().st_size / 1024 / 1024
        print(f"\nMSI ready: {msi_path}  ({size_mb:.1f} MB)")
    else:
        print("ERROR: MSI was not created.")
        sys.exit(1)


# ── macOS .dmg via create-dmg ────────────────────────────────────────────

def build_dmg(app_bundle: Path) -> None:
    """Build a .dmg from the .app bundle using create-dmg."""
    if not which("create-dmg"):
        print("ERROR: create-dmg not found.")
        print("  Install: brew install create-dmg")
        sys.exit(1)

    OUTPUT.mkdir(exist_ok=True)
    dmg_path = OUTPUT / f"Scanlite-{APP_VERSION}.dmg"

    # Remove stale dmg so create-dmg doesn't fail
    if dmg_path.exists():
        dmg_path.unlink()

    cmd = [
        "create-dmg",
        "--volname", APP_NAME,
        "--window-pos", "200", "120",
        "--window-size", "600", "400",
        "--icon-size", "100",
        "--icon", f"{APP_NAME}.app", "150", "190",
        "--app-drop-link", "450", "190",
        "--no-internet-enable",
        str(dmg_path),
        str(app_bundle),
    ]

    # Optional background image
    bg = INSTALLER_DIR / "dmg_background.png"
    if bg.exists():
        cmd.insert(1, "--background")
        cmd.insert(2, str(bg))

    # Optional volume icon
    volicon = INSTALLER_DIR / "scanlite.icns"
    if volicon.exists():
        cmd.insert(1, "--volicon")
        cmd.insert(2, str(volicon))

    print("Building .dmg ...")
    run(cmd)

    if dmg_path.exists():
        size_mb = dmg_path.stat().st_size / 1024 / 1024
        print(f"\nDMG ready: {dmg_path}  ({size_mb:.1f} MB)")
    else:
        print("ERROR: DMG was not created.")
        sys.exit(1)


# ── Linux .deb / .rpm via fpm ────────────────────────────────────────────

def _build_fpm(bundle_dir: Path, pkg_type: str) -> None:
    if not which("fpm"):
        print("ERROR: fpm not found.")
        print("  Install: sudo gem install fpm")
        sys.exit(1)

    OUTPUT.mkdir(exist_ok=True)
    desktop_src = INSTALLER_DIR / "scanlite.desktop"
    icon_src = INSTALLER_DIR / "scanlite.png"

    pkg_path = OUTPUT / f"scanlite-{APP_VERSION}.{pkg_type}"
    if pkg_path.exists():
        pkg_path.unlink()

    cmd = [
        "fpm",
        "-s", "dir",
        "-t", pkg_type,
        "--name", "scanlite",
        "--version", APP_VERSION,
        "--description", "Document scanner: crop, perspective-correct, enhance, OCR, combine to PDF",
        "--license", "MIT",
        "--maintainer", "Gilles Colling",
        "--url", "https://github.com/gcol33/scanlite",
        "--package", str(pkg_path),
    ]

    # Dependencies must come before path arguments (fpm treats trailing args as paths)
    if pkg_type == "deb":
        for dep in ("libgl1", "libglib2.0-0", "python3-tk", "tesseract-ocr"):
            cmd.extend(["-d", dep])
    elif pkg_type == "rpm":
        for dep in ("mesa-libGL", "glib2", "python3-tkinter", "tesseract"):
            cmd.extend(["-d", dep])

    # Path mappings go last
    cmd.append(f"{bundle_dir}/=/opt/scanlite/")
    if desktop_src.exists():
        cmd.append(f"{desktop_src}=/usr/share/applications/scanlite.desktop")
    if icon_src.exists():
        cmd.append(f"{icon_src}=/usr/share/icons/hicolor/256x256/apps/scanlite.png")

    print(f"Building .{pkg_type} ...")
    run(cmd)

    if pkg_path.exists():
        size_mb = pkg_path.stat().st_size / 1024 / 1024
        install_cmd = "dpkg -i" if pkg_type == "deb" else "rpm -i"
        print(f"\n{pkg_type.upper()} ready: {pkg_path}  ({size_mb:.1f} MB)")
        print(f"  Install: sudo {install_cmd} {pkg_path}")
        print(f"  Run:     /opt/scanlite/scanlite")
    else:
        print(f"ERROR: .{pkg_type} was not created.")
        sys.exit(1)


def build_deb(bundle_dir: Path) -> None:
    _build_fpm(bundle_dir, "deb")


def build_rpm(bundle_dir: Path) -> None:
    _build_fpm(bundle_dir, "rpm")


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    args = set(sys.argv[1:])

    if "--clean" in args:
        clean()
        args.discard("--clean")
        if not args:
            return

    system = platform.system()

    want_msi = "--msi" in args or "--all" in args
    want_dmg = "--dmg" in args or "--all" in args
    want_deb = "--deb" in args or "--all" in args
    want_rpm = "--rpm" in args or "--all" in args
    want_bundle_only = not (want_msi or want_dmg or want_deb or want_rpm)

    bd = bundle()

    if want_bundle_only:
        print("\nBundle created. Use --msi / --dmg / --deb / --rpm to build a native installer.")
        return

    if want_msi:
        if system != "Windows":
            print("SKIP: .msi can only be built on Windows.")
        else:
            build_msi(bd)

    if want_dmg:
        if system != "Darwin":
            print("SKIP: .dmg can only be built on macOS.")
        else:
            build_dmg(bd)

    if want_deb:
        if system != "Linux":
            print("SKIP: .deb can only be built on Linux.")
        else:
            build_deb(bd)

    if want_rpm:
        if system != "Linux":
            print("SKIP: .rpm can only be built on Linux.")
        else:
            build_rpm(bd)


if __name__ == "__main__":
    main()
