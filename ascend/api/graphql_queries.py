"""GraphQL query strings for the Warcraft Logs API v2.

Every field referenced here was confirmed against the official published
schema docs at https://www.warcraftlogs.com/v2-api-docs/warcraft/ (the
Query, ReportData, Report, ReportFight, ReportMasterData, ReportActor,
RateLimitData, Guild, User, and Zone type pages) before being used - no
historical/unofficial field names.

ReportMasterData.actors(type, subType) filters server-side; we request only
type: "Player" since character detection only needs player actors, not NPCs
or pets. ReportActor has no region field (only `server`, a "normalized
server name") - matching a participant to a tracked Character is therefore
name+server only, not region-qualified. See
ascend/services/character_detection.py for the documented limitation this
implies (a same-named character on the same realm name in a different
region would be ambiguous - out of scope for a personal-scale tracker).
"""

RATE_LIMIT_QUERY = """
query RateLimit {
  rateLimitData {
    limitPerHour
    pointsSpentThisHour
    pointsResetIn
  }
}
"""

REPORT_BY_CODE_QUERY = """
query ReportByCode($code: String!) {
  reportData {
    report(code: $code) {
      code
      title
      startTime
      endTime
      zone {
        id
        name
      }
      owner {
        name
      }
      guild {
        name
        server {
          name
        }
      }
      masterData {
        actors(type: "Player") {
          id
          name
          server
          subType
        }
      }
      fights {
        id
        name
        encounterID
        difficulty
        kill
        startTime
        endTime
        friendlyPlayers
      }
    }
  }
}
"""
