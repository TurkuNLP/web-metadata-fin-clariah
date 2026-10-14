"""Country step: a country signal from the URL's top-level domain.

First version. A country-code top-level domain (ccTLD)
is read as the country; generic domains (.com, .org, ...) give no country.
Some ccTLDs are marketed worldwide as generic ones (.io, .co, .tv, ...); they
are treated as no country, because a .io site says little about Indian Ocean
territory. The result is a signal, not a ground truth.
"""

from urllib.parse import urlsplit

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

# ccTLDs commonly used as generic domains. Edit to taste.
VANITY = {"io", "co", "tv", "me", "ai", "ly", "fm", "cc", "ws", "to", "gg", "sh", "am", "nu", "tk"}


def tld(url):
    """The top-level domain of a URL, lowercased ('https://yle.fi/a' -> 'fi')."""
    if not url:
        return None
    host = urlsplit(url if "//" in url else "//" + url).hostname or ""
    host = host.rstrip(".")
    if not host or host.replace(".", "").isdigit():
        return None
    return host.rsplit(".", 1)[-1].lower()


def country(url, vanity=VANITY):
    """ISO 3166-1 alpha-2 country for a URL, or None when the domain names none."""
    t = tld(url)
    if not t or t in vanity:
        return None
    code = TLD_TO_ISO.get(t, t.upper())
    return code if code in ISO_ALPHA2 else None


def annotate(record):
    return {"tld": tld(record.get("url")), "country": country(record.get("url"))}


def matches(meta, country=None):
    """country: an ISO code or a list of them; None = any (including unknown)."""
    if country is None:
        return True
    wanted = {country.upper()} if isinstance(country, str) else {c.upper() for c in country}
    return meta["country"] in wanted
