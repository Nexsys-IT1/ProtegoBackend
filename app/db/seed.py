from app.api.v1.endpoints.third_party.travel.auth import authenticate_all_providers
from app.db.models.third_party_api import ThirdPartyAuth
from sqlalchemy.orm import Session
from app.core.config import settings

providers = [
    # 1️⃣ RAK Insurance
    ThirdPartyAuth(
        name="RAK Insurance",
        base_url="https://uat-connect.rakinsurance.com",
        auth_url="/login/authenticate",
        auth_config={
            "token_type": "Bearer",
            "partner_id": "RAKUSERAPI",
            "location_code": "20",
            "user_name": settings.RAK_USER_NAME,
            "password": settings.RAK_PASSWORD,
            "token": None,
            "client_id": None,
            "client_secret": None,
            "token_expires_at": None
        }
    ),

    # 2️⃣ Gulf Insurance
    ThirdPartyAuth(
        name="Gulf Insurance",
        base_url="https://gulf-insurance-pp.eu.auth0.com",
        auth_url="/oauth/token",
        auth_config={
            "grant_type": "client_credentials",
            "client_id": settings.GULF_CLIENT_ID,
            "client_secret": settings.GULF_CLIENT_SECRET,
            "audience": "integration-platform",
            "access_token": None,
            "expires_in": None,
            "token_type": None,
            "token_expires_at": None
        }
    ),

    # 3️⃣ Liva Insurance
    ThirdPartyAuth(
        name="Liva Insurance",
        base_url="https://uatproductsvc.livainsurance.ae",
        auth_url="/auth-token",
        auth_config={
            "grant_type": "client_credentials",
            "client_id": settings.LIVA_CLIENT_ID,
            "client_secret": settings.LIVA_CLIENT_SECRET,
            "scope": settings.LIVA_SCOPE,
            "Location": settings.LIVA_LOCATION,
            "AuthKey": settings.LIVA_AUTHKEY,
            "Language": settings.LIVA_LANGUAGE,
            "PartnerID": settings.LIVA_PARTNERID,
            "SubscriptionKey": settings.LIVA_SUBSCRIPTIONKEY,
            "access_token": None,
            "expires_in": None,
            "token_type": None,
            "token_expires_at": None
        }
    )
]



def seed_third_party_providers(db: Session):
    try:
        for provider in providers:
            # Check if provider already exists
            existing = (
                db.query(ThirdPartyAuth)
                .filter(ThirdPartyAuth.name == provider.name)
                .first()
            )

            if existing:
                print(f"[SEED] Provider already exists → {provider.name}")
                continue

            # Add new provider
            db.add(provider)
            db.flush()   # Get ID assigned
            db.refresh(provider)

            print(f"[SEED] Added provider → {provider.name}")

        db.commit()
        authenticate_all_providers(db)

    except Exception as e:
        db.rollback()
        print("[SEED] Error while seeding providers:", str(e))
        raise
