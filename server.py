from flask import Flask, request, jsonify
import requests
import os
import time

app = Flask(__name__)

TD_USERNAME   = os.environ.get("TD_USERNAME")
TD_PASSWORD   = os.environ.get("TD_PASSWORD")
TD_CID        = os.environ.get("TD_CID")
TD_SEC        = os.environ.get("TD_SEC")
TD_ACCOUNT_ID = os.environ.get("TD_ACCOUNT_ID")
TD_ACCOUNT_SPEC = os.environ.get("TD_ACCOUNT_SPEC")
TRADOVATE_ENV = os.environ.get("TRADOVATE_ENV", "live")  # "live" or "demo"

BASE_URL = "https://live.tradovateapi.com/v1" if TRADOVATE_ENV == "live" else "https://demo.tradovateapi.com/v1"

# cache token
_cached_token = None
_cached_token_exp_ms = 0

def _now_ms():
    return int(time.time() * 1000)

def get_access_token():
    global _cached_token, _cached_token_exp_ms

    # if token still valid (give 30s margin)
    if _cached_token and _now_ms() < (_cached_token_exp_ms - 30_000):
        return _cached_token

    url = f"{BASE_URL}/auth/accesstokenrequest"
    payload = {
        "name": TD_USERNAME,
        "password": TD_PASSWORD,
        "appId": TD_CID,
        "appVersion": "1.0",
        "cid": TD_CID,
        "sec": TD_SEC,
    }

    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()
    data = r.json()

    _cached_token = data["accessToken"]
    # expirationTime is ISO; simplest: assume ~1h if not parsing.
    # If you want exact parsing later, we can add it.
    _cached_token_exp_ms = _now_ms() + 55 * 60 * 1000
    return _cached_token

@app.route("/", methods=["GET"])
def home():
    return "Bot MNQ Running"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json or {}
    print("Received:", data)

    ticker = data.get("ticker")
    action = data.get("action")
    qty    = int(data.get("quantity", 0))

    if not ticker or action not in ("buy", "sell") or qty <= 0:
        return jsonify({"status":"error","error":"Bad payload"}), 400

    token = get_access_token()

    # ⚠️ Tradovate expects orderQty (not quantity) and endpoint is placeorder.
    order = {
        "accountSpec": TD_ACCOUNT_SPEC,
        "accountId": str(TD_ACCOUNT_ID),
        "action": "Buy" if action == "buy" else "Sell",
        "symbol": ticker,
        "orderQty": qty,
        "orderType": "Market",
        "isAutomated": "true"
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    url = f"{BASE_URL}/order/placeorder"
    r = requests.post(url, json=order, headers=headers, timeout=10)

    print("Order status:", r.status_code, "body:", r.text)

    # IMPORTANT: if Tradovate refuses, return 500 so you see it
    if r.status_code != 200:
        return jsonify({"status":"error","tradovate_status": r.status_code, "body": r.text}), 500

    return jsonify({"status":"ok","tradovate": r.json()})

@app.route("/accounts", methods=["GET"])
def list_accounts():
    token = get_access_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    url = f"{BASE_URL}/account/list"
    r = requests.get(url, headers=headers, timeout=10)

    print("Account list:", r.text)
    return r.text
