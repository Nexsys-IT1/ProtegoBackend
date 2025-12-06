from typing import Dict, Any, List, Optional
from datetime import date, datetime
import json
import requests
from sqlalchemy.orm import Session
from app.schemas.lob.travel import TravelInsuranceRequest
from app.db.models.third_party_api import ThirdPartyAuth
from app.api.v1.endpoints.third_party.travel.auth import authenticate_rak


# ---------------------------------------------------------------------------
# RAK configuration
# ---------------------------------------------------------------------------

RAK_RATING_URL = "https://uat-connect.rakinsurance.com/api/travel/gettravelrating"

# RAK cover IDs used in our CDM mapping
RAK_COVER_ID_MAP: Dict[str, str] = {
    # Emergency block
    "emergency_medical_amount": "1200",          # Emergency Medical Expenses
    "delayed_departure_amount": "1211",          # Delayed Departure

    # Accident block
    "personal_accident_amount": "1219",          # Personal Accident / common carrier
    "repatriation_expenses_amount": "1181",      # Repatriation of mortal remains

    # Additional block
    "personal_liability_amount": "1222",         # Personal Civil Liability
    "delayed_baggage_amount": "1217",            # Delay of luggage
    "loss_of_id_amount": "1212",                 # Loss of passport / ID documents
}


# ---------------------------------------------------------------------------
# Public entrypoint used by /get-quotes
# ---------------------------------------------------------------------------

def get_rak_quotes(payload: TravelInsuranceRequest, db: Session) -> Dict[str, Any]:

    # 1) canonical dict from Pydantic model
    canonical_payload: Dict[str, Any] = payload.model_dump()

    # 2) Build insurer request body
    rak_request_body = build_rak_request(canonical_payload)
    print("\n===== RAK RAW REQUEST =====")
    print(json.dumps(rak_request_body, indent=2))
    print("===== END RAK REQUEST =====\n")
    token = get_rak_token(db)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    # 4) Call RAK rating API
    try:
        response = requests.post(
            RAK_RATING_URL,
            json=rak_request_body,
            headers=headers,
            timeout=30,
        )
    except Exception as exc:
        return {
            "insurer": "RAK",
            "insurer_name": "RAK Insurance",
            "plans": [],
            "raw_insurer_response": None,
            "error": f"Request to RAK failed: {exc}",
        }

    try:
        real_quote = response.json()
    except Exception:
        real_quote = {"error": "Invalid JSON", "raw": response.text}

    # 5) Extract plans from raw response
    plans_raw = [
        p
        for p in real_quote
        if isinstance(p, dict) and p.get("planName") and p.get("total") is not None
    ]

    # 6) Map each RAK plan -> canonical plan card
    mapped_plans = [_map_plan_card(p) for p in plans_raw]

    return {
        "insurer": "RAK",
        "insurer_name": "RAK Insurance",
        "plans": mapped_plans,
        "error": None,
    }


# ---------------------------------------------------------------------------
# token provider
# ---------------------------------------------------------------------------

def get_rak_token(db: Session) -> str | None:
    provider = (
        db.query(ThirdPartyAuth)
        .filter(ThirdPartyAuth.name.ilike("%rak%")) 
        .first()
    )

    if not provider:
        print("RAK provider not found in DB")
        return None

    token = authenticate_rak(db, provider)

    if not token:
        print("Failed to authenticate RAK")
        return None
    return provider.auth_config.get("token")



# ---------------------------------------------------------------------------
# Request building (canonical -> RAK request)
# ---------------------------------------------------------------------------

def build_rak_request(canonical_payload: Dict[str, Any]) -> Dict[str, Any]:
    travel = canonical_payload["travel_details"]
    personal = canonical_payload["personal_details"]

    start_iso = _to_iso_date(travel["travel_dates"]["start_date"])
    end_iso = _to_iso_date(travel["travel_dates"]["end_date"])
    trip_duration = _days_inclusive(start_iso, end_iso)

    travellers = travel["travellers"]
    traveller_info = _map_travellers_simple(travellers)

    # --- coverage_type decides inbound vs outbound ---
    coverage_type_raw = str(travel.get("coverage_type", "")).strip()
    coverage_type_lower = coverage_type_raw.lower()

    if coverage_type_lower == "uae inbound":
        # Inbound → user gives FROM (departure), TO is fixed UAE
        departure = travel.get("departure") or ""
        destination = "UAE"
        travel_type_value = "Inbound"
    else:
        # Outbound (Worldwide / Schengen / etc.)
        # FROM is UAE, user gives TO (destination)
        departure = "UAE"
        destination = travel.get("destination") or ""
        travel_type_value = "Outbound"

    # 🔹 NEW: tripType logic (depends on travelType)
    plan_type_raw = str(travel.get("plan_type", "")).lower()
    if travel_type_value == "Inbound":
        # RAK expects just "Single" for inbound
        trip_type_value = "Single"
    else:
        # Outbound: use full names
        if "annual" in plan_type_raw:
            trip_type_value = "Annual"
        else:
            trip_type_value = "Single"

    # cover_type → traveller label
    traveller_label = travel.get("cover_type") or (
        "Individual" if len(travellers) == 1 else "Family"
    )

    # coverage amount
    coverage = travel.get("coverage") or str(trip_duration)

    # incWorldwide logic for UI display
    inc_worldwide = coverage_type_lower == "worldwide"

    email = personal.get("email", "")
    contact_no = personal.get("mobile_number", "")

    rak_request = {
        "tripStartDate": start_iso,
        "tripEndDate": end_iso,
        "tripDuration": trip_duration,
        "travelType": travel_type_value,
        "destination": destination,
        "departure": departure,
        "tripType": trip_type_value,
        "traveller": traveller_label,
        "noOfTravellers": str(len(travellers)),
        "travelling": "Yes",
        "coverage": str(coverage),
        "incWorldwide": inc_worldwide,
        "travellerInfo": traveller_info,
        "email": email,
        "contactNo": contact_no,
    }

    print("\n====== RAK QUOTES SINGLE EVENT ======")
    print(json.dumps(rak_request, indent=2))
    print("=====================================\n")
    return rak_request


# ---------------------------------------------------------------------------
# Response mapping (RAK plan -> canonical plan card)
# ---------------------------------------------------------------------------

def _map_plan_card(plan: Dict[str, Any]) -> Dict[str, Any]:
    plan_name = plan.get("planName")
    premium_total = plan.get("total")

    # Emergency block
    em_med_amount = _map_amount_by_cdm_field(plan, "emergency_medical_amount")
    delayed_dep_amount = _map_amount_by_cdm_field(plan, "delayed_departure_amount")

    # Accident block
    pa_amount = _map_amount_by_cdm_field(plan, "personal_accident_amount")
    rep_amount = _map_amount_by_cdm_field(plan, "repatriation_expenses_amount")

    # Additional block
    additional_block = {
        "personal_liability_amount": _map_amount_by_cdm_field(
            plan, "personal_liability_amount"
        ),
        "delayed_baggage_amount": _map_amount_by_cdm_field(
            plan, "delayed_baggage_amount"
        ),
        "loss_of_id_amount": _map_amount_by_cdm_field(plan, "loss_of_id_amount"),
    }

    return {
        "insurer_code": "RAK",
        "insurer_name": "RAKINSURANCE",
        "plan_name": plan_name,
        "currency": "AED",
        "premium_total": premium_total,
        "coverage_summary": {
            "emergency": {
                "emergency_medical_amount": em_med_amount,
                "delayed_departure_amount": delayed_dep_amount,
            },
            "accident": {
                "personal_accident_amount": pa_amount,
                "repatriation_expenses_amount": rep_amount,
            },
            "additional": additional_block,
        },
    }


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _map_amount_by_cdm_field(plan: Dict[str, Any], cdm_field_name: str) -> Optional[str]:
    cover_id = RAK_COVER_ID_MAP.get(cdm_field_name)
    if not cover_id:
        return None
    cover = _find_cover(plan, cover_id)
    return _extract_amount(cover)


def _find_cover(plan: Dict[str, Any], cover_id: str) -> Optional[Dict[str, Any]]:
    covers = plan.get("covers") or []
    for c in covers:
        if str(c.get("id")) == str(cover_id):
            return c
    return None


def _extract_amount(cover: Optional[Dict[str, Any]]) -> Optional[str]:
    if not cover:
        return None

    values = cover.get("values") or []
    if values:
        raw = str(values[0].get("value", "")).strip()
        if raw:
            if "usd" in raw.lower():
                return raw
            return f"USD {raw}"

    limit = cover.get("limit")
    if isinstance(limit, (int, float)) and limit > 0:
        return f"USD {int(limit):,}"

    return None


def _to_iso_date(val: Any) -> str:
    if isinstance(val, date):
        return val.isoformat()
    return str(val)


def _days_inclusive(start_iso: str, end_iso: str) -> int:
    start_date = datetime.fromisoformat(start_iso).date()
    end_date = datetime.fromisoformat(end_iso).date()
    return (end_date - start_date).days + 1


def _map_travellers_simple(travellers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    for t in travellers:
        name = f"{t.get('first_name', '').strip()} {t.get('last_name', '').strip()}".strip()
        dob = _to_iso_date(t.get("date_of_birth"))
        relation = t.get("relation") or None
        out.append({"name": name, "relation": relation, "dob": dob})

    if len(out) == 1 and not out[0].get("relation"):
        out[0]["relation"] = "Self"

    return out
