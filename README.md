# Gmail Forwarder Web

A self-hosted interface for creating Google Groups that act as mail forwarders and searching existing groups. The app includes GAM7 in the same container and uses one server-side GAM authorization. Configure the eligible group owners with `EMAIL_RECIPIENTS`.

## Requirements

- Docker Engine with the Compose plugin
- A Google Workspace administrator account with permission to manage Groups
- GAM API/OAuth setup appropriate to your Workspace and GAM7 version
- An authenticated reverse proxy, or another trusted access-control boundary

## Configure and authorize GAM

1. Copy `.env.example` to `.env` and set `EMAIL_RECIPIENTS` to a whitespace-separated list of email addresses. The selected address is added as the new group's owner, and its domain is used for the forwarder address. Keep `.env` private; it is ignored by Git.
2. Set `GAM_AUTH_DIR` in `.env` to a host directory for the two OAuth files (the example uses `./gam_auth`). GAM's `gam.cfg` and `gamcache` are stored separately in the Docker-managed `gam_state` volume; GAM's work directory is in `gam_work`. Compose bind-mounts the host credential directory at `/run/gam-credentials`, sets GAM's `GAMUSERCONFIGDIR` there, and sets `GAMCFGDIR=/var/lib/gam` for the named config volume. The credential directory must be accessible to the non-root `app` account (UID/GID `999:999`) because GAM may lock or refresh `oauth2.txt`. On Linux, grant UID 999 access with ownership or ACLs rather than making credentials world-writable. For example, with the default `./gam_auth` path:

   ```sh
   chmod 700 gam_auth
   setfacl -m u:999:rwx,m::rwx -m d:u::rwx,d:u:999:rwx,d:g::---,d:m::rwx,d:o::--- gam_auth
   chmod 600 gam_auth/client_secrets.json gam_auth/oauth2.txt
   setfacl -m u:999:rw,m::rw gam_auth/client_secrets.json gam_auth/oauth2.txt
   ```
3. Build the image, then choose one GAM setup path. Both run with the same bind mount and runtime user as the web service.

   **Create a new GAM project and authorize it:**

   ```sh
   docker compose build
   docker compose run --rm web python -m gmail_forwarder_web.gam_setup
   ```

   This runs GAM's `config`, `create project`, and `oauth create` sequence. The no-browser mode prints authorization links and prompts for verification URLs/codes in the terminal. Complete the prompts and choose only the Directory Groups and Groups Settings scopes needed by this service.

   **Reuse existing GAM credentials:** copy both `client_secrets.json` and `oauth2.txt` from your existing GAM configuration into the host directory named by `GAM_AUTH_DIR` (for example, `./gam_auth`), then run:

   ```sh
   docker compose run --rm web python -m gmail_forwarder_web.gam_setup --reuse-existing-credentials
   ```

   Those files must be at the root of `GAM_AUTH_DIR` on the host, which is mounted as `/run/gam-credentials` in the container. This mode checks both files exist, configures GAM to use the mounted credential directory, and verifies access by listing the Workspace group count. It does **not** run `create project` or `oauth create`, so it will not initiate OAuth authorization. If verification fails, check that the token is still valid and has Directory Groups/Groups Settings access. Keep the credential files and host directory private; they contain sensitive OAuth material.

   In either setup path, only `client_secrets.json` and `oauth2.txt` (plus GAM's transient lock file) live in the host directory configured by `GAM_AUTH_DIR`. GAM's `gam.cfg` and cache live in the `gam_state` volume. Back up the credential directory and both Docker volumes securely.
4. Set `PORT` in `.env` to the host port you want (default `8000`), start the app with `docker compose up -d --build`, and open `http://127.0.0.1:<PORT>`. `PORT` changes only the host-side port; the app listens on port `8000` inside the container and the health check uses that internal port. Compose binds the host port on loopback only, so other machines cannot connect directly. For remote access, place it behind an authenticated reverse proxy and configure the network explicitly.

The UI creates a group at `name@recipient-domain`, sets `whoCanPostMessage` to `ANYONE_CAN_POST` (same behavior as the CLI), then adds the selected email recipient as owner. The forwarder-name field accepts only the local part; the selected recipient's domain is appended. Search checks matching email addresses across all Workspace groups.

## Security and operations

- Do **not** expose port 8000 directly to the public internet. The application has no built-in user login or CSRF token; protect it with an authenticated reverse proxy and restrict network access.
- GAM OAuth credentials are sensitive. Back up the host credential directory, `gam_state`, and `gam_work` securely; restrict Docker host access; and do not include credentials in source control or image backups shared without protection.
- The container runs as the image's non-root `app` account (UID/GID `999:999`). Ensure it can read/write the credential directory without making it world-writable; GAM config/cache permissions are managed inside the named volume.
- `GET /healthz` is a process health check; it does not make a Google API request or prove authorization is valid.
- For updates, review GAM release notes, bump and test the pinned `gam7` version in `pyproject.toml`, rebuild and smoke-test an updated image, back up GAM state, then redeploy. Keep the previous image available for rollback. Do not self-update GAM inside a running container. Reauthorization may be needed if Google or GAM invalidates credentials.
- Group creation consists of two GAM operations. If group creation succeeds but owner assignment fails, the UI reports that the group exists and owner assignment needs attention; it does not attempt automatic rollback.

## Local development

Use Python 3.13 and install the project with its development extras (for example, `uv sync --extra dev`). Set `EMAIL_RECIPIENTS` before starting the app. Run `uv run uvicorn gmail_forwarder_web.web:app --reload --app-dir src` to start locally. GAM must also be configured and authorized for live operations.

Run the mocked tests with `uv run pytest`. Tests do not call Google or require GAM credentials.

## License

This project is licensed under the GNU General Public License v3.0 or, at your option, any later version. See [LICENSE](LICENSE).