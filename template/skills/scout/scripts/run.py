# ABOUTME: Runs one of Regina's commands from regina_lib.
# ABOUTME: Every skill shares this script; the first argument names the command.
import sys

from regina_lib.cli import main

raise SystemExit(main(sys.argv[1:]))
