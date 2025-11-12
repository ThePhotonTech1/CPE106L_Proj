ROLE_SCOPES = {
    "admin": ["*"],
    "dispatcher": ["pickups:create", "pickups:assign", "routes:view", "webhooks:manage"],
    "driver": ["pickups:update_status", "routes:view"],
    "donor_staff": ["donations:create", "donations:view"],
    "recipient_staff": ["donations:view", "pickups:update_status"]
}

def roles_to_scopes(roles):
    scopes = set()
    for r in roles:
        scopes.update(ROLE_SCOPES.get(r, []))
    return list(scopes)
