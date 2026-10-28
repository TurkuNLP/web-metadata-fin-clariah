"""Country table: name, UN region and subregion, a map point, and languages.

The country step reads a country from the URL's top-level domain; this table
places that country: its name, UN region and subregion (e.g. "Europe",
"Northern Europe"), a label point for maps (longitude, latitude), and the
languages spoken there with their population shares.

The table is built from public sources and cached, so that country names and
borders can follow the sources without a new webmeta release:

1. ``WEBMETA_GEO_TABLE`` (a path), if set: always used. Pin a table this way for
   a reproducible rerun.
2. The cached table in ``~/.cache/webmeta/`` (``WEBMETA_CACHE_DIR`` overrides),
   if it is younger than ``MAX_AGE_DAYS``.
3. Otherwise it is rebuilt from the sources, which needs the ``geo`` extra
   (geopandas) and network access, and cached.
4. If that is not possible: the stale cache, or the snapshot shipped with webmeta.

Every exported dataset records which table it used (``table_info()``).

Sources: Natural Earth 10m admin-0 countries, with map units for the few
territories the countries file folds into another country (public domain);
Unicode CLDR territory information for languages (Unicode License); SIL's ISO
639-3 code table to turn CLDR's two-letter codes into the three-letter codes
corpora such as HPLT use.

The geolocation (Natural Earth regions and label points) follows a TurkuNLP
geolocator for ccTLDs.
"""

import datetime as _dt
import json
import os
import warnings
from pathlib import Path

MAX_AGE_DAYS = 90
TABLE_NAME = "countries.json"
SNAPSHOT = Path(__file__).parent / "data" / TABLE_NAME

SOURCES = {
    "countries": "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip",
    "map_units": "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_map_units.zip",
    "cldr_territories": "https://raw.githubusercontent.com/unicode-org/cldr-json/main/cldr-json/"
                        "cldr-core/supplemental/territoryInfo.json",
    "iso639_3": "https://iso639-3.sil.org/sites/iso639-3/files/downloads/iso-639-3.tab",
}

_TABLE = None


# ------------------------------------------------------------------ lookup

def lookup(code):
    """The table row for an ISO 3166-1 alpha-2 code ('FI'), or None."""
    if not code:
        return None
    return table()["countries"].get(code.upper())


def region(code):
    row = lookup(code)
    return row["region"] if row else None


def subregion(code):
    row = lookup(code)
    return row["subregion"] if row else None


def table_info():
    """Where the loaded table came from: build date, sources, and how it was loaded."""
    t = table()
    return {k: v for k, v in t.items() if k != "countries"}


# ------------------------------------------------------------------ loading

def cache_dir():
    d = os.environ.get("WEBMETA_CACHE_DIR")
    if d:
        return Path(d)
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "webmeta"


def table(refresh="auto"):
    """The country table, loaded once per process.

    refresh  "auto"   rebuild when the cache is missing or older than MAX_AGE_DAYS
             "never"  use the cache or the snapshot as they are
             "force"  rebuild now
    """
    global _TABLE
    if _TABLE is not None and refresh != "force":
        return _TABLE
    _TABLE = _load(refresh)
    return _TABLE


def _load(refresh):
    pinned = os.environ.get("WEBMETA_GEO_TABLE")
    if pinned:
        return _read(Path(pinned), "pinned")
    cached = cache_dir() / TABLE_NAME
    fresh = cached.exists() and _age_days(_read(cached, "cache")) < MAX_AGE_DAYS
    if fresh and refresh != "force":
        return _read(cached, "cache")
    if refresh in ("auto", "force"):
        try:
            t = build()
            cached.parent.mkdir(parents=True, exist_ok=True)
            tmp = cached.with_suffix(".tmp")
            tmp.write_text(json.dumps(t, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, cached)
            return _read(cached, "rebuilt")
        except Exception as e:    # no geopandas, no network, a source changed shape
            if refresh == "force":
                raise
            warnings.warn(f"webmeta: could not rebuild the country table ({e}); "
                          "using the cached or shipped copy", stacklevel=3)
    if cached.exists():
        return _read(cached, "stale cache")
    return _read(SNAPSHOT, "snapshot")


def _read(path, how):
    t = json.loads(Path(path).read_text(encoding="utf-8"))
    t["loaded_from"] = {"path": str(path), "how": how}
    return t


def _age_days(t):
    built = _dt.datetime.fromisoformat(t["built"])
    return (_dt.datetime.now(_dt.timezone.utc) - built).total_seconds() / 86400


# ------------------------------------------------------------------ building

def build(sources=SOURCES):
    """Build the table from the sources. Needs geopandas (the ``geo`` extra) and network."""
    import geopandas as gpd
    from shapely.ops import polylabel

    from .country import ISO_ALPHA2

    countries = {}
    for key in ("countries", "map_units"):          # map units only fill gaps
        world = gpd.read_file(sources[key])
        world = world[world["ISO_A2_EH"].isin(ISO_ALPHA2) & ~world["ISO_A2_EH"].isin(countries)]
        for code, part in world.groupby("ISO_A2_EH"):
            geom = part.geometry.union_all() if len(part) > 1 else part.geometry.iloc[0]
            first = part.iloc[0]
            point = polylabel(geom, tolerance=0.01)  # a point inside the country, ~1 km precision
            countries[code] = {
                "name": first["ADMIN"] if len(part) > 1 else first["NAME"],
                "region": first["REGION_UN"],
                "subregion": first["SUBREGION"],
                "lon": round(point.x, 4),
                "lat": round(point.y, 4),
            }

    iso3 = {}
    for i, line in enumerate(_fetch(sources["iso639_3"]).decode("utf-8").splitlines()):
        cols = line.split("\t")
        if i and len(cols) > 3:
            iso3[cols[0]] = cols[0]
            if cols[3]:
                iso3[cols[3]] = cols[0]
    cldr = json.loads(_fetch(sources["cldr_territories"]))["supplemental"]
    for code, info in cldr["territoryInfo"].items():
        if code not in countries:
            continue
        langs = {}
        for lang, d in info.get("languagePopulation", {}).items():
            three = iso3.get(lang.split("_")[0])
            if three:
                share = float(d.get("_populationPercent", 0)) / 100
                langs[three] = max(langs.get(three, 0.0), round(share, 6))
        countries[code]["languages"] = dict(sorted(langs.items(), key=lambda kv: -kv[1]))

    return {
        "built": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "sources": dict(sources),
        "cldr_version": cldr.get("version", {}).get("_cldrVersion"),
        "licences": "Natural Earth: public domain. CLDR: Unicode License v3. ISO 639-3 code table: SIL.",
        "countries": dict(sorted(countries.items())),
    }


def _fetch(url):
    import urllib.request
    from . import __version__
    req = urllib.request.Request(url, headers={"User-Agent": f"webmeta/{__version__}"})
    with urllib.request.urlopen(req, timeout=120) as fh:
        return fh.read()
