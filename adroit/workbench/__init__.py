"""The workbench (DM11): a local web page to run the pipelines and read their results.

``adroit workbench`` serves it at http://127.0.0.1:8765. It runs the same code as the
command line (``orchestrator.runs``), one job at a time, each in its own folder under
the runs directory, and shows the runs, DM10's evaluation and the external tools.
It uses only Python's standard library and markdown-it-py, and listens on this
machine only.
"""
