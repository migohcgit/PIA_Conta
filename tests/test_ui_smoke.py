"""Smoke test: executes the whole Streamlit script against lightweight stand-ins for streamlit and plotly.

It does not judge appearance; it guarantees that every code path of the interface runs with the bundled data
(names, types, data flow, exports). The real Streamlit/Plotly are exercised by running the app manually.
"""
import runpy
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

# Import compiled dependencies up front: patch.dict(sys.modules) would otherwise drop them on exit and they
# cannot be loaded twice in one process.
import numpy  # noqa: F401
import pandas  # noqa: F401
import pdfplumber  # noqa: F401
import xlsxwriter  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "Seguros Monterrey"


class _Ctx:
    def __init__(self, st):
        self.st = st

    def __enter__(self):
        return self.st

    def __exit__(self, *exc):
        return False

    def __getattr__(self, name):
        return getattr(self.st, name)


class FakeStreamlit(types.ModuleType):
    """Records calls and returns sensible defaults for every widget the app uses."""

    def __init__(self):
        super().__init__("streamlit")
        self.session_state = {}
        self.calls = []
        self.downloads = []
        self.column_config = types.SimpleNamespace(NumberColumn=lambda *a, **k: ("num", a, k))
        self.sidebar = _Ctx(self)

    def _log(self, name, *a, **k):
        self.calls.append(name)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def call(*a, **k):
            self._log(name, *a, **k)
            return None
        return call

    # widgets with meaningful return values
    def radio(self, label, options, index=0, **k):
        return options[index]

    def selectbox(self, label, options, index=0, **k):
        return list(options)[index]

    def text_input(self, label, value="", **k):
        return value

    def button(self, *a, **k):
        return False

    def file_uploader(self, *a, **k):
        return []

    def columns(self, spec, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [_Ctx(self) for _ in range(n)]

    def tabs(self, labels):
        return [_Ctx(self) for _ in labels]

    def expander(self, *a, **k):
        return _Ctx(self)

    def spinner(self, *a, **k):
        return _Ctx(self)

    def data_editor(self, df, **k):
        return df

    def download_button(self, label, data=None, **k):
        self.downloads.append((label, len(data)))
        return False

    def stop(self):
        raise SystemExit

    def rerun(self):
        raise AssertionError("unexpected rerun")


class UiSmokeTest(unittest.TestCase):
    @unittest.skipUnless(DATA.exists(), "bundled data folder not present")
    def test_app_runs_end_to_end(self):
        fake = FakeStreamlit()
        plotly = types.ModuleType("plotly")
        go = mock.MagicMock(name="graph_objects")
        plotly.graph_objects = go
        modules = {"streamlit": fake, "plotly": plotly, "plotly.graph_objects": go}
        for lang in ("es", "en"):
            fake.session_state.clear()
            fake.calls.clear()
            fake.downloads.clear()
            fake.radio = lambda label, options, index=0, _l=lang, **k: (_l if "es" in options else options[index])
            with mock.patch.dict(sys.modules, modules):
                for name in [m for m in sys.modules if m.startswith("src.interface")]:
                    del sys.modules[name]
                runpy.run_path(str(ROOT / "src" / "interface" / "streamlit_app.py"), run_name="__main__")
            self.assertGreaterEqual(fake.calls.count("plotly_chart"), 8)
            self.assertGreaterEqual(fake.calls.count("dataframe"), 6)
            self.assertEqual(len(fake.downloads), 3)
            self.assertGreater(fake.downloads[0][1], 10_000)  # the Excel file has real content
            self.assertIsNone(fake.session_state.get("error"))


if __name__ == "__main__":
    unittest.main()
