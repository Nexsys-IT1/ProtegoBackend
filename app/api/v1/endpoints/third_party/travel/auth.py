import requests
from sqlalchemy.orm import Session
from app.db.models.third_party_api import ThirdPartyAuth
from datetime import datetime, timedelta, timezone


def authenticate_provider(db: Session, provider: ThirdPartyAuth):
    name = provider.name.lower()

    if "rak" in name:
        return authenticate_rak(db, provider)

    elif "gulf" in name:
        return authenticate_gulf(db, provider)

    elif "liva" in name:
        return authenticate_liva(db, provider)

    else:
        print(f"[AUTH] No auth handler found for: {provider.name}")
        return None




def authenticate_rak(db: Session, provider: ThirdPartyAuth):
    url = provider.base_url + provider.auth_url

    body = {
        "username": provider.auth_config["user_name"],
        "password": provider.auth_config["password"]
    }

    headers = {
        "PartnerId": provider.auth_config["partner_id"],
        "Location": provider.auth_config["location_code"],
        "Content-Type": "application/json",
    }

    print(f"[AUTH-RAK] Calling: {url}")

    if is_valid_api_call_time(provider) is False:
        response = requests.post(url, json=body, headers=headers)
        data = response.json()

        if "token" not in data:
            print("[AUTH-RAK] Auth failed:", data)
            return None

        provider.auth_config["token"] = data["token"]
        provider.auth_config["token_expires_at"] = (
            datetime.now(timezone.utc) + timedelta(hours=1)
        ).isoformat()

        db.commit()
        db.refresh(provider)

        print(f"[AUTH-RAK] Token updated for {provider.name}")
        return data
    else:
        print(f"[AUTH-RAK] Token still valid for {provider.name}")
        return provider.auth_config.get("token")




def authenticate_gulf(db: Session, provider: ThirdPartyAuth):
    url = provider.base_url + provider.auth_url

    payload = {
        "grant_type": provider.auth_config["grant_type"],
        "client_id": provider.auth_config["client_id"],
        "client_secret": provider.auth_config["client_secret"],
        "audience": provider.auth_config["audience"],
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    print(f"[AUTH-GULF] Calling: {url}")
    if is_valid_api_call_time(provider) is False:
     response = requests.post(url, data=payload, headers=headers)
     data = response.json()

     if "access_token" not in data:
         print("[AUTH-GULF] Auth failed:", data)
         return None

     provider.auth_config["access_token"] = data["access_token"]
     provider.auth_config["token_type"] = data["token_type"]
     provider.auth_config["expires_in"] = data["expires_in"]
     provider.auth_config["token_expires_at"] = (
        datetime.utcnow() + timedelta(seconds=data["expires_in"])
     ).isoformat()

     db.commit()
     db.refresh(provider)

     print(f"[AUTH-GULF] Token updated for {provider.name}")
     return data
    else:
        print(f"[AUTH-GULF] Token still valid for {provider.name}")
        return provider.auth_config.get("token")



def authenticate_liva(db: Session, provider: ThirdPartyAuth):
    url = provider.base_url + provider.auth_url

    payload = {
        "client_id": provider.auth_config["client_id"],
        "client_secret": provider.auth_config["client_secret"],
        "grant_type": provider.auth_config["grant_type"],
        "scope": provider.auth_config["scope"],
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Location": provider.auth_config["Location"],
        "AuthKey": provider.auth_config["AuthKey"],
        "Language": provider.auth_config["Language"],
        "PartnerID": provider.auth_config["PartnerID"],
        "SubscriptionKey": provider.auth_config["SubscriptionKey"],
    }

    print(f"[AUTH-LIVA] Calling: {url}")
    if is_valid_api_call_time(provider) is False:
     response = requests.post(url, data=payload, headers=headers)
     data = response.json()

     if "access_token" not in data:
         print("[AUTH-LIVA] Auth failed:", data)
         return None

     provider.auth_config["access_token"] = data["access_token"]
     provider.auth_config["token_type"] = data["token_type"]
     provider.auth_config["expires_in"] = data["expires_in"]
     provider.auth_config["token_expires_at"] = (
        datetime.utcnow() + timedelta(seconds=data["expires_in"])
     ).isoformat()

     db.commit()
     db.refresh(provider)

     print(f"[AUTH-LIVA] Token updated for {provider.name}")
     return data
    else:
        print(f"[AUTH-LIVA] Token still valid for {provider.name}")
        return provider.auth_config.get("token")




def authenticate_all_providers(db: Session):
    providers = db.query(ThirdPartyAuth).all()

    for provider in providers:
        print(f"\n[AUTH] Authenticating → {provider.name}")
        authenticate_provider(db, provider)


def is_valid_api_call_time(provider: ThirdPartyAuth) -> bool:
    two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
    if not provider.updated_at or provider.updated_at < two_hours_ago:
        return False
    return True