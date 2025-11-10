# FoodBridge API (Backend)

## Quickstart
```sh
python -m venv .venv
. .venv/Scripts/activate   # Windows
pip install -r requirements.txt

# env
copy .env.sample .env  # edit Mongo URI, JWT, ORG defaults

uvicorn app.main:app --reload
