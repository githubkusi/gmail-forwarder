# Gmail Forwarder

In order to protect your main email address, it is a good idea to use a separate email address for each service. Gmail as part of Google Workplace only allows [30 email aliases](https://knowledge.workspace.google.com/admin/users/add-or-delete-an-alternate-email-address-email-alias#whatEmailAlias).

An alternative to email aliases is [Google Groups](https://groups.google.com/). Groups behave similar to aliases. For each alias, a group is created with the main email address as owner.

Group administration is organized with [GAM](https://github.com/GAM-team/GAM).


## Requirements
- Google Workplace subscription
- Google Workspace administrator account
- Authentication/access-control mechanism (e.g. authenticated reverse proxy)
- Docker

## Installation

1. Copy `.env.example` to `.env`
2. In .env, set `EMAIL_RECIPIENTS` to a whitespace-separated list of email addresses of users which are part of your Google Workspace subscriptions
3. In `.env`, set `PORT`.
4. Build the image:

   ```sh
   docker compose build
   ```
5. Initialize GAM and complete the initial authorization. Choose **one** of these options:

   - **Generate a client secrets file during setup:**

     ```sh
     docker compose run --rm web python -m gmail_forwarder_web.gam_setup
     ```

   - **Import an existing client secrets file:**

     ```sh
     docker compose run --rm \\
       --volume "$PWD/path/to/client_secrets.json:/import/client_secrets.json:ro" \\
       web python -m gmail_forwarder_web.gam_setup
     ```

   In either case, setup stores `client_secrets.json` in the Docker-managed volume. The host file in the import option is mounted read-only and is not modified. Do not run both commands; either one performs setup and authorization.
6. Start the app with `docker compose up` and open `http://127.0.0.1:<PORT>`.


## Security consideration

If gmail-forwarder is exposed to the internet, you must add some kind of access-control. Examples:

- [Caddy](https://caddyserver.com) reverse proxy with basic http auth
- [Authelia](https://www.authelia.com/)


## Technical details

GAM's `gam.cfg` and cache live in the Docker-managed `gam_state` volume; `oauth2.txt` and its lock file are kept in the separate writable `gam_auth_state` volume; the client secret is kept in `gam_client_secrets`; GAM's work directory is in `gam_work`. Back up all four volumes securely. The host file used for import is mounted read-only and is not modified.

When `client_secrets.json` is missing, setup runs `gam create project` and writes the generated file into the `gam_client_secrets` volume. Project creation enables only the Admin SDK and Groups Settings APIs used by the app, plus IAM, which GAM needs to provision its service account. GAM then reads the file and writes `oauth2.txt` to the `gam_auth_state` volume, before requesting the two application OAuth scopes: Directory API – Groups and Groups Settings API. GAM also adds its required email and profile identity scopes. Complete the Google admin consent in the terminal/browser. The token and client-secret volumes persist across restarts, so this initial setup should not be needed again unless Google revokes the token or its scopes change.

The UI creates a group at `name@recipient-domain`, sets `whoCanPostMessage` to `ANYONE_CAN_POST`, then adds the selected email recipient as owner of the group

The UI creates a group at `name@recipient-domain`, sets `whoCanPostMessage` to `ANYONE_CAN_POST` (same behavior as the CLI), then adds the selected email recipient as owner. The forwarder-name field accepts only the local part; the selected recipient's domain is appended. Search checks matching email addresses across all Workspace groups.

For updates, review GAM release notes, bump and test the pinned `gam7` version in `pyproject.toml`, rebuild and smoke-test an updated image, back up GAM state, then redeploy. Keep the previous image available for rollback. Do not self-update GAM inside a running container. Reauthorization may be needed if Google or GAM invalidates credentials.

## License

This project is licensed under the GNU General Public License v3.0 or, at your option, any later version. See [LICENSE](LICENSE).