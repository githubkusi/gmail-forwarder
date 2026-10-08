# Gmail Forwarder Web

A self-hosted interface for creating Google Groups that act as mail forwarders and searching existing groups. The app includes GAM7 in the same container and uses one server-side GAM authorization. It is limited to `titlis.org` and `lsass.ch`.

## Requirements

- Docker Engine with the Compose plugin
- A Google Workspace administrator account with permission to manage Groups
- GAM API/OAuth setup appropriate to your Workspace and GAM7 version
- An authenticated reverse proxy, or another trusted access-control boundary

## Configure and authorize GAM

1. Copy `.env.example` to `.env` and set `TITLIS_ORG_OWNER` and `LSASS_CH_OWNER` to the owner mailboxes. Each mailbox must use its matching domain. Keep `.env` private; it is ignored by Git.
2. Build the image, then run GAM7's interactive bootstrap against its persistent volumes using the same image and runtime user as the web service:

   ```sh
   docker compose build
   docker compose run --rm web python -m gmail_forwarder_web.gam_setup
   ```

   This runs GAM's documented `config`, `create project`, and `oauth create` sequence with `GAMCFGDIR=/var/lib/gam`; the separate working directory is persisted at `/var/lib/gam-work`. The no-browser mode prints authorization links and prompts for verification URLs/codes in the terminal. Complete the prompts, create/authorize the GAM project as required by your Workspace, and choose only the Directory Groups and Groups Settings scopes needed by this service rather than granting unrelated APIs. The resulting `gam.cfg`, OAuth tokens, client files, and caches remain in Docker volumes, not the image. GAM's setup involves sensitive project credentials and administrator authorization; keep the terminal private and back up volumes securely.
3. Start the app with `docker compose up -d --build`.
4. Make it reachable only through an authenticated reverse proxy. For local testing, uncomment the loopback-only `ports` mapping in Compose and browse to `http://127.0.0.1:8000`.

The UI creates a group at `name@selected-domain`, sets `whoCanPostMessage` to `ANYONE_CAN_POST` (same behavior as the CLI), then adds that domain's configured mailbox as owner. Search checks matching email addresses in groups across both domains.

## Security and operations

- Do **not** expose port 8000 directly to the public internet. The application has no built-in user login or CSRF token; protect it with an authenticated reverse proxy and restrict network access.
- GAM OAuth/config data is sensitive. Back up the `gam_state` volume securely, restrict Docker host access, and do not include it in source control or image backups shared without protection.
- The image uses a non-root user. Verify volume ownership/permissions required by your GAM setup. The Compose-managed named volume is mounted at GAMCFGDIR.
- `GET /healthz` is a process health check; it does not make a Google API request or prove authorization is valid.
- For updates, review GAM release notes, bump and test the pinned `gam7` version in `pyproject.toml`, rebuild and smoke-test an updated image, back up GAM state, then redeploy. Keep the previous image available for rollback. Do not self-update GAM inside a running container. Reauthorization may be needed if Google or GAM invalidates credentials.
- Group creation consists of two GAM operations. If group creation succeeds but owner assignment fails, the UI reports that the group exists and owner assignment needs attention; it does not attempt automatic rollback.

## Local development

Use Python 3.13 and install the project with its development extras (for example, `uv sync --extra dev`). Set both owner mailbox environment variables before starting the app. Run `uv run uvicorn gmail_forwarder_web.web:app --reload --app-dir src` to start locally. GAM must also be configured and authorized for live operations.

Run the mocked tests with `uv run pytest`. Tests do not call Google or require GAM credentials.