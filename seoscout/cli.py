#!/usr/bin/env python3
"""
seoscout CLI — unified entry point.

Usage:
    seoscout search --keywords FILE --project NAME [--category CAT]
    seoscout extract --project NAME
    seoscout run --keywords FILE --project NAME [--category CAT]
"""

import asyncio
import argparse
import sys

from . import __version__


def main():
    parser = argparse.ArgumentParser(
        prog="seoscout",
        description="Keyword research & content collection CLI for SEO"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── search ──
    search_parser = subparsers.add_parser(
        "search",
        help="Search keywords on YouTube and Google, output pending_review.json"
    )
    search_parser.add_argument(
        "--keywords", "-k", required=True,
        help="Path to keywords JSON file"
    )
    search_parser.add_argument(
        "--project", "-p", required=True,
        help="Project name (data stored in output/<project>/)"
    )
    search_parser.add_argument(
        "--category", "-c", default=None,
        help="Only search keywords in this category"
    )

    # ── extract ──
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract YouTube transcripts and web content from search results"
    )
    extract_parser.add_argument(
        "--project", "-p", required=True,
        help="Project name"
    )

    # ── run (search + extract) ──
    run_parser = subparsers.add_parser(
        "run",
        help="Search and extract in one step"
    )
    run_parser.add_argument(
        "--keywords", "-k", required=True,
        help="Path to keywords JSON file"
    )
    run_parser.add_argument(
        "--project", "-p", required=True,
        help="Project name"
    )
    run_parser.add_argument(
        "--category", "-c", default=None,
        help="Only process keywords in this category"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "search":
        asyncio.run(_run_search(args))
    elif args.command == "extract":
        asyncio.run(_run_extract(args))
    elif args.command == "run":
        asyncio.run(_run_all(args))


async def _run_search(args):
    """Delegate to collect.py logic."""
    # Import here to avoid circular imports and to allow
    # the package to be used as a library too.
    from .collect import run_collect
    await run_collect(args.project, args.keywords, args.category)


async def _run_extract(args):
    """Delegate to extract.py logic."""
    from .extract import run_extract
    await run_extract(args.project)


async def _run_all(args):
    """Search then extract."""
    from .collect import run_collect
    from .extract import run_extract

    await run_collect(args.project, args.keywords, args.category)
    await run_extract(args.project)


if __name__ == "__main__":
    main()
