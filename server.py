from flask import Flask, request, jsonify
import os, requests, time

app = Flask(__name__)

# --- ENV (Railway) ---
TD_USERNAME     = os.environ.get("TD_USERNAME")
TD_PASSWORD     = os.environ.get("TD_PASSWORD")
TD_CID          = os.environ.get("TD_CID")        # API Client ID
TD_SEC          = os.environ.get("TD_SEC")        # API Secret
TD_ACCOUNT_ID   = os.environ.get("TD_ACCOUNT_ID") # ex: 861089
TD_ACCOUNT_SPEC = os.environ.get("TD_ACCOUNT_SPEC")  # ex: "1697337"

# Choose LIVE or DEMO
BASE_URL  = os.environ.get("TD_BASE_URL", "https://live.tradovateapi.com/v1")
LOGIN_URL = f"{BASE_URL}/auth/accesstoken"
ORDER_URL = f"{BASE_URL}/order/placeorder"

# --- simple token cache ---
_token = {"accessToken": None, "expiresAt": 0}

def require_env():
    missing = [k for k,v in {
        "TD_USERNAME": TD_USERNAME,
        "TD_PASSWORD": TD_PASSWORD,
        "TD_CID": TD_CID,
        "TD_SEC": TD_SEC,
        "TD_ACCOUNT_ID": TD_ACCOUNT_ID,
        "TD_ACCOUNT_SPEC": TD_ACCOUNT_SPEC,
    }.items() if not v]
    return missing

def td_login():
    # cache valid token
    now = int(time.time())
    if _token["accessToken"] and now < _token["expiresAt"] - 30:
        return _token["accessToken"]

    payload = {
        "name": TD_USERNAME,
        "password": TD_PASSWORD,
        "appId": TD_CID,
        "appVersion": "1",
        "cid": TD_CID,
        "sec": TD_SEC
    }

    r = requests.post(LOGIN_URL, json=payload, timeout=15)
    print("Login status:", r.status_code, "body:", r.text)
    r.raise_for_status()

    j = r.json()
    _token["accessToken"] = j["accessToken"]

    # expirationTime ressemble à "2026-02-06T10:46:32.335Z"
    # on met un TTL safe (20 min) si on ne veut pas parser la date
    _token["expiresAt"] = int(time.time()) + 20*60
    return _token["accessToken"]

def place_market_order(symbol: str, side: str, qty: int):
    access = td_login()

    order = {
        "accountSpec": str(TD_ACCOUNT_SPEC),
        "accountId": int(TD_ACCOUNT_ID),
        "symbol": symbol,              # ex: "MNQH6" (contrat réel)
        "orderQty": int(qty),
        "orderType": "Market",
        "timeInForce": "Day",
        "isAutomated": True
    }

    # Tradovate ne met pas toujours "action" dans placeorder.
    # Si ton compte exige le side explicite, on passe par la convention :
    # Buy = qty positive, Sell = qty positive MAIS on envoie un "side" si nécessaire.
    # (Si ça refuse, on adaptera au retour d’erreur exact.)
    if side.lower() == "sell":
        # option A: qty négatif (souvent accepté)
        order["orderQty"] = -int(qty)

    headers = {
        "Authorization": f"Bearer {access}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    r = requests.post(ORDER_URL, json=order, headers=headers, timeout=15)
    print("Order status:", r.status_code, "body:", r.text)
    r.raise_for_status()
    return r.json() if r.text else {"status": "sent"}

@app.route("/", methods=["GET"])
def home():
    return "Bot MNQ Running"

@app.route("/webhook", methods=["POST"])
def webhook():
    missing = require_env()
    if missing:
        return jsonify({"status":"error", "error": f"Missing env vars: {missing}"}), 500

    data = request.get_json(force=True, silent=True) or {}
    print("Received:", data)

    symbol = data.get("ticker")  # IMPORTANT: doit être un contrat (MNQH6), pas MNQ1!
    action = (data.get("action") or "").lower()
    qty    = int(data.get("quantity", 0))

    if not symbol or action not in ("buy","sell") or qty <= 0:
        return jsonify({"status":"error","error":"Bad payload. Need ticker/action/quantity"}), 400

    try:
        res = place_market_order(symbol, action, qty)
        return jsonify({"status":"ok", "tradovate": res})
    except Exception as e:
        return jsonify({"status":"error", "error": str(e)}), 500
