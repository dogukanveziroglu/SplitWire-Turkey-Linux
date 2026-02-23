"""
Vulture whitelist for SplitWire Linux.

This file lists false positives for Vulture dead code analysis.
These are symbols that appear unused but are actually called by
GTK/GObject signal dispatch, framework callbacks, or dynamic
invocation patterns.

Usage:
    vulture src/splitwire/ vulture_whitelist.py --min-confidence 80
"""

# GTK signal handler parameters
# notify::active signals pass (widget, pspec) -- pspec is required by signature
# These are already handled with underscore prefix convention (_pspec)

# BasePage methods overridden by subclasses
# (none flagged at 80%+ confidence currently)

# Framework-called methods
# (none flagged at 80%+ confidence currently)
