from flask import Flask, request, jsonify
import requests
import os
import datetime as dt

app = Flask(__name__)

# --- ENV (Railway Variables) ---
TD_USERNAME   = os.environ.get("TD_USERNAME")
TD_PASSWORD   = os.environ.get("TD_PASSWORD")
TD_CID        = os.environ.get("TD_CID")
TD_SEC        = os.environ.get("TD_SEC")
TD_ACCOUNT_ID = os.environ.get("TD_ACCOUNT_ID")  # ex: 861089 (l'id, pas "name")

BASE_URL  = "https://live.tradovateapi.com/v1"
LOGIN_URL = f"{BASE_URL}/auth/accesstokenrequest"
ORDER_URL = f"{BASE_URL}/order/place"

# --- Token cache (in-memory) ---
_token = None
_token_expiry = None  # datetime

def _parse_expiry(expiration_time: str):
    # ex: "2026-02-06T10:36:22.557Z"
    if not expiration_time:
        return None
    if expiration_time.endswith("Z"):
        expiration_time = expiration_time.replace("Z", "+00:00")
    return dt.datetime.fromisoformat(expiration_time)

def td_login():
    global _token, _token_expiry

    missing = [k for k, v in {
        "TD_USERNAME": TD_USERNAME,
        "TD_PASSWORD": TD_PASSWORD,
        "TD_CID": TD_CID,
        "TD_SEC": TD_SEC,
        "TD_ACCOUNT_ID": TD_ACCOUNT_ID,
    }.items() if not v]

    if missing:
        raise RuntimeError(f"Missing env vars: {missing}")

    # token encore valide ?
    now = dt.datetime.now(dt.timezone.utc)
    if _token and _token_expiry and now < (_token_expiry - dt.timedelta(seconds=30)):
        return _token

    payload = {
        "name": TD_USERNAME,
        "password": TD_PASSWORD,
        "appId": TD_CID,
        "appVersion": "1.0",
        "deviceId": "railway-bot",
        "cid": TD_CID,
        "sec": TD_SEC
    }

    r = requests.post(LOGIN_URL, json=payload, timeout=15)
    print("Login status:", r.status_code, "body:", r.text)
    r.raise_for_status()

    js = r.json()
    _token = js.get("accessToken")
    _token_expiry = _parse_expiry(js.get("expirationTime"))

    if not _token:
        raise RuntimeError(f"Login OK but no accessToken in response: {js}")

    return _token

@app.route("/", methods=["GET"])
def home():
    return "Bot MNQ Running"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True, silent=False)
        print("Received:", data)

        ticker = data["ticker"]      # ATTENTION: doit être un symbole Tradovate valide (voir note plus bas)
        action = data["action"]      # "buy" / "sell"
        qty    = int(data["quantity"])

        token = td_login()

        order = {
            "accountId": int(TD_ACCOUNT_ID),
            "action": "Buy" if action == "buy" else "Sell",
            "symbol": ticker,
            "orderQty": qty,
            "orderType": "Market"
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        r = requests.post(ORDER_URL, json=order, headers=headers, timeout=15)
        print("Order status:", r.status_code, "body:", r.text)

        # Tradovate peut répondre 200 + failureReason => on le renvoie au client
        try:
            resp_json = r.json()
        except Exception:
            resp_json = {"raw": r.text}

        return jsonify({"status": "ok", "tradovate": resp_json}), 200

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"status": "error", "error": str(e)}), 500
