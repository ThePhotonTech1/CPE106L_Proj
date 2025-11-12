# CPE106L_Proj


# FoodBridge: Food Rescue and Redistribution Platform

**Course:** Software Design Project
**Section:** CPE106-4
**Group:** Group 07
**Date:** November 2025

---

## Project Overview

FoodBridge is a software system that connects food donors such as restaurants and grocery stores with recipients such as shelters or food banks. The goal is to reduce food waste and improve community food distribution. The system allows users to register as donors, recipients, dispatchers, or drivers. It provides modules for donation offers, food requests, automatic matching, route planning, and delivery tracking.

---

## System Architecture

FoodBridge follows a three-tier architecture:

1. **Presentation Layer** – Flet-based graphical user interface (GUI)
2. **Application Layer** – FastAPI backend for handling requests and logic
3. **Data Layer** – MongoDB database for persistent storage

Data flows between these layers through RESTful API endpoints.

```
[User Interface: Flet] <--> [API Server: FastAPI] <--> [Database: MongoDB]
```

---

## Features

* User registration and authentication using JWT
* Role-based access control (Donor, Recipient, Dispatcher, Driver)
* Donors can create and manage donation offers
* Recipients can submit food requests
* Dispatcher can match offers to requests using a greedy algorithm
* Route planning for delivery and driver assignment
* Driver progress tracking through checkpoints
* Reporting module for tracking food saved and activity summaries

---

## Technologies Used

| Layer     | Technology                                           |
| --------- | ---------------------------------------------------- |
| Frontend  | Flet, Matplotlib                                     |
| Backend   | FastAPI, Uvicorn, Pydantic                           |
| Database  | MongoDB with Motor driver                            |
| Utilities | Python-Dotenv, PyJWT, Requests, Geopy, Pandas, Numpy |

---

## Folder Structure

```
FoodBridge/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── routes/
│   │   ├── models/
│   │   ├── services/
│   │   └── utils/
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── main_flet.py
│   ├── api.py
│   ├── views/
│   ├── requirements.txt
│
└── README.md
```

---

## Installation and Setup

### 1. Clone or Extract the Project

```bash
git clone https://github.com/<your-repo>/foodbridge.git
cd foodbridge
```

Or extract the ZIP file provided by your group.

---

### 2. Backend Setup

```bash
cd backend
pip install -r requirements.txt
```

Copy the sample environment file:

```bash
cp .env.example .env
```

Edit the `.env` file and set your MongoDB connection string and JWT secret key.

Start the FastAPI server:

```bash
uvicorn app.main:app --reload
```

Verify it is running at:
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

### 3. Frontend Setup

In a new terminal:

```bash
cd frontend
pip install -r requirements.txt
python main_flet.py
```

The GUI will open showing the login and registration window.

---

## Sample Demo Accounts

| Role       | Email                                                   | Password |
| ---------- | ------------------------------------------------------- | -------- |
| Donor      | [donor@example.com](mailto:donor@example.com)           | 1234     |
| Recipient  | [recipient@example.com](mailto:recipient@example.com)   | 1234     |
| Dispatcher | [dispatcher@example.com](mailto:dispatcher@example.com) | 1234     |
| Driver     | [driver@example.com](mailto:driver@example.com)         | 1234     |

---

## Key API Endpoints

| Method | Endpoint                             | Description                |
| ------ | ------------------------------------ | -------------------------- |
| POST   | /api/auth/register                   | Register a new user        |
| POST   | /api/auth/login                      | User login                 |
| POST   | /api/offers                          | Create donation offer      |
| POST   | /api/requests                        | Create food request        |
| POST   | /api/match/plan                      | Generate donation matches  |
| POST   | /api/routes/plan_from_matches        | Plan delivery route        |
| POST   | /api/dispatch/routes/{id}/start      | Start a route              |
| POST   | /api/dispatch/routes/{id}/checkpoint | Record route checkpoint    |
| POST   | /api/dispatch/routes/{id}/complete   | Complete a route           |
| GET    | /api/reports/summary                 | Retrieve analytics summary |

---

## Reports and Analytics

* Total food saved (in kilograms)
* Active donor and recipient count
* Number of completed deliveries
* Participation and route performance charts

---

## Troubleshooting

| Issue                  | Solution                                    |
| ---------------------- | ------------------------------------------- |
| Module not found       | Run `pip install -r requirements.txt` again |
| MongoDB not connecting | Check `MONGO_URI` in your `.env` file       |
| API unauthorized       | Ensure JWT token is included in headers     |
| Flet app not launching | Run the frontend with `python main_flet.py` |

---

## Documentation Contents

1. Community Needs and Requirements
2. Use Case and Class Diagrams
3. Requirements Traceability Matrix
4. System Architecture Description
5. Detailed Use Case Descriptions
6. User Interface Screenshots
7. Project Plan and Timeline

---

