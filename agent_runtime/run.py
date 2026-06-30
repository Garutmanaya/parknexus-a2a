"""
CLI runner for ParkNexus A2A provider agents.

Examples:
    python -m agent_runtime.run \
      --config agents/company_a/agent.yaml \
      --a2a agents/company_a/a2a.yaml \
      --port 8011 \
      --ssl-certfile certs/local.crt \
      --ssl-keyfile certs/local.key
"""

import argparse

import uvicorn

from agent_runtime.main import create_app_from_config

from shared.logging.logger import get_logger

logger = get_logger(__name__)

def main() -> None:
    """
    Parse CLI args, create provider app, and start uvicorn.
    """
    parser = argparse.ArgumentParser(description="Run ParkNexus provider agent")

    parser.add_argument("--config", required=True, help="Path to provider agent.yaml")
    parser.add_argument("--a2a", required=True, help="Path to provider a2a.yaml")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, required=True, help="Bind port")

    parser.add_argument(
        "--ssl-certfile",
        default=None,
        help="Path to HTTPS certificate file",
    )

    parser.add_argument(
        "--ssl-keyfile",
        default=None,
        help="Path to HTTPS private key file",
    )

    args = parser.parse_args()

    app = create_app_from_config(args.config, args.a2a)

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        ssl_certfile=args.ssl_certfile,
        ssl_keyfile=args.ssl_keyfile,
    )


if __name__ == "__main__":
    main()