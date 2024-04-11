PROMPT = """
For example, if the question is "I am a part time cleaner. I rent my house in Birmingham from my
employer. He and his wife own the house but they are going through a divorce. My contract is for a
fixed term of five years and ends on 06/06/2024. There isn’t a break clause but I really want to
leave now if I find suitable accommodation. My employer has said that I can stay until the end of the
fixed term but that I might need to leave earlier if he needs to sell the house as part of the divorce.
Can I leave without a financial penalty?" you could respond with:
-----
Is the client a service occupier? Probably not as it is not necessary to live in accommodation for
better performance of her duties.

What is the client's security of tenure? She is an assured shorthold tenant.

How can the tenancy be lawfully ended?
Surrender: requires agreement of all the parties including the employer's wife.
Client’s NTQ: not possible at the moment as there is no break clause. It can be used once the fixed
term expires.
Client can leave on the last day of the fixed term.
Section 21 notice can only be used by LL on expiry of the fixed term.

Tactics: It might be in her best interests to stay in the house as she might not be able to find
alternative accommodation.
----
NOTE: Advisors will ask you to provide advice on a citizen's question which can often be
cross-cutting - this means that the question will have multiple themes. It's important to
understand that a client seeking advice related to housing are also likely to be advised on
benefits and tax credits, universal credit, debt, charitable support (such as grants) and
food banks as well as utilities, communications and energy supplier issues. You must think
step-by-step about the question identifying any evidence of these present in the query and
formulate your response to the advisor accordingly
"""
