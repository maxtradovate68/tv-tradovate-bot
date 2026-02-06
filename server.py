from flask import Flask, request, jsonify
import requests, os, time, uuid

app = Flask(__name__)

TD_USERNAME   = os.environ.get("TD_USERNAME")
TD_PASSWORD   = os.environ.get("TD_PASSWORD")
TD_CID        = os.environ.get("TD_CID")
TD_SEC        = os.environ.get("TD_SEC")
TD_ACCOUNT_ID = os.environ.get("TD_ACCOUNT_ID")  # string -> cast int plus bas

BASE = "https://live.tradovateapi.com/v1"

_token = None
_token_exp = 0  # epoch seconds


def _require_env():
    missing = [k for k,v in {
        "TD_USERNAME": TD_USERNAME,
        "TD_PASSWORD": TD_PASSWORD,
        "TD_CID": TD_CID,
        "TD_SEC": TD_SEC,
        "TD_ACCOUNT_ID": TD_ACCOUNT_ID,
    }.items() if not v]
    if missing:
        raise RuntimeError(f"Missing env vars: {missing}")


def get_token():
    global _token, _token_exp
    _require_env()

    now = int(time.time())
    if _token and now < (_token_exp - 30):
        return _token

    # Auth (format le plus courant Tradovate)
    url = f"{BASE}/auth/accesstoken"
    payload = {
        "name": TD_USERNAME,
        "password": TD_PASSWORD,
        "appId": "tv-bot",
        "appVersion": "1.0",
        "cid": TD_CID,
        "sec": TD_SEC
    }

    r = requests.post(url, json=payload, timeout=20)
    print("Login status:", r.status_code, "body:", r.text)

    r.raise_for_status()
    data = r.json()

    _token = data["accessToken"]

    # expirationTime est souvent ISO -> on fait simple: si dispo en secondes ms, sinon fallback 10min
    # Beaucoup de comptes ont un token ~10-20min.
    _token_exp = now + 600
    return _token


def auth_headers():
    return {
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json",
    }


def resolve_front_month_contract_id(root="MNQ"):
    # On cherche un contrat "front month" à partir du root.
    # Endpoint courant: /contract/find?name=MNQ
    url = f"{BASE}/contract/find"
    r = requests.get(url, params={"name": root}, headers=auth_headers(), timeout=20)
    print("Contract find:", r.status_code, r.text)
    r.raise_for_status()
    items = r.json()

    if not isinstance(items, list) or not items:
        raise RuntimeError(f"No contracts returned for {root}")

    # Heuristique robuste :
    # - si champ isFrontMonth existe, on le prend
    # - sinon: on prend le premier "isActive" / ou le plus récent non expiré
    front = [c for c in items if c.get("isFrontMonth") is True]
    if front:
        return int(front[0]["id"])

    active = [c for c in items if c.get("isActive") is True]
    if active:
        return int(active[0]["id"])

    return int(items[0]["id"])


def place_market_order(contract_id, action, qty):
    url = f"{BASE}/order/place"
    payload = {
        "accountId": int(TD_ACCOUNT_ID),
        "action": "Buy" if action == "buy" else "Sell",
        "orderType": "Market",
        "contractId": int(contract_id),
        "quantity": int(qty),
        "clOrdId": str(uuid.uuid4()),
    }

    r = requests.post(url, json=payload, headers=auth_headers(), timeout=20)
    print("Order place status:", r.status_code, "body:", r.text)
    return r


@app.route("/", methods=["GET"])
def home():
    return "Bot MNQ Running"


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("Received:", data)

        ticker = data.get("ticker", "MNQ")      # "MNQ" root
        action = data["action"]                # buy/sell
        qty    = int(data["quantity"])

        # root -> contractId front month
        contract_id = resolve_front_month_contract_id(ticker)

        r = place_market_order(contract_id, action, qty)

        if r.status_code >= 400:
            return jsonify({"status": "error", "tradovate": r.text}), 400

        return jsonify({"status": "ok", "tradovate": r.text})

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"status": "error", "error": str(e)}), 500
