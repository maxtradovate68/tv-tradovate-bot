from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

TD_ACCESS_TOKEN = os.environ.get("TD_ACCESS_TOKEN")
TD_ACCOUNT_ID   = os.environ.get("TD_ACCOUNT_ID")

TRADOVATE_URL = "https://live.tradovateapi.com/v1/order/place"

@app.route("/", methods=["GET"])
def home():
    return "Bot MNQ Running"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print("Received:", data)

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
        "Authorization": f"Bearer {TD_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    r = requests.post(TRADOVATE_URL, json=order, headers=headers)
    print("Tradovate response:", r.text)

    return jsonify({"status": "ok"})
