# Gmail Forwarder

In order to protect your main email address, it is a good idea to use a separate email address for each service. Gmail as part of Google Workplace only allows 30 email aliases.
An alternative to email aliases are [Google Groups](https://groups.google.com/), which behaves similar to aliases.

## Requirements
- Google Workplace subscription
- Google Workspace administrator account
- Authentication/access-control mechanism (e.g. authenticated reverse proxy)
- Docker

## Installation

1. Copy `.env.example` to `.env`
2. In .env, set `EMAIL_RECIPIENTS` to a whitespace-separated list of email addresses of users which are part of your Google Workspace subscriptions
3. If you already have a GAM OAuth client file, put it at `$GAM_AUTH_DIR/client_secrets.json`. If not, make sure `$GAM_AUTH_DIR` is writable by the container's `app` user (UID 999); the setup command will guide you through GAM project creation and create the file there.
4. In .env, set `PORT`
5. Build the image and perform the initial authorization:

   ```sh
   docker compose build
   docker compose run --rm gam-setup
   ```
6. Start the app with `docker compose up` and open `http://127.0.0.1:<PORT>`


## Security consideration

If gmail-forwarder is exposed to the internet, you must add some kind of access-control. Examples:

- [Caddy](https://caddyserver.com) reverse proxy with basic http auth
- [Authelia](https://www.authelia.com/)


## Technical details

GAM's `gam.cfg` and cache live in the Docker-managed `gam_state` volume; `oauth2.txt` and its lock file are kept in the separate writable `gam_auth_state` volume; GAM's work directory is in `gam_work`.

When `client_secrets.json` is missing, setup runs `gam create project` and writes the generated file into `$GAM_AUTH_DIR`. GAM then reads the file and writes `oauth2.txt` to the `gam_auth_state` volume, before running `gam oauth create` with only the Directory API – Groups and Groups Settings API scopes preselected. GAM skips the scope-selection menu; complete the Google admin consent in the terminal/browser. The token volume persists across restarts, so this initial consent should not be needed again unless Google revokes the token or its scopes change.

The UI creates a group at `name@recipient-domain`, sets `whoCanPostMessage` to `ANYONE_CAN_POST`, then adds the selected email recipient as owner of the group

The UI creates a group at `name@recipient-domain`, sets `whoCanPostMessage` to `ANYONE_CAN_POST` (same behavior as the CLI), then adds the selected email recipient as owner. The forwarder-name field accepts only the local part; the selected recipient's domain is appended. Search checks matching email addresses across all Workspace groups.

For updates, review GAM release notes, bump and test the pinned `gam7` version in `pyproject.toml`, rebuild and smoke-test an updated image, back up GAM state, then redeploy. Keep the previous image available for rollback. Do not self-update GAM inside a running container. Reauthorization may be needed if Google or GAM invalidates credentials.

## License

This project is licensed under the GNU General Public License v3.0 or, at your option, any later version. See [LICENSE](LICENSE).