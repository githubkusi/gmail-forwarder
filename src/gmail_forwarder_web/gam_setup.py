"""Interactive GAM authorization entry point for initial container setup."""

import argparse

from .gam_client import initialize_gam


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize GAM for Gmail Forwarder Web.")
    parser.add_argument(
        "--reuse-existing-credentials",
        action="store_true",
        help=(
            "Use client_secrets.json and oauth2.txt already present in GAMCFGDIR; "
            "do not create a project or start OAuth authorization."
        ),
    )
    args = parser.parse_args()
    initialize_gam(reuse_existing_credentials=args.reuse_existing_credentials)


if __name__ == "__main__":
    main()