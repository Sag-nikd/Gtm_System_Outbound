#!/usr/bin/env python
"""
Generate CRM setup for a client.

Usage:
    python scripts/generate_crm_setup.py --client acme_saas --crm hubspot --mode dry-run
    python scripts/generate_crm_setup.py --client acme_saas --crm hubspot --mode live
    python scripts/generate_crm_setup.py --client acme_saas --crm salesforce --mode dry-run
    python scripts/generate_crm_setup.py --client acme_saas --crm hubspot --mode inspect-only
"""
from __future__ import annotations

import argparse
import os
import sys

# Allow running from repo root without installing the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.crm.base import SetupMode
from src.crm.setup_generator import CRMSetupGenerator
from src.utils.logger import get_logger

log = get_logger("generate_crm_setup")

_OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "outputs",
    "crm_setup",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate CRM setup for a GTM client.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--client",
        required=True,
        help="Client name (e.g. acme_saas). Looks for config/crm/{client}.yaml.",
    )
    parser.add_argument(
        "--crm",
        required=True,
        choices=["hubspot", "salesforce"],
        help="CRM platform to target.",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["inspect-only", "dry-run", "live", "force-update"],
        help=(
            "inspect-only: scan and report gaps. "
            "dry-run: plan what would be created, no API calls. "
            "live: create missing components only. "
            "force-update: (future) update existing components."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=_OUTPUT_DIR,
        help=f"Directory for output reports (default: {_OUTPUT_DIR})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        mode = SetupMode(args.mode)
    except ValueError:
        log.error("Invalid mode: %s", args.mode)
        sys.exit(1)

    log.info(
        "Starting CRM setup — client=%s  crm=%s  mode=%s",
        args.client, args.crm, mode.value,
    )

    generator = CRMSetupGenerator(
        client_name=args.client,
        crm=args.crm,
        mode=mode,
        output_dir=args.output_dir,
    )

    try:
        report = generator.run()
    except RuntimeError as exc:
        log.error("Setup failed: %s", exc)
        sys.exit(1)

    summary = report.summary()
    print("\n" + "=" * 60)
    print(f"  CRM Setup Complete — {args.client} / {args.crm} / {mode.value}")
    print("=" * 60)
    print(f"  Fields planned:      {summary['fields_planned']}")
    print(f"  Fields created:      {summary['fields_created']}")
    print(f"  Fields skipped:      {summary['fields_skipped']}")
    print(f"  Fields need review:  {summary['fields_needs_review']}")
    print(f"  Pipelines planned:   {summary['pipelines_planned']}")
    print(f"  Pipelines created:   {summary['pipelines_created']}")
    print(f"  Stages planned:      {summary['stages_planned']}")
    print(f"  Stages created:      {summary['stages_created']}")
    if summary["warnings"]:
        print(f"  Warnings:            {summary['warnings']}")
    if summary["errors"]:
        print(f"  Errors:              {summary['errors']}")
    print(f"\n  Reports in: {args.output_dir}")
    print("=" * 60 + "\n")

    if report.next_manual_steps:
        print("Next manual steps in CRM UI:")
        for step in report.next_manual_steps:
            print(f"  - {step}")
        print()

    sys.exit(1 if summary["errors"] else 0)


if __name__ == "__main__":
    main()
