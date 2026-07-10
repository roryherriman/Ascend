"""GraphQL query strings for the Warcraft Logs API v2.

Every field referenced here was confirmed against the official published
schema docs at https://www.warcraftlogs.com/v2-api-docs/warcraft/ (the
Query, ReportData, Report, ReportFight, RateLimitData, Guild, User, and Zone
type pages) before being used - no historical/unofficial field names.
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
