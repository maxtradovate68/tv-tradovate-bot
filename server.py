from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

TD_USERNAME = os.environ.get("TD_USERNAME")
TD_PASSWORD = os.environ.get("TD_PASSWORD")
TD_CID      = os.environ.get("TD_CID")
TD_SEC      = os.environ.get("TD_SEC")
TD_ACCOUNT_ID = os.environ.get("TD_ACCOUNT_ID")
TD_ACCOUNT_SPEC = os.environ.get("TD_ACCOUNT_SPEC")

LOGIN_URL = "https://live-api.tradovate.com/v1/auth/accessTokenRequest"
ORDER_URL = "https://live.tradovateapi.com/v1/order/place"

def td_login():
    payload = {
        "name": TD_USERNAME,
        "password": TD_PASSWORD,
        "cid": TD_CID,
        "sec": TD_SEC
    }
    r = requests.post(LOGIN_URL, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()["accessToken"]

@app.route("/")
def home():
    return "Bot MNQ Running"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        print("Received:", data)

        access_token = td_login()

        order = {
            "accountId": int(TD_ACCOUNT_ID),
            "accountSpec": TD_ACCOUNT_SPEC,
            "symbol": data["ticker"],
            "action": "Buy" if data["action"] == "buy" else "Sell",
            "orderType": "Market",
            "orderQty": int(data["quantity"])
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        r = requests.post(ORDER_URL, json=order, headers=headers, timeout=15)
        print("Order status:", r.status_code, r.text)

        return jsonify({"status": "ok", "tradovate": r.json()})

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"status": "error", "error": str(e)}), 500
