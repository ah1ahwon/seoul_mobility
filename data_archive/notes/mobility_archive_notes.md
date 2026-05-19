# Mobility Archive Notes

## Recommended Starting Window

Start with 2026-03 and 2026-04 because those are the latest files observed on 2026-05-10:

- Subway: `CARD_SUBWAY_MONTH_202604.csv`
- Bus: `bus_time_station_202604.csv`
- Capital-region living migration: `seoul_purpose_admdong4_in_20260331.zip`

For modeling, avoid downloading every daily living-migration ZIP at first. Use a sampling plan:

- Recent month: all Saturdays and Sundays plus selected weekdays.
- Reference periods: same weekdays from 3, 6, and 12 months before if available.
- Event exclusion: mark major holidays and city events before trend scoring.

## Analysis Fit

The strongest mobility-only signal is not total volume. Use:

- weekend / weekday ratio
- 20s + 30s share of destination arrivals
- non-commute purpose share, especially shopping/tourism/other where available
- evening and late-night arrival concentration
- OD diversity: more distinct origins can indicate wider commercial pull

## Known Caveats

- Subway and bus files do not identify age.
- Bus CSV text is encoded in Korean legacy encoding on download; convert to UTF-8 during preprocessing before column-name handling.
- Subway CSV is UTF-8 with BOM.
- Capital-region living-migration ZIP contains a CSV with direct `2030_cnt` and `total_cnt` fields, so it is the cleanest starting point for the target age group.
- Living-migration data is estimated from mobile data and may mask counts of 3 or fewer.
- Administrative-dong units need mapping to commercial-area codes before final scoring.
- Station and stop catchment areas should be spatially joined rather than matched by name.
- Station/stop coordinate CSV files are optional until their download source is documented; the main analysis should not depend on undocumented coordinate files.
- Current final scoring already combines mobility with residential adjustment, land use, estimated sales, daytime influx, and visit-pattern bonus. Additional store-count, rent, and detailed card-sales layers are still validation inputs, not current required sources.
