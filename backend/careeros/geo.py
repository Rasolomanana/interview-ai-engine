"""Deduce country / province / city from a free-text location (aggregated statistics only)."""
import re
import unicodedata

PROVINCES = {"Québec": ["quebec", "qc", "pq"], "Ontario": ["ontario", "on"], "Colombie-Britannique": ["colombie britannique", "british columbia", "bc"],
             "Alberta": ["alberta", "ab"], "Manitoba": ["manitoba", "mb"], "Saskatchewan": ["saskatchewan", "sk"], "Nouvelle-Écosse": ["nouvelle ecosse", "nova scotia", "ns"],
             "Nouveau-Brunswick": ["nouveau brunswick", "new brunswick", "nb"], "Terre-Neuve-et-Labrador": ["terre neuve", "newfoundland", "nl"],
             "Île-du-Prince-Édouard": ["ile du prince edouard", "prince edward island", "pei", "pe"]}
CITIES = {"Montréal": "Québec", "Laval": "Québec", "Longueuil": "Québec", "Gatineau": "Québec", "Sherbrooke": "Québec", "Trois-Rivières": "Québec",
          "Lévis": "Québec", "Saguenay": "Québec", "Terrebonne": "Québec", "Brossard": "Québec", "Drummondville": "Québec", "Saint-Jérôme": "Québec",
          "Granby": "Québec", "Blainville": "Québec", "Repentigny": "Québec", "Boucherville": "Québec", "Rimouski": "Québec", "Québec": "Québec",
          "Toronto": "Ontario", "Ottawa": "Ontario", "Mississauga": "Ontario", "Brampton": "Ontario", "Hamilton": "Ontario", "London": "Ontario", "Markham": "Ontario",
          "Vancouver": "Colombie-Britannique", "Surrey": "Colombie-Britannique", "Victoria": "Colombie-Britannique", "Burnaby": "Colombie-Britannique",
          "Calgary": "Alberta", "Edmonton": "Alberta", "Winnipeg": "Manitoba", "Regina": "Saskatchewan", "Saskatoon": "Saskatchewan",
          "Halifax": "Nouvelle-Écosse", "Moncton": "Nouveau-Brunswick", "Fredericton": "Nouveau-Brunswick", "St. John's": "Terre-Neuve-et-Labrador",
          "Charlottetown": "Île-du-Prince-Édouard"}
COUNTRIES = {"Canada": ["canada"], "France": ["france"], "Belgique": ["belgique", "belgium"], "Suisse": ["suisse", "switzerland"],
             "États-Unis": ["etats unis", "usa", "united states", "us"], "Maroc": ["maroc", "morocco"], "Tunisie": ["tunisie", "tunisia"],
             "Algérie": ["algerie", "algeria"], "Sénégal": ["senegal"], "Côte d'Ivoire": ["cote d ivoire", "ivory coast"], "Haïti": ["haiti"], "Cameroun": ["cameroun", "cameroon"]}
FOREIGN_CITIES = {"Paris": "France", "Lyon": "France", "Marseille": "France", "Bruxelles": "Belgique", "Genève": "Suisse", "Casablanca": "Maroc",
                  "Rabat": "Maroc", "Tunis": "Tunisie", "Alger": "Algérie", "Dakar": "Sénégal", "Abidjan": "Côte d'Ivoire", "New York": "États-Unis"}


def _n(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()).strip()


def _has(text: str, term: str) -> bool:
    return f" {_n(term)} " in f" {text} "


def deduce(location: str) -> dict:
    t = _n(location)
    out = {"country": "", "province": "", "city": ""}
    if not t:
        return out
    for city, prov in sorted(CITIES.items(), key=lambda x: -len(x[0])):
        if _has(t, city) and not (city == "Québec" and not re.search(r"(ville de|city of)\s+quebec|quebec city|^quebec (qc|quebec)\b", t)):
            out.update(city=city, province=prov, country="Canada")
            break
    for city, country in FOREIGN_CITIES.items():
        if not out["city"] and _has(t, city):
            out.update(city=city, country=country)
    if not out["province"]:
        for prov, keys in PROVINCES.items():
            if any(_has(t, k) for k in keys if len(k) > 2) or any(re.search(rf"(,|\s)\s*{k}\s*$", t) for k in keys if len(k) == 2):
                out.update(province=prov, country="Canada")
                break
    if not out["country"]:
        out["country"] = next((c for c, keys in COUNTRIES.items() if any(_has(t, k) for k in keys)), "")
    return out


def member_geo(profile: dict, radar_location: str = "") -> dict:
    """Member-entered fields first, then deduction from Career Memory location, then the Radar location."""
    geo = {k: (profile.get(k) or "").strip() for k in ("country", "province", "city")}
    if all(geo.values()):
        return geo
    for src in (profile.get("location") or "", radar_location or ""):
        d = deduce(src)
        for k in geo:
            geo[k] = geo[k] or d[k]
    if geo["province"] and not geo["country"]:
        geo["country"] = "Canada" if geo["province"] in PROVINCES else ""
    return geo
