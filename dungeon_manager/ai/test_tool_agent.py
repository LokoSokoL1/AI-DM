"""Backward-compatible entry point for opt-in live ToolAgent validation."""

from .live_tool_loop_validation import main


if __name__ == "__main__":
    raise SystemExit(main())
