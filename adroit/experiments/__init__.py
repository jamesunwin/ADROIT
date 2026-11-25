"""Experiment modules: one exchangeable module per direct-detection search.

A module turns the physics of an interaction into the signal it predicts in
one search, and from that search's data sets a limit on it (``base.py``).
Each declares its collaboration's published conventions and must reproduce
the published limit before it enters likelihoods (``validation.py``; build
plan, DM3; record in docs/dm3_experiments.md). ``registry.py`` loads modules
by name; their data are fetched into the tools folder, never committed.
"""
