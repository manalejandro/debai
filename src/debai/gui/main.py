"""
Main entry point for the Debai GTK GUI.
"""

import sys
import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gio

from debai.gui.app import DebaiApplication

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main() -> int:
    """Main entry point for the GUI application."""
    app = DebaiApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
