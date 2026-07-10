# Warcraft Logs API v2 Usage

Ascend uses the official Warcraft Logs API v2 exclusively - GraphQL over
OAuth client-credentials. It never scrapes warcraftlogs.com pages. Every
field referenced below was verified against the published schema docs at
`https://www.warcraftlogs.com/v2-api-docs/warcraft/` before being used.

## Authentication

- Token endpoint: `https://www.warcraftlogs.com/oauth/token`
- Grant type: `client_credentials`, exchanged via HTTP Basic auth
  (`client_id` as username, `client_secret` as password) - see
  `ascend/api/auth.py`.
- The token is cached in memory with an expiry safety margin
  (`TOKEN_EXPIRY_SAFETY_MARGIN_SECONDS`) and refreshed automatically on a 401.

## GraphQL endpoint

- Client-credentials-protected endpoint: `https://www.warcraftlogs.com/api/v2/client`
  (as opposed to `/api/v2/user`, which requires user-level OAuth and isn't
  used by Ascend).

## Queries currently used (`ascend/api/graphql_queries.py`)

**`RATE_LIMIT_QUERY`** - `Query.rateLimitData { limitPerHour
pointsSpentThisHour pointsResetIn }`. Used for Test Connection and to expose
rate-limit status.

**`REPORT_BY_CODE_QUERY`** - `Query.reportData.report(code: String)` returning
`code, title, startTime, endTime, zone { id name }, owner { name },
guild { name, server { name } }, masterData { actors(type: "Player") { id
name server subType } }, fights { id, name, encounterID, difficulty, kill,
startTime, endTime, friendlyPlayers }`.

`masterData.actors` (verified against `reportmasterdata.doc.html` /
`reportactor.doc.html`) is used for character detection: `fights[].
friendlyPlayers` gives per-fight actor **ids**, and `masterData.actors`
resolves those ids to `name`/`server`/`subType` (class). `ReportActor` has
no region field, so matching a participant to a tracked `Character` is
name+server only - see `ascend/services/character_detection.py` for the
documented limitation this implies.

## Error handling (`ascend/api/client.py`)

| Condition | Behavior |
|---|---|
| HTTP 401 | Token invalidated and the request retried once |
| HTTP 429 | Raises `WCLRateLimitError`, logged as a warning |
| HTTP 5xx / network failure | Raises `WCLNetworkError` |
| GraphQL `errors` array present | Raises `WCLGraphQLError` with the messages, logged |
| Bad client credentials | Raises `WCLAuthError` (surfaced in the connection test) |

## Verifying new queries

Before adding a query for a later phase (events, rankings, encounter
rankings, etc.), re-fetch and re-check the relevant type's schema page
(e.g. `https://www.warcraftlogs.com/v2-api-docs/warcraft/reportfight.doc.html`)
rather than relying on historical/community examples, since the schema does
change between game versions and API updates.
