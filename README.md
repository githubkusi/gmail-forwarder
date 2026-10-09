# Gmail Forwarder Web

A self-hosted interface for creating Google Groups that act as mail forwarders and searching existing groups. The app includes GAM7 in the same container and uses one server-side GAM authorization. Configure the eligible group owners with `EMAIL_RECIPIENTS`.

## Requirements

- Docker Engine with the Compose plugin
- A Google Workspace administrator account with permission to manage Groups
- GAM API/OAuth setup appropriate to your Workspace and GAM7 version
- An authenticated reverse proxy, or another trusted access-control boundary

## Configure and authorize GAM

1. Copy `.env.example` to `.env` and set `EMAIL_RECIPIENTS` to a whitespace-separated list of email addresses. The selected address is added as the new group's owner, and its domain is used for the forwarder address. Keep `.env` private; it is ignored by Git.
2. Put your GAM OAuth client file at `GAM_AUTH_DIR/client_secrets.json` (default `./gam_auth/client_secrets.json`). The app bind-mounts that single file read-only; the container's `app` user (UID 999) needs read access to this file, but no write access. GAM's `gam.cfg` and cache live in the Docker-managed `gam_state` volume; `oauth2.txt` and its lock file are kept in the separate writable `gam_oauth` volume; GAM's work directory is in `gam_work`. GAM can therefore refresh its token without modifying the host file or needing host ACL/write permissions.
3. Build the image and perform the initial authorization:

   ```sh
   docker compose build
   docker compose run --rm web python -m gmail_forwarder_web.gam_setup
   ```

   This configures GAM to read `client_secrets.json` from the read-only mount and write `oauth2.txt` to the `gam_oauth` volume, then runs `gam oauth create` with only the Directory API – Groups and Groups Settings API scopes preselected. GAM skips the scope-selection menu; complete the Google admin consent in the terminal/browser. The token volume persists across restarts, so this initial consent should not be needed again unless Google revokes the token or its scopes change. Back up the `gam_auth`, `gam_state`, `gam_oauth`, and `gam_work` data securely; the host client-secret file and volume token are sensitive.
4. Set `PORT` in `.env` to the host port you want (default `8000`), start the app with `docker compose up -d --build`, and open `http://127.0.0.1:<PORT>`. `PORT` changes only the host-side port; the app listens on port `8000` inside the container and the health check uses that internal port. Compose binds the host port on loopback only, so other machines cannot connect directly. For remote access, place it behind an authenticated reverse proxy and configure the network explicitly.

The UI creates a group at `name@recipient-domain`, sets `whoCanPostMessage` to `ANYONE_CAN_POST` (same behavior as the CLI), then adds the selected email recipient as owner. The forwarder-name field accepts only the local part; the selected recipient's domain is appended. Search checks matching email addresses across all Workspace groups.

## Security and operations

- Do **not** expose port 8000 directly to the public internet. The application has no built-in user login or CSRF token; protect it with an authenticated reverse proxy and restrict network access.
- GAM OAuth credentials are sensitive. Back up the host client-secret file, `gam_state`, `gam_oauth`, and `gam_work` securely; restrict Docker host access; and do not include credentials in source control or image backups shared without protection.
- The container runs as the image's non-root `app` account (UID/GID `999:999`). It needs read access to the read-only client-secret mount. OAuth token writes and GAM config/cache permissions are contained in Docker-managed volumes.
- `GET /healthz` is a process health check; it does not make a Google API request or prove authorization is valid.
- For updates, review GAM release notes, bump and test the pinned `gam7` version in `pyproject.toml`, rebuild and smoke-test an updated image, back up GAM state, then redeploy. Keep the previous image available for rollback. Do not self-update GAM inside a running container. Reauthorization may be needed if Google or GAM invalidates credentials.
- Group creation consists of two GAM operations. If group creation succeeds but owner assignment fails, the UI reports that the group exists and owner assignment needs attention; it does not attempt automatic rollback.

## Local development

Use Python 3.13 and install the project with its development extras (for example, `uv sync --extra dev`). Set `EMAIL_RECIPIENTS` before starting the app. Run `uv run uvicorn gmail_forwarder_web.web:app --reload --app-dir src` to start locally. GAM must also be configured and authorized for live operations.

Run the mocked tests with `uv run pytest`. Tests do not call Google or require GAM credentials.

## License

This project is licensed under the GNU General Public License v3.0 or, at your option, any later version. See [LICENSE](LICENSE).