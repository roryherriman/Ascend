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

Fight.difficulty is a bare Int with no self-describing enum - Difficulty ids
and names are scoped per-Zone (Zone.difficulties, verified against
zone.doc.html / worlddata.doc.html / difficulty.doc.html), so resolving a
fight's difficulty to a label like "Mythic" requires a separate
worldData.zone(id).difficulties lookup keyed by the report's zone id - see
ZONE_DIFFICULTIES_QUERY and ascend/services/zone_data.py.

Report.table(dataType: TableDataType, fightIDs: [Int]) (verified against
report.doc.html / tabledatatype.doc.html) returns a bare `JSON` scalar - WCL
does not publish a GraphQL type for its contents (the schema explicitly
warns "this data is not considered frozen"). Ascend therefore treats the
payload as opaque/best-effort rather than asserting a field-level contract
it can't verify - see ascend/services/death_data.py.
"""

ZONES_QUERY = """
query Zones {
  worldData {
    zones {
      id
      name
      frozen
      expansion {
        id
        name
      }
    }
  }
}
"""

GUILD_LOOKUP_QUERY = """
query GuildLookup($name: String!, $serverSlug: String!, $serverRegion: String!) {
  guildData {
    guild(name: $name, serverSlug: $serverSlug, serverRegion: $serverRegion) {
      id
      name
      server {
        name
        slug
        region {
          slug
          name
        }
      }
      faction {
        id
        name
      }
    }
  }
}
"""

ZONE_DIFFICULTIES_QUERY = """
query ZoneDifficulties($zoneId: Int!) {
  worldData {
    zone(id: $zoneId) {
      id
      name
      difficulties {
        id
        name
      }
    }
  }
}
"""

DEATH_TABLE_QUERY = """
query DeathTable($code: String!, $fightIds: [Int]) {
  reportData {
    report(code: $code) {
      table(dataType: Deaths, fightIDs: $fightIds)
    }
  }
}
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
