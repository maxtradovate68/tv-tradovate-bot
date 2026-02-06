from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

TD_USERNAME = os.environ.get("TD_USERNAME")
TD_PASSWORD = os.environ.get("TD_PASSWORD")
TD_CID      = os.environ.get("TD_CID")
TD_SEC      = os.environ.get("TD_SEC")
TD_ACCOUNT_ID = os.environ.get("TD_ACCOUNT_ID")

LOGIN_URL = "https://live.tradovateapi.com/v1/auth/accesstokenrequest"
ORDER_URL = "https://live.tradovateapi.com/v1/order/place"

def get_access_token():
    payload = {
        "name": TD_USERNAME,
        "password": TD_PASSWORD,
        "cid": TD_CID,
        "sec": TD_SEC
    }
    r = requests.post(LOGIN_URL, json=payload)
    data = r.json()
    print("Login response:", data)
    return data.get("accessToken")

@app.route("/", methods=["GET"])
def home():
    return "Bot MNQ Running"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print("Received:", data)

    access_token = get_access_token()
    if not access_token:
        return jsonify({"status": "login failed"}), 400

    ticker = data["ticker"]
    action = data["action"]
    qty    = int(data["quantity"])

    order = {
        "accountId": TD_ACCOUNT_ID,
        "symbol": ticker,
        "orderType": "Market",
        "action": "Buy" if action == "buy" else "Sell",
        "quantity": qty
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    r = requests.post(ORDER_URL, json=order, headers=headers)
    print("Tradovate response:", r.text)

    return jsonify({"status": "ok"})
