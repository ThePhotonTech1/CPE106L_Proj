import flet as ft
import httpx

API = "http://127.0.0.1:8000/api/routes/optimize_by_address"

def call_optimize_by_address_sync(addresses):
    # longer timeout to avoid client-side timeouts first
    with httpx.Client(timeout=90) as client:
        r = client.post(API, json={"addresses": addresses})
        r.raise_for_status()
        return r.json()

def main(page: ft.Page):
    page.title = "FoodBridge Route Demo"

    origin = ft.TextField(label="Origin (donor) address", value="Manila City Hall, Manila", width=420)
    stop1  = ft.TextField(label="Stop 1 (recipient)", value="Makati City Hall, Makati", width=420)
    stop2  = ft.TextField(label="Stop 2 (recipient)", value="Bonifacio Global City, Taguig", width=420)

    out = ft.Column()
    img = ft.Image(width=560, height=360, fit=ft.ImageFit.CONTAIN, visible=False)

    def run_optimize(e):
        try:
            out.controls = [ft.Text("Finding route...")]
            img.visible = False
            img.src_base64 = None
            page.update()

            addrs = [origin.value.strip()]
            if stop1.value.strip():
                addrs.append(stop1.value.strip())
            if stop2.value.strip():
                addrs.append(stop2.value.strip())

            res = call_optimize_by_address_sync(addrs)
            kms = round(res["distance_m"] / 1000, 2)
            mins = round(res["duration_s"] / 60, 1)
            labels = res.get("ordered_labels", [])
            order_lines = "\n".join(f"{i+1}. {lab}" for i, lab in enumerate(labels))

            out.controls = [
                ft.Text(f"Distance: {kms} km  |  Duration: {mins} min"),
                ft.Text("Order:"),
                ft.Text(order_lines if order_lines else "(no labels)")
            ]

            b64 = res.get("map_png_base64")
            if b64:
                img.src_base64 = b64
                img.visible = True

        except httpx.TimeoutException:
            out.controls = [ft.Text("Error: timed out")]
            img.visible = False
        except Exception as err:
            out.controls = [ft.Text(f"Error: {err}")]
            img.visible = False

        page.update()

    page.add(
        ft.Row([origin]),
        ft.Row([stop1, stop2]),
        ft.ElevatedButton("Optimize Route from Addresses", on_click=run_optimize),
        out,
        img
    )

    hist_out = ft.Column(scroll=ft.ScrollMode.AUTO, height=220)

    def load_history(e):
        try:
            with httpx.Client(timeout=45) as client:
                r = client.get("http://127.0.0.1:8000/api/routes/history?limit=20")
                r.raise_for_status()
                routes = r.json()["routes"]
            hist_out.controls = [
                ft.Text(f"{r['created_at']} | {r['distance_km']} km | {r['duration_min']} min")
                for r in routes
            ] or [ft.Text("No routes yet.")]
        except Exception as err:
            hist_out.controls = [ft.Text(f"Error: {err}")]
        page.update()

    page.add(ft.ElevatedButton("View Route History", on_click=load_history), hist_out)

    def show_summary(e):
        try:
            with httpx.Client(timeout=45) as client:
                r = client.get("http://127.0.0.1:8000/api/reports/routes_summary")
                r.raise_for_status()
                b64 = r.json()["img_base64"]
            summary_img = ft.Image(src_base64=b64, width=560, height=360)
            page.dialog = ft.AlertDialog(
            title=ft.Text("Routes Summary"),
                content=summary_img
            )
            page.dialog.open = True
            page.update()
        except Exception as err:
            page.snack_bar = ft.SnackBar(ft.Text(f"Error: {err}"), open=True)
            page.update()

    page.add(ft.ElevatedButton("Show Analytics (Matplotlib)", on_click=show_summary))



ft.app(target=main)
