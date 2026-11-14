"""Launcher: ``streamlit run app_gui.py``.

runpy re-executes the interface script on every Streamlit rerun (a plain import would be cached).
"""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parent / "src" / "interface" / "streamlit_app.py"), run_name="__main__")
