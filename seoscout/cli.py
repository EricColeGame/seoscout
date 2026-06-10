#!/usr/bin/env python3
"""
seoscout CLI — unified entry point.

Usage:
    seoscout search --keywords FILE
    seoscout extract --project NAME
    seoscout run --keywords FILE
"""

import asyncio
import argparse
import json
import os
import sys

from . import __version__


def _derive_project(keywords_file: str) -> str:
    """Derive project name from topic_name in JSON, or fall back to filename."""
    try:
        with open(keywords_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        topic = data.get('topic_name', '').strip()
        if topic:
            return topic.replace(' ', '_').lower()
    except Exception:
        pass
    # Fall back to filename without extension
    base = os.path.splitext(os.path.basename(keywords_file))[0]
    return base.replace(' ', '_').lower()


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

    # ── extract ──
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract YouTube transcripts and web content from search results"
    )
    extract_parser.add_argument(
        "--project", "-p",
        help="Project name (auto-derived from keywords file if not set)"
    )
    extract_parser.add_argument(
        "--keywords", "-k",
        help="Keywords JSON file (used to derive project name if --project not set)"
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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Derive project name
    if args.command in ("search", "run"):
        args.project = _derive_project(args.keywords)
        print(f"📁 Project: {args.project}\n")
    elif args.command == "extract":
        if args.project:
            pass  # manual override
        elif args.keywords:
            args.project = _derive_project(args.keywords)
        else:
            print("❌ Need --project or --keywords to identify project")
            sys.exit(1)

    if args.command == "search":
        asyncio.run(_run_search(args))
    elif args.command == "extract":
        asyncio.run(_run_extract(args))
    elif args.command == "run":
        asyncio.run(_run_all(args))


async def _run_search(args):
    from .collect import run_collect
    await run_collect(args.project, args.keywords)


async def _run_extract(args):
    from .extract import run_extract
    await run_extract(args.project)


async def _run_all(args):
    from .collect import run_collect
    from .extract import run_extract

    await run_collect(args.project, args.keywords)
    await run_extract(args.project)


if __name__ == "__main__":
    main()
