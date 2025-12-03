from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import date

# Traveller model
class Traveller(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date

# Travel dates model
class TravelDates(BaseModel):
    start_date: date
    end_date: date

# Travel details model
class TravelDetails(BaseModel):
    coverage_type: str
    plan_type: str
    travel_dates: TravelDates
    cover_type: str
    travellers: List[Traveller]
    departure: str
    destination: str

# Personal details model
class PersonalDetails(BaseModel):
    first_name: str
    last_name: str
    mobile_number: str
    email: EmailStr
    partner_code: Optional[str] = None
    friends_and_family_contact: Optional[str] = None
    marketing_consent: str

# Main request model
class TravelInsuranceRequest(BaseModel):
    travel_details: TravelDetails
    personal_details: PersonalDetails
