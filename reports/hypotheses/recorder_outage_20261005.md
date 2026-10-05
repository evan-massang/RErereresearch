# Recorder outage 2026-10-05 ~12:02-12:04 UTC (container restart)

The container restarted around 12:02 UTC; the local agent proxy moved ports, so every running recorder lost its
network connection (first "ConnectionRefused/ProxyError" at 12:03:05-12:03:07Z in each recorder.log). All
recorders were restarted at 12:03:58Z with the remaining hours of their original runs:
multivenue (to ~10-07 07:19), memelag (to ~10-07 09:37), liqmap (to ~10-07 12:57; resumed 1154 known addresses),
pumplean (72 h from restart), twap_recorder (to ~10-07 06:07), and the HLLAG forward collector.
The window from the last good message before 12:03:05Z to the first message after 12:03:58Z is a declared gap
for every pre-registration that has a gap rule (no triggers, no fills inside it). Split boundaries (T0, T0+24h,
T0+48h) are unchanged.
