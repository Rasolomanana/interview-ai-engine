# Offers with ISO country codes / postal codes (Workday, SuccessFactors) must be recognised and filtered by the member's zones.
from careeros import zone as Z

ZS = [("Montréal, Qc", "25"), ("Boucherville, Qc", "25"), ("Longeuil, Qc", "25")]


def test_foreign_iso_codes_out_of_zone():
    for loc in ["NEUILLY SUR SEINE, FR", "Gurugram, HR, IN, 122002", "Belleville, 69, FR, 69220", "Melville, SK, CA, S0A 2P0",
                "Lussac les châteaux, 86, FR", "Austin, TX, US", "Toronto, ON, CA"]:
        assert Z.check(loc, ZS)[0] is False, loc


def test_local_and_imprecise_kept():
    for loc in ["Longueuil, QC, CA", "Montréal, QC, H3B 2Y5", "Boucherville, Québec", "Télétravail", "", "Saint-Rémi, CA", "Québec, Québec, CA"]:
        ok = Z.check(loc, ZS)[0] if loc != "Québec, Québec, CA" else Z.place(loc)["city"] == "Québec"
        assert ok, loc


def test_reason_readable():
    assert Z.check("NEUILLY SUR SEINE, FR", ZS)[1] == "France : hors de votre zone (Canada)"


def test_zone_city_typo_tolerated():
    assert Z.member_place("Longeuil, Qc")["city"] == "Longueuil"
    assert Z.check("Sherbrooke, QC", ZS)[0] is False  # the misspelt zone must not widen to the whole province
