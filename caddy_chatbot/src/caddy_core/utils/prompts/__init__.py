from caddy_core.utils.prompts.advice_area import (
    benefits_and_tax_credits,
    benefits_and_universal_credit,
    charitable_support_and_food_banks,
    consumer_goods_and_services,
    debt,
    education,
    employment,
    financial_services_and_capability,
    gva_and_hate_crime,
    health_and_community_care,
    housing,
    immigration_and_asylum,
    legal,
    relationships_and_family,
    tax,
    travel_and_transport,
    utilities_and_communications,
)
from caddy_core.utils.prompts.core_prompts import CORE_PROMPT, FALLBACK_PROMPT

CORE = CORE_PROMPT
FALLBACK = FALLBACK_PROMPT
BENEFITS_AND_TAX_CREDITS = benefits_and_tax_credits.PROMPT
BENEFITS_AND_UNIVERSAL_CREDIT = benefits_and_universal_credit.PROMPT
CHARITABLE_SUPPORT_AND_FOOD_BANKS = charitable_support_and_food_banks.PROMPT
CONSUMER_GOODS_AND_SERVICES = consumer_goods_and_services.PROMPT
DEBT = debt.PROMPT
EDUCATION = education.PROMPT
EMPLOYMENT = employment.PROMPT
FINANCIAL_SERVICES_AND_CAPABILITY = financial_services_and_capability.PROMPT
GVA_AND_HATE_CRIME = gva_and_hate_crime.PROMPT
HEALTH_AND_COMMUNITY_CARE = health_and_community_care.PROMPT
HOUSING = housing.PROMPT
IMMIGRATION_AND_ASYLUM = immigration_and_asylum.PROMPT
LEGAL = legal.PROMPT
RELATIONSHIPS_AND_FAMILY = relationships_and_family.PROMPT
TAX = tax.PROMPT
TRAVEL_AND_TRANSPORT = travel_and_transport.PROMPT
UTILITIES_AND_COMMUNICATIONS = utilities_and_communications.PROMPT

__all__ = [
    "CORE",
    "FALLBACK",
    "BENEFITS_AND_TAX_CREDITS",
    "BENEFITS_AND_UNIVERSAL_CREDIT",
    "CHARITABLE_SUPPORT_AND_FOOD_BANKS",
    "CONSUMER_GOODS_AND_SERVICES",
    "DEBT",
    "EDUCATION",
    "EMPLOYMENT",
    "FINANCIAL_SERVICES_AND_CAPABILITY",
    "GVA_AND_HATE_CRIME",
    "HEALTH_AND_COMMUNITY_CARE",
    "HOUSING",
    "IMMIGRATION_AND_ASYLUM",
    "LEGAL",
    "RELATIONSHIPS_AND_FAMILY",
    "TAX",
    "TRAVEL_AND_TRANSPORT",
    "UTILITIES_AND_COMMUNICATIONS",
]
