#!/usr/bin/env python
"""
Validate existing CRM setup against the required GTM configuration.

Usage:
    python scripts/validate_crm_setup.py --client acme_saas --crm hubspot
    python scripts/validate_crm_setup.py --client acme_saas --crm salesforce
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.crm.base import SetupMode
from src.crm.setup_generator import CRMSetupGenerator
from src.utils.logger import get_logger

log = get_logger("validate_crm_setup")

_OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "outputs",
    "crm_setup",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate CRM setup — inspect existing CRM and report gaps.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--client", required=True, help="Client name.")
    parser.add_argument(
        "--crm", required=True, choices=["hubspot", "salesforce"], help="CRM platform."
    )
    parser.add_argument(
        "--output-dir",
        default=_OUTPUT_DIR,
        help=f"Directory for output reports (default: {_OUTPUT_DIR})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    log.info("Validating CRM setup — client=%s  crm=%s", args.client, args.crm)

    generator = CRMSetupGenerator(
        client_name=args.client,
        crm=args.crm,
        mode=SetupMode.INSPECT_ONLY,
        output_dir=args.output_dir,
    )

    try:
        report = generator.run()
    except Exception as exc:
        log.error("Validation failed: %s", exc)
        sys.exit(1)

    summary = report.summary()
    print("\n" + "=" * 60)
    print(f"  Validation Report — {args.client} / {args.crm}")
    print("=" * 60)
    print(f"  Fields existing:     {summary['fields_skipped']}")
    print(f"  Fields missing:      {summary['fields_planned']}")
    print(f"  Fields need review:  {summary['fields_needs_review']}")
    print(f"  Pipelines existing:  {summary['pipelines_skipped']}")
    print(f"  Pipelines missing:   {summary['pipelines_planned']}")
    print(f"  Stages existing:     {summary['stages_skipped']}")
    print(f"  Stages missing:      {summary['stages_planned']}")
    if summary["warnings"]:
        print(f"  Warnings: {summary['warnings']}")
    print(f"\n  Reports in: {args.output_dir}")
    print("=" * 60 + "\n")

    missing = summary["fields_planned"] + summary["pipelines_planned"]
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
