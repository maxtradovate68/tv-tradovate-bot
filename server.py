from flask import Flask, request, jsonify
import os, requests

app = Flask(__name__)

BASE_URL   = "https://live.tradovateapi.com/v1"
LOGIN_URL  = f"{BASE_URL}/auth/accesstokenrequest"
ORDER_URL  = f"{BASE_URL}/order/placeorder"

TD_USERNAME     = os.getenv("TD_USERNAME")
TD_PASSWORD     = os.getenv("TD_PASSWORD")
TD_CID          = os.getenv("TD_CID")
TD_SEC          = os.getenv("TD_SEC")
TD_ACCOUNT_ID   = os.getenv("TD_ACCOUNT_ID")
TD_ACCOUNT_SPEC = os.getenv("TD_ACCOUNT_SPEC")

def must_env(*names):
    missing = [n for n in names if not os.getenv(n)]
    if missing:
        raise RuntimeError(f"Missing env vars: {missing}")

def td_login():
    must_env("TD_USERNAME","TD_PASSWORD","TD_CID","TD_SEC")
    payload = {
        "name": TD_USERNAME,
        "password": TD_PASSWORD,
        "appId": "tv-bridge",
        "appVersion": "1.0",
        "deviceId": "railway-tv-bridge",
        "cid": TD_CID,
        "sec": TD_SEC
    }
    r = requests.post(LOGIN_URL, json=payload, timeout=15)
    print("Login status:", r.status_code, "body:", r.text[:500])
    r.raise_for_status()
    j = r.json()
    return j["accessToken"]

def place_order(access_token, symbol, side, qty):
    must_env("TD_ACCOUNT_ID","TD_ACCOUNT_SPEC")
    order = {
        "accountSpec": TD_ACCOUNT_SPEC,           # ex: "1697337"
        "accountId": int(TD_ACCOUNT_ID),          # ex: 861089
        "action": "Buy" if side == "buy" else "Sell",
        "symbol": symbol,                         # ex: "MNQH6"
        "orderType": "Market",
        "timeInForce": "Day",
        "orderQty": int(qty),
        "isAutomated": True
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    r = requests.post(ORDER_URL, json=order, headers=headers, timeout=15)
    print("Order status:", r.status_code, "body:", r.text[:800])
    return r.status_code, r.text

@app.route("/", methods=["GET"])
def home():
    return "Bot MNQ Running"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("Received:", data)

        symbol = data.get("ticker")
        side   = data.get("action")
        qty    = int(data.get("quantity", 1))

        # Sécurité minimale
        if side not in ("buy", "sell"):
            return jsonify({"status":"error","error":"action must be buy/sell"}), 400
        if not symbol:
            return jsonify({"status":"error","error":"missing ticker"}), 400

        access = td_login()
        code, body = place_order(access, symbol, side, qty)

        return jsonify({"status":"ok", "tradovate_status": code, "tradovate_raw": body[:500]})
    except Exception as e:
        return jsonify({"status":"error","error": str(e)}), 500
