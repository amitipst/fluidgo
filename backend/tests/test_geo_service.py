import pytest
from app.services import geo_service as g


def test_geo_payload_shape():
    p = g.geo_payload()
    assert len(p["countries"]) > 200 and {"code": "IN", "name": "India"} in p["countries"]
    assert "Karnataka" in p["states"]["IN"] and p["postal_hints"]["IN"]


@pytest.mark.parametrize("country,postal,ok", [
    ("IN", "560001", True), ("IN", "56001", False), ("IN", "060001", False),
    ("US", "94105", True), ("US", "94105-1234", True), ("US", "9410", False),
    ("GB", "sw1a 1aa", True), ("CA", "k1a0b1", True), ("AU", "2000", True),
    ("FR", "75001", True), ("FR", "!", False),
])
def test_postal(country, postal, ok):
    if ok:
        assert g.normalize_postal(country, postal)
    else:
        with pytest.raises(ValueError):
            g.normalize_postal(country, postal)


def test_postal_case_normalised_for_uk():
    assert g.normalize_postal("GB", "sw1a 1aa") == "SW1A 1AA"


def test_validate_address_rules():
    ok = g.validate_address({"city": " Pune ", "state": "Maharashtra", "country": "in", "postal_code": "411001"})
    assert ok["city"] == "Pune" and ok["country"] == "IN"
    with pytest.raises(ValueError):
        g.validate_address({"city": "Pune"})                     # country required
    with pytest.raises(ValueError):
        g.validate_address({"country": "IN", "state": "Narnia"})
    with pytest.raises(ValueError):
        g.validate_address({"country": "ZZ"})
    assert g.validate_address({"country": "US", "state": "Any free text"})["state"] == "Any free text"
