"""The demo notebook runs end to end on the test fixtures (outside Colab)."""
import contextlib
import io
import json
import os
from pathlib import Path

import pytest

NB = Path(__file__).parent.parent / "notebooks" / "webmeta_demo.ipynb"


@pytest.mark.parametrize("source,fmt", [("Demo sample (HPLT 4, multilingual)", "txt"),
                                        ("Upload my own file", "jsonl")])
def test_notebook_runs(tmp_path, source, fmt):
    pytest.importorskip("pandas")
    nb = json.loads(NB.read_text())
    work = tmp_path / "notebooks"
    work.mkdir()
    (tmp_path / "tests").symlink_to(NB.parent.parent / "tests")
    g, cwd = {}, os.getcwd()
    os.chdir(work)
    try:
        for cell in nb["cells"]:
            if cell["cell_type"] != "code":
                continue
            src = "".join(cell["source"])
            src = src.replace('SOURCE = "Demo sample (HPLT 4, multilingual)"', f'SOURCE = "{source}"')
            src = src.replace('LANGUAGES = "fi,sv"', 'LANGUAGES = ""')
            src = src.replace('FORMAT = "jsonl"', f'FORMAT = "{fmt}"')
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile(src, "notebook", "exec"), g)
    finally:
        os.chdir(cwd)
    assert len(g["sample"]) > 0
    assert (work / "webmeta_dataset" / "cells.tsv").exists()
    assert (work / "webmeta_dataset.zip").exists()
