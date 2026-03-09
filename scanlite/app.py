"""Scanlite GUI: tkinter-based document scanner interface."""

from __future__ import annotations

import platform
import shutil
import subprocess
import threading
import tkinter as tk
import webbrowser
from collections.abc import Callable
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageTk

from scanlite.pdf_io import export_pdf, load_file
from scanlite.processing import auto_crop, auto_perspective, enhance_scan

# Thumbnail size in pixels
THUMB_W, THUMB_H = 140, 200
PREVIEW_MAX = 800


class PageItem:
    """One page in the document."""

    __slots__ = ("original", "processed", "thumb_photo")

    def __init__(self, img: np.ndarray) -> None:
        self.original = img
        self.processed = img.copy()
        self.thumb_photo: ImageTk.PhotoImage | None = None

    def make_thumbnail(self) -> ImageTk.PhotoImage:
        rgb = cv2.cvtColor(self.processed, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        pil.thumbnail((THUMB_W, THUMB_H), Image.LANCZOS)
        self.thumb_photo = ImageTk.PhotoImage(pil)
        return self.thumb_photo

    def make_preview(self, max_dim: int = PREVIEW_MAX) -> ImageTk.PhotoImage:
        rgb = cv2.cvtColor(self.processed, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        pil.thumbnail((max_dim, max_dim), Image.LANCZOS)
        return ImageTk.PhotoImage(pil)


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Scanlite")
        self.root.geometry("1100x700")
        self.root.minsize(800, 500)

        self.pages: list[PageItem] = []
        self.selected: int = -1
        self._preview_photo: ImageTk.PhotoImage | None = None  # prevent GC

        self._build_ui()
        self._bind_keys()
        self._bind_dnd()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Top toolbar
        toolbar = ttk.Frame(self.root, padding=4)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(toolbar, text="Import Files", command=self._import).pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        ttk.Button(toolbar, text="Auto Crop All", command=self._crop_all).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(toolbar, text="Auto Perspective All", command=self._perspective_all).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(toolbar, text="Enhance All", command=self._enhance_all).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(toolbar, text="Reset Selected", command=self._reset_selected).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(toolbar, text="Remove Selected", command=self._remove_selected).pack(
            side=tk.LEFT, padx=2
        )

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        ttk.Label(toolbar, text="DPI:").pack(side=tk.LEFT, padx=(2, 0))
        self._export_dpi = tk.IntVar(value=150)
        dpi_spin = ttk.Spinbox(
            toolbar, from_=72, to=600, increment=10, width=5,
            textvariable=self._export_dpi,
        )
        dpi_spin.pack(side=tk.LEFT, padx=2)

        ttk.Label(toolbar, text="Quality:").pack(side=tk.LEFT, padx=(4, 0))
        self._export_quality = tk.IntVar(value=85)
        qual_spin = ttk.Spinbox(
            toolbar, from_=10, to=100, increment=5, width=4,
            textvariable=self._export_quality,
        )
        qual_spin.pack(side=tk.LEFT, padx=2)

        ttk.Button(toolbar, text="Export PDF", command=self._export).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Export PDF + OCR", command=self._export_ocr).pack(
            side=tk.LEFT, padx=2
        )

        # Show "Install Tesseract" if not found
        if not shutil.which("tesseract"):
            ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
            ttk.Button(
                toolbar, text="Install Tesseract", command=self._install_tesseract
            ).pack(side=tk.LEFT, padx=2)

        # Per-page controls
        page_bar = ttk.Frame(self.root, padding=4)
        page_bar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(page_bar, text="Crop", command=self._crop_sel).pack(side=tk.LEFT, padx=2)
        ttk.Button(page_bar, text="Perspective", command=self._persp_sel).pack(
            side=tk.LEFT, padx=2
        )

        ttk.Label(page_bar, text="Enhance:").pack(side=tk.LEFT, padx=(10, 2))
        self._enhance_mode = tk.StringVar(value="auto")
        for mode in ("auto", "bw", "gray"):
            ttk.Radiobutton(
                page_bar, text=mode, variable=self._enhance_mode, value=mode
            ).pack(side=tk.LEFT)
        ttk.Button(page_bar, text="Apply", command=self._enhance_sel).pack(side=tk.LEFT, padx=4)

        ttk.Separator(page_bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Button(page_bar, text="Move Up", command=self._move_up).pack(side=tk.LEFT, padx=2)
        ttk.Button(page_bar, text="Move Down", command=self._move_down).pack(side=tk.LEFT, padx=2)

        # Main area: thumbnail list (left) + preview (right)
        main = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True)

        # Thumbnail panel with scrollbar
        thumb_frame = ttk.Frame(main, width=180)
        self.thumb_canvas = tk.Canvas(
            thumb_frame, width=160, bg="#1c1c1c", highlightthickness=0
        )
        thumb_scroll = ttk.Scrollbar(
            thumb_frame, orient=tk.VERTICAL, command=self.thumb_canvas.yview
        )
        self.thumb_canvas.configure(yscrollcommand=thumb_scroll.set)

        thumb_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.thumb_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.thumb_inner = ttk.Frame(self.thumb_canvas)
        self.thumb_canvas.create_window((0, 0), window=self.thumb_inner, anchor=tk.NW)
        self.thumb_inner.bind("<Configure>", self._on_thumb_configure)

        main.add(thumb_frame, weight=0)

        # Preview panel
        preview_frame = ttk.Frame(main)
        self.preview_label = ttk.Label(preview_frame, anchor=tk.CENTER)
        self.preview_label.pack(fill=tk.BOTH, expand=True)
        main.add(preview_frame, weight=1)

        # Status bar
        self.status_var = tk.StringVar(value="Import PDF or image files to get started.")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, padding=2).pack(
            side=tk.BOTTOM, fill=tk.X
        )

    # ------------------------------------------------------------------
    # Keyboard shortcuts and scrolling
    # ------------------------------------------------------------------

    def _bind_keys(self) -> None:
        self.root.bind("<Up>", lambda _: self._select_relative(-1))
        self.root.bind("<Down>", lambda _: self._select_relative(1))
        self.root.bind("<Delete>", lambda _: self._remove_selected())
        self.root.bind("<Control-o>", lambda _: self._import())
        self.root.bind("<Control-s>", lambda _: self._export())
        self.root.bind("<Control-Shift-S>", lambda _: self._export_ocr())

        # Cross-platform mousewheel scrolling
        system = platform.system()
        if system == "Linux":
            self.thumb_canvas.bind_all("<Button-4>", lambda _: self._scroll_thumbs(-3))
            self.thumb_canvas.bind_all("<Button-5>", lambda _: self._scroll_thumbs(3))
        else:
            # Windows and macOS both use <MouseWheel>, but delta differs
            self.thumb_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _scroll_thumbs(self, units: int) -> None:
        self.thumb_canvas.yview_scroll(units, "units")

    def _on_mousewheel(self, event: tk.Event) -> None:
        if platform.system() == "Darwin":
            # macOS: delta is already in the right direction, small integers
            self.thumb_canvas.yview_scroll(-event.delta, "units")
        else:
            # Windows: delta is multiples of 120
            self.thumb_canvas.yview_scroll(-event.delta // 120, "units")

    def _select_relative(self, offset: int) -> None:
        if not self.pages:
            return
        new = max(0, min(len(self.pages) - 1, self.selected + offset))
        if new != self.selected:
            self._select(new)

    # ------------------------------------------------------------------
    # Drag-and-drop file import (tkdnd or fallback)
    # ------------------------------------------------------------------

    def _bind_dnd(self) -> None:
        """Enable drag-and-drop if tkdnd is available (bundled on many systems)."""
        try:
            self.root.tk.eval("package require tkdnd")
            # Register the root window as a drop target
            self.root.tk.eval(
                f'tkdnd::drop_target register {self.root._w} *'
            )
            self.root.tk.eval(
                f'bind {self.root._w} <<Drop>> [list _scanlite_drop %D]'
            )
            # Create the Tcl command that handles the drop
            self.root.createcommand("_scanlite_drop", self._handle_drop)
        except tk.TclError:
            # tkdnd not available; drag-and-drop silently disabled
            pass

    def _handle_drop(self, data: str) -> None:
        """Handle files dropped onto the window."""
        # tkdnd delivers space-separated paths; braces around paths with spaces
        paths: list[str] = []
        raw = data.strip()
        i = 0
        while i < len(raw):
            if raw[i] == "{":
                end = raw.index("}", i)
                paths.append(raw[i + 1 : end])
                i = end + 2
            elif raw[i] == " ":
                i += 1
            else:
                end = raw.find(" ", i)
                if end == -1:
                    end = len(raw)
                paths.append(raw[i:end])
                i = end + 1

        count_before = len(self.pages)
        for p in paths:
            try:
                imgs = load_file(p)
                for img in imgs:
                    self.pages.append(PageItem(img))
            except Exception:
                pass  # silently skip unsupported files in a drop

        added = len(self.pages) - count_before
        if added > 0:
            if self.selected < 0:
                self.selected = 0
            self.status_var.set(f"Dropped {added} page(s).")
            self._refresh_thumbs()
            self._show_preview()

    # ------------------------------------------------------------------
    # Thumbnail panel
    # ------------------------------------------------------------------

    def _on_thumb_configure(self, _event: tk.Event) -> None:
        self.thumb_canvas.configure(scrollregion=self.thumb_canvas.bbox("all"))

    def _refresh_thumbs(self) -> None:
        for w in self.thumb_inner.winfo_children():
            w.destroy()

        for i, page in enumerate(self.pages):
            photo = page.make_thumbnail()
            lbl = tk.Label(
                self.thumb_inner,
                image=photo,
                bg="#4a90d9" if i == self.selected else "#1c1c1c",
                padx=4,
                pady=4,
                cursor="hand2",
            )
            lbl.image = photo  # prevent GC
            lbl.pack(pady=2)
            lbl.bind("<Button-1>", lambda e, idx=i: self._select(idx))

        self.thumb_inner.update_idletasks()
        self.thumb_canvas.configure(scrollregion=self.thumb_canvas.bbox("all"))

    def _select(self, idx: int) -> None:
        self.selected = idx
        self._refresh_thumbs()
        self._show_preview()

    def _show_preview(self) -> None:
        if 0 <= self.selected < len(self.pages):
            page = self.pages[self.selected]
            self._preview_photo = page.make_preview()
            self.preview_label.configure(image=self._preview_photo)
            h, w = page.processed.shape[:2]
            self.status_var.set(
                f"Page {self.selected + 1}/{len(self.pages)}  |  {w}x{h} px"
            )
        else:
            self.preview_label.configure(image="")
            self.status_var.set(f"{len(self.pages)} pages loaded.")

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def _import(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select files",
            filetypes=[
                ("Supported files", "*.pdf *.png *.jpg *.jpeg *.tif *.tiff *.bmp *.webp"),
                ("PDF", "*.pdf"),
                ("Images", "*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.webp"),
            ],
        )
        if not paths:
            return

        count_before = len(self.pages)
        for p in paths:
            try:
                imgs = load_file(p)
                for img in imgs:
                    self.pages.append(PageItem(img))
            except Exception as exc:
                messagebox.showwarning("Import error", f"Could not load {p}:\n{exc}")

        added = len(self.pages) - count_before
        self.status_var.set(f"Imported {added} page(s) from {len(paths)} file(s).")
        if self.selected < 0 and self.pages:
            self.selected = 0
        self._refresh_thumbs()
        self._show_preview()

    # ------------------------------------------------------------------
    # Processing (batch)
    # ------------------------------------------------------------------

    def _run_batch(self, fn: Callable[[NDArray], NDArray], label: str) -> None:
        """Apply a processing function to all pages in a background thread."""
        if not self.pages:
            return
        self.status_var.set(f"{label}...")
        self.root.update_idletasks()

        def worker() -> None:
            for page in self.pages:
                page.processed = fn(page.processed)
            self.root.after(0, self._after_batch, label)

        threading.Thread(target=worker, daemon=True).start()

    def _after_batch(self, label: str) -> None:
        self._refresh_thumbs()
        self._show_preview()
        self.status_var.set(f"{label} done.")

    def _crop_all(self) -> None:
        self._run_batch(auto_crop, "Auto-cropping all pages")

    def _perspective_all(self) -> None:
        self._run_batch(auto_perspective, "Perspective-correcting all pages")

    def _enhance_all(self) -> None:
        mode = self._enhance_mode.get()
        self._run_batch(lambda img: enhance_scan(img, mode=mode), "Enhancing all pages")

    # ------------------------------------------------------------------
    # Processing (single page)
    # ------------------------------------------------------------------

    def _get_selected(self) -> PageItem | None:
        if 0 <= self.selected < len(self.pages):
            return self.pages[self.selected]
        return None

    def _crop_sel(self) -> None:
        p = self._get_selected()
        if p:
            p.processed = auto_crop(p.processed)
            self._refresh_thumbs()
            self._show_preview()

    def _persp_sel(self) -> None:
        p = self._get_selected()
        if p:
            p.processed = auto_perspective(p.processed)
            self._refresh_thumbs()
            self._show_preview()

    def _enhance_sel(self) -> None:
        p = self._get_selected()
        if p:
            p.processed = enhance_scan(p.processed, mode=self._enhance_mode.get())
            self._refresh_thumbs()
            self._show_preview()

    def _reset_selected(self) -> None:
        p = self._get_selected()
        if p:
            p.processed = p.original.copy()
            self._refresh_thumbs()
            self._show_preview()

    def _remove_selected(self) -> None:
        if 0 <= self.selected < len(self.pages):
            self.pages.pop(self.selected)
            if self.selected >= len(self.pages):
                self.selected = len(self.pages) - 1
            self._refresh_thumbs()
            self._show_preview()

    # ------------------------------------------------------------------
    # Reorder
    # ------------------------------------------------------------------

    def _move_up(self) -> None:
        if self.selected > 0:
            self.pages[self.selected], self.pages[self.selected - 1] = (
                self.pages[self.selected - 1],
                self.pages[self.selected],
            )
            self.selected -= 1
            self._refresh_thumbs()
            self._show_preview()

    def _move_down(self) -> None:
        if 0 <= self.selected < len(self.pages) - 1:
            self.pages[self.selected], self.pages[self.selected + 1] = (
                self.pages[self.selected + 1],
                self.pages[self.selected],
            )
            self.selected += 1
            self._refresh_thumbs()
            self._show_preview()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _do_export(self, ocr: bool) -> None:
        if not self.pages:
            messagebox.showinfo("Nothing to export", "Import some files first.")
            return

        path = filedialog.asksaveasfilename(
            title="Save PDF",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        if not path:
            return

        dpi = self._export_dpi.get()
        quality = self._export_quality.get()
        label = "Exporting with OCR" if ocr else "Exporting"
        self.status_var.set(f"{label} ({dpi} DPI, quality {quality})...")
        self.root.update_idletasks()

        def worker() -> None:
            try:
                imgs = [p.processed for p in self.pages]
                export_pdf(imgs, path, ocr=ocr, dpi=dpi, jpeg_quality=quality)
                self.root.after(0, lambda: self.status_var.set(f"Saved: {path}"))
            except Exception as exc:
                self.root.after(
                    0, lambda: messagebox.showerror("Export error", str(exc))
                )

        threading.Thread(target=worker, daemon=True).start()

    def _export(self) -> None:
        self._do_export(ocr=False)

    def _export_ocr(self) -> None:
        self._do_export(ocr=True)

    # ------------------------------------------------------------------
    # Tesseract install helper
    # ------------------------------------------------------------------

    def _install_tesseract(self) -> None:
        """Guide the user to install Tesseract for their platform."""
        system = platform.system()
        if system == "Windows":
            # Try winget first; fall back to download page
            try:
                subprocess.Popen(
                    ["winget", "install", "UB-Mannheim.TesseractOCR"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
                self.status_var.set("Installing Tesseract via winget (check the new window)...")
                return
            except FileNotFoundError:
                webbrowser.open(
                    "https://github.com/UB-Mannheim/tesseract/wiki"
                )
                self.status_var.set("Opened Tesseract download page in browser.")
        elif system == "Darwin":
            for cmd, msg in [
                (["brew", "install", "tesseract"], "Homebrew"),
                (["port", "install", "tesseract"], "MacPorts"),
                (["conda", "install", "-y", "-c", "conda-forge", "tesseract"], "conda"),
            ]:
                if shutil.which(cmd[0]):
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.status_var.set(f"Installing Tesseract via {msg}...")
                    return
            webbrowser.open(
                "https://tesseract-ocr.github.io/tessdoc/Installation.html"
            )
            self.status_var.set("Opened Tesseract install guide in browser.")
        else:
            # Linux: try apt, then dnf, then browser
            for cmd in (["sudo", "apt", "install", "-y", "tesseract-ocr"],
                        ["sudo", "dnf", "install", "-y", "tesseract"]):
                if shutil.which(cmd[1]):
                    try:
                        subprocess.Popen(cmd)
                        self.status_var.set(f"Installing Tesseract via {cmd[1]}...")
                        return
                    except Exception:
                        pass
            webbrowser.open("https://github.com/tesseract-ocr/tesseract")
            self.status_var.set("Opened Tesseract page in browser.")


def _apply_theme(root: tk.Tk) -> None:
    """Apply Sun Valley dark theme if available, otherwise fall back to clam."""
    try:
        import sv_ttk

        sv_ttk.set_theme("dark")
        return
    except ImportError:
        pass
    # Fallback: clam is the best built-in ttk theme
    style = ttk.Style(root)
    available = style.theme_names()
    theme = "clam" if "clam" in available else available[0]
    style.theme_use(theme)
    # Dark-ish colors for clam fallback
    style.configure(".", background="#1e1e1e", foreground="#d4d4d4")
    style.configure("TButton", padding=4)
    style.configure("TLabel", background="#1e1e1e", foreground="#d4d4d4")
    style.configure("TFrame", background="#1e1e1e")
    root.configure(bg="#1e1e1e")


def main() -> None:
    root = tk.Tk()
    _apply_theme(root)
    App(root)
    root.mainloop()
