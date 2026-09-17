import argparse
import json

from alembic import command
from alembic.config import Config

from .config import ROOT, settings


def SessionLocal():
    from .db import SessionLocal as factory

    return factory()


def execute_evaluations(db):
    from .services import execute_evaluations as execute

    return execute(db)


def seed_database(db, seed):
    from .services import seed_database as execute

    return execute(db, seed)


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
    reset = subcommands.add_parser(
        "demo-reset",
        help="DESTROY and recreate only the reserved disposable demo database, then evaluate",
    )
    reset.add_argument(
        "--postgres-port",
        type=int,
        help="Use the pre-created localhost aegisgraph_demo database instead of reserved SQLite",
    )
    serve = subcommands.add_parser("demo-api", help="Serve the reserved demo database on loopback")
    serve.add_argument("--postgres-port", type=int)
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--provider", choices=["deterministic", "openai"], default="deterministic")
    health = subcommands.add_parser(
        "demo-health",
        help="Check a local API, scenario, fixtures, and explicit deterministic provider without external calls",
    )
    health.add_argument("--api-url", default="http://127.0.0.1:8000")
    initialize = subcommands.add_parser(
        "public-init", help="Migrate public PostgreSQL; seed only when explicitly requested"
    )
    initialize.add_argument(
        "--seed", action="store_true", help="Initialize an empty synthetic demo"
    )
    subcommands.add_parser("public-check", help="Verify the public synthetic dataset is ready")
    subcommands.add_parser("public-serve", help="Serve read-only public demo on platform PORT")
    args = parser.parse_args()
    if args.command.startswith("public-"):
        from .deployment import InitializationError, check_public, initialize_public, serve_public

        try:
            if args.command == "public-serve":
                serve_public()
                return
            result = (
                initialize_public(seed=args.seed)
                if args.command == "public-init"
                else check_public()
            )
            print(json.dumps(result, indent=2))
            if not result["ready"]:
                raise SystemExit(1)
        except InitializationError as exc:
            parser.error(str(exc))
        except Exception:
            # Connection exceptions can contain credentials, hostnames and local paths.
            parser.error(
                "Public administration failed. Check database availability and configuration."
            )
        return
    if settings.public_demo:
        parser.error(
            "Local demo commands are disabled in public_demo. Use public-init/public-check."
        )
    if args.command in {"demo-reset", "demo-api", "demo-health"}:
        from .demo import DemoCommandError, check_demo_health, reset_demo, serve_demo

        try:
            if args.command == "demo-reset":
                result = reset_demo(args.postgres_port)
            elif args.command == "demo-health":
                result = check_demo_health(args.api_url)
            else:
                raise SystemExit(serve_demo(args.postgres_port, args.port, args.provider))
            print(json.dumps(result, indent=2))
            if result["status"] == "unhealthy":
                raise SystemExit(1)
        except DemoCommandError as exc:
            parser.error(str(exc))
        return
    config = Config(str(ROOT / "alembic.ini"))
    if args.command == "seed":
        if args.reset:
            from .demo import DemoCommandError, validate_reset_target

            try:
                validate_reset_target(settings.database_url)
            except DemoCommandError as exc:
                parser.error(str(exc))
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
