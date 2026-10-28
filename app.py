import os
import re
from datetime import datetime, timezone
import urllib.error
import urllib.parse
import urllib.request

from dotenv import load_dotenv
from flask import Flask, jsonify, request, render_template, Response
from pymongo import MongoClient
from pymongo.errors import PyMongoError

load_dotenv()
app = Flask(__name__)

SCREENSHOT_API_URL = "https://api.screenshotmachine.com/"
SCREENSHOT_MACHINE_KEY = os.getenv("SCREENSHOT_MACHINE_KEY", "").strip()
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/").strip()

mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
database = mongo_client["sample_db"]
screenshots_collection = database["screenshots"]


def generate_screenshot_api_url(url, 
                                dimension="1366x768", 
                                device="desktop",
                                cache_limit="0",
                                delay="200", 
                                zoom="100"):
    options = {
        "url": url, 
        "dimension": dimension,
        "device": device,
        "cacheLimit": cache_limit,
        "delay": delay,
        "zoom": zoom,
    }

    api_url = f"{SCREENSHOT_API_URL}?key={urllib.parse.quote(SCREENSHOT_MACHINE_KEY, safe='')}"
    return api_url + "&" + urllib.parse.urlencode(options)


def validate_screenshot_url(value):
    if not isinstance(value, str):
        return False
    parsed = urllib.parse.urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_integer(value, minimum, maximum, field_name):
    if not re.fullmatch(r"\d+", str(value)):
        return f"{field_name} must be an integer between {minimum} and {maximum}."
    number = int(value)
    if number < minimum or number > maximum:
        return f"{field_name} must be between {minimum} and {maximum}."
    return None

@app.get("/")
def screenshot_page():
    return render_template("screenshot.html")


@app.post("/api/screenshot")
def create_screenshot_url():
    data = request.get_json(silent=True) or request.form.to_dict()
    url = str(data.get("url", "")).strip()
    dimension = str(data.get("dimension", "1366x768")).strip()
    device = str(data.get("device", "desktop")).strip()
    cache_limit = str(data.get("cacheLimit", "0")).strip()
    delay = str(data.get("delay", "200")).strip()
    zoom = str(data.get("zoom", "100")).strip()

    if not validate_screenshot_url(url):
        return jsonify({"success": False, "error": "Enter a valid HTTP or HTTPS URL."}), 400
    if not SCREENSHOT_MACHINE_KEY:
        return jsonify({
            "success": False,
            "error": "Screenshot Machine is not configured. Set SCREENSHOT_MACHINE_KEY.",
        }), 503
    if not re.fullmatch(r"(?:\d+x(?:\d+|full)|full)", dimension):
        return jsonify({"success": False, "error": "Dimension must look like 1366x768 or 1366xfull."}), 400
    if device not in {"desktop", "mobile", "tablet"}:
        return jsonify({"success": False, "error": "Device must be desktop, mobile, or tablet."}), 400

    for value, minimum, maximum, field_name in (
        (cache_limit, 0, 365, "cacheLimit"),
        (delay, 0, 60000, "delay"),
        (zoom, 25, 500, "zoom"),
    ):
        error = validate_integer(value, minimum, maximum, field_name)
        if error:
            return jsonify({"success": False, "error": error}), 400

    screenshot_url = generate_screenshot_api_url(
        url, dimension, device, cache_limit, delay, zoom
    )

    screenshot_document = {
        "url": url,
        "dimension": dimension,
        "device": device,
        "cacheLimit": cache_limit,
        "delay": delay,
        "zoom": zoom,
        "screenshotUrl": screenshot_url,
        "createdAt": datetime.now(timezone.utc),
    }

    try:
        result = screenshots_collection.insert_one(screenshot_document)
        return jsonify({
            "success": True,
            "screenshotUrl": screenshot_url,
            "id": str(result.inserted_id),
        })
    except PyMongoError:
        return jsonify({
            "success": False,
            "error": "Could not save the screenshot request to MongoDB.",
        }), 503


@app.get("/api/screenshot/download")
def download_screenshot():
    url = str(request.args.get("url", "")).strip()
    if not validate_screenshot_url(url):
        return jsonify({"success": False, "error": "Enter a valid HTTP or HTTPS URL."}), 400
    if not SCREENSHOT_MACHINE_KEY:
        return jsonify({
            "success": False,
            "error": "Screenshot Machine is not configured. Set SCREENSHOT_MACHINE_KEY.",
        }), 503

    options = request.args.to_dict(flat=True)
    options.pop("url", None)
    screenshot_url = generate_screenshot_api_url(url, **{
        "dimension": options.get("dimension", "1366x768"),
        "device": options.get("device", "desktop"),
        "cache_limit": options.get("cacheLimit", "0"),
        "delay": options.get("delay", "200"),
        "zoom": options.get("zoom", "100"),
    })

    try:
        with urllib.request.urlopen(screenshot_url, timeout=60) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"image/png", "image/jpeg", "image/gif", "image/webp"}:
                return jsonify({"success": False,
                                "error": "Screenshot Machine did not return an image."}), 502
            image = response.read()
            return Response(image, mimetype=content_type, headers={
                "Content-Disposition": "attachment; filename=screenshot.png"
            })
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return jsonify({"success": False, "error": "Could not download the screenshot."}), 502


@app.get("/api/screenshots")
def get_screenshot_requests():
    try:
        screenshots = []
        for screenshot in screenshots_collection.find({}).sort("createdAt", -1):
            screenshot["_id"] = str(screenshot["_id"])
            created_at = screenshot.get("createdAt")
            if hasattr(created_at, "isoformat"):
                screenshot["createdAt"] = created_at.isoformat()
            screenshots.append(screenshot)

        return jsonify({
            "success": True,
            "message": "Screenshot requests retrieved successfully.",
            "data": screenshots,
        })
    except PyMongoError:
        return jsonify({
            "success": False,
            "message": "Could not fetch screenshot requests from MongoDB.",
            "data": [],
        }), 503


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5080, debug=True)
