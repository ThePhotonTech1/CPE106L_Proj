import flet as ft
import requests
import urllib.parse
from datetime import datetime

import webbrowser
import base64

API_BASE = "http://127.0.0.1:8000"

# ---- Status label ↔ API value mapping ----
STATUS_LABELS = [
    "Open", "Planned", "Assigned", "Picked Up", "In Transit", "Delivered", "Closed", "Cancelled"
]
STATUS_TO_API = {
    "Open": "open",
    "Planned": "planned",
    "Assigned": "assigned",
    "Picked Up": "picked_up",
    "In Transit": "in_transit",
    "Delivered": "delivered",
    "Closed": "closed",
    "Cancelled": "canceled",
}
API_TO_STATUS = {v: k for k, v in STATUS_TO_API.items()}


# ---------------- HTTP helpers ----------------
def http_post_form(url, data: dict, headers=None):
    print("POST FORM", url, data)
    r = requests.post(url, data=data, headers=headers or {})
    print("->", r.status_code, r.text[:200])
    r.raise_for_status()
    return r.json()

def http_post_json(url, payload: dict, headers=None):
    print("POST JSON", url, payload)
    r = requests.post(url, json=payload, headers=headers or {})
    print("->", r.status_code, r.text[:200])
    r.raise_for_status()
    return r.json()

def http_get(url, headers=None):
    print("GET", url)
    r = requests.get(url, headers=headers or {})
    print("->", r.status_code)
    r.raise_for_status()
    return r.json()

def http_patch(url, params=None, headers=None, timeout=10):
    print("PATCH", url, params)
    r = requests.patch(url, params=params or {}, headers=headers or {}, timeout=timeout)
    print("->", r.status_code, r.text[:200])
    if r.status_code >= 400:
        raise Exception(f"{r.status_code}: {r.text}")
    return r

def http_patch_json(url, payload=None, headers=None, timeout=10):
    print("PATCH-JSON", url, payload)
    r = requests.patch(url, json=payload or {}, headers=headers or {}, timeout=timeout)
    print("->", r.status_code, r.text[:200])
    if r.status_code >= 400:
        raise Exception(f"{r.status_code}: {r.text}")
    return r

def http_put_json(url, payload=None, headers=None, timeout=10):
    print("PUT-JSON", url, payload)
    r = requests.put(url, json=payload or {}, headers=headers or {}, timeout=timeout)
    print("->", r.status_code, r.text[:200])
    if r.status_code >= 400:
        raise Exception(f"{r.status_code}: {r.text}")
    return r

def http_delete(url, headers=None, timeout=10):
    print("DELETE", url)
    r = requests.delete(url, headers=headers or {}, timeout=timeout)
    print("->", r.status_code, r.text[:200])
    if r.status_code >= 400:
        raise Exception(f"{r.status_code}: {r.text}")
    return r

def _num(v):
    try:
        return float(v)
    except Exception:
        return 0.0

def set_driver_available(driver_id: str, available: bool, headers=None):
    """Send ?available=true|false as query param (matches backend)."""
    url = f"{API_BASE}/drivers/{driver_id}/availability"
    params = {"available": str(available).lower()}
    print("PATCH", url, params)
    r = requests.patch(url, params=params, headers=headers or {})
    print("->", r.status_code, r.text[:200])
    r.raise_for_status()
    return r

def find_driver_for_donation(donation_id: str, headers=None):
    try:
        data = http_get(f"{API_BASE}/api/donations", headers=headers or {})
    except Exception:
        return None
    for d in data:
        did = d.get("id") or d.get("_id")
        if did == donation_id:
            if isinstance(d.get("driver_id"), str):
                return d["driver_id"]
            if isinstance(d.get("driver"), str):
                return d["driver"]
            if isinstance(d.get("driver"), dict):
                return d["driver"].get("id") or d["driver"].get("_id")
    return None

def find_driver(resource_id: str, kind: str, headers=None):
    """
    Look up the attached driver for a donation/request by scanning list endpoints.
    kind: "donation" or "request"
    Returns driver_id (str) or None.
    """
    try:
        if kind == "donation":
            data = http_get(f"{API_BASE}/api/donations", headers=headers or {})
        else:
            data = http_get(f"{API_BASE}/api/requests", headers=headers or {})
    except Exception:
        return None

    for rec in data:
        rid = rec.get("id") or rec.get("_id")
        if rid != resource_id:
            continue
        # Accept several shapes
        if isinstance(rec.get("driver"), dict):
            return rec["driver"].get("id") or rec["driver"].get("_id")
        if isinstance(rec.get("driver_id"), str):
            return rec["driver_id"]
        if isinstance(rec.get("driver"), str):
            # backend might store a name here; can't turn that into id
            return None
    return None

def free_assigned_driver(donation_id: str, headers=None, donation_driver_map=None):
    """Mark the driver of this donation available=True, if we can find one."""
    try:
        driver_id = None
        if donation_driver_map:
            driver_id = donation_driver_map.get(donation_id)

        if not driver_id:
            data = http_get(f"{API_BASE}/api/donations", headers=headers or {})
            for d in data:
                did = d.get("id") or d.get("_id")
                if did == donation_id:
                    if isinstance(d.get("driver"), dict):
                        driver_id = d["driver"].get("id") or d["driver"].get("_id")
                    elif isinstance(d.get("driver_id"), str):
                        driver_id = d["driver_id"]
                    break

        if driver_id:
            set_driver_available(driver_id, True, headers=headers)
            if donation_driver_map:
                donation_driver_map.pop(donation_id, None)
            return True
    except Exception as ex:
        print("free_assigned_driver failed:", ex)
    return False



# Toast helper
def toast(page: ft.Page, text: str):
    dlg = ft.AlertDialog(title=ft.Text(text))
    page.dialog = dlg
    dlg.open = True
    page.update()


# ---------------- Main app ----------------
def main(page: ft.Page):
    reports_refresh_fn = None
    donation_driver_map: dict[str, str] = {}

    page.title = "FoodBridge"
    page.theme_mode = "dark"
    page.window_width = 1100
    page.window_height = 720

    TOKEN = None
    USER_EMAIL = ""
    USER_ROLE = ""

    content_host = ft.Container(expand=True)
    tabs_ref: ft.Ref[ft.Tabs] = ft.Ref()

    origin_tf = ft.TextField(width=500)
    stop_tf = ft.TextField(width=500)
    route_msg = ft.Text("Click the map icon in Offers/Requests to prefill Destination.")

    # Shared BottomSheet for actions
    action_sheet = ft.BottomSheet(
        ft.Container(
            content=ft.Column([], spacing=10, tight=True),
            padding=20,
            width=600,
        ),
        open=False,
        show_drag_handle=True,
    )
    page.overlay.append(action_sheet)

    def set_screen(ctrl: ft.Control):
        content_host.content = ctrl
        page.update()

    # ===== AUTH VIEW =====
    login_email = ft.TextField(label="Email", width=320)
    login_pwd = ft.TextField(label="Password", width=320, password=True, can_reveal_password=True)
    login_msg = ft.Text("", selectable=True)

    def do_login(_):
        nonlocal TOKEN, USER_EMAIL, USER_ROLE
        login_msg.value = ""
        page.update()
        try:
            data = http_post_form(f"{API_BASE}/api/auth/login",
                                  {"email": login_email.value, "password": login_pwd.value})
            TOKEN = data.get("access_token")
            USER_EMAIL = data.get("email") or login_email.value
            USER_ROLE = data.get("role") or "user"
            show_dashboard()
            toast(page, f"Welcome, {USER_EMAIL}")
        except Exception as ex:
            login_msg.value = f"Login failed: {ex}"
            page.update()

    login_tab = ft.Column(
        [login_email, login_pwd, ft.ElevatedButton("Login", on_click=do_login), login_msg],
        spacing=10,
    )

    reg_name = ft.TextField(label="Name / Organization", width=320)
    reg_email = ft.TextField(label="Email", width=320)
    reg_pwd = ft.TextField(label="Password", width=320, password=True, can_reveal_password=True)
    reg_role = ft.Dropdown(
        label="Role",
        width=200,
        options=[ft.dropdown.Option(r) for r in ["donor", "recipient", "admin"]],
        value="donor",
    )
    reg_msg = ft.Text("", selectable=True)

    def do_register(_):
        reg_msg.value = ""
        page.update()
        try:
            payload = {
                "name": reg_name.value.strip(),
                "email": reg_email.value.strip(),
                "password": reg_pwd.value.strip(),
                "role": reg_role.value,
            }
            http_post_json(f"{API_BASE}/api/auth/register", payload)
            toast(page, "Registration successful. Please login.")
            auth_tabs.selected_index = 0
            page.update()
        except Exception as ex:
            reg_msg.value = f"Registration failed: {ex}"
            page.update()

    register_tab = ft.Column(
        [reg_name, reg_email, reg_pwd, reg_role,
         ft.ElevatedButton("Create account", on_click=do_register),
         reg_msg],
        spacing=10,
    )

    auth_tabs = ft.Tabs(
        tabs=[
            ft.Tab(text="Login", content=login_tab),
            ft.Tab(text="Register", content=register_tab),
        ],
        selected_index=0,
    )

    auth_view = ft.Column(
        [ft.Text("FoodBridge", size=26, weight="bold"),
         ft.Text("Sign in or create an account"),
         auth_tabs],
        spacing=10,
    )

    # ====== DASHBOARD ======
    UNITS = ["kg", "pcs", "L", "packs"]

    # --- Offers table (with driver/status)
    offers_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Donor")),
            ft.DataColumn(ft.Text("Item")),
            ft.DataColumn(ft.Text("Qty")),
            ft.DataColumn(ft.Text("Unit")),
            ft.DataColumn(ft.Text("Address")),
            ft.DataColumn(ft.Text("Driver / Status")),
            ft.DataColumn(ft.Text("Route")),
        ],
        rows=[],
    )

    # --- Requests table (same shape you use in load_requests)
    requests_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("NGO")),
            ft.DataColumn(ft.Text("Item")),
            ft.DataColumn(ft.Text("Qty")),
            ft.DataColumn(ft.Text("Unit")),
            ft.DataColumn(ft.Text("Address")),
            ft.DataColumn(ft.Text("Route")),
        ],
        rows=[],
    )

    # --- Matches table (used by load_matches; safe even if endpoint missing)
    matches_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Donor")),
            ft.DataColumn(ft.Text("Item")),
            ft.DataColumn(ft.Text("Allocated")),
            ft.DataColumn(ft.Text("NGO")),
            ft.DataColumn(ft.Text("Status")),
        ],
        rows=[],
    )


    # ---------- Helpers to prefill routing ----------
    def prefill_destination(address: str):
        if not (address or "").strip():
            toast(page, "No address on this row.")
            return
        stop_tf.value = address or ""
        if tabs_ref.current:
            # Routing tab index will be set later after tabs are built; safe to switch after UI is constructed
            try:
                tabs_ref.current.selected_index = 2
            except Exception:
                pass
        page.update()

    def open_maps(_):
        dst = (stop_tf.value or "").strip()
        if not dst:
            route_msg.value = "Destination missing."
            page.update()
            return
        orig = (origin_tf.value or "").strip()
        if orig:
            url = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(orig)}&destination={urllib.parse.quote(dst)}"
        else:
            url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(dst)}"
        webbrowser.open(url)

    # ---- Unified route prefiller (must be inside main so it sees USER_ROLE) ----
    def route_fill(address: str, source: str):
        nonlocal USER_ROLE  # <- so we can read the current role
        addr = (address or "").strip()
        if not addr:
            route_msg.value = "No address found on this row."
            page.update()
            return

        # Behavior per your spec:
        # - Recipient clicking route on an OFFER: put offer address in ORIGIN
        # - Donor   clicking route on a REQUEST: put request address in DESTINATION
        # - Otherwise (admin/driver or other cases): set DESTINATION
        if USER_ROLE == "recipient" and source == "offer":
            origin_tf.value = addr
            route_msg.value = "Origin set from offer address."
        elif USER_ROLE == "donor" and source == "request":
            stop_tf.value = addr
            route_msg.value = "Destination set from request address."
        else:
            stop_tf.value = addr
            route_msg.value = "Destination set."

        # Jump to Routing tab (index depends on which tabs are visible)
        try:
            if tabs_ref.current:
                # Typically: Offers(0) / Requests(1) / Routing(2) / ...
                # If your tab order changes, adjust the index accordingly.
                tabs_ref.current.selected_index = 2
        except Exception:
            pass

        page.update()


    # ---------- Offers loader (shows driver/status) ----------
    def load_offers(_=None):
        offers_table.rows.clear()
        try:
            data = http_get(
                f"{API_BASE}/api/donations",
                headers={"Authorization": f"Bearer {TOKEN}"} if TOKEN else None
            )
            print("OFFERS DEBUG SAMPLE:", data[:1])
            for d in data:
                donor = d.get("donor_name", "") or ""
                addr = d.get("address", "") or ""

                # driver name: accept several backend shapes
                driver_name = None
                if isinstance(d.get("driver"), dict):
                    driver_name = d["driver"].get("name")
                elif isinstance(d.get("driver"), str):
                    driver_name = d.get("driver")  # may already be a name
                elif isinstance(d.get("driver_name"), str):
                    driver_name = d.get("driver_name")

                # status (api snake_case → label)
                api_status = (d.get("status") or "").strip().lower()
                status_label = API_TO_STATUS.get(api_status, "Open")

                # Driver / Status cell text
                if driver_name:
                    drv_cell = f"{driver_name} ({status_label})"
                else:
                    # if assigned but no name, still show reserved
                    if api_status in ("assigned", "picked_up", "in_transit"):
                        drv_cell = f"(Reserved) {status_label}"
                    else:
                        drv_cell = "Available"

                items = d.get("items", []) or []
                if not items:
                    # still render one row for visibility
                    offers_table.rows.append(
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(donor)),
                            ft.DataCell(ft.Text("—")),
                            ft.DataCell(ft.Text("—")),
                            ft.DataCell(ft.Text("—")),
                            ft.DataCell(ft.Text(addr)),
                            ft.DataCell(ft.Text(drv_cell)),
                            ft.DataCell(ft.IconButton(
                                ft.Icons.MAP,
                                tooltip="Route",
                                on_click=lambda e, a=addr: route_fill(a, "offer")
                            )),
                        ])
                    )
                else:
                    for it in items:
                        offers_table.rows.append(
                            ft.DataRow(cells=[
                                ft.DataCell(ft.Text(donor)),
                                ft.DataCell(ft.Text(it.get("name", ""))),
                                ft.DataCell(ft.Text(str(it.get("qty", "")))),
                                ft.DataCell(ft.Text(it.get("unit", ""))),
                                ft.DataCell(ft.Text(addr)),
                                ft.DataCell(ft.Text(drv_cell)),
                                ft.DataCell(ft.IconButton(
                                    ft.Icons.MAP,
                                    tooltip="Route",
                                    on_click=lambda e, a=addr: route_fill(a, "offer")
                                )),
                            ])
                        )
        except Exception as ex:
            msg = f"Error: {ex}"
            offers_table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(msg)),
                    ft.DataCell(ft.Text("")),
                    ft.DataCell(ft.Text("")),
                    ft.DataCell(ft.Text("")),
                    ft.DataCell(ft.Text("")),
                    ft.DataCell(ft.Text("")),
                    ft.DataCell(ft.Text("")),
                ])
            )
        page.update()

    # ---------- Requests loader (shows driver/status if present) ----------
    def load_requests(_=None):
        requests_table.rows.clear()
        try:
            data = http_get(
                f"{API_BASE}/api/requests",
                headers={"Authorization": f"Bearer {TOKEN}"} if TOKEN else None
            )
            print("REQUESTS DEBUG SAMPLE:", data[:1])

            for r in data:
                ngo = r.get("ngo_name", "") or ""
                addr = r.get("address", "") or ""

                # If backend attaches driver info to a planned match or reservation:
                driver_name = None
                if isinstance(r.get("driver"), dict):
                    driver_name = r["driver"].get("name")
                elif isinstance(r.get("driver"), str):
                    driver_name = r.get("driver")
                elif isinstance(r.get("driver_name"), str):
                    driver_name = r.get("driver_name")

                api_status = (r.get("status") or "").strip().lower()
                status_label = API_TO_STATUS.get(api_status, "Open")
                if driver_name:
                    drv_cell = f"{driver_name} ({status_label})"
                else:
                    if api_status in ("assigned", "picked_up", "in_transit"):
                        drv_cell = f"(Reserved) {status_label}"
                    else:
                        drv_cell = "Available"

                needs = r.get("needs", []) or []
                if not needs:
                    requests_table.rows.append(
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(ngo)),
                            ft.DataCell(ft.Text("—")),
                            ft.DataCell(ft.Text("—")),
                            ft.DataCell(ft.Text("—")),
                            ft.DataCell(ft.Text(addr)),
                            ft.DataCell(ft.IconButton(
                                ft.Icons.MAP,
                                tooltip="Route",
                                on_click=lambda e, a=addr: route_fill(a, "request")
                            )),
                        ])
                    )
                else:
                    for nd in needs:
                        # support both "qty" and legacy "quantity"
                        qval = nd.get("qty", nd.get("quantity"))
                        qty_txt = str(_num(qval))

                        requests_table.rows.append(
                            ft.DataRow(cells=[
                                ft.DataCell(ft.Text(ngo)),
                                ft.DataCell(ft.Text(nd.get("name", ""))),
                                ft.DataCell(ft.Text(qty_txt)),             # ← use normalized value
                                ft.DataCell(ft.Text(nd.get("unit", ""))),
                                ft.DataCell(ft.Text(addr)),
                                ft.DataCell(ft.IconButton(
                                    ft.Icons.MAP, tooltip="Route",
                                    on_click=lambda e, a=addr: route_fill(a, "request")
                                )),
                            ])
                        )

        except Exception as ex:
            msg = f"Error: {ex}"
            requests_table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(msg)),
                    ft.DataCell(ft.Text("")),
                    ft.DataCell(ft.Text("")),
                    ft.DataCell(ft.Text("")),
                    ft.DataCell(ft.Text("")),
                    ft.DataCell(ft.Text("")),
                ])
            )
        page.update()

    def load_matches(_=None):
        try:
            data = http_get(
                f"{API_BASE}/api/matching/plan",
                headers={"Authorization": f"Bearer {TOKEN}"} if TOKEN else None
            )
            matches_table.rows.clear()
            for m in data or []:
                matches_table.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(m.get("donor", ""))),
                        ft.DataCell(ft.Text(m.get("item", ""))),
                        ft.DataCell(ft.Text(str(m.get("allocated", "")))),
                        ft.DataCell(ft.Text(m.get("ngo", ""))),
                        ft.DataCell(ft.Text(m.get("status", "planned"))),
                    ])
                )
            if not data:
                # nice hint if empty
                matches_table.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text("No matches yet. Click Run Matching after adding Offers/Requests.")),
                        ft.DataCell(ft.Text("")),
                        ft.DataCell(ft.Text("")),
                        ft.DataCell(ft.Text("")),
                        ft.DataCell(ft.Text("")),
                    ])
                )
        except Exception as ex:
            matches_table.rows.clear()
            matches_table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(f"Error: {ex}")),
                    ft.DataCell(ft.Text("")),
                    ft.DataCell(ft.Text("")),
                    ft.DataCell(ft.Text("")),
                    ft.DataCell(ft.Text("")),
                ])
            )
        page.update()


    # ---------- Reports tab UI ----------
    def ReportsTab():
        # PNG images from backend
        img_food = ft.Image(src=f"{API_BASE}/reports/food_saved.png?days=30", width=900, height=360, fit=ft.ImageFit.CONTAIN)
        img_mpd  = ft.Image(src=f"{API_BASE}/reports/matches_per_day.png?days=30", width=900, height=360, fit=ft.ImageFit.CONTAIN)
        img_drv  = ft.Image(src=f"{API_BASE}/reports/deliveries_per_driver.png?days=30", width=900, height=360, fit=ft.ImageFit.CONTAIN)
        kpi_txt  = ft.Text("Loading KPIs…")

        def refresh(e=None):
            # cache-busting query so images update
            nonce = f"&_={datetime.now().timestamp()}"
            img_food.src = f"{API_BASE}/reports/food_saved.png?days=30{nonce}"
            img_mpd.src  = f"{API_BASE}/reports/matches_per_day.png?days=30{nonce}"
            img_drv.src  = f"{API_BASE}/reports/deliveries_per_driver.png?days=30{nonce}"
            img_food.update(); img_mpd.update(); img_drv.update()
            try:
                r = requests.get(f"{API_BASE}/reports/kpi?days=30", timeout=10)
                r.raise_for_status()
                j = r.json()
                kpi_txt.value = (f"Matches: {j.get('matches_created',0)}   |   "
                                f"Routes: {j.get('routes_planned',0)}   |   "
                                f"Pickups: {j.get('pickups_logged',0)}   |   "
                                f"Drops: {j.get('drops_logged',0)}")
            except Exception as ex:
                kpi_txt.value = f"KPI error: {ex}"
            kpi_txt.update()

        btn = ft.ElevatedButton("Refresh Charts", on_click=refresh)
        reports_tab = ft.Column(
            [btn, kpi_txt, img_food, img_mpd, img_drv],
            spacing=10, scroll=ft.ScrollMode.AUTO
        )
        return reports_tab, refresh

    def AdminToolsTab():
        out = ft.Text("", selectable=True)

        def seed_demo(_):
            out.value = "Seeding demo data..."
            page.update()
            headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else None

            # Donations (with addresses only — backend will geocode)
            donations = [
                {
                    "donor_name": "[DEMO] Yoboy Grill",
                    "items": [{"name": "bread", "qty": 10, "unit": "kg"}],
                    "address": "SM Mall of Asia, Pasay, Philippines",
                    "ready_after": datetime.now().isoformat(timespec="minutes"),
                },
                {
                    "donor_name": "[DEMO] Green Grocer",
                    "items": [{"name": "vegetables", "qty": 15, "unit": "kg"}],
                    "address": "UP Diliman, Quezon City, Philippines",
                    "ready_after": datetime.now().isoformat(timespec="minutes"),
                },
            ]

            # Requests (one good address, one intentionally vague to test Fix Geocodes)
            requests_payload = [
                {
                    "ngo_name": "[DEMO] Barangay Shelter",
                    "needs": [{"name": "bread", "qty": 6, "unit": "kg"}],
                    "address": "Pasay City Hall, Pasay, Philippines",
                },
                {
                    "ngo_name": "[DEMO] Community Pantry",
                    "needs": [{"name": "vegetables", "qty": 12, "unit": "kg"}],
                    "address": "Near donor",  # will likely fail geocode → fixed by button
                },
            ]

            try:
                for d in donations:
                    http_post_json(f"{API_BASE}/api/donations", d, headers=headers)
                for r in requests_payload:
                    http_post_json(f"{API_BASE}/api/requests", r, headers=headers)
                out.value = "Seeded 2 donations + 2 requests. Now click: Run Matching → Routing: Plan from Matches."
            except Exception as e:
                out.value = f"Seeding failed: {e}"
            page.update()

        def fix_geos(_):
            out.value = "Fixing geocodes..."
            page.update()
            try:
                res = http_post_json(f"{API_BASE}/admin/fix/geos", {})
                out.value = f"Fix result: {res}"
            except Exception as e:
                out.value = f"Fix failed: {e}"
            page.update()

        return ft.Column(
            [
                ft.Text("Admin Tools", size=20, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.ElevatedButton("Seed Demo Data", on_click=seed_demo),
                    ft.OutlinedButton("Fix Geocodes", on_click=fix_geos),
                ]),
                out,
                ft.Divider(),
                ft.Text("Flow:", weight=ft.FontWeight.BOLD),
                ft.Text("1) Seed Demo Data"),
                ft.Text("2) Click Run Matching (header)"),
                ft.Text("3) Go to Routing → Plan from Matches"),
                ft.Text("4) Assign Driver → Start → Checkpoint → Complete"),
            ],
            spacing=10,
        )


    # ---------- New Offer form ----------
    def new_offer_view(back_fn):
        donor = ft.TextField(label="Donor name", width=330)
        item = ft.TextField(label="Item name", width=330)
        qty = ft.TextField(label="Qty", width=150)
        unit = ft.Dropdown(
            label="Unit", width=150,
            options=[ft.dropdown.Option(u) for u in UNITS], value=UNITS[0]
        )
        addr = ft.TextField(label="Address", width=520)
        ready = ft.TextField(
            label="Ready after (ISO)",
            value=datetime.now().isoformat(timespec="minutes"),
            width=330
        )
        err = ft.Text("", selectable=True)

        def submit(_):
            err.value = ""
            page.update()
            try:
                payload = {
                    "donor_name": donor.value.strip(),
                    "items": [{
                        "name": (item.value or "").strip().lower(),   # normalize
                        "qty": float(qty.value),
                        "unit": (unit.value or "").strip().lower()     # normalize
                    }],
                    "address": addr.value.strip(),
                    "ready_after": (ready.value or datetime.now().isoformat(timespec="minutes")).strip()
                }

                http_post_json(
                    f"{API_BASE}/api/donations", payload,
                    headers={"Authorization": f"Bearer {TOKEN}"} if TOKEN else None
                )
                toast(page, "Offer created")
                back_fn()
                load_offers()
                load_matches() 
            except Exception as ex:
                err.value = str(ex)
                page.update()

        return ft.Column([
            ft.Row([
                ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: back_fn()),
                ft.Text("New Offer", size=20, weight="bold")
            ], alignment="start", spacing=8),
            donor, item, ft.Row([qty, unit]), addr, ready, err,
            ft.Row([ft.ElevatedButton("Create", on_click=submit)], alignment="end"),
        ], spacing=10, scroll="auto")

    # ---------- New Request form ----------
    def new_request_view(back_fn):
        ngo = ft.TextField(label="NGO name", width=330)
        item = ft.TextField(label="Item name", width=330)
        qty = ft.TextField(label="Qty", width=150)
        unit = ft.Dropdown(
            label="Unit", width=150,
            options=[ft.dropdown.Option(u) for u in UNITS], value=UNITS[0]
        )
        addr = ft.TextField(label="Address", width=520)
        err = ft.Text("", selectable=True)

        def submit(_):
            err.value = ""
            page.update()
            try:
                payload = {
                    "ngo_name": ngo.value.strip(),
                    "needs": [{
                        "name": (item.value or "").strip().lower(),   # normalize
                        "qty": float(qty.value),
                        "unit": (unit.value or "").strip().lower()     # normalize
                    }],
                    "address": addr.value.strip(),  # <-- ADD THIS
                }
                http_post_json(
                    f"{API_BASE}/api/requests",  # <-- FIX PATH
                    payload,
                    headers={"Authorization": f"Bearer {TOKEN}"} if TOKEN else None
                )
                toast(page, "Request created")
                back_fn()
                load_requests()
                load_matches() 
            except Exception as ex:
                err.value = str(ex)
                page.update()


        return ft.Column([
            ft.Row([
                ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: back_fn()),
                ft.Text("New Request", size=20, weight="bold")
            ], alignment="start", spacing=8),
            ngo, item, ft.Row([qty, unit]), addr, err,
            ft.Row([ft.ElevatedButton("Create", on_click=submit)], alignment="end"),
        ], spacing=10, scroll="auto")


    # ========== Deliveries tab ==========
    deliveries_column = ft.Column(scroll=ft.ScrollMode.ALWAYS)

    def load_deliveries(_=None):
        deliveries_column.controls.clear()

        try:
            if USER_ROLE == "recipient":
                # Recipients see OFFERS only
                dataset = http_get(
                    f"{API_BASE}/api/donations",
                    headers={"Authorization": f"Bearer {TOKEN}"} if TOKEN else None,
                )
                kind = "donation"
            elif USER_ROLE == "donor":
                # Donors see REQUESTS only
                dataset = http_get(
                    f"{API_BASE}/api/requests",
                    headers={"Authorization": f"Bearer {TOKEN}"} if TOKEN else None,
                )
                kind = "request"
            else:
                # Admin/driver: default to donations
                dataset = http_get(
                    f"{API_BASE}/api/donations",
                    headers={"Authorization": f"Bearer {TOKEN}"} if TOKEN else None,
                )
                kind = "donation"

            # Pre-cache driver map (for freeing later)
            for rec in dataset:
                rid = rec.get("id") or rec.get("_id")
                if not rid:
                    continue
                if isinstance(rec.get("driver"), dict):
                    did = rec["driver"].get("id") or rec["driver"].get("_id")
                    if did:
                        donation_driver_map[rid] = did
                elif isinstance(rec.get("driver_id"), str):
                    donation_driver_map[rid] = rec["driver_id"]

            # Build cards
            for rec in dataset:
                rid = rec.get("id") or rec.get("_id")
                if not rid:
                    continue

                title = rec.get("donor_name") if kind == "donation" else rec.get("ngo_name")
                title = title or "(unknown)"
                api_status = (rec.get("status") or "").strip().lower()
                disp_status = API_TO_STATUS.get(api_status, "Open")

                driver_name = None
                if isinstance(rec.get("driver"), dict):
                    driver_name = rec["driver"].get("name")
                elif isinstance(rec.get("driver"), str):
                    driver_name = rec["driver"]
                elif isinstance(rec.get("driver_name"), str):
                    driver_name = rec["driver_name"]

                subtitle = f"Status: {disp_status}"
                if driver_name:
                    subtitle += f"  ·  Driver: {driver_name}"

                deliveries_column.controls.append(
                    ft.Card(
                        content=ft.Container(
                            padding=10,
                            content=ft.Column(
                                [
                                    ft.Text(title, weight=ft.FontWeight.BOLD),
                                    ft.Text(f"{kind.title()} ID: {rid}", size=12),
                                    ft.Text(subtitle, size=12),
                                    ft.Row(
                                        [
                                            ft.ElevatedButton(
                                                "Assign Driver",
                                                on_click=lambda e, _rid=rid, _k=kind: on_click_assign(_rid, _k),
                                            ),
                                            ft.ElevatedButton(
                                                "Update Status",
                                                on_click=lambda e, _rid=rid, _st=api_status, _k=kind: on_click_status(_rid, _st, _k),
                                            ),
                                        ],
                                        spacing=10,
                                    ),
                                ],
                                spacing=6,
                            ),
                        )
                    )
                )

        except Exception as ex:
            deliveries_column.controls.append(ft.Text(f"Error loading deliveries: {ex}"))

        page.update()


    # OPEN bottom sheet first, then populate (so user always sees something)
    def on_click_assign(resource_id: str, kind: str):
        # kind: "donation" or "request"
        print("CLICK Assign Driver", kind, resource_id)
        toast(page, f"Assign Driver ({resource_id[:6]})")

        content = action_sheet.content.content
        content.controls.clear()
        loading_txt = ft.Text("Loading drivers…")
        dd = ft.Dropdown(width=320, visible=False)
        msg = ft.Text("")

        def close(_):
            action_sheet.open = False
            page.update()

        def do_assign(_):
            if not dd.value:
                msg.value = "Select a driver first."
                page.update()
                return

            msg.value = "Assigning…"
            page.update()
            headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else None
            base = "donations" if kind == "donation" else "requests"

            try:
                # primary path (no /api)
                http_patch(f"{API_BASE}/{base}/{resource_id}/assign_driver",
                        params={"driver_id": dd.value}, headers=headers)
            except Exception as ex1:
                print("assign primary failed:", ex1)
                try:
                    # fallback path (/api)
                    http_patch(f"{API_BASE}/api/{base}/{resource_id}/assign_driver",
                            params={"driver_id": dd.value}, headers=headers)
                except Exception as ex2:
                    msg.value = ""
                    page.update()
                    toast(page, f"Assign failed:\n{ex2}")
                    return

            # Mark driver unavailable
            try:
                set_driver_available(dd.value, False, headers=headers)
                donation_driver_map[resource_id] = dd.value
            except Exception as ex_av:
                toast(page, f"Assigned, but failed to set driver unavailable: {ex_av}")

            toast(page, "Driver assigned!")
            action_sheet.open = False
            page.update()
            load_deliveries()
            load_drivers()
            load_offers()
            load_requests()

        content.controls.extend([
            ft.Text(f"{kind.title()} ID: {resource_id}"),
            loading_txt, dd, msg,
            ft.Row([ft.TextButton("Close", on_click=close),
                    ft.ElevatedButton("Assign", on_click=do_assign)], alignment="end")
        ])
        action_sheet.open = True
        page.update()

        # Fetch available drivers
        try:
            drivers = http_get(
                f"{API_BASE}/drivers?available=true",
                headers={"Authorization": f"Bearer {TOKEN}"} if TOKEN else None
            )
            if not drivers:
                loading_txt.value = "No available drivers."
                dd.visible = False
            else:
                dd.options = [ft.dropdown.Option(d.get("id") or d.get("_id"), d.get("name", "Driver")) for d in drivers]
                loading_txt.value = "Select driver:"
                dd.visible = True
        except Exception as ex:
            loading_txt.value = f"Load drivers failed: {ex}"
            dd.visible = False
        page.update()

    def on_click_status(donation_id: str, current_status_api: str, kind: str | None = None):
        # current_status_api from backend is snake_case (e.g., "assigned")
        print("CLICK Update Status for", donation_id, "curr:", current_status_api, "kind:", kind)
        toast(page, f"Update Status ({donation_id[:6]})")

        display_current = API_TO_STATUS.get((current_status_api or "").strip(), "Open")

        content = action_sheet.content.content
        content.controls.clear()

        dd = ft.Dropdown(
            label="Select new status",
            options=[ft.dropdown.Option(lbl) for lbl in STATUS_LABELS],
            value=display_current,
            width=320,
        )
        msg = ft.Text("")

        def close(_):
            action_sheet.open = False
            page.update()

        def do_update(_):
            msg.value = "Updating…"
            page.update()
            headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else None

            api_status = STATUS_TO_API.get(dd.value)
            if not api_status:
                msg.value = "Invalid selection."
                page.update()
                return

            try:
                # backend expects ?status=<snake_case>
                http_patch(
                    f"{API_BASE}/api/donations/{donation_id}/status",
                    params={"status": api_status},
                    headers=headers,
                )

                # Free the driver when status is open / delivered / closed / canceled
                if api_status in ("open", "delivered", "closed", "canceled"):
                    freed = free_assigned_driver(
                        donation_id, headers=headers, donation_driver_map=donation_driver_map
                    )
                    if not freed:
                        # Not fatal—just inform
                        print("No driver freed (none assigned or lookup failed).")

                toast(page, f"Status → {dd.value}")
                action_sheet.open = False
                page.update()

                # Refresh views so buttons/tables update
                load_deliveries()
                load_drivers()
                load_offers()
                load_requests()
            except Exception as ex:
                msg.value = ""
                page.update()
                toast(page, f"Update failed:\n{ex}")

        content.controls.extend(
            [
                ft.Text(f"Donation: {donation_id}"),
                dd,
                msg,
                ft.Row([ft.TextButton("Close", on_click=close),
                        ft.ElevatedButton("Update", on_click=do_update)], alignment="end"),
            ]
        )

        action_sheet.open = True
        page.update()





    # ========== Drivers (Admin) ==========
    drivers_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Name")),
            ft.DataColumn(ft.Text("Phone")),
            ft.DataColumn(ft.Text("Available")),
            ft.DataColumn(ft.Text("Actions")),
        ],
        rows=[],
    )

    new_driver_name = ft.TextField(label="Driver name", width=240)
    new_driver_phone = ft.TextField(label="Phone", width=180)
    new_driver_msg = ft.Text("", size=12)

    def load_drivers(_=None):
        drivers_table.rows.clear()
        try:
            data = http_get(
                f"{API_BASE}/drivers",
                headers={"Authorization": f"Bearer {TOKEN}"} if TOKEN else None,
            )
            for d in data:
                did = d.get("id") or d.get("_id")
                name = d.get("name", "")
                phone = d.get("phone", "")
                available = bool(d.get("available", False))

                sw = ft.Switch(value=available)

                def on_toggle(e, driver_id=did, s=sw):
                    auth = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else None
                    try:
                        set_driver_available(driver_id, bool(s.value), headers=auth)
                        toast(page, f"Driver {'available' if s.value else 'unavailable'}")
                    except Exception as ex:
                        s.value = not s.value
                        s.update()
                        toast(page, f"Update failed: {ex}")

                sw.on_change = on_toggle

                del_btn = ft.IconButton(
                    ft.Icons.DELETE,
                    tooltip="Remove driver",
                    on_click=lambda e, driver_id=did: delete_driver(driver_id),
                )

                drivers_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(name)),
                            ft.DataCell(ft.Text(phone)),
                            ft.DataCell(sw),
                            ft.DataCell(del_btn),
                        ]
                    )
                )
        except Exception as ex:
            drivers_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f"Error: {ex}")),
                        ft.DataCell(ft.Text("")),
                        ft.DataCell(ft.Text("")),
                        ft.DataCell(ft.Text("")),
                    ]
                )
            )
        page.update()

    def add_driver(_):
        new_driver_msg.value = ""
        page.update()
        name = new_driver_name.value.strip()
        phone = new_driver_phone.value.strip()
        if not name:
            new_driver_msg.value = "Name required"
            page.update()
            return
        try:
            http_post_json(
                f"{API_BASE}/drivers",
                {"name": name, "phone": phone, "available": True},
                headers={"Authorization": f"Bearer {TOKEN}"} if TOKEN else None,
            )
            new_driver_name.value = ""
            new_driver_phone.value = ""
            toast(page, "Driver added")
            load_drivers()
        except Exception as ex:
            new_driver_msg.value = f"Add failed: {ex}"
            page.update()

    def delete_driver(driver_id: str):
        try:
            http_delete(
                f"{API_BASE}/drivers/{driver_id}",
                headers={"Authorization": f"Bearer {TOKEN}"} if TOKEN else None,
            )
            toast(page, "Driver removed")
            load_drivers()
        except Exception as ex:
            toast(page, f"Delete failed: {ex}")

    def DriversTab():
        add_row = ft.Row(
            [new_driver_name, new_driver_phone, ft.ElevatedButton("Add driver", on_click=add_driver), new_driver_msg],
            spacing=10,
        )
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Drivers (Admin)", size=20, weight="bold"),
                        ft.Container(expand=True),
                        ft.OutlinedButton("Refresh", on_click=load_drivers),
                    ],
                    spacing=10,
                ),
                add_row,
                drivers_table,
            ],
            spacing=10,
        )

    # ===== Role-based tabs =====
    def allowed_tabs_for(role: str):
        # Everyone can see Offers, Requests, and Routing
        base = {"Offers", "Requests", "Routing"}
        base.add("Deliveries")

        if role == "admin":
            base |= {"Reports", "Matches", "Drivers"}
        return base

# ---- Run matching button handler ----
    def run_matching(_):
        try:
            r = requests.get(f"{API_BASE}/api/matching/run", timeout=12)
            r.raise_for_status()
            try:
                body = r.json()
            except Exception:
                body = r.text
            dlg = ft.AlertDialog(
                title=ft.Text("Matching recomputed"),
                content=ft.Text(str(body)[:1200])
            )
            page.dialog = dlg
            dlg.open = True
            page.update()
            load_matches()
            if reports_refresh_fn:
                reports_refresh_fn()
        except Exception as ex:
            toast(page, f"Run Matching failed: {ex}")

    # ------- Dashboard view (with Tabs) -------
    def dashboard_view():
        # --- Build all tab contents first (tables are already defined earlier in main) ---
        offers_tab = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Offers", size=20, weight="bold"),
                        ft.Container(expand=True),
                        ft.OutlinedButton("Refresh", on_click=load_offers),
                        ft.ElevatedButton(
                            "New Offer",
                            on_click=lambda e: set_screen(new_offer_view(show_dashboard))
                        ),
                    ],
                    spacing=10,
                ),
                offers_table,
            ],
            spacing=10,
        )

        requests_tab = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Requests", size=20, weight="bold"),
                        ft.Container(expand=True),
                        ft.OutlinedButton("Refresh", on_click=load_requests),
                        ft.ElevatedButton(
                            "New Request",
                            on_click=lambda e: set_screen(new_request_view(show_dashboard))
                        ),
                    ],
                    spacing=10,
                ),
                requests_table,
            ],
            spacing=10,
        )

        # ------ ROUTES & DISPATCH PANEL ------
        depot_lat = ft.TextField(label="Depot lat", value="14.5547", width=160)
        depot_lng = ft.TextField(label="Depot lng", value="121.0244", width=160)
        capacity_kg = ft.TextField(label="Capacity (kg)", value="80", width=160)

        plans_dd = ft.Dropdown(label="Route plan", width=420)
        driver_dd = ft.Dropdown(label="Driver", width=300)
        kg_override_tf = ft.TextField(label="KG override (optional)", width=200)

        routes_info = ft.Text("", selectable=True)
        steps_lv = ft.ListView(expand=True, spacing=6, padding=10)

        start_btn = ft.ElevatedButton("Start Route")
        checkpoint_btn = ft.ElevatedButton("Checkpoint")
        complete_btn = ft.ElevatedButton("Complete")

        def load_driver_options(only_available=True):
            try:
                q = "available=true" if only_available else ""
                url = f"{API_BASE}/drivers" + (f"?{q}" if q else "")
                data = http_get(url, headers={"Authorization": f"Bearer {TOKEN}"} if TOKEN else None)
                opts = []
                for d in data:
                    did = d.get("id") or d.get("_id")
                    name = (d.get("name") or "Driver").strip()
                    opts.append(ft.dropdown.Option(key=str(did), text=name))
                driver_dd.options = opts
                driver_dd.value = opts[0].key if opts else None
                driver_dd.update()
            except Exception as ex:
                toast(page, f"Load drivers failed: {ex}")


        def _refresh_route_status_text(route_id: str):
            try:
                r = requests.get(f"{API_BASE}/api/routes/{route_id}", timeout=6)
                if r.ok:
                    j = r.json()
                    routes_info.value = f"Route {route_id[:6]} · status: {j.get('status', '?')}"
                    routes_info.update()
            except Exception as e:
                print("refresh status failed:", e)


        plans_store: list[dict] = []

        def _load_plans_into_dropdown(plans: list[dict]):
            plans_dd.options = []
            for i, p in enumerate(plans):
                rid = str(p.get("_id") or p.get("id", ""))
                label = f'Batch {p.get("batch_index", i)} • {p.get("total_distance_km",0):.1f} km • {p.get("duration_min",0):.0f} min'
                plans_dd.options.append(ft.dropdown.Option(key=rid or f"idx:{i}", text=label))
            if plans_dd.options:
                plans_dd.value = plans_dd.options[0].key
            plans_dd.update()

        def _render_steps(plan: dict):
            steps_lv.controls.clear()
            for s in plan.get("steps", []):
                txt = s.get("action","").upper()
                lab = s.get("label","")
                kg = s.get("kg")
                line = f"{txt:<7}  {lab}" + (f"  • {kg:.3f} kg" if kg is not None else "")
                steps_lv.controls.append(ft.Text(line))
            steps_lv.update()

        def _pick_plan_by_key(key: str) -> dict | None:
            for p in plans_store:
                if str(p.get("_id")) == key or str(p.get("id")) == key:
                    return p
            if key and key.startswith("idx:"):
                try:
                    idx = int(key.split(":")[1])
                    if 0 <= idx < len(plans_store):
                        return plans_store[idx]
                except Exception:
                    pass
            return None

        def on_plan_from_matches(_):
            try:
                payload = {
                    "depot": {"lat": float(depot_lat.value), "lng": float(depot_lng.value)},
                    "capacity_kg": float(capacity_kg.value)
                }
                res = http_post_json(f"{API_BASE}/api/routes/plan_from_matches", payload)
                print("PLAN_FROM_MATCHES RESPONSE:", res)
                cnt = res.get("count", 0)
                routes_info.value = f"Created {cnt} route batch(es)."
                routes_info.update()
                nonlocal plans_store
                plans_store = res.get("plans", []) or []
                _load_plans_into_dropdown(plans_store)
                if plans_store:
                    _render_steps(plans_store[0])
                toast(page, "Route planning OK")
            except Exception as e:
                toast(page, f"Plan failed: {e}")

        def on_plans_changed(e: ft.ControlEvent):
            plan = _pick_plan_by_key(plans_dd.value)
            if plan:
                _render_steps(plan)

        def on_assign_driver(_):
            rid = plans_dd.value
            if not rid or not driver_dd.value:
                toast(page, "Select a route and choose a driver")
                return
            try:
                http_patch_json(
                    f"{API_BASE}/api/dispatch/routes/{rid}/assign_driver",
                    {"driver_id": driver_dd.value}
                )
                toast(page, "Driver assigned")
            except Exception as e:
                toast(page, f"Assign failed: {e}")


        def on_start_route(_):
            rid = plans_dd.value
            if not rid:
                toast(page, "Select a route")
                return
            try:
                http_post_json(f"{API_BASE}/api/dispatch/routes/{rid}/start", {})
                toast(page, "🚚 Route started")
                _refresh_route_status_text(rid)

                # UI feedback
                start_btn.disabled = True
                start_btn.update()
            except Exception as e:
                toast(page, f"Start failed: {e}")


        def on_checkpoint(_):
            rid = plans_dd.value
            if not rid:
                toast(page, "Select a route")
                return
            payload = {}
            if kg_override_tf.value.strip():
                try:
                    payload["kg_override"] = float(kg_override_tf.value)
                except Exception:
                    toast(page, "KG override must be a number")
                    return
            try:
                http_post_json(f"{API_BASE}/api/dispatch/routes/{rid}/checkpoint", payload)
                toast(page, "📍 Checkpoint logged")

                msg = f"• Checkpoint logged"
                if "kg_override" in payload:
                    msg += f" (kg={payload['kg_override']})"
                msg += f" @ {datetime.now().strftime('%H:%M:%S')}"
                steps_lv.controls.append(ft.Text(msg))
                steps_lv.update()

                _refresh_route_status_text(rid)
            except Exception as e:
                toast(page, f"Checkpoint failed: {e}")


        def on_complete_route(_):
            rid = plans_dd.value
            if not rid:
                toast(page, "Select a route")
                return
            try:
                # complete the route
                http_post_json(f"{API_BASE}/api/dispatch/routes/{rid}/complete", {})
                toast(page, "✅ Route completed")

                # UI feedback
                routes_info.value = f"✅ Route {rid[:6]} COMPLETED."
                routes_info.update()
                steps_lv.controls.append(ft.Text("✅ Route completed."))
                steps_lv.update()

                # Disable buttons & clear selection
                checkpoint_btn.disabled = True
                complete_btn.disabled = True
                checkpoint_btn.update(); complete_btn.update()
                plans_dd.value = None; plans_dd.update()

                # 🔁 IMPORTANT: recompute matching & refresh tabs so 'planned' disappears
                try:
                    requests.get(f"{API_BASE}/api/matching/run", timeout=10).raise_for_status()
                except Exception as _ex:
                    pass  # non-fatal; just means re-match didn’t run

                load_matches()
                load_offers()
                load_requests()
                load_deliveries()
                if reports_refresh_fn:
                    reports_refresh_fn()

            except Exception as e:
                toast(page, f"Complete failed: {e}")


        start_btn.on_click = on_start_route
        checkpoint_btn.on_click = on_checkpoint
        complete_btn.on_click = on_complete_route

        row = ft.Row([kg_override_tf, start_btn, checkpoint_btn, complete_btn])

        plans_dd.on_change = on_plans_changed

        routing_tab = ft.Column(
            [
                ft.Text("Routes & Dispatch", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([depot_lat, depot_lng, capacity_kg,
                        ft.ElevatedButton("Plan from Matches", on_click=on_plan_from_matches)]),
                routes_info,
                ft.Row([
                    plans_dd,
                    driver_dd,
                    ft.OutlinedButton("↻", tooltip="Refresh drivers", on_click=lambda e: load_driver_options(True)),
                    ft.ElevatedButton("Assign Driver", on_click=on_assign_driver)
                ]),
                ft.Row([
                    kg_override_tf,
                    start_btn,
                    checkpoint_btn,
                    complete_btn
                ]),
                ft.Container(steps_lv, expand=True, padding=10, bgcolor="#2A2A2A", border_radius=8),
                ft.Divider(),
                ft.Text("Quick Google Maps", size=16, weight=ft.FontWeight.BOLD),
                origin_tf, stop_tf, ft.ElevatedButton("Open in Google Maps", on_click=open_maps), route_msg,
            ],
            spacing=10,
        )

        reports_view, reports_refresh = ReportsTab()

        matches_tab = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Matches", size=20, weight="bold"),
                        ft.Container(expand=True),
                        ft.OutlinedButton("Refresh", on_click=load_matches),
                    ],
                    spacing=10,
                ),
                matches_table,
            ],
            spacing=10,
        )

        deliveries_tab = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Deliveries", size=20, weight="bold"),
                        ft.Container(expand=True),
                        ft.OutlinedButton("Refresh", on_click=load_deliveries),
                    ],
                    spacing=10,
                ),
                deliveries_column,
            ],
            spacing=10,
        )

        drivers_view = DriversTab()

        # --- Filter tabs by role ---
        allowed = allowed_tabs_for(USER_ROLE)
        tab_list = []
        if "Offers" in allowed:
            tab_list.append(ft.Tab(text="Offers", content=offers_tab))
        if "Requests" in allowed:
            tab_list.append(ft.Tab(text="Requests", content=requests_tab))
        if "Routing" in allowed:
            tab_list.append(ft.Tab(text="Routing", content=routing_tab))
        if "Reports" in allowed:
            tab_list.append(ft.Tab(text="Reports", content=reports_view))
        if "Matches" in allowed:
            tab_list.append(ft.Tab(text="Matches", content=matches_tab))
        if "Deliveries" in allowed:
            tab_list.append(ft.Tab(text="Deliveries", content=deliveries_tab))
        if "Drivers" in allowed:
            tab_list.append(ft.Tab(text="Drivers", content=drivers_view))


        tabs = ft.Tabs(ref=tabs_ref, tabs=tab_list)

        header = ft.Row(
            [
                ft.Text(f"FoodBridge  |  {USER_EMAIL} ({USER_ROLE})", size=20, weight="bold"),
                ft.Container(expand=True),
                ft.OutlinedButton("Run Matching", on_click=run_matching),
                ft.ElevatedButton("Logout", on_click=lambda e: show_auth()),
            ],
            alignment="spaceBetween",
        )

        def wrapper_reports_refresh():
            if "Reports" in allowed:
                reports_refresh()

        load_driver_options(True)

        return ft.Column([header, tabs], spacing=8), wrapper_reports_refresh

    # ---- Screen switchers ----
    def show_dashboard():
        nonlocal reports_refresh_fn
        reports_refresh_fn = lambda: None

        ui, refresh_reports = dashboard_view()
        content_host.content = ui
        page.update()

        reports_refresh_fn = refresh_reports
        refresh_reports()
        
        try:
            requests.get(f"{API_BASE}/api/matching/run", timeout=8).raise_for_status()
        except Exception:
            pass
        load_matches()

        # set Routing labels based on role
        if USER_ROLE == "recipient":
            origin_tf.label = "Origin (pickup location)"
            stop_tf.label = "Destination (your address)"
        elif USER_ROLE == "donor":
            origin_tf.label = "Origin (your address)"
            stop_tf.label = "Destination (recipient address)"
        else:
            origin_tf.label = "Origin"
            stop_tf.label = "Destination"

        origin_tf.update()
        stop_tf.update()

        # load data for visible tabs by role
        allowed = allowed_tabs_for(USER_ROLE)
        if "Offers" in allowed:
            load_offers()
        if "Requests" in allowed:
            load_requests()
        if "Matches" in allowed:
            load_matches()
        if "Deliveries" in allowed:
            load_deliveries()
        if "Drivers" in allowed:
            load_drivers()

    def show_auth():
        content_host.content = ft.Container(auth_view, padding=20)
        page.update()

    # ---- MOUNT ROOT + show first screen ----
    page.add(content_host)
    show_auth()



# ---- Flet App bootstrap ----
if __name__ == "__main__":
    view = getattr(ft.AppView, "WINDOW", None) or getattr(ft.AppView, "FLET_APP", None)
    ft.app(target=main, view=view if view else None)
