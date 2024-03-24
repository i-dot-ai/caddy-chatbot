from caddy.utils.tables import offices_table, users_table


def check_domain_status(domain):
    """
    Checks if the domain is enrolled with Caddy
    """
    domain_registered = offices_table.get_item(Key={"emailDomain": domain})
    if "Item" in domain_registered:
        return True
    else:
        return False


def check_user_status(user):
    """
    Checks if the user is registered with Caddy
    """
    user_registered = users_table.get_item(Key={"userEmail": user})
    if "Item" in user_registered:
        return True
    else:
        return False
