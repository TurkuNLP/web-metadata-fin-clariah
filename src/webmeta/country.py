"""Country step: a country signal from the URL's top-level domain.

A country-code top-level domain (ccTLD) is read as the country; generic
domains (.com, .org, ...) give no country. Some ccTLDs are sold worldwide as
generic ones (.tv, .io, .me): on those, only documents in the country's own
languages get the country (``webmeta.cctld``, measured from corpus counts).
The result is a signal, not a ground truth.
"""

from urllib.parse import urlsplit

from . import language as _language

# ISO 3166-1 alpha-2 codes, all of which are also ccTLDs (lowercased).
ISO_ALPHA2 = set("""
AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL
BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV
CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD
GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM
IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK
LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW
MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR
PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS
ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY
UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW
""".split())

# ccTLDs whose code differs from the ISO code.
TLD_TO_ISO = {"uk": "GB"}


def tld(url):
    """The top-level domain of a URL, lowercased ('https://yle.fi/a' -> 'fi')."""
    if not url:
        return None
    host = urlsplit(url if "//" in url else "//" + url).hostname or ""
    host = host.rstrip(".")
    if not host or host.replace(".", "").isdigit():
        return None
    return host.rsplit(".", 1)[-1].lower()


def code(url):
    """The ISO 3166-1 alpha-2 code a URL's domain names, or None ('https://yle.fi/a' -> 'FI')."""
    t = tld(url)
    if not t:
        return None
    c = TLD_TO_ISO.get(t, t.upper())
    return c if c in ISO_ALPHA2 else None


def country(url, lang=None):
    """The country of a document at ``url`` written in ``lang``, or None.

    On a code used worldwide (``webmeta.cctld``), only a document in one of the
    country's own languages gets the country; without ``lang`` it gets none.
    """
    from . import cctld
    c = code(url)
    if c is None:
        return None
    return c if cctld.gives_country(c, _language.base(lang) if lang else None) else None


def annotate(record):
    """tld, country (with how the code is used), and from the country table
    (webmeta.geo): its name, UN region and subregion."""
    from . import cctld, geo
    url = record.get("url")
    c = country(url, record.get("lang"))
    row = geo.lookup(c) or {}
    named = code(url)
    use = cctld.use()["codes"].get(named, {}).get("class", "national") if named else None
    return {"tld": tld(url), "country": c, "tld_use": use, "country_name": row.get("name"),
            "region": row.get("region"), "subregion": row.get("subregion")}


def matches(meta, country=None, region=None, subregion=None):
    """country: ISO code(s); region, subregion: UN names, e.g. "Europe", "Northern Europe".
    Each is a value or a list of them; None = any (including unknown)."""
    def ok(value, wanted, fold):
        if wanted is None:
            return True
        wanted = [wanted] if isinstance(wanted, str) else wanted
        return value is not None and fold(value) in {fold(w) for w in wanted}
    return (ok(meta["country"], country, str.upper)
            and ok(meta.get("region"), region, str.casefold)
            and ok(meta.get("subregion"), subregion, str.casefold))
