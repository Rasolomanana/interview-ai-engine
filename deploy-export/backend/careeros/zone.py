"""Geographic zone of the Radar: keep offers near the member's Radar location (city ≤ RADIUS_KM, else province, else country)."""
import math
import re

from careeros.geo import COUNTRIES, PROVINCES, _has, _n

RADIUS_KM = 100
VERSION = 3
RADII = ("25", "50", "100", "200", "province", "country")
# city -> (lat, lon, province or "", country)
PLACES = {
    "Montréal": (45.50, -73.57, "Québec", "Canada"), "Laval": (45.57, -73.69, "Québec", "Canada"), "Longueuil": (45.53, -73.52, "Québec", "Canada"),
    "Brossard": (45.46, -73.47, "Québec", "Canada"), "Candiac": (45.39, -73.51, "Québec", "Canada"), "La Prairie": (45.42, -73.50, "Québec", "Canada"),
    "Saint-Amable": (45.65, -73.30, "Québec", "Canada"), "Boucherville": (45.59, -73.44, "Québec", "Canada"), "Varennes": (45.68, -73.43, "Québec", "Canada"),
    "Sainte-Julie": (45.58, -73.33, "Québec", "Canada"), "Saint-Bruno-de-Montarville": (45.53, -73.35, "Québec", "Canada"), "Chambly": (45.45, -73.29, "Québec", "Canada"),
    "Beloeil": (45.57, -73.20, "Québec", "Canada"), "Saint-Hyacinthe": (45.63, -72.96, "Québec", "Canada"), "Granby": (45.40, -72.73, "Québec", "Canada"),
    "Saint-Jean-sur-Richelieu": (45.31, -73.26, "Québec", "Canada"), "Châteauguay": (45.38, -73.75, "Québec", "Canada"), "Delson": (45.37, -73.55, "Québec", "Canada"),
    "Salaberry-de-Valleyfield": (45.25, -74.13, "Québec", "Canada"), "Vaudreuil-Dorion": (45.40, -74.03, "Québec", "Canada"), "Dorval": (45.45, -73.75, "Québec", "Canada"),
    "Pointe-Claire": (45.45, -73.82, "Québec", "Canada"), "Lachine": (45.43, -73.67, "Québec", "Canada"), "Saint-Laurent": (45.51, -73.68, "Québec", "Canada"),
    "Anjou": (45.61, -73.56, "Québec", "Canada"), "Terrebonne": (45.70, -73.65, "Québec", "Canada"), "Mascouche": (45.75, -73.60, "Québec", "Canada"),
    "Repentigny": (45.74, -73.45, "Québec", "Canada"), "Blainville": (45.67, -73.88, "Québec", "Canada"), "Boisbriand": (45.62, -73.84, "Québec", "Canada"),
    "Mirabel": (45.65, -74.08, "Québec", "Canada"), "Saint-Jérôme": (45.78, -74.00, "Québec", "Canada"), "Joliette": (46.02, -73.44, "Québec", "Canada"),
    "Sorel-Tracy": (46.04, -73.11, "Québec", "Canada"), "Drummondville": (45.88, -72.48, "Québec", "Canada"), "Sherbrooke": (45.40, -71.89, "Québec", "Canada"),
    "Trois-Rivières": (46.34, -72.54, "Québec", "Canada"), "Québec": (46.81, -71.21, "Québec", "Canada"), "Lévis": (46.80, -71.18, "Québec", "Canada"),
    "Gatineau": (45.48, -75.70, "Québec", "Canada"), "Saguenay": (48.43, -71.07, "Québec", "Canada"), "Rimouski": (48.45, -68.52, "Québec", "Canada"),
    "Toronto": (43.65, -79.38, "Ontario", "Canada"), "Mississauga": (43.59, -79.64, "Ontario", "Canada"), "Brampton": (43.73, -79.76, "Ontario", "Canada"),
    "Markham": (43.86, -79.34, "Ontario", "Canada"), "Vaughan": (43.84, -79.50, "Ontario", "Canada"), "Oakville": (43.47, -79.69, "Ontario", "Canada"),
    "Hamilton": (43.26, -79.87, "Ontario", "Canada"), "Ottawa": (45.42, -75.70, "Ontario", "Canada"), "London": (42.98, -81.25, "Ontario", "Canada"),
    "Kitchener": (43.45, -80.49, "Ontario", "Canada"), "Waterloo": (43.46, -80.52, "Ontario", "Canada"), "Windsor": (42.31, -83.04, "Ontario", "Canada"),
    "Cornwall": (45.02, -74.73, "Ontario", "Canada"), "Kingston": (44.23, -76.49, "Ontario", "Canada"),
    "Vancouver": (49.28, -123.12, "Colombie-Britannique", "Canada"), "Surrey": (49.19, -122.85, "Colombie-Britannique", "Canada"),
    "Burnaby": (49.25, -122.98, "Colombie-Britannique", "Canada"), "Richmond": (49.17, -123.14, "Colombie-Britannique", "Canada"),
    "Delta": (49.09, -123.06, "Colombie-Britannique", "Canada"), "Victoria": (48.43, -123.37, "Colombie-Britannique", "Canada"),
    "Calgary": (51.05, -114.07, "Alberta", "Canada"), "Edmonton": (53.55, -113.49, "Alberta", "Canada"), "Winnipeg": (49.90, -97.14, "Manitoba", "Canada"),
    "Regina": (50.45, -104.62, "Saskatchewan", "Canada"), "Saskatoon": (52.13, -106.67, "Saskatchewan", "Canada"), "Halifax": (44.65, -63.58, "Nouvelle-Écosse", "Canada"),
    "Moncton": (46.09, -64.78, "Nouveau-Brunswick", "Canada"), "Fredericton": (45.96, -66.64, "Nouveau-Brunswick", "Canada"),
    "St. John's": (47.56, -52.71, "Terre-Neuve-et-Labrador", "Canada"), "Charlottetown": (46.24, -63.13, "Île-du-Prince-Édouard", "Canada"),
    "St-Hyacinthe": (45.63, -72.96, "Québec", "Canada"), "St-Jérôme": (45.78, -74.00, "Québec", "Canada"), "St-Jean-sur-Richelieu": (45.31, -73.26, "Québec", "Canada"),
    "Sainte-Anne-des-Monts": (49.12, -66.49, "Québec", "Canada"), "Chicoutimi": (48.43, -71.07, "Québec", "Canada"), "Jonquière": (48.42, -71.25, "Québec", "Canada"),
    "Alma": (48.55, -71.65, "Québec", "Canada"), "Rouyn-Noranda": (48.24, -79.02, "Québec", "Canada"), "Val-d'Or": (48.10, -77.78, "Québec", "Canada"),
    "Amos": (48.57, -78.12, "Québec", "Canada"), "Gaspé": (48.83, -64.48, "Québec", "Canada"), "Sept-Îles": (50.22, -66.38, "Québec", "Canada"),
    "Baie-Comeau": (49.22, -68.15, "Québec", "Canada"), "Matane": (48.85, -67.53, "Québec", "Canada"), "Rivière-du-Loup": (47.83, -69.53, "Québec", "Canada"),
    "Victoriaville": (46.06, -71.96, "Québec", "Canada"), "Thetford Mines": (46.09, -71.30, "Québec", "Canada"), "Saint-Georges": (46.12, -70.67, "Québec", "Canada"),
    "Shawinigan": (46.57, -72.75, "Québec", "Canada"), "La Tuque": (47.44, -72.78, "Québec", "Canada"), "Magog": (45.27, -72.15, "Québec", "Canada"),
    "Cowansville": (45.20, -72.75, "Québec", "Canada"), "Bromont": (45.32, -72.65, "Québec", "Canada"), "Mont-Laurier": (46.55, -75.50, "Québec", "Canada"),
    "Mont-Tremblant": (46.12, -74.60, "Québec", "Canada"), "Sainte-Agathe-des-Monts": (46.05, -74.28, "Québec", "Canada"), "Lachute": (45.65, -74.33, "Québec", "Canada"),
    "Saint-Eustache": (45.56, -73.90, "Québec", "Canada"), "Sainte-Thérèse": (45.64, -73.83, "Québec", "Canada"), "Rosemère": (45.64, -73.80, "Québec", "Canada"),
    "Saint-Constant": (45.37, -73.57, "Québec", "Canada"), "Sainte-Catherine": (45.40, -73.58, "Québec", "Canada"), "Beauharnois": (45.31, -73.87, "Québec", "Canada"),
    "Saint-Lazare": (45.40, -74.13, "Québec", "Canada"), "Kirkland": (45.45, -73.87, "Québec", "Canada"), "Pointe-aux-Trembles": (45.65, -73.50, "Québec", "Canada"),
    "Marieville": (45.43, -73.17, "Québec", "Canada"), "Contrecoeur": (45.85, -73.24, "Québec", "Canada"), "Lavaltrie": (45.88, -73.28, "Québec", "Canada"),
    "L'Assomption": (45.82, -73.43, "Québec", "Canada"), "Berthierville": (46.08, -73.18, "Québec", "Canada"), "Coteau-du-Lac": (45.30, -74.18, "Québec", "Canada"),
    "Valleyfield": (45.25, -74.13, "Québec", "Canada"), "Vaudreuil": (45.40, -74.03, "Québec", "Canada"), "Saint-Bruno": (45.53, -73.35, "Québec", "Canada"),
    "New York": (40.71, -74.01, "", "États-Unis"), "Chattanooga": (35.05, -85.31, "", "États-Unis"), "Chicago": (41.88, -87.63, "", "États-Unis"),
    "Seattle": (47.61, -122.33, "", "États-Unis"), "Boston": (42.36, -71.06, "", "États-Unis"), "Dallas": (32.78, -96.80, "", "États-Unis"),
    "Atlanta": (33.75, -84.39, "", "États-Unis"), "Los Angeles": (34.05, -118.24, "", "États-Unis"), "Miami": (25.76, -80.19, "", "États-Unis"),
    "Paris": (48.86, 2.35, "", "France"), "Lyon": (45.76, 4.84, "", "France"), "Marseille": (43.30, 5.37, "", "France"), "Bruxelles": (50.85, 4.35, "", "Belgique"),
    "Genève": (46.20, 6.14, "", "Suisse"), "London UK": (51.51, -0.13, "", "Royaume-Uni"), "Bucharest": (44.43, 26.10, "", "Roumanie"), "Bucarest": (44.43, 26.10, "", "Roumanie"),
    "Antananarivo": (-18.88, 47.51, "", "Madagascar"), "Casablanca": (33.57, -7.59, "", "Maroc"), "Rabat": (34.02, -6.84, "", "Maroc"), "Tunis": (36.81, 10.18, "", "Tunisie"),
    "Alger": (36.75, 3.06, "", "Algérie"), "Dakar": (14.72, -17.47, "", "Sénégal"), "Abidjan": (5.36, -4.01, "", "Côte d'Ivoire"),
    "Mexico": (19.43, -99.13, "", "Mexique"), "Bangalore": (12.97, 77.59, "", "Inde"), "Bengaluru": (12.97, 77.59, "", "Inde"), "Manila": (14.60, 120.98, "", "Philippines"),
    "Krakow": (50.06, 19.94, "", "Pologne"), "Warsaw": (52.23, 21.01, "", "Pologne"), "Dublin": (53.35, -6.26, "", "Irlande"),
}
MORE_COUNTRIES = {"Roumanie": ["romania", "roumanie"], "Madagascar": ["madagascar"], "Royaume-Uni": ["united kingdom", "royaume uni", "uk", "england"],
                  "Mexique": ["mexico", "mexique"], "Inde": ["india", "inde"], "Philippines": ["philippines"], "Pologne": ["poland", "pologne"],
                  "Irlande": ["ireland", "irlande"], "Allemagne": ["germany", "allemagne"], "Espagne": ["spain", "espagne"], "Brésil": ["brazil", "bresil"],
                  "Chine": ["china", "chine"], "Japon": ["japan", "japon"], "Australie": ["australia", "australie"], "Pays-Bas": ["netherlands", "pays bas"]}
ALL_COUNTRIES = {**COUNTRIES, **MORE_COUNTRIES}
US_STATES = {"al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms", "mo",
             "mt", "ne", "nv", "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy"}
REMOTE = re.compile(r"\b(remote|teletravail|a distance|work from home|virtual)\b")


def _km(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def place(text: str) -> dict:
    """{city, coords, province, country} recognised in a free-text location (empty values if unknown)."""
    t = _n(text)
    out = {"city": "", "coords": None, "province": "", "country": ""}
    if not t:
        return out
    for city, (la, lo, prov, country) in sorted(PLACES.items(), key=lambda x: -len(x[0])):
        name = city.replace(" UK", "")
        if not _has(t, name):
            continue
        if city == "Québec" and not re.search(r"(ville de|city of)\s+quebec|quebec city|^quebec (qc|quebec)\b", t):
            continue
        if city == "London" and re.search(r"\b(uk|united kingdom|england)\b", t):
            continue
        out.update(city=city.replace(" UK", ""), coords=(la, lo), province=prov, country=country)
        return out
    for prov, keys in PROVINCES.items():
        if any(_has(t, k) for k in keys if len(k) > 2) or any(re.search(rf"(^|,|\s)\s*{k}(\s*,?\s*(ca|canada))?\s*$", t) for k in keys if len(k) == 2):
            out.update(province=prov, country="Canada")
            return out
    if re.search(r"(,|\s)\s*(" + "|".join(US_STATES) + r")(\s*,?\s*(us|usa))?\s*$", t) and not re.search(r"\bcanada\b", t):
        out["country"] = "États-Unis"
        return out
    out["country"] = next((c for c, keys in ALL_COUNTRIES.items() if any(_has(t, k) for k in keys)), "")
    return out


def zones_of(st: dict) -> list:
    """Member zones [(location, radius)] : main Radar location + up to 2 extra cities."""
    out = [(st.get("location") or "", str(st.get("radius") or RADIUS_KM))]
    out += [(z.get("location") or "", str(z.get("radius") or RADIUS_KM)) for z in (st.get("extra_zones") or [])[:2]]
    return [(loc.strip(), r if r in RADII else str(RADIUS_KM)) for loc, r in out if loc.strip()]


def label(radius: str) -> str:
    return {"province": "toute la province", "country": "tout le pays"}.get(radius, f"{radius} km")


def check(offer_location: str, zones) -> tuple:
    """(in_zone, reason) — kept if inside any of the member's zones."""
    zones = [(zones, str(RADIUS_KM))] if isinstance(zones, str) else zones
    reason = ""
    for loc, radius in zones or [("", str(RADIUS_KM))]:
        ok, why = _check_one(offer_location, loc, radius)
        if ok:
            return True, why
        reason = reason or why
    return False, reason or "Hors zone"


def _check_one(offer_location: str, member_location: str, radius: str) -> tuple:
    """(in_zone, reason) — any segment of a multi-location offer inside the zone keeps it."""
    m = place(member_location)
    if radius in ("province", "country") and m["city"]:
        m = {**m, "city": "", "coords": None}
    if radius == "country":
        m["province"] = ""
    km = int(radius) if radius.isdigit() else RADIUS_KM
    if not (m["city"] or m["province"] or m["country"]):
        return True, ""
    loc = (offer_location or "").strip()
    if not loc:
        return True, "Lieu non précisé"
    segs = [s for s in re.split(r"\s*[;|/]\s*|\s+(?:or|ou)\s+", loc) if s.strip()] or [loc]
    reason = ""
    for s in segs:
        o = place(s)
        if REMOTE.search(_n(s)) and o["country"] in ("", m["country"]):
            return True, "Télétravail"
        if not (o["city"] or o["province"] or o["country"]):
            return True, "Lieu non reconnu"
        if m["city"] and o["city"] == m["city"]:
            return True, ""
        if o["country"] != m["country"] and m["country"]:
            reason = reason or f"{o['city'] or o['province'] or o['country']} ({o['country']}) hors de votre zone ({m['country']})"
            continue
        if m["coords"] and o["coords"]:
            d = round(_km(m["coords"], o["coords"]))
            if d <= km:
                return True, f"{d} km de {m['city']}"
            reason = reason or f"{o['city']} est à {d} km de {m['city']} (rayon {km} km)"
            continue
        if m["province"] and o["province"]:
            if o["province"] == m["province"] and not (m["coords"] and o["coords"]):
                return True, "" if not m["coords"] else f"Province : {o['province']} (ville non précisée)"
            reason = reason or f"Province {o['province']} hors de votre zone ({m['province']})"
            continue
        if not o["province"] and not o["city"]:  # offer gives only the (same) country
            return True, "" if not (m["city"] or m["province"]) else f"{o['country']} (lieu imprécis)"
        if not m["province"] and not m["city"]:  # member gave only a country
            return True, ""
        reason = reason or f"{o['city'] or s} hors de votre zone"
    return False, reason or "Hors zone"


def signature(zones: list) -> str:
    return f"{VERSION}|" + ";".join(f"{_n(loc)}@{r}" for loc, r in zones)


def nearest(offer_location: str, zones: list) -> dict:
    """Map point of an offer: coordinates of its first recognised city and distance to the closest zone centre."""
    for seg in re.split(r"\s*[;|/]\s*", offer_location or ""):
        o = place(seg)
        if o["coords"]:
            best = None
            for loc, _r in zones:
                c = place(loc)["coords"]
                if c:
                    d = round(_km(c, o["coords"]))
                    if best is None or d < best[0]:
                        best = (d, place(loc)["city"])
            return {"lat": o["coords"][0], "lon": o["coords"][1], "city": o["city"],
                    "distance_km": best[0] if best else None, "from": best[1] if best else ""}
    return {}
