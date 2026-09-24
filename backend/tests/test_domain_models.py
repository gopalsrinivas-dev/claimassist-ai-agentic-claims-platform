"""Core domain mapping contracts independent of PostgreSQL availability."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import CHAR, DateTime, Numeric, String, UniqueConstraint, inspect

from app.domain.models import (
    Claim,
    ClaimLine,
    ClaimStatus,
    Member,
    Policy,
    PolicyIndexStatus,
    PolicyVersion,
    Provider,
)
from app.identity.models import User

DOMAIN_MODELS = (Member, Provider, Policy, PolicyVersion, Claim, ClaimLine)


@pytest.mark.parametrize("model", DOMAIN_MODELS)
def test_domain_primary_keys_and_safe_representation(model: type) -> None:
    table = inspect(model).local_table
    assert list(table.primary_key.columns.keys()) == ["id"]
    assert table.c.id.type.as_uuid is True
    assert "SYNTHETIC_PRIVATE" not in repr(model())
    for column in table.c:
        if isinstance(column.type, String) and not isinstance(column.type, CHAR):
            # The field dictionary specifies no arbitrary varchar length caps.
            assert column.type.length is None or column.name in {"status", "index_status"}


def test_policy_index_status_contract() -> None:
    assert {status.value for status in PolicyIndexStatus} == {
        "PENDING",
        "INDEXING",
        "READY",
        "FAILED",
    }
    column = PolicyVersion.__table__.c.index_status
    assert column.nullable is False
    assert column.default.arg == PolicyIndexStatus.PENDING
    assert str(column.server_default.arg) == "'PENDING'"


@pytest.mark.parametrize("model", (Member, Provider, Policy, PolicyVersion, Claim))
def test_domain_timestamps(model: type) -> None:
    table = inspect(model).local_table
    for name in ("created_at", "updated_at"):
        assert isinstance(table.c[name].type, DateTime)
        assert table.c[name].type.timezone
        assert not table.c[name].nullable
        assert table.c[name].server_default is not None
    assert table.c.updated_at.onupdate is not None
    assert "created_at" not in ClaimLine.__table__.c


def test_claim_money_states_indexes_and_version_mapping() -> None:
    for column in (Claim.__table__.c.claimed_amount, ClaimLine.__table__.c.amount):
        assert isinstance(column.type, Numeric)
        assert (column.type.precision, column.type.scale, column.type.asdecimal) == (14, 2, True)
    assert {state.value for state in ClaimStatus} == {
        "DRAFT",
        "SUBMITTED",
        "PROCESSING",
        "NEED_INFO",
        "READY_FOR_REVIEW",
        "APPROVED",
        "REJECTED",
        "ESCALATED",
    }
    assert {tuple(index.columns.keys()) for index in Claim.__table__.indexes} == {
        ("status", "created_at"),
        ("member_id", "service_start_date"),
        ("provider_id", "service_start_date"),
        ("policy_version_id",),
    }
    assert inspect(Claim).version_id_col is Claim.__table__.c.row_version
    assert Claim.__table__.c.currency.type.length == 3
    assert PolicyVersion.__table__.c.document_sha256.type.length == 64


@pytest.mark.parametrize(
    "model,columns",
    [
        (Member, ("member_number",)),
        (Provider, ("provider_code",)),
        (Policy, ("policy_number",)),
        (PolicyVersion, ("policy_id", "version_code")),
        (Claim, ("claim_number",)),
        (ClaimLine, ("claim_id", "line_number")),
    ],
)
def test_domain_uniqueness(model: type, columns: tuple[str, ...]) -> None:
    assert any(
        isinstance(constraint, UniqueConstraint) and tuple(constraint.columns.keys()) == columns
        for constraint in inspect(model).local_table.constraints
    )


def test_domain_relationships() -> None:
    member = Member(member_number="SYNTHETIC_PRIVATE", display_name="SYNTHETIC_PRIVATE")
    provider = Provider(name="Synthetic provider")
    policy = Policy()
    version = PolicyVersion(policy=policy)
    creator = User()
    claim = Claim(
        member=member,
        provider=provider,
        policy_version=version,
        creator=creator,
        claim_number="SYNTHETIC_PRIVATE",
        status=ClaimStatus.DRAFT,
        claimed_amount=Decimal("12.34"),
        service_start_date=date(2026, 1, 1),
        service_end_date=date(2026, 1, 1),
        currency="USD",
    )
    line = ClaimLine(claim=claim, line_number=1, amount=Decimal("12.34"))
    assert member.claims == provider.claims == version.claims == [claim]
    assert policy.versions == [version]
    assert claim.creator is creator
    assert claim.lines == [line]
    assert "SYNTHETIC_PRIVATE" not in repr(member) + repr(claim)
    for model, name in (
        (Member, "claims"),
        (Provider, "claims"),
        (Policy, "versions"),
        (PolicyVersion, "claims"),
        (Claim, "lines"),
    ):
        assert inspect(model).relationships[name].passive_deletes == "all"
