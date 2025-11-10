PICKUP_STATES = [
    "created", "scheduled", "en_route", "picked_up",
    "delivered", "verified", "closed", "canceled"
]

TRANSITIONS = {
    ("created",   "scheduled"):  {"roles": ["dispatcher", "admin"]},
    ("scheduled", "canceled"):   {"roles": ["dispatcher", "admin"]},
    ("verified",  "closed"):     {"roles": ["dispatcher", "admin"]},

    ("scheduled", "en_route"):   {"roles": ["driver", "admin"]},
    ("en_route",  "picked_up"):  {"roles": ["driver", "admin"]},
    ("picked_up", "delivered"):  {"roles": ["driver", "admin"]},

    ("delivered", "verified"):   {"roles": ["recipient_staff", "dispatcher", "admin"]},
}

def can_transition(src: str, dst: str, user_roles: list[str]) -> bool:
    rule = TRANSITIONS.get((src, dst))
    if not rule:
        return False
    return bool(set(rule["roles"]) & set(user_roles))
