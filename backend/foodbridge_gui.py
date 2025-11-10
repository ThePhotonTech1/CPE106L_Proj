# foodbridge_gui.py
import tkinter as tk
from tkinter import ttk, messagebox
import requests, json
from datetime import datetime
from services.api_client import ApiClient
import base64, io
from PIL import Image, ImageTk

API_URL = "http://127.0.0.1:8000"
api = ApiClient()

AUTH_TOKEN = None
CURRENT_USER = None  # {"email":..., "name":..., "role":...}

def auth_headers():
    h = {"Accept": "application/json"}
    if AUTH_TOKEN:
        h["Authorization"] = f"Bearer {AUTH_TOKEN}"
    return h


# ----------------------------- MAIN APP (single window, switch frames) -----------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FoodBridge")
        self.geometry("980x640")
        self.configure(bg="#f8fafc")
        self._frame = None
        self.show_auth()

    def show_auth(self):
        self._switch(AuthFrame)

    def show_main(self):
        self._switch(MainFrame)

    def _switch(self, frame_cls):
        if self._frame is not None:
            self._frame.destroy()
        self._frame = frame_cls(self)
        self._frame.pack(fill="both", expand=True, padx=10, pady=10)


# ----------------------------- AUTH FRAME (login / register) --------------------------------------
class AuthFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self._build()

    def _build(self):
        title = ttk.Label(self, text="FoodBridge – Sign in or Create an account", font=("Segoe UI", 14, "bold"))
        title.pack(pady=16)

        nb = ttk.Notebook(self)
        nb.pack(fill="x", padx=10, pady=10)

        # ---- Login Tab
        login_tab = ttk.Frame(nb)
        nb.add(login_tab, text="Login")

        self.login_email = tk.StringVar()
        self.login_pwd   = tk.StringVar()

        self._row(login_tab, "Email", self.login_email, 0)
        self._row(login_tab, "Password", self.login_pwd, 1, show="*")
        ttk.Button(login_tab, text="Login", command=self._do_login).grid(row=2, column=0, columnspan=2, pady=10)

        # ---- Register Tab
        reg_tab = ttk.Frame(nb)
        nb.add(reg_tab, text="Register")

        self.reg_name  = tk.StringVar()
        self.reg_email = tk.StringVar()
        self.reg_pwd   = tk.StringVar()
        self.reg_role  = tk.StringVar(value="donor")

        self._row(reg_tab, "Name", self.reg_name, 0)
        self._row(reg_tab, "Email", self.reg_email, 1)
        self._row(reg_tab, "Password", self.reg_pwd, 2, show="*")
        ttk.Label(reg_tab, text="Role").grid(row=3, column=0, sticky="e", padx=6, pady=4)
        ttk.Combobox(reg_tab, values=["donor","recipient","driver","admin"], textvariable=self.reg_role,
                     width=26, state="readonly").grid(row=3, column=1, sticky="w", padx=6, pady=4)
        ttk.Button(reg_tab, text="Create account", command=self._do_register).grid(row=4, column=0, columnspan=2, pady=10)

        ttk.Label(self, text="Tip: use the Register tab first if you have no account.").pack(pady=4)

    def _row(self, parent, label, var, r, show=None):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="e", padx=6, pady=4)
        ttk.Entry(parent, textvariable=var, width=28, show=show).grid(row=r, column=1, sticky="w", padx=6, pady=4)

    def _do_login(self):
        global AUTH_TOKEN, CURRENT_USER
        email = self.login_email.get().strip()
        pwd   = self.login_pwd.get().strip()
        if not email or not pwd:
            messagebox.showwarning("Missing", "Please enter email and password.")
            return

        url = f"{API_URL}/auth/login"
        attempts = [
            # OAuth2 style
            dict(kind="form+grant", kwargs=dict(
                data={"username": email, "password": pwd, "grant_type": "password", "scope": ""},
                headers={"Accept":"application/json", "Content-Type":"application/x-www-form-urlencoded"}
            )),
            # Simple form
            dict(kind="form", kwargs=dict(
                data={"username": email, "password": pwd},
                headers={"Accept":"application/json", "Content-Type":"application/x-www-form-urlencoded"}
            )),
            # JSON (email/password) – likely for your backend
            dict(kind="json-email", kwargs=dict(
                json={"email": email, "password": pwd},
                headers={"Accept":"application/json"}
            )),
        ]

        last_err = ""
        for att in attempts:
            try:
                r = requests.post(url, **att["kwargs"])
                r.raise_for_status()
                data = r.json()
                token = data.get("access_token") or data.get("token") or data.get("jwt")
                if not token:
                    raise ValueError(f"No token in response: {data}")

                # ADDED: set ApiClient token & current user
                AUTH_TOKEN = token
                api.set_token(AUTH_TOKEN)                     # <<<<<<<<<<<<<<<<<< ADDED
                CURRENT_USER = data.get("user") or {"email": email}  # <<<<<<<<<<<< ADDED

                messagebox.showinfo("Welcome", "✅ Login successful.")
                self.master.show_main()
                return
            except Exception as e:
                last_err = f"{att['kind']}: {getattr(e, 'response', None).text if hasattr(e, 'response') and e.response is not None else str(e)}"

        messagebox.showerror("Login failed", f"All attempts failed.\n\nDetails:\n{last_err}")

    def _do_register(self):
        name  = self.reg_name.get().strip()
        email = self.reg_email.get().strip()
        pwd   = self.reg_pwd.get().strip()
        role  = self.reg_role.get().strip()
        if not name or not email or not pwd:
            messagebox.showwarning("Missing", "Please fill name, email and password.")
            return
        try:
            r = requests.post(f"{API_URL}/auth/register",
                              json={"name": name, "email": email, "password": pwd, "role": role},
                              headers={"Accept":"application/json"})
            r.raise_for_status()
            messagebox.showinfo("Account created", "✅ Registration successful. You can now login.")
        except requests.HTTPError as e:
            msg = e.response.text if getattr(e, "response", None) else str(e)
            messagebox.showerror("Registration failed", msg)
        except Exception as e:
            messagebox.showerror("Registration failed", str(e))


# ----------------------------- MAIN APP FRAME (shows after login) ---------------------------------
UNITS = ["kg", "pcs", "L", "packs"]

class MainFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self._build()

    # ---------- API helpers
    def _get(self, path):
        r = requests.get(f"{API_URL}{path}", headers=auth_headers())
        r.raise_for_status(); return r.json()

    def _post(self, path, payload=None, params=None):
        r = requests.post(f"{API_URL}{path}", json=payload, params=params, headers=auth_headers())
        r.raise_for_status(); return r.json()

    # NEW: routing endpoints (address-based routing, history, report)
    def _post_optimize_by_addresses(self, addresses):
        return self._post("/api/routes/optimize_by_address", {"addresses": addresses})

    def _get_route_history(self, limit=20):
        r = requests.get(f"{API_URL}/api/routes/history", params={"limit": limit}, headers=auth_headers())
        r.raise_for_status()
        return r.json().get("routes", [])

    def _get_routes_summary_img(self):
        r = requests.get(f"{API_URL}/api/reports/routes_summary", headers=auth_headers())
        r.raise_for_status()
        return r.json()["img_base64"]

    # ---------- UI
    def _build(self):
        # header
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="FoodBridge", font=("Segoe UI", 14, "bold")).pack(side="left")
        ttk.Button(top, text="Logout", command=self._logout).pack(side="right")

        # notebook
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, pady=8)

        # tabs
        self._build_dashboard()
        self._build_offers()
        self._build_requests()
        self._build_match_routes()
        self._build_routing_by_address()   # NEW: routing with addresses + map + history + report

        # initial loads
        self.load_offers()
        self.load_requests()

    def _logout(self):
        global AUTH_TOKEN, CURRENT_USER
        AUTH_TOKEN = None; CURRENT_USER = None
        api.set_token(None)  # keep client clean on logout
        self.master.show_auth()

    # ----- Dashboard
    def _build_dashboard(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="Dashboard")
        ttk.Button(tab, text="Check Backend Health", command=self._health).pack(pady=20)

    def _health(self):
        try:
            r = requests.get(f"{API_URL}/health", headers=auth_headers())
            messagebox.showinfo("Health", f"OK: {r.json()}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ----- Offers
    def _build_offers(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="Offers")

        bar = ttk.Frame(tab); bar.pack(fill="x", pady=5)
        ttk.Button(bar, text="Reload Offers", command=self.load_offers).pack(side="left", padx=4)
        ttk.Button(bar, text="+ Add Donation", command=self._open_add_donation).pack(side="left", padx=4)

        self.offers_tree = ttk.Treeview(tab, columns=("donor","item","qty","unit"), show="headings", height=16)
        for col in ("donor","item","qty","unit"):
            self.offers_tree.heading(col, text=col.capitalize())
        self.offers_tree.pack(fill="both", expand=True, padx=6, pady=6)

    def load_offers(self):
        try:
            data = self._get("/donations")
            self.offers_tree.delete(*self.offers_tree.get_children())
            for d in data:
                donor = d.get("donor_name") or f'ID {d.get("id")}'
                for it in d.get("items", []):
                    name = it.get("name") or it.get("item") or "—"
                    qty  = it.get("qty") if it.get("qty") is not None else it.get("quantity")
                    unit = it.get("unit") or "—"
                    self.offers_tree.insert("", "end", values=(donor, name, qty if qty is not None else "—", unit))
        except Exception as e:
            messagebox.showerror("Load offers failed", str(e))

    def _open_add_donation(self):
        win = tk.Toplevel(self); win.title("Add Donation"); win.resizable(False, False)

        donor = tk.StringVar(); item = tk.StringVar(); qty = tk.StringVar()
        unit  = tk.StringVar(value=UNITS[0]); lat = tk.StringVar(); lng = tk.StringVar()
        ready = tk.StringVar(value=datetime.now().isoformat(timespec="seconds"))

        self._entry(win, "Donor Name *", donor, 0)
        self._entry(win, "Item *", item, 1)
        self._entry(win, "Qty *", qty, 2)
        ttk.Label(win, text="Unit *").grid(row=3, column=0, sticky="e", padx=6, pady=4)
        ttk.Combobox(win, values=UNITS, textvariable=unit, width=26, state="readonly").grid(row=3, column=1, sticky="w", padx=6, pady=4)
        self._entry(win, "Lat", lat, 4); self._entry(win, "Lng", lng, 5)
        self._entry(win, "Ready After (ISO)", ready, 6)

        def submit():
            try:
                payload = {
                    "donor_name": donor.get().strip(),
                    "items": [{"name": item.get().strip(), "qty": float(qty.get()), "unit": unit.get()}],
                    "location": {"lat": float(lat.get() or 0), "lng": float(lng.get() or 0)},
                    "ready_after": ready.get().strip()
                }
                self._post("/donations", payload)
                messagebox.showinfo("Success", "Donation created.")
                win.destroy(); self.load_offers()
            except Exception as e:
                messagebox.showerror("Create failed", str(e))

        ttk.Button(win, text="Create", command=submit).grid(row=7, column=0, columnspan=2, pady=8)

    # ----- Requests
    def _build_requests(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="Requests")

        bar = ttk.Frame(tab); bar.pack(fill="x", pady=5)
        ttk.Button(bar, text="Reload Requests", command=self.load_requests).pack(side="left", padx=4)
        ttk.Button(bar, text="+ Add Request", command=self._open_add_request).pack(side="left", padx=4)

        self.requests_tree = ttk.Treeview(tab, columns=("ngo","item","qty","unit"), show="headings", height=16)
        for col in ("ngo","item","qty","unit"):
            self.requests_tree.heading(col, text=col.capitalize())
        self.requests_tree.pack(fill="both", expand=True, padx=6, pady=6)

    def load_requests(self):
        try:
            data = self._get("/requests")
            self.requests_tree.delete(*self.requests_tree.get_children())
            for r in data:
                ngo = r.get("ngo_name") or f'ID {r.get("id")}'
                for nd in r.get("needs", []):
                    name = nd.get("name") or nd.get("item") or "—"
                    qty  = nd.get("qty") if nd.get("qty") is not None else nd.get("quantity")
                    unit = nd.get("unit") or "—"
                    self.requests_tree.insert("", "end", values=(ngo, name, qty if qty is not None else "—", unit))
        except Exception as e:
            messagebox.showerror("Load requests failed", str(e))

    def _open_add_request(self):
        win = tk.Toplevel(self); win.title("Add Request"); win.resizable(False, False)

        ngo = tk.StringVar(); item = tk.StringVar(); qty = tk.StringVar()
        unit = tk.StringVar(value=UNITS[0]); lat = tk.StringVar(); lng = tk.StringVar()

        self._entry(win, "NGO Name *", ngo, 0)
        self._entry(win, "Item *", item, 1)
        self._entry(win, "Qty *", qty, 2)
        ttk.Label(win, text="Unit *").grid(row=3, column=0, sticky="e", padx=6, pady=4)
        ttk.Combobox(win, values=UNITS, textvariable=unit, width=26, state="readonly").grid(row=3, column=1, sticky="w", padx=6, pady=4)
        self._entry(win, "Lat", lat, 4); self._entry(win, "Lng", lng, 5)

        def submit():
            try:
                payload = {
                    "ngo_name": ngo.get().strip(),
                    "needs": [{"name": item.get().strip(), "qty": float(qty.get()), "unit": unit.get()}],
                    "location": {"lat": float(lat.get() or 0), "lng": float(lng.get() or 0)}
                }
                self._post("/requests", payload)
                messagebox.showinfo("Success", "Request created.")
                win.destroy(); self.load_requests()
            except Exception as e:
                messagebox.showerror("Create failed", str(e))

        ttk.Button(win, text="Create", command=submit).grid(row=6, column=0, columnspan=2, pady=8)

    # ----- Matching / Routes (existing minimal tab)
    def _build_match_routes(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="Matching & Routes")
        bar = ttk.Frame(tab); bar.pack(pady=5)
        ttk.Button(bar, text="Run Matching", command=self._run_matching).pack(side="left", padx=4)
        ttk.Button(bar, text="Plan Routes", command=self._plan_routes).pack(side="left", padx=4)

        self.result_box = tk.Text(tab, height=22)
        self.result_box.pack(fill="both", expand=True, padx=8, pady=6)

    def _run_matching(self):
        try:
            data = self._post("/matching/run", {})
            self.result_box.delete("1.0", tk.END)
            self.result_box.insert(tk.END, json.dumps(data, indent=2))
        except Exception as e:
            messagebox.showerror("Matching failed", str(e))

    def _plan_routes(self):
        try:
            dons = self._get("/donations")
            reqs = self._get("/requests")
            stops = []
            for d in dons:
                loc = d.get("location") or {}
                if "lat" in loc and "lng" in loc:
                    stops.append({"lat": loc["lat"], "lng": loc["lng"], "label": d.get("donor_name") or f'D{d.get("id")}'})
            for r in reqs:
                loc = r.get("location") or {}
                if "lat" in loc and "lng" in loc:
                    stops.append({"lat": loc["lat"], "lng": loc["lng"], "label": r.get("ngo_name") or f'R{r.get("id")}'})
            data = self._post("/routes/plan", {"stops": stops}, params={"provider":"internal"})
            self.result_box.delete("1.0", tk.END)
            self.result_box.insert(tk.END, json.dumps(data, indent=2))
        except Exception as e:
            messagebox.showerror("Plan routes failed", str(e))

    # ----- NEW: Routing (Address) tab with map + history + report
    def _build_routing_by_address(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="Routing (Address)")

        # inputs
        frm_in = ttk.Frame(tab); frm_in.pack(fill="x", pady=6)
        ttk.Label(frm_in, text="Origin (donor) address *").grid(row=0, column=0, sticky="w", padx=6)
        self.rt_origin = tk.StringVar(value="Manila City Hall, Manila")
        ttk.Entry(frm_in, textvariable=self.rt_origin, width=70).grid(row=1, column=0, sticky="w", padx=6, pady=2)

        self.rt_stops_frame = ttk.Frame(tab); self.rt_stops_frame.pack(fill="x", pady=2)
        self._routing_stop_vars = []
        def add_stop_field():
            var = tk.StringVar()
            self._routing_stop_vars.append(var)
            idx = len(self._routing_stop_vars)
            row = len(self._routing_stop_vars)-1
            ttk.Label(self.rt_stops_frame, text=f"Stop {idx}").grid(row=row, column=0, sticky="e", padx=6, pady=2)
            ttk.Entry(self.rt_stops_frame, textvariable=var, width=60).grid(row=row, column=1, sticky="w", padx=6, pady=2)
        add_stop_field(); add_stop_field()

        bar = ttk.Frame(tab); bar.pack(fill="x", pady=8)
        ttk.Button(bar, text="+ Add Stop", command=add_stop_field).pack(side="left", padx=4)
        ttk.Button(bar, text="Optimize Route from Addresses", command=self._do_optimize_route).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh History", command=self._load_route_history).pack(side="left", padx=12)
        ttk.Button(bar, text="Show Routes Summary", command=self._show_routes_summary).pack(side="left", padx=4)

        # output: info + map
        self.rt_info = tk.Text(tab, height=6)
        self.rt_info.pack(fill="x", padx=8, pady=6)

        self.rt_map_lbl = ttk.Label(tab)    # holds PhotoImage
        self.rt_map_lbl.pack(padx=8, pady=6)
        self._rt_map_photo = None           # keep reference

        # history panel
        hist_box = ttk.LabelFrame(tab, text="Recent Routes")
        hist_box.pack(fill="both", expand=True, padx=8, pady=6)
        self.rt_hist = tk.Text(hist_box, height=10)
        self.rt_hist.pack(fill="both", expand=True, padx=6, pady=6)

    def _do_optimize_route(self):
        try:
            origin = self.rt_origin.get().strip()
            stops = [v.get().strip() for v in self._routing_stop_vars if v.get().strip()]
            if not origin or len(stops) < 1:
                messagebox.showwarning("Missing", "Enter an origin and at least one stop.")
                return

            self.rt_info.delete("1.0", tk.END)
            self.rt_info.insert(tk.END, "Optimizing route...\n")
            self.rt_map_lbl.config(image=""); self._rt_map_photo = None
            self.update_idletasks()

            res = self._post_optimize_by_addresses([origin] + stops)

            kms = round(res["distance_m"]/1000, 2)
            mins = round(res["duration_s"]/60, 1)
            labels = res.get("ordered_labels", [])
            order = "\n".join(f"{i+1}. {lab}" for i, lab in enumerate(labels))

            self.rt_info.delete("1.0", tk.END)
            self.rt_info.insert(tk.END, f"Distance: {kms} km | Duration: {mins} min\nOrder:\n{order}\n")

            b64 = res.get("map_png_base64")
            if b64:
                img = Image.open(io.BytesIO(base64.b64decode(b64)))
                img.thumbnail((760, 440))
                self._rt_map_photo = ImageTk.PhotoImage(img)
                self.rt_map_lbl.config(image=self._rt_map_photo)

            self._load_route_history()

        except requests.Timeout:
            messagebox.showerror("Timeout", "The request timed out. Try again.")
        except Exception as e:
            messagebox.showerror("Routing failed", str(e))

    def _load_route_history(self):
        try:
            routes = self._get_route_history(limit=20)
            self.rt_hist.delete("1.0", tk.END)
            if not routes:
                self.rt_hist.insert(tk.END, "No routes yet.\n")
                return
            for r in routes:
                created = r.get("created_at","")
                dist = r.get("distance_km","?")
                dur = r.get("duration_min","?")
                labels = " → ".join(r.get("ordered_labels", []))
                self.rt_hist.insert(tk.END, f"{created} | {dist} km | {dur} min | {labels}\n")
        except Exception as e:
            messagebox.showerror("History failed", str(e))

    def _show_routes_summary(self):
        try:
            b64 = self._get_routes_summary_img()
            img = Image.open(io.BytesIO(base64.b64decode(b64)))
            img.thumbnail((820, 520))
            photo = ImageTk.PhotoImage(img)
            win = tk.Toplevel(self); win.title("Routes Summary")
            lbl = ttk.Label(win, image=photo)
            lbl.image = photo
            lbl.pack(padx=8, pady=8)
        except Exception as e:
            messagebox.showerror("Report failed", str(e))

    # small helper
    def _entry(self, parent, label, var, row, show=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="e", padx=6, pady=4)
        ttk.Entry(parent, textvariable=var, width=28, show=show).grid(row=row, column=1, sticky="w", padx=6, pady=4)


if __name__ == "__main__":
    App().mainloop()
