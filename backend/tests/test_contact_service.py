from types import SimpleNamespace as NS
import uuid
import pytest
from app.services import contact_service as cs


@pytest.mark.parametrize("raw,exp", [
    ("98765 43210", "+919876543210"), ("+91 98765-43210", "+919876543210"),
    ("09876543210", "+919876543210"), ("919876543210", "+919876543210"),
    ("+1 (415) 555-2671", "+14155552671"), ("00441234567890", "+441234567890"),
    ("12345", None), ("abc", None), ("", None), (None, None),
    ("98766555", None), ("+9198766555", None), ("98765x4321", None), ("1234567890", None),
    ("022 2345 6789", "+912223456789"), ("+44 20 7946 0958", "+442079460958"),
])
def test_normalize_phone(raw, exp):
    assert cs.normalize_phone(raw) == exp


def test_split_and_full_name():
    assert cs.split_name("  Ravi  Kumar Singh ") == ("Ravi", "Kumar Singh")
    assert cs.split_name("Madonna") == ("Madonna", None)
    assert cs.full_name("Ravi", None) == "Ravi"


def test_duplicate_reasons():
    a = {"first_name": "Ravi", "last_name": "Kumar", "email": "R@x.com", "phone_primary": "+919876543210"}
    assert cs.duplicate_reasons(a, dict(a)) == ["same primary number", "same email", "same name"]
    b = {"first_name": "Sita", "last_name": None, "email": None, "phone_primary": "+911111111111"}
    assert cs.duplicate_reasons(a, b) == []
    assert cs.duplicate_reasons({**a, "email": "r@X.com"}, {**b, "email": "R@x.COM"}) == ["same email"]


def D(decision, slot): return {"decision": decision, "approver_slot": slot}


def test_decide_state():
    assert cs.decide_state([]) == "pending"
    assert cs.decide_state([D("approve", "manager")]) == "pending"
    assert cs.decide_state([D("approve", "governance")]) == "pending"
    assert cs.decide_state([D("approve", "manager"), D("approve", "governance")]) == "approved"
    assert cs.decide_state([D("approve", "inside_sales"), D("approve", "manager")]) == "approved"
    assert cs.decide_state([D("approve", "manager"), D("reject", "governance")]) == "rejected"
    assert cs.decide_state([D("reject", "manager")]) == "rejected"


def U(role, manager_id=None):
    return NS(id=uuid.uuid4(), role=role, manager_id=manager_id)


def test_approver_slot():
    mgr = U("manager"); req = U("rep", mgr.id)
    assert cs.approver_slot(mgr, req, set()) == "manager"
    assert cs.approver_slot(U("governance"), req, set()) == "governance"
    assert cs.approver_slot(U("inside_sales"), req, set()) == "inside_sales"
    assert cs.approver_slot(req, req, set()) is None                  # own request
    assert cs.approver_slot(U("rep"), req, set()) is None             # random rep
    assert cs.approver_slot(U("manager"), req, set()) is None         # someone else's manager
    orphan = U("rep")                                                 # no manager
    assert cs.approver_slot(U("business_head"), orphan, set()) == "manager"
    assert cs.approver_slot(U("super_admin"), req, set()) == "manager"
    assert cs.approver_slot(U("super_admin"), req, {"manager"}) == "governance"


def test_can_complete_contact():
    assert cs.can_complete_contact(NS(phone_primary="+919876543210", incomplete=False))
    assert not cs.can_complete_contact(NS(phone_primary=None, incomplete=True))
    assert not cs.can_complete_contact(NS(phone_primary="+919876543210", incomplete=True))


@pytest.mark.parametrize("name,ok", [
    ("ab kumar", True), ("Dr. O'Neil-Smith", True), ("Åsa Öberg", True), ("राहुल शर्मा", True),
    ("R2D2", False), ("x@y", False), ("", False), ("   ", False), ("a" * 101, False),
])
def test_valid_person_name(name, ok):
    if ok:
        assert cs.valid_person_name(name)
    else:
        with pytest.raises(ValueError):
            cs.valid_person_name(name)


def test_valid_person_name_optional_blank():
    assert cs.valid_person_name("", required=False) is None


def test_valid_linkedin():
    assert cs.valid_linkedin("https://www.linkedin.com/in/ab-kumar")
    assert cs.valid_linkedin("") is None
    with pytest.raises(ValueError):
        cs.valid_linkedin("https://evil.com/in/x")


def test_company_key_dedupes_legal_suffixes():
    assert cs.company_key("Acme Pvt. Ltd.") == cs.company_key("ACME private limited") == cs.company_key("acme")
    assert cs.company_key("abc company") != cs.company_key("xyz company")
