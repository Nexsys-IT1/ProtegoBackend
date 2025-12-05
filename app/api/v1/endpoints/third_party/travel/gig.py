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
COUNTRY_CODE_MAP: Dict[str, Dict[str, str]] = {
    "uae": {"code": "ARE", "value": "United Arab Emirates"},
    "united arab emirates": {"code": "ARE", "value": "United Arab Emirates"},
    "australia": {"code": "AUS", "value": "Australia"},
    "aus": {"code": "AUS", "value": "Australia"},
    # add more as needed
}

def _country_to_code_and_name(raw: str) -> Dict[str, str]:
    if not raw:
        return {"code": "", "value": ""}
    key = raw.strip().lower()
    mapped = COUNTRY_CODE_MAP.get(key)
    if mapped:
        return mapped
    return {"code": raw, "value": raw}

GIG_AREA_OF_COVERAGE_MAP = {
    "uae inbound": {"code": "IB", "value": "Inbound"},
    "worldwide": {"code": "WWXUC", "value": "Worldwide excluding USA/Canada"},
    "schengen": {"code": "SCH", "value": "Schengen"},
}

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

    # dates
    start_iso = _to_iso_date(travel["travel_dates"]["start_date"])
    end_iso = _to_iso_date(travel["travel_dates"]["end_date"])

    creation_date = f"{start_iso}T00:00:01"
    effective_date = f"{start_iso}T00:00:00"
    expiration_date = f"{end_iso}T23:59:59"

    policy_type = {"code": "1", "value": "Single Trip"}

    coverage_type_raw = str(travel.get("coverage_type", "")).strip()
    coverage_type_lower = coverage_type_raw.lower()

    # ===== ORIGIN / DESTINATION rules =====
    if coverage_type_lower == "uae inbound":
        # Inbound → FROM user, TO UAE
        origin_raw = travel.get("departure", "")
        origin_country = _country_to_code_and_name(origin_raw)

        destination_country = COUNTRY_CODE_MAP["uae"]
    else:
        # Outbound → FROM UAE, TO user
        origin_country = COUNTRY_CODE_MAP["uae"]

        dest_raw = travel.get("destination", "")
        destination_country = _country_to_code_and_name(dest_raw)

    # Area of coverage
    area_of_coverage = GIG_AREA_OF_COVERAGE_MAP.get(
        coverage_type_lower,
        {"code": "IB", "value": "Inbound"},  # sensible default / fallback
    )

    insured_members = _build_insured_members(travel.get("travellers", []))

    gig_request = {
        "policySchedule": {
            "creationDate": creation_date,
            "effectiveDate": effective_date,
            "expirationDate": expiration_date,
            "policyType": policy_type,
        },
        "travelInformation": {
            "originCountry": {
                "code": origin_country["code"],
                "value": origin_country["value"],
            },
            "destinationCountries": [
                {
                    "code": destination_country["code"],
                    "value": destination_country["value"],
                }
            ],
            "areaOfCoverage": area_of_coverage,
        },
        "insuredMembers": insured_members,
        "schemeId": "64824A00001",
        "branchId": {"code": "13", "value": "Dubai"},
        "includeOriginalPremium": "true",
        "includeOptionalCoverPremium": "true",
    }
    print("\n====== GIG QUOTES SINGLE EVENT ======")
    print(json.dumps(gig_request, indent=2))
    print("=====================================\n")
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
    return provider.auth_config.get("access_token")


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

    if response.status_code >= 400:
        return {
            "insurer": "GIG",
            "insurer_name": "GIG Gulf",
            "plans": [],
            "error": f"GIG returned HTTP {response.status_code}",
        }

    plans_raw = resp_data.get("eligiblePlans") or []
    mapped_plans = [_map_plan_card_gig(p) for p in plans_raw]
    
    result = {
        "insurer": "GIG",
        "insurer_name": "GIG Gulf",
        "plans": mapped_plans,
        "error": None,
    }
    return result
