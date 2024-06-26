from caddy_core.services.router import get_route
from caddy_core.utils.prompts import issues_map

from caddy_core.utils.prompts.default_template import (
    CADDY_FALLBACK_EXAMPLE,
)


def retrieve_route_specific_augmentation(query):
    route = get_route(query).name

    match route:
        case "benefits_and_tax_credits":
            route_specific_augmentation = issues_map.BENEFITS_AND_TAX_CREDITS
        case "benefits_and_universal_credit":
            route_specific_augmentation = issues_map.BENEFITS_AND_UNIVERSAL_CREDIT
        case "charitable_support_and_food_banks":
            route_specific_augmentation = issues_map.CHARITABLE_SUPPORT_AND_FOOD_BANKS
        case "consumer_goods_and_services":
            route_specific_augmentation = issues_map.CONSUMER_GOODS_AND_SERVICES
        case "debt":
            route_specific_augmentation = issues_map.DEBT
        case "education":
            route_specific_augmentation = issues_map.EDUCATION
        case "employment":
            route_specific_augmentation = issues_map.EMPLOYMENT
        case "financial_services_and_capability":
            route_specific_augmentation = issues_map.FINANCIAL_SERVICES_AND_CAPABILITY
        case "gva_and_hate_crime":
            route_specific_augmentation = issues_map.GVA_AND_HATE_CRIME
        case "health_and_community_care":
            route_specific_augmentation = issues_map.HEALTH_AND_COMMUNITY_CARE
        case "housing":
            route_specific_augmentation = issues_map.HOUSING
        case "immigration_and_asylum":
            route_specific_augmentation = issues_map.IMMIGRATION_AND_ASYLUM
        case "legal":
            route_specific_augmentation = issues_map.LEGAL
        case "relationships_and_family":
            route_specific_augmentation = issues_map.RELATIONSHIPS_AND_FAMILY
        case "tax":
            route_specific_augmentation = issues_map.TAX
        case "travel_and_transport":
            route_specific_augmentation = issues_map.TRAVEL_AND_TRANSPORT
        case "utilities_and_communications":
            route_specific_augmentation = issues_map.UTILITIES_AND_COMMUNICATIONS
        case _:
            route_specific_augmentation = CADDY_FALLBACK_EXAMPLE

    return route_specific_augmentation
