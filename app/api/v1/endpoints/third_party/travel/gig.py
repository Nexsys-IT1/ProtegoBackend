from typing import Dict, Any, List, Optional
from datetime import date, datetime
import json
import requests
from sqlalchemy.orm import Session

from app.schemas.lob.travel import TravelInsuranceRequest
from app.db.models.third_party_api import ThirdPartyAuth
from app.api.v1.endpoints.third_party.travel.auth import authenticate_gulf


GIG_PRODUCTS_URL = "https://apigw.pp.atom.gig-gulf.com/apis/travel/v1/products"


# -------------------------------------------------------------------
# GIG cover id → CDM coverage fields (for response mapping)
# -------------------------------------------------------------------
GIG_COVER_ID_MAP = {
    "emergency_medical_amount": "ZT01",
    "repatriation_expenses_amount": "ZT02",
    "delayed_departure_amount": "ZT209",
    "delayed_baggage_amount": "ZT210",
    "loss_of_id_amount": "ZT213",
}


# -------------------------------------------------------------------
# Helpers for response mapping
# -------------------------------------------------------------------
def _extract_premium(plan: Dict[str, Any]) -> Optional[int]:
    premium_block = (plan.get("premium") or plan.get("originalPremium") or {})
    premium_data = premium_block.get("premium") or {}
    amount = premium_data.get("amount")
    if amount:
        return int(amount)

    for c in plan.get("covers", []):
        cp = c.get("coverPremium")
        if cp and cp.get("amount"):
            return int(cp["amount"])

    return None


def _find_cover(covers: List[Dict[str, Any]], cover_id: str) -> Optional[Dict[str, Any]]:
    for c in covers:
        if str(c.get("id")) == str(cover_id):
            return c
    return None


def _extract_amount_from_cover(cover: Optional[Dict[str, Any]]) -> Optional[str]:
    if not cover:
        return None

    if "sumInsured" in cover and cover["sumInsured"].get("amount") is not None:
        amount = cover["sumInsured"]["amount"]
        return f"AED {int(amount):,}"

    benefits = cover.get("benefits") or []
    if benefits:
        return benefits[0].get("limit")

    return None


def _map_plan_card_gig(plan: Dict[str, Any]) -> Dict[str, Any]:
    plan_name = plan["product"]["value"]
    covers = plan.get("covers", [])
    premium = _extract_premium(plan)

    # Resolve covers by IDs
    cover_em_med = _find_cover(covers, "ZT01")
    cover_rep = _find_cover(covers, "ZT02")
    cover_delayed_dep = _find_cover(covers, "ZT209")
    cover_delayed_baggage = _find_cover(covers, "ZT210")
    cover_loss_passport = _find_cover(covers, "ZT213")

    return {
        "insurer_code": "GIG",
        "insurer_name": "GIG Gulf",
        "plan_name": plan_name,
        "currency": "AED",
        "premium_total": premium,
        "coverage_summary": {
            "emergency": {
                "emergency_medical_amount": _extract_amount_from_cover(cover_em_med),
                "delayed_departure_amount": _extract_amount_from_cover(cover_delayed_dep),
            },
            "accident": {
                "personal_accident_amount": None,  # not provided explicitly by GIG here
                "repatriation_expenses_amount": _extract_amount_from_cover(cover_rep),
            },
            "additional": {
                "delayed_baggage_amount": _extract_amount_from_cover(cover_delayed_baggage),
                "loss_of_id_amount": _extract_amount_from_cover(cover_loss_passport),
            },
        },
    }


# -------------------------------------------------------------------
# Helpers for request building
# -------------------------------------------------------------------
def _to_iso_date(val: Any) -> str:
    if isinstance(val, date):
        return val.isoformat()
    return str(val)


def _build_insured_members(travellers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    members: List[Dict[str, Any]] = []
    for t in travellers:
        dob = _to_iso_date(t.get("date_of_birth"))
        members.append(
            {
                "person": {
                    "birthDate": dob,
                    "gender": {"code": "M", "value": "Male"},
                }
            }
        )
    return members


def build_gig_request(canonical_payload: Dict[str, Any]) -> Dict[str, Any]:
    travel = canonical_payload["travel_details"]
    # personal = canonical_payload["personal_details"]  # not used for GIG request (for now)

    # 1) Dates
    start_iso = _to_iso_date(travel["travel_dates"]["start_date"])
    end_iso = _to_iso_date(travel["travel_dates"]["end_date"])

    creation_date = f"{start_iso}T00:00:01"
    effective_date = f"{start_iso}T00:00:00"
    expiration_date = f"{end_iso}T23:59:59"

    # 2) Policy type (static for this product)
    policy_type = {
        "code": "1",
        "value": "Single Trip",
    }

    # 3) Origin / Destination (Inbound: origin = CDM departure, destination = UAE)
    origin_code = str(travel.get("departure", "")).strip() or "AUS"
    origin_value = origin_code  # you can later map this to full country name

    destination_countries = [
        {
            "code": "ARE",
            "value": "United Arab Emirates",
        }
    ]

    # 4) Area of coverage (always inbound for this product)
    area_of_coverage = {
        "code": "IB",
        "value": "Inbound",
    }

    # 5) Insured members from travellers
    insured_members = _build_insured_members(travel.get("travellers", []))

    # 6) Static product config
    gig_request = {
        "policySchedule": {
            "creationDate": creation_date,
            "effectiveDate": effective_date,
            "expirationDate": expiration_date,
            "policyType": policy_type,
        },
        "travelInformation": {
            "originCountry": {
                "code": origin_code,
                "value": origin_value,
            },
            "destinationCountries": destination_countries,
            "areaOfCoverage": area_of_coverage,
        },
        "insuredMembers": insured_members,
        "schemeId": "64824A00001",
        "branchId": {
            "code": "13",
            "value": "Dubai",
        },
        "includeOriginalPremium": "true",
        "includeOptionalCoverPremium": "true",
    }

    return gig_request


# -------------------------------------------------------------------
# Token retrieval (using your existing authenticate_gulf logic)
# -------------------------------------------------------------------
def get_gig_token(db: Session) -> Optional[str]:
    provider = (
        db.query(ThirdPartyAuth)
        .filter(ThirdPartyAuth.name.ilike("%gulf%"))
        .first()
    )

    if not provider:
        print("[GIG] ThirdPartyAuth provider not found (name like '%gulf%')")
        return None
    

    # authenticate_gulf will either refresh or return existing token
    token = authenticate_gulf(db, provider)

    if not token:
        print("Failed to authenticate GIG")
        return None
    return provider.auth_config.get("token")


# -------------------------------------------------------------------
# Public entrypoint used by /get-quotes SSE
# -------------------------------------------------------------------
def get_gig_quotes(payload: TravelInsuranceRequest, db: Session) -> Dict[str, Any]:
    cdm = payload.model_dump()
    gig_request_body = build_gig_request(cdm)

    token = get_gig_token(db)
    if not token:
        return {
            "insurer": "GIG",
            "insurer_name": "GIG Gulf",
            "plans": [],
            "raw_insurer_response": None,
            "error": "Missing or invalid GIG token",
        }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "opCo": "uae",
    }

    try:
        response = requests.post(
            GIG_PRODUCTS_URL,
            json=gig_request_body,
            headers=headers,
            timeout=30,
        )
    except Exception as exc:
        return {
            "insurer": "GIG",
            "insurer_name": "GIG Gulf",
            "plans": [],
            "raw_insurer_response": None,
            "error": f"Request to GIG failed: {exc}",
        }

    try:
        resp_data = response.json()
    except Exception:
        resp_data = {"error": "Invalid JSON", "raw": response.text}

    # Optional: debug log
    print("\n===== GIG RAW RESPONSE =====")
    print(json.dumps(resp_data, indent=2))
    print("===== END GIG RESPONSE =====\n")

    if response.status_code >= 400:
        return {
            "insurer": "GIG",
            "insurer_name": "GIG Gulf",
            "plans": [],
            "raw_insurer_response": resp_data,
            "error": f"GIG returned HTTP {response.status_code}",
        }

    plans_raw = resp_data.get("eligiblePlans") or []
    mapped_plans = [_map_plan_card_gig(p) for p in plans_raw]

    return {
        "insurer": "GIG",
        "insurer_name": "GIG Gulf",
        "plans": mapped_plans,
        "raw_insurer_response": resp_data,
        "error": None,
    }
