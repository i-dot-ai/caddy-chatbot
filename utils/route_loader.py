import boto3

TABLE_NAME = "caddyRoutes"

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

routes_data = [
    {
        "name": "benefits_and_tax_credits",
        "utterances": [
            "What are benefits available?",
            "How do I apply for tax credits?",
            "Can you explain the eligibility criteria for tax credits?",
            "Are there any changes to tax credits this year?",
            "How can I calculate my entitlement to benefits and tax credits?",
            "What documents do I need to provide for benefits and tax credits?",
            "Can you help me with a benefits and tax credits claim issue?",
            "Where can I find more information about benefits and tax credits?",
        ],
    },
    {
        "name": "benefits_and_universal_credit",
        "utterances": [
            "What is Universal Credit?",
            "How do I apply for Universal Credit?",
            "What are the eligibility criteria for Universal Credit?",
            "Can you explain the Universal Credit claim process?",
            "What documents do I need to provide for a Universal Credit claim?",
            "How can I calculate my entitlement to Universal Credit?",
            "Can you help me with a Universal Credit claim issue?",
            "Where can I find more information about Universal Credit?",
        ],
    },
    {
        "name": "charitable_support_and_food_banks",
        "utterances": [
            "What are the eligibility criteria for receiving charitable support?",
            "How can someone apply for charitable support?",
            "What types of assistance do food banks provide?",
            "Are there any income limits or requirements to access food banks?",
            "What documentation is needed to receive charitable support?",
            "How can someone find local food banks?",
            "What other resources or services are available for individuals in need?",
            "Are there any restrictions or limitations on the frequency of accessing food banks?",
        ],
    },
    {
        "name": "consumer_goods_and_services",
        "utterances": [
            "What are my rights as a consumer?",
            "How can I make a complaint about a product or service?",
            "What are the refund and return policies for consumer goods?",
            "Can you help me with a dispute with a retailer?",
            "Where can I find information about consumer protection laws?",
            "What are the regulations for online shopping?",
            "How can I avoid scams and fraudulent sellers?",
            "Can you provide guidance on product warranties and guarantees?",
        ],
    },
    {
        "name": "debt",
        "utterances": [
            "What are the different types of debt?",
            "How can someone negotiate with creditors to reduce debt?",
            "What are the consequences of not paying off debt?",
            "Can you explain the debt collection process?",
            "What are the options for debt consolidation?",
            "How can someone deal with overwhelming debt?",
            "What are the rights and protections for individuals in debt?",
            "Can you provide guidance on bankruptcy and insolvency?",
        ],
    },
    {
        "name": "education",
        "utterances": [
            "What are the available education options for my client?",
            "How can my client access financial support for education?",
            "What are the eligibility criteria for educational grants and scholarships?",
            "Can you explain the process of applying for student loans?",
            "What documentation is required for enrolling in educational programs?",
            "How can my client navigate the admissions process for schools and universities?",
            "Can you provide guidance on special education services and accommodations?",
            "What resources are available for adult education and vocational training?",
            "How can my client address issues related to bullying or discrimination in educational settings?",
            "Where can I find more information about educational rights and regulations?",
        ],
    },
    {
        "name": "employment",
        "utterances": [
            "What are the rights and responsibilities of employees?",
            "How can someone address workplace discrimination or harassment?",
            "What is the process for filing a complaint against an employer?",
            "Can you provide guidance on employment contracts and terms?",
            "What are the regulations for minimum wage and working hours?",
            "How can someone negotiate a fair salary or benefits package?",
            "Can you explain the process of redundancy and severance pay?",
            "What are the rights and protections for individuals facing unfair dismissal?",
            "How can someone access support for workplace health and safety issues?",
            "Where can I find more information about employment rights and regulations?",
        ],
    },
    {
        "name": "financial_services_and_capability",
        "utterances": [
            "What financial services are available for individuals?",
            "How can someone access financial advice and guidance?",
            "Can you explain the process of opening a bank account?",
            "What are the options for managing debt and improving credit?",
            "How can someone access affordable loans or credit?",
            "Can you provide guidance on budgeting and saving?",
            "What resources are available for financial planning and retirement?",
            "How can someone protect themselves from financial scams and fraud?",
            "Where can I find more information about financial services and capability?",
        ],
    },
    {
        "name": "gva_and_hate_crime",
        "utterances": [
            "What support services are available for victims of gender-based violence and hate crimes?",
            "How can someone report a gender-based violence or hate crime incident?",
            "What legal protections are in place for victims of gender-based violence and hate crimes?",
            "Can you explain the process of obtaining a restraining order or protection order?",
            "What resources are available for counseling and emotional support for victims of gender-based violence and hate crimes?",
            "How can someone access emergency accommodation or safe houses?",
            "Can you provide guidance on safety planning for victims of gender-based violence and hate crimes?",
            "Where can I find more information about gender-based violence and hate crimes?",
        ],
    },
    {
        "name": "health_and_community_care",
        "utterances": [
            "What are the available healthcare services in the area?",
            "How can someone access primary healthcare?",
            "Can you explain the process of registering with a general practitioner (GP)?",
            "What are the eligibility criteria for receiving community care services?",
            "How can someone apply for community care services?",
            "What types of support are available for individuals with specific health conditions?",
            "Are there any income limits or requirements to access community care services?",
            "What documentation is needed to receive community care services?",
            "How can someone find local healthcare providers and specialists?",
            "What other resources or services are available for individuals in need of healthcare and community care support?",
            "Are there any restrictions or limitations on the frequency of accessing community care services?",
            "Can you provide guidance on mental health support services?",
            "What are the options for accessing long-term care facilities?",
            "How can someone navigate the process of obtaining medical equipment or assistive devices?",
            "What are the rights and protections for individuals receiving healthcare and community care services?",
            "Where can I find more information about healthcare rights and regulations?",
        ],
    },
    {
        "name": "housing",
        "utterances": [
            "What are the rights and responsibilities of a tenant?",
            "How can someone find affordable housing options?",
            "Can you explain the process of renting a property?",
            "What are the regulations for tenancy agreements?",
            "How can someone address issues with their landlord?",
            "What are the options for dealing with eviction?",
            "Can you provide guidance on housing benefits and assistance programs?",
            "Where can I find more information about housing rights and regulations?",
        ],
    },
    {
        "name": "immigration_and_asylum",
        "utterances": [
            "What are the eligibility criteria for different types of visas?",
            "How can someone apply for asylum in this country?",
            "What are the rights and protections for asylum seekers?",
            "Can you explain the process of appealing a visa or asylum decision?",
            "What are the options for family reunification for refugees?",
            "How can someone access legal representation for immigration cases?",
            "Can you provide guidance on immigration detention and removal?",
            "What are the requirements for obtaining citizenship or permanent residency?",
            "How can someone address issues with their immigration status?",
            "Where can I find more information about immigration and asylum rights and regulations?",
        ],
    },
    {
        "name": "legal",
        "utterances": [
            "What are the different types of legal cases?",
            "How can someone find a lawyer or legal representation?",
            "Can you explain the process of filing a lawsuit?",
            "What are the options for alternative dispute resolution?",
            "How can someone access legal aid or pro bono services?",
            "Can you provide guidance on court procedures and protocols?",
            "What are the rights and protections for individuals in the justice system?",
            "How can someone navigate the process of obtaining legal documents or records?",
            "Where can I find more information about the legal system, courts, and justice system?",
        ],
    },
    {
        "name": "relationships_and_family",
        "utterances": [
            "What are the legal rights and responsibilities in a marriage or civil partnership?",
            "How can someone navigate the process of divorce or dissolution?",
            "What are the options for child custody and visitation rights?",
            "Can you provide guidance on child support and maintenance?",
            "What are the rights and protections for victims of domestic violence?",
            "How can someone address issues related to child protection and safeguarding?",
            "Can you explain the process of adoption or fostering?",
            "What resources are available for couples or families going through relationship breakdown?",
            "How can someone access counseling or mediation services for family disputes?",
            "Where can I find more information about relationship and family rights and regulations?",
        ],
    },
    {
        "name": "tax",
        "utterances": [
            "What are the different types of taxes?",
            "How can someone calculate their income tax?",
            "Can you explain the process of filing a tax return?",
            "What are the deductions and credits available for taxpayers?",
            "How can someone address issues with their tax payments?",
            "What are the options for resolving tax disputes?",
            "Can you provide guidance on self-employment taxes?",
            "What are the tax implications of owning a business?",
            "How can someone navigate the process of paying taxes as an employee (PAYE)?",
            "Where can I find more information about tax laws and regulations?",
        ],
    },
    {
        "name": "travel_and_transport",
        "utterances": [
            "What are the available modes of public transportation in the area?",
            "How can someone plan their travel using public transportation?",
            "Can you explain the process of purchasing tickets for trains or buses?",
            "What are the options for traveling between different cities or regions?",
            "How can someone access information about train schedules and routes?",
            "Are there any discounts or concessions available for public transportation?",
            "Can you provide guidance on navigating public transportation systems?",
            "What are the rights and protections for passengers using public transportation?",
            "How can someone address issues with delays or cancellations of trains or buses?",
            "Where can I find more information about travel and transportation services?",
        ],
    },
    {
        "name": "utilities_and_communications",
        "utterances": [
            "How can someone reduce their energy bills?",
            "What assistance programs are available for individuals struggling to pay their energy bills?",
            "Can you explain the process of switching energy providers?",
            "What are the options for accessing affordable broadband services?",
            "How can someone address issues with their broadband connection?",
            "What support is available for individuals experiencing fuel poverty?",
            "Can you provide guidance on energy-saving measures for heating and cooling?",
            "What are the rights and protections for consumers in the energy and communications sectors?",
            "How can someone navigate the process of installing and using prepayment meters?",
            "Where can I find more information about energy crisis management and resources?",
        ],
    },
]


def load_routes_to_dynamodb():
    for route in routes_data:
        table.put_item(Item=route)
    print("All routes have been loaded into the DynamoDB table.")


if __name__ == "__main__":
    load_routes_to_dynamodb()
