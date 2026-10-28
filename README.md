# Screenshot Machine Flask API

## Setup

```powershell
py -m pip install -r requirements.txt
py app.py
```

The customer key is configured in the local `.env` file. To change it, update:

```text
SCREENSHOT_MACHINE_KEY=your_customer_key
```

Open `http://127.0.0.1:5080/`.

## MongoDB API

Requires MongoDB running locally. The database is `sample_db` and screenshot requests are stored in the `screenshots` collection.

Every successful `POST /api/screenshot` request is automatically saved. Use `GET /api/screenshots` to retrieve the saved requests.

Change the MongoDB connection with `MONGO_URI` in `.env`.

## Test the API

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:5080/api/screenshot" `
  -ContentType "application/json" `
  -Body '{"url":"https://example.com"}'
```

