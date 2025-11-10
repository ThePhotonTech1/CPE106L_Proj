import flet as ft
import httpx

API_BASE = "http://127.0.0.1:8000"
API_OPTIMIZE = f"{API_BASE}/api/routes/optimize_by_address"
API_HISTORY  = f"{API_BASE}/api/routes/history"
API_REPORT   = f"{API_BASE}/api/reports/routes_summary"

class RoutingView:
    def __init__(self, page: ft.Page):
        self.page = page

        # UI controls
        self.origin_tf = ft.TextField(label="Origin (donor) address", width=600, value="Manila City Hall, Manila")
        self.stops_col = ft.Column()
        self.route_out = ft.Column()
        self.route_img = ft.Image(width=700, height=420, fit=ft.ImageFit.CONTAIN, visible=False)

        # history + reports (optional)
        self.hist_out = ft.Column(scroll=ft.ScrollMode.AUTO, height=220)
        self.report_img = ft.Image(width=700, height=420, fit=ft.ImageFit.CONTAIN, visible=False)
        self.report_out = ft.Text("", size=12)

        # buttons
        self.btn_add_stop = ft.ElevatedButton("Add Stop", on_click=self.add_stop)
        self.btn_optimize = ft.ElevatedButton("Optimize Route from Addresses", on_click=self.run_optimize)
        self.btn_history  = ft.OutlinedButton("Refresh Route History", on_click=self.load_history)
        self.btn_report   = ft.OutlinedButton("Show Routes Summary (Matplotlib)", on_click=self.load_report)

        # start with two stops
        self.add_stop(); self.add_stop()

    # ---------- HTTP helpers (sync) ----------
    def _optimize_by_addresses(self, addresses: list[str]) -> dict:
        with httpx.Client(timeout=90) as c:
            r = c.post(API_OPTIMIZE, json={"addresses": addresses})
            r.raise_for_status()
            return r.json()

    def _history(self, limit: int = 20) -> list[dict]:
        with httpx.Client(timeout=45) as c:
            r = c.get(f"{API_HISTORY}?limit={limit}")
            r.raise_for_status()
            return r.json()["routes"]

    def _routes_summary_img(self) -> str:
        with httpx.Client(timeout=45) as c:
            r = c.get(API_REPORT)
            r.raise_for_status()
            return r.json()["img_base64"]

    # ---------- UI handlers ----------
    def add_stop(self, e=None):
        self.stops_col.controls.append(ft.TextField(label=f"Stop {len(self.stops_col.controls)+1}", width=600))
        self.page.update()

    def run_optimize(self, e=None):
        try:
            base = self.origin_tf.value.strip()
            stops = [c.value.strip() for c in self.stops_col.controls if isinstance(c, ft.TextField) and c.value.strip()]
            if not base or len(stops) < 1:
                self.route_out.controls = [ft.Text("Please enter an origin and at least one stop.", color=ft.colors.RED)]
                self.route_img.visible = False
                self.page.update()
                return

            self.route_out.controls = [ft.Text("Finding and optimizing route...")]
            self.route_img.visible = False
            self.route_img.src_base64 = None
            self.page.update()

            res = self._optimize_by_addresses([base] + stops)
            kms = round(res["distance_m"]/1000, 2)
            mins = round(res["duration_s"]/60, 1)
            labels = res.get("ordered_labels", [])
            order_lines = "\n".join(f"{i+1}. {lab}" for i, lab in enumerate(labels))

            self.route_out.controls = [
                ft.Text(f"Distance: {kms} km  |  Duration: {mins} min", size=16, weight=ft.FontWeight.W_600),
                ft.Text("Order:", size=14),
                ft.Text(order_lines if order_lines else "(no labels)"),
            ]

            b64 = res.get("map_png_base64")
            if b64:
                self.route_img.src_base64 = b64
                self.route_img.visible = True

        except httpx.TimeoutException:
            self.route_out.controls = [ft.Text("Error: timed out", color=ft.colors.RED)]
            self.route_img.visible = False
        except Exception as err:
            self.route_out.controls = [ft.Text(f"Error: {err}", color=ft.colors.RED)]
            self.route_img.visible = False

        self.page.update()

    def load_history(self, e=None):
        try:
            routes = self._history(20)
            if not routes:
                self.hist_out.controls = [ft.Text("No routes yet.")]
            else:
                self.hist_out.controls = [
                    ft.Text(
                        f"{r.get('created_at','')}  |  {r.get('distance_km','?')} km  |  {r.get('duration_min','?')} min  |  {' → '.join(r.get('ordered_labels', []))[:140]}",
                        size=12,
                    )
                    for r in routes
                ]
        except Exception as err:
            self.hist_out.controls = [ft.Text(f"Error: {err}", color=ft.colors.RED)]
        self.page.update()

    def load_report(self, e=None):
        try:
            self.report_out.value = "Loading report..."
            self.report_img.visible = False
            self.page.update()
            b64 = self._routes_summary_img()
            self.report_img.src_base64 = b64
            self.report_img.visible = True
            self.report_out.value = ""
        except Exception as err:
            self.report_img.visible = False
            self.report_out.value = f"Error: {err}"
        self.page.update()

    # ---------- Public: a ready-to-insert tab/page ----------
    def as_tab(self) -> ft.Tab:
        content = ft.Container(
            padding=10,
            content=ft.Column(
                [
                    ft.Text("Routing", size=20, weight=ft.FontWeight.BOLD),
                    ft.Row([self.origin_tf]),
                    ft.Row([self.btn_add_stop]),
                    self.stops_col,
                    ft.Row([self.btn_optimize]),
                    self.route_out,
                    self.route_img,
                    ft.Divider(),
                    ft.Text("History", size=16, weight=ft.FontWeight.W_600),
                    ft.Row([self.btn_history]),
                    self.hist_out,
                    ft.Divider(),
                    ft.Text("Reports", size=16, weight=ft.FontWeight.W_600),
                    ft.Row([self.btn_report]),
                    self.report_out,
                    self.report_img,
                ],
                scroll=ft.ScrollMode.AUTO,
            ),
        )
        return ft.Tab(text="Routing", content=content)
