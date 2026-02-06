from flask import Flask, request, jsonify
import requests, os, time

app = Flask(__name__)

TD_USERNAME   = os.environ.get("TD_USERNAME")
TD_PASSWORD   = os.environ.get("TD_PASSWORD")
TD_CID        = os.environ.get("TD_CID")
TD_SEC        = os.environ.get("TD_SEC")
TD_ACCOUNT_ID = os.environ.get("TD_ACCOUNT_ID")

AUTH_URL  = "https://live.tradovateapi.com/v1/auth/accesstokenrequest"
ORDER_URL = "https://live.tradovateapi.com/v1/order/placeorder"  # plus standard que /order/place

# cache token en mémoire
_cached_token = None
_cached_exp_ms = 0

def get_access_token():
    global _cached_token, _cached_exp_ms

    now_ms = int(time.time() * 1000)
    if _cached_token and now_ms < (_cached_exp_ms - 30_000):  # marge 30s
        return _cached_token

    if not all([TD_USERNAME, TD_PASSWORD, TD_CID, TD_SEC]):
        raise RuntimeError("Missing TD_* env vars for login")

    payload = {
        "name": TD_USERNAME,
        "password": TD_PASSWORD,
        "appId": TD_CID,
        "appVersion": "1.0",
        "cid": TD_CID,
        "sec": TD_SEC,
        "deviceId": "railway-bot"
    }

    r = requests.post(AUTH_URL, json=payload, timeout=20)
    print("Login status:", r.status_code, "body:", r.text)
    r.raise_for_status()
    j = r.json()

    _cached_token = j["accessToken"]
    _cached_exp_ms = j.get("expirationTime", 0)  # Tradovate renvoie souvent un timestamp ms
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
        return jsonify({"status":"error", "error":"Bad payload"}), 400

    token = get_access_token()

    order = {
        "accountId": int(TD_ACCOUNT_ID),
        "action": "Buy" if action == "buy" else "Sell",
        "symbol": ticker,      # ex: "MNQ" ou "MNQH6" selon ce que tu veux gérer
        "orderType": "Market",
        "quantity": qty
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    r = requests.post(ORDER_URL, json=order, headers=headers, timeout=20)
    print("Order status:", r.status_code, "body:", r.text)

    # IMPORTANT: si Tradovate refuse, on remonte l’erreur (sinon tu crois que “c’est ok”)
    if r.status_code >= 300:
        return jsonify({"status":"error", "tradovate": r.text}), 500

    return jsonify({"status":"ok", "tradovate": r.json() if r.headers.get("content-type","").startswith("application/json") else r.text})
