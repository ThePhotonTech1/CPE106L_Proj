# CPE106L_Proj

# FoodBridge - Guide

1. Install **Python 3.10+** and **MongoDB** (local or Atlas).
2. Open terminal → go to **backend** folder.
3. Run:

   pip install -r requirements.txt
   
   cp .env.example .env
   
   uvicorn app.main:app --reload
   
5. Open another terminal → go to **frontend** folder.
6. Run:

   pip install -r requirements.txt
   
   python main_flet.py

7. Make sure the backend is running before starting the Flet app.
8. Access backend docs at **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**.
9. Use the app window to register, log in, and test features.



