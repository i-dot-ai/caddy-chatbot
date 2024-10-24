import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timezone, timedelta

from semantic_router import Route, RouteLayer
from semantic_router.encoders import BedrockEncoder
from caddy_core.utils.monitoring import logger
from caddy_core.routes import routes_data

from semantic_router.index.postgres import PostgresIndex
from semantic_router.index.local import LocalIndex


from dotenv import load_dotenv

load_dotenv()


class CachedRouteLayer(RouteLayer):
    """
    Custom RouteLayer that skips initial encoding when using cached routes
    """

    def __init__(self, encoder, routes, index, **kwargs):
        super().__init__(encoder=encoder, index=index, **kwargs)
        self.routes = routes


class AutoRefreshBedrockEncoder:
    def __init__(self, region="eu-west-3", score_threshold=0.5):
        logger.info("Constructing encoder")
        self.region = region
        self.score_threshold = score_threshold
        self.encoder = None
        self.expiration = datetime.now(
            timezone.utc
        )  # assume we're expired when we construct

    def refresh_credentials(self):
        logger.info("Refreshing credentials")
        try:
            sts_client = boto3.client("sts")
            role_arn = os.environ.get("TASK_ROLE_ARN")
            response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName="CaddyTaskSession",
                DurationSeconds=3600,
            )

            credentials = response["Credentials"]
            self.encoder = BedrockEncoder(
                access_key_id=credentials["AccessKeyId"],
                secret_access_key=credentials["SecretAccessKey"],
                session_token=credentials["SessionToken"],
                region=self.region,
                score_threshold=self.score_threshold,
            )

            self.expiration = credentials["Expiration"]
            logger.info(f"Refreshed credentials, new expiry time: {self.expiration}")
        except ClientError as e:
            logger.error(f"Failed to refresh credentials: {e}")
            raise

    def __call__(self, *args, **kwargs):
        logger.info("Calling encoder")
        if datetime.now(timezone.utc) >= self.expiration - timedelta(minutes=5):
            logger.info("Credentials expiring soon, refreshing...")
            self.refresh_credentials()

        return self.encoder(*args, **kwargs)

    def __getattr__(self, name):
        if name == "score_threshold":
            return self.score_threshold
        return getattr(self.encoder, name)


def load_semantic_router() -> RouteLayer:
    routes = []
    for route in routes_data:
        utterances = route["utterances"]
        route = Route(name=route["name"], utterances=utterances)
        routes.append(route)

    if os.environ.get("POSTGRES_CONNECTION_STRING", False):
        logger.info(
            "POSTGRES_CONNECTION_STRING is set, looking for routes in postgres..."
        )
        index = PostgresIndex(dimensions=1024)
    else:
        index = LocalIndex()

    try:
        route_count_in_index = len(index.get_routes())
    except ValueError:
        route_count_in_index = 0

    embeddings = AutoRefreshBedrockEncoder(region="eu-west-3", score_threshold=0.5)
    if route_count_in_index > 0:
        logger.info(f"Loading {route_count_in_index} routes from index...")
        return CachedRouteLayer(encoder=embeddings, routes=routes, index=index)
    else:
        return RouteLayer(encoder=embeddings, routes=routes, index=index)


get_route = load_semantic_router()

# messages that work with routing
"""
For short messages under 50 characters such as:
Client is sofa surfing what can he do?
what is power of attorney
pip change of circumstances
improvement notices from doncaster council
My client has a section 21, is this valid?
How to apply for Housing Benefit
unfair dismissal eligibility
section 21 advice
how do i work out how much to pay a creditor?
What is pip?
placing a complaint against a solicitor
can I claim PIP
can you be evicted without a tenancy agreement?
how long does SDPTE last for on UC?


Caddy can provide a good response on these because things like PIP, UC are acronyms for universal credit and personal independence payment which it will be able to find in the RAG docuemnts provided.
In addition the questions are direct and ask questions about these sections that are general like seciton 21 advice or what is pip?
Becuase they are general and not about a client, Caddy will not need further information to provide a coherent response.


For messages under 50 characters such as:
can i get information from you?
when did claims for irESA stop?
section 13
My client has a section 20, is this valid?
can i claim uc?
pip
PIP pack posted

Although these contain sections or PIP or section numbers, we do not inherently know what the advisor is interested in.
In addition questions such as can I claim UC or my client has a section 20, is this valid are going to need further client information or background to hone in the answer as applicability or validity is often too broad.
Finally general questions that have no specific direction such as can i get information from you are not going to illicit a good response.

In these eventualities, Caddy must ask for further information, and provide the advisor with several potential questions they could ask before providing a response.
"""


# messages that DO NOT work with routing
"""
For long messages with plenty detail, i.e. over 400 characters such as Caddy can get confused or miss detail, therefore it is important to break down the required information carefully.

Messages such as

400+:
I saw a house I would like to rent on Gumtree. The person advertising the house asked me to send a deposit which I did via bank transfer. They then asked for more money which I said I would send once I viewed the house. The person then disappeared and I realised it was a scam. I spoke to my bank but they will not recover my money as I willingly transferred it. I only have the person's bank details. Is there any way I can get my money back?
Caddy, client is an EU national who has been living the UK for the last 5 years with settled status. After client got his settled status, he took a career break of 7 months to travel outside of Europe (190 days). Client then discovered law saying that one cannot stay outside of the UK for more than 90 days in the 12 months prior to applying for British Citizenship. Client is still employed in the UK. Client wants to know if he is eligible to apply for British Citizenship now or if he should wait 12 months before applying.
Caddy, client is British, single, and lives in council property. Client is not working and claims Universal Credit and Personal Independence Payment. Client was in a brief relationship with a third party in December 2023 before it ended. Since February 2024, there has been domestic abuse towards client by third party (physical, mental and financial). Last month, third party kicked and punched the client and forced the client to withdraw their benefit payments from the bank to give to them. Third party has coerced the client to let them into their property despite them changing the locks. On 8th June 2024, third party entered client‚Äôs property and painted two of the walls. Third party then demanded the client pay them ¬£400 by 17th June 2024 (the date client's Universal Credit is paid) even though they never asked them to decorate. Client has reported third party to the police, who are investigating, but police have not arrested them. Council said they can put client in temporary accommodation (in conjunction with Leeds Domestic Violence Service) but they would be separated from their dog. Client has also contacted their MP for help. MP, police and council have signposted client to Citizens Advice for help in getting a non-molestation order and accessing legal advice.
Client is Ukrainian and been in UK since 2022. She contacted us about benefit entitlement. she is currently working 40 hour week but not really well enough to do so. Partner on low wage and not in secure employment. Rent is ¬£795.00 a month. Client on minimum wage ¬£11.70 an hour and partner on ¬£11.44 an hour. Client wanted to know about possible benefit entitlement. She is being treated as at high risk of a stroke but reason for symptoms not yet diagnosed. Universal Credit information. Help to Claim and PIP information. Cohabiting couple. No children. Private rented property. Through letting agency. Also sent SSP and PIP
Caddy, client works full-time, does not claim any benefits and lives in a private rented property. Client has an assured shorthold tenancy agreement in his name only and this was recently renewed for a further fixed term of 6 months. The terms of the tenancy outline that the client‚Äôs flat and others in the development are for those aged 55 and over only. Client has a partner who is 38. Client‚Äôs partner is currently going through immigration proceedings to secure their status in the UK (client‚Äôs partner does not need advice on this as they have an immigration solicitor) and one of the recent judgements confirmed the partner can live with the client irrespective of the age restriction in the client‚Äôs tenancy agreement. Client‚Äôs landlord agreed to this arrangement. However, there have been complaints from neighbours about the client‚Äôs partner‚Äôs presence in terms of their age and allegations of antisocial behaviour. Client suspects¬† sexual orientation and race discrimination from the neighbours. Client has now received an ‚Äòinjunction notice‚Äô with a court hearing on 20th June 2024, which client believes has the aim of removing their partner from the property. Client is also worried about potentially being evicted. There is no mention of eviction on the notice. Client needs advice on understanding and responding to the ‚Äòinjunction notice‚Äô and preparing for the court hearing.
i have a client who is having issues with her housing association property. the property has no insulation and considerable noise affecting her sleep and health. she has gone through the formal complaints procedure and escalated the case to the housing ombudsman already. the housing ombudsman ordered the housing association to carry out necessary repairs but the housing association did this wrong and made the problem worse.
my client's private tenancy ended on 17th august. they were due to move into their new private rented property on 16th august. however, it failed the gas safety certificate twice, so this has now been delayed. the client spent ¬£300 on a moving van which was not used, and may also have to pay for the extra week they have had to stay in the old property. can the client claim to get this money back?
Caddy, client is British and lives with their 5 children (1, 2, 3, 11, 18) in private rented property. Client is a carer and claims Universal Credit, Child Benefit, Council Tax Support, and DLA. Client‚Äôs eldest child became 18 on 25 May 2024 and told them they would be leaving full-time education to look for work. Child will still live with the client. Client has reported the change of circumstances on their online journal, but when they called the Helpline they were told they will need to wait for a work coach to contact them. Client asked if the housing costs element will be affected, but the Department for Work and Pensions told them to wait until their next payment on 3 July 2024. Client wants to know how the change of circumstances will affect their Universal Credit.
Caddy, client contacted us by email so information is limited. Client paid ¬£300 to Instasmile for clip-on veneers but Instasmile rejected the client‚Äôs teeth impressions and they could not make the veneers. Client suggests their teeth impressions have been rejected more than once. Instasmile will not issue new impression kits, they will not issue a refund due to the cost of the impression kits they have already provided and client has been left without the product. Client has contacted Instasmile several times without reaching a resolution. Client suggested the dispute has been ongoing for 8 months. Client would like to know if they‚Äôre entitled to the product or failing this, a refund.
Client moved out of jointly owned (mortgaged) property in September 2022 as environment unsafe for himself and his daughter. Former partner had stabbed him and attempted to hang herself (police aware). Client continued to pay mortgage ¬£893 a month but stopped a year ago. Now arrears of ¬£4,000. Partner has put property on market without clients knowledge although he wants to sell. ¬£90,000 mortgage left to pay and ¬£4,000 arrears. Client concerned that he and his daughter should get their share of equity. Wants to ensure equal split.
Client wanted some advice on what her rights are regarding repairs for her new place. Client has recently moved and has noticed that there is mould inside of the washing machine which was included with the property. Client has tried to clean this but when she washed her clothes huge chunks of the mould had spread onto her clothes.
Client has stated that on her tenancy agreement it is stating that the landlord is responsible for the repairs within the property unless this is damaged by the tenant. Client believes that the issue with the washing machine was present from the start, as she had gone on holiday she hadn't used her washing machine until now. Client has not yet spoken with her landlord about this as she would like to know what her legal rights are.

Will stand well becaause there is plenty detail on:
1. the main legal topic or issue being discussed.
2. specific questions being asked.
3. relevant personal details of the individual involved (e.g., age, nationality, employment status).
4. key facts or circumstances related to the legal situation.
5. mentioned dates, locations, or monetary amounts.
6. any legal terms or concepts mentioned.

Caddy will struggle iwth messages such as:

400+:
message
Caddy, client contacted us by email and gave limited information. Client asked not to be called back for a full exploration. Client is British, 54 years old, and lives alone in council property. Client works part time and their income is ¬£2200/month (wages and benefits). Client planned to retire on 10th February 2025 due to ill-health, but wants to stop work before this date. They had a meeting with their employer on 11th June 2024 to discuss the issue.
on the 4th july the client's family came back from their holiday and had an argument and the kids got scared because the client's husband smashed their TV. the client's daughter called 999. the Police then came and looked at their house, took pictures, interviewed client's children. the Police said there was no problem but then started taking pictures of kids bruise with no consent. they investigated the bruises and stated there was no danger with this. client's 6 year old child said her father was hitting them but this is not true (no one else said he was violent). the police are now accusing husband of domestic abuse but the client is certain this is not true. on the 6th july the client and husband went to the police station do make their statement as they were told but no one came to see them and the police had lost the record. The client was told the police would be in touch with them but they haven't heard anything in ten days. Client has now been contacted by social services who stated they had an urgent referral about assaults (client told them none of this is true). client's Husband was then arrested by the police (violently) and taken from his family. the client is unable to contact her husband and struggling as she is disabled and her husband usually takes care of her. Now the client has to take her son to hospital for operations for several days and is unsure what to do. the client does not know where her husband is. Client has called her local council but they were unable to help. the client Can‚Äôt afford legal help."
Client wants advice regarding a settlement of ¬£16,000 she has received from her divorce and how this would affect her Universal credit. Client has been advised to use the settlement money to either gift it to her daughter through Deed of Gift or to use it to buy a property, and has stated that she will be receiving help from her family and friends to pay for a downpayment. Client has been advised by her solicitor that she can request for a Disregarded Capital which will provide her with a 6 month grace period as she uses this time to search for a property.
The client currently has a smart prepayment meter for both their gas and electric. The client lives in Council social housing. The energy supplier for the property is British Gas. The client wishes for their smart meters to be removed and replaced with traditional meters. British Gas have stated that the client would need to pay ¬£300 for the removal of the smart meters and their replacement. What are the clients rights in this situation?
Client has received a possession order from court and has advised there is no eviction date. She is being invited to attend a court hearing on 22nd July. Client lives in an HMO with 3 other adults and believes that the property is being repossessed because the landlord did not inform the council this property was a HMO. Client is unemployed and has no support from friends and family, and will become homeless if she is evicted. Client wants to know if she needs to take a solicitor with her to the court hearing.
Client is single, not in paid employment and has long term health issues and was promised a tax rebate in February 2024 but has not yet received it. How can this be chased up. Client is struggling financially. Client is receiving help claiming Personal Independence Payments. Client also believes should have the limited capability for work and work related activity for her Universal Credit, how can this be claimed?
I have a Client who has received a managed migration notice with a deadline  of 15/06/2024. She currently receives child tax credits for two children. Both children are under 16. Her son also receives higher rate DLA. The client has opened savings accounts in her children's names in which she has saved up ¬£20,000. The children's father, by court order, transfers funds to the client and she deposits them into the children's savings account. Both children are under 16. She also has ¬£10,000 in her current account. Will the capital in her children's savings accounts be considered as capital for her universal credit claim?

This can be for a few reasons
1) Caddy will always provide a section asking the advisor to ask more questions, whcih if they have asked not to be called back is not possible.
2) The question may not be direct enough and Caddy will get focussed on one part of the context
3) The question may be looking for a softer touch and Caddy can be quite factual, the

"""
