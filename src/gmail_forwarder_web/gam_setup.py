"""Run the initial interactive GAM OAuth authorization flow."""

from .gam_client import initialize_gam


def main() -> None:
    """Authorize the configured client and persist oauth2.txt in its volume."""
    initialize_gam()


if __name__ == "__main__":
    main()