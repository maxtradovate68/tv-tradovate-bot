from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# ENV
TD_USERNAME   = os.getenv("TD_USERNAME")
TD_PASSWORD   = os.getenv("TD_PASSWORD")
TD_CID        = os.getenv("TD_CID")      # Client ID
TD_SEC        = os.getenv("TD_SEC")      # Client Secret
TD_ACCOUNT_ID = os.getenv("TD_ACCOUNT_ID")  # IMPORTANT: l'ID numérique ex: 861089

BASE_URL  = "https://live.tradovateapi.com"
LOGIN_URL = f"{BASE_URL}/v1/auth/accesstoken"
ORDER_URL = f"{BASE_URL}/v1/order/place"

def missing_env():
    need = ["TD_USERNAME","TD_PASSWORD","TD_CID","TD_SEC","TD_ACCOUNT_ID"]
    missing = [k for k in need if not os.getenv(k)]
    return missing

def td_login():
    payload = {
        "name": TD_USERNAME,
        "password": TD_PASSWORD,
        "appId": TD_CID,
        "appVersion": "1.0",
        "cid": TD_CID,
        "sec": TD_SEC
    }
    r = requests.post(LOGIN_URL, json=payload, timeout=15)
    print("Login status:", r.status_code, "body:", r.text)
    r.raise_for_status()
    return r.json()["accessToken"]

@app.route("/", methods=["GET"])
def home():
    return "Bot MNQ Running"

@app.route("/webhook", methods=["POST"])
def webhook():
    miss = missing_env()
    if miss:
        return jsonify({"status": "error", "error": f"Missing env vars: {miss}"}), 500

    data = request.get_json(force=True, silent=True) or {}
    print("Received:", data)

    symbol = data.get("ticker", "MNQ")
    side   = data.get("action", "").lower()
    qty    = int(data.get("quantity", 0))

    if side not in ("buy", "sell") or qty <= 0:
        return jsonify({"status": "error", "error": "Bad payload (action/quantity)"}), 400

    try:
        token = td_login()

        order = {
            "accountId": int(TD_ACCOUNT_ID),
            "action": "Buy" if side == "buy" else "Sell",
            "symbol": symbol,
            "ordType": "Market",
            "orderQty": qty,
            "isAutomated": True
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        r = requests.post(ORDER_URL, json=order, headers=headers, timeout=15)
        print("Order status:", r.status_code, "body:", r.text)

        # si Tradovate refuse, on renvoie l’erreur au caller (TradingView / curl)
        if r.status_code >= 400:
            return jsonify({"status": "error", "tradovate": r.text}), 400

        return jsonify({"status": "ok", "tradovate": r.json()})

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"status": "error", "error": str(e)}), 500
