"""Shared A-B/C-D relay vocabulary, used by both IndoorMode and FlintMode.

A "relay" is a group of archers (A-B or C-D) sharing the same physical
shooting position. Which relays are used, and in which order, is a
per-match setting chosen before the match starts and never changed
mid-match.
"""

TURN_MODES = {
    "ab_then_cd": ["A-B", "C-D"],
    "cd_then_ab": ["C-D", "A-B"],
    "ab_only": ["A-B"],
    "cd_only": ["C-D"],
}
