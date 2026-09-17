import argparse
import json

from alembic import command
from alembic.config import Config

from .config import ROOT
from .db import SessionLocal
from .services import execute_evaluations, seed_database


def main():
    parser = argparse.ArgumentParser(description="AegisGraph synthetic demo management")
    subcommands = parser.add_subparsers(dest="command", required=True)
    seed = subcommands.add_parser("seed", help="Migrate then ingest deterministic synthetic demo")
    seed.add_argument(
        "--reset",
        action="store_true",
        help="Delete all local demo data by downgrading/reapplying migrations",
    )
    seed.add_argument("--seed", type=int, default=42)
    subcommands.add_parser(
        "evaluate", help="Execute and persist the actual deterministic security suite"
    )
    args = parser.parse_args()
    config = Config(str(ROOT / "alembic.ini"))
    if args.command == "seed":
        if args.reset:
            command.downgrade(config, "base")
        command.upgrade(config, "head")
        with SessionLocal() as db:
            print(json.dumps(seed_database(db, args.seed), indent=2))
    else:
        with SessionLocal() as db:
            result = execute_evaluations(db)
            print(json.dumps(result, indent=2))
            if result["failed"]:
                raise SystemExit(1)


if __name__ == "__main__":
    main()
