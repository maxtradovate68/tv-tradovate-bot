from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

TD_USERNAME     = os.environ.get("TD_USERNAME")
TD_PASSWORD     = os.environ.get("TD_PASSWORD")
TD_CID          = os.environ.get("TD_CID")
TD_SEC          = os.environ.get("TD_SEC")
TD_ACCOUNT_ID   = os.environ.get("TD_ACCOUNT_ID")
TD_ACCOUNT_SPEC = os.environ.get("TD_ACCOUNT_SPEC")

BASE = "https://live.tradovateapi.com/v1"

def td_login():
    url = f"{BASE}/auth/accesstoken"
    payload = {
        "name": TD_USERNAME,
        "password": TD_PASSWORD,
        "appId": TD_CID,
        "appVersion": "1.0",
        "deviceId": "railway",
        "cid": TD_CID,
        "sec": TD_SEC,
    }
    r = requests.post(url, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()["accessToken"]

@app.route("/", methods=["GET"])
def home():
    return "Bot MNQ Running"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    print("Received:", data)

    ticker = data["ticker"]              # ex: "MNQ"
    action = data["action"]              # "buy" / "sell"
    qty    = int(data["quantity"])       # IMPORTANT: int

    access_token = td_login()

    order = {
        "accountId": int(TD_ACCOUNT_ID),         # IMPORTANT: int
        "accountSpec": TD_ACCOUNT_SPEC,          # ex: "1697337"
        "action": "Buy" if action == "buy" else "Sell",
        "symbol": ticker,                        # on verra après pour front-month auto
        "orderType": "Market",
        "orderQty": qty                          # IMPORTANT: orderQty (pas quantity)
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    r = requests.post(f"{BASE}/order/place", json=order, headers=headers, timeout=20)
    print("Order status:", r.status_code, "body:", r.text)

    return jsonify({"status": "ok", "tradovate_status": r.status_code, "tradovate_body": r.text})
