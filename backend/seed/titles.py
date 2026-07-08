"""Curated seed lists: well-known, mood/genre-diverse titles per medium.

These are search queries (top search result is auto-selected — no human
disambiguation during seeding), chosen to span a wide range of tone/pacing/
theme so early cross-medium search has interesting, varied material rather
than 300 near-duplicates of the same vibe.

NOTE ON LIST SIZE: this was trimmed from an original ~245-title list to a
smaller, balanced set — movie has 46 (seeded first), and the other 6 mediums
get ~6 each so cross-medium recommendations have real material to draw from
in every medium. Feel free to add more titles here and re-run
`python -m seed.seed` (or `--retry-failed`) to grow the library.
"""

SEED_TITLES: dict[str, list[str]] = {
    "movie": [
        "A Ghost Story",
        "Amelie",
        "American Beauty",
        "Arrival",
        "Big Fish",
        "Blade Runner 2049",
        "Burning",
        "Call Me by Your Name",
        "Chungking Express",
        "Columbus",
        "Donnie Darko",
        "Drive",
        "Eternal Beauty",
        "Eternal Sunshine of the Spotless Mind",
        "Everything Everywhere All at Once",
        "Fight Club",
        "Get Out",
        "Gone Girl",
        "Her",
        "In the Mood for Love",
        "Inside Llewyn Davis",
        "La La Land",
        "Lost in Translation",
        "Manchester by the Sea",
        "Memories of Murder",
        "Midsommar",
        "Moonlight",
        "Nightcrawler",
        "No Country for Old Men",
        "Oldboy",
        "Pan's Labyrinth",
        "Parasite",
        "Portrait of a Lady on Fire",
        "Prisoners",
        "Requiem for a Dream",
        "Se7en",
        "Spirited Away",
        "The Florida Project",
        "The Grand Budapest Hotel",
        "The Lighthouse",
        "The Shape of Water",
        "The Social Network",
        "The Truman Show",
        "There Will Be Blood",
        "Whiplash",
        "Zodiac",
    ],
    "tv": [
        "Fleabag",
        "Breaking Bad",
        "The Wire",
        "Twin Peaks",
        "Chernobyl",
        "Severance",
    ],
    "anime": [
        "Violet Evergarden",
        "Cowboy Bebop",
        "Neon Genesis Evangelion",
        "Monster",
        "Made in Abyss",
        "Perfect Blue",
    ],
    "manga": [
        "Vagabond",
        "Berserk",
        "Monster",
        "Chainsaw Man",
        "Oyasumi Punpun",
        "Fullmetal Alchemist",
    ],
    "book": [
        "Never Let Me Go",
        "Slaughterhouse-Five",
        "Norwegian Wood",
        "The Road",
        "Klara and the Sun",
        "Piranesi",
    ],
    "game": [
        "Disco Elysium",
        "Hades",
        "Outer Wilds",
        "Journey",
        "The Last of Us",
        "Celeste",
    ],
    "music": [
        "In Rainbows",
        "To Pimp a Butterfly",
        "Blonde",
        "Blue",
        "Kind of Blue",
        "Nevermind",
    ],
}
