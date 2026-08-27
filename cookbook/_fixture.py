"""Render-time sandbox for the cookbook's executable chapters.

Every chapter in this book is executed on each CI run (`_freeze/` is
gitignored), so the recipes really do create directories and write files.
They must not write into the source tree or the reader's home.

`sandbox()` handles that *outside* the recipes: it chdirs the chapter's
kernel into a throwaway copy of `data/`, so the visible code can use the
ordinary relative paths a reader would write -- `data/worklist.csv`,
`experiments/<run_id>/` -- with nothing about the render leaking into the
snippet. The copy is removed when the kernel shuts down, and any sandbox an
earlier render left behind is swept on the next call.

Call it from a hidden cell (`#| include: false`) at the top of a chapter.
Works regardless of the working directory Quarto starts the kernel in: the
hidden cell walks up from the cwd to find this file.
"""

import atexit
import os
import shutil
import tempfile
import time
from pathlib import Path

_BOOK = Path(__file__).resolve().parent

# Sandboxes older than this are swept on the next `sandbox()` call. Quarto can
# leave kernels to be killed rather than shut down, in which case the atexit
# hook below never runs, so the sweep -- not the hook -- is what actually bounds
# accumulation. Comfortably longer than a full render, so a sweep cannot delete
# a sandbox belonging to a render still in progress.
_MAX_AGE_SECONDS = 3600


def _sweep() -> None:
    """Remove sandboxes left behind by earlier renders."""
    now = time.time()
    for old in Path(tempfile.gettempdir()).glob("cookbook_*"):
        try:
            if old.is_dir() and now - old.stat().st_mtime > _MAX_AGE_SECONDS:
                shutil.rmtree(old, ignore_errors=True)
        except OSError:      # vanished, or held open by another process
            pass


def sandbox(name: str) -> Path:
    """Chdir into a throwaway copy of the book's `data/` directory."""
    _sweep()
    tmp = Path(tempfile.mkdtemp(prefix=f"cookbook_{name}_"))
    shutil.copytree(_BOOK / "data", tmp / "data")
    atexit.register(_discard, tmp)
    os.chdir(tmp)
    return tmp


def _discard(tmp: Path) -> None:
    """Drop a sandbox at kernel shutdown.

    Windows refuses to remove a directory that is some process's working
    directory, so step out of it first -- otherwise this silently does nothing
    and every render leaks a sandbox.
    """
    os.chdir(_BOOK)
    shutil.rmtree(tmp, ignore_errors=True)
