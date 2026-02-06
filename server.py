from flask import Flask, request, jsonify
import requests
import os
import time

app = Flask(__name__)

# ===== Tradovate endpoints =====
BASE_URL = os.getenv("TD_BASE_URL", "https://live.tradovateapi.com")
AUTH_URL = f"{BASE_URL}/auth/accesstoken"
ORDER_URL = f"{BASE_URL}/v1/order/place"

# ===== Required ENV vars (Railway Variables) =====
TD_USERNAME   = os.getenv("maxtradovate68")      # ton login Tradovate (email/username)
TD_PASSWORD   = os.getenv("LogiTtel65&*")      # ton mot de passe Tradovate
TD_CID        = os.getenv("9773")           # Client ID (API Key) Tradovate
TD_SEC        = os.getenv("da4c7376-95e5-401e-ba81-f744a108a0b7")           # Client Secret Tradovate
TD_ACCOUNT_ID = os.getenv("1697337")    # ex: "1692941"

# App metadata (peu important, mais requis)
TD_APP_ID      = os.getenv("TD_APP_ID", "tv-bot")
TD_APP_VERSION = os.getenv("TD_APP_VERSION", "1.0")
TD_DEVICE_ID   = os.getenv("TD_DEVICE_ID", "railway")

# Optional: mapping simple ticker -> symbole Tradovate
# Exemple: TD_SYMBOL_MAP='{"MNQ":"MNQH6","NQ":"NQH6"}'
import json
TD_SYMBOL_MAP = {}
try:
    if os.getenv("TD_SYMBOL_MAP"):
        TD_SYMBOL_MAP = json.loads(os.getenv("TD_SYMBOL_MAP"))
except Exception:
    TD_SYMBOL_MAP = {}


# ===== Token cache (en mémoire) =====
_token = None
_token_expiry_ts = 0  # epoch seconds


def _missing_env():
    missing = []
    for k, v in {
        "TD_USERNAME": TD_USERNAME,
        "TD_PASSWORD": TD_PASSWORD,
        "TD_CID": TD_CID,
        "TD_SEC": TD_SEC,
        "TD_ACCOUNT_ID": TD_ACCOUNT_ID,
    }.items():
        if not v:
            missing.append(k)
    return missing


def get_access_token(force=False) -> str:
    """
    Récupère un access token Tradovate et le met en cache avec une expiration.
    Si force=True, on re-login même si le token semble valide.
    """
    global _token, _token_expiry_ts

    # marge de sécurité 20s
    now = int(time.time())
    if (not force) and _token and (now < _token_expiry_ts - 20):
        return _token

    payload = {
        "name": TD_USERNAME,
        "password": TD_PASSWORD,
        "appId": TD_APP_ID,
        "appVersion": TD_APP_VERSION,
        "cid": TD_CID,
        "sec": TD_SEC,
        "deviceId": TD_DEVICE_ID
    }

    r = requests.post(AUTH_URL, json=payload, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"Auth failed ({r.status_code}): {r.text}")

    j = r.json()
    _token = j.get("accessToken")
    # Tradovate renvoie souvent expiresIn (secondes)
    expires_in = int(j.get("expiresIn", 0)) if j.get("expiresIn") is not None else 0
    # fallback si pas fourni
    _token_expiry_ts = now + (expires_in if expires_in > 0 else 600)

    if not _token:
        raise RuntimeError(f"Auth response missing accessToken: {j}")

    return _token


def place_order(symbol: str, side: str, qty: int) -> requests.Response:
    """
    side: "Buy" ou "Sell"
    """
    token = get_access_token(force=False)

    order = {
        "accountId": int(TD_ACCOUNT_ID),
        "symbol": symbol,
        "orderType": "Market",
        "action": side,
        "quantity": int(qty),
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    return requests.post(ORDER_URL, json=order, headers=headers, timeout=20)


@app.route("/", methods=["GET"])
def home():
    return "Bot MNQ Running"


@app.route("/webhook", methods=["POST"])
def webhook():
    missing = _missing_env()
    if missing:
        return jsonify({"status": "error", "error": f"Missing env vars: {missing}"}), 500

    data = request.get_json(silent=True) or {}
    print("Received:", data)

    try:
        ticker = str(data["ticker"])
        action = str(data["action"]).lower()
        qty    = int(data["quantity"])

        # mapping symbole si tu veux
        symbol = TD_SYMBOL_MAP.get(ticker, ticker)

        if action not in ("buy", "sell"):
            return jsonify({"status": "error", "error": "action must be 'buy' or 'sell'"}), 400
        if qty <= 0:
            return jsonify({"status": "error", "error": "quantity must be > 0"}), 400

        side = "Buy" if action == "buy" else "Sell"

        # 1) tentative normale
        r = place_order(symbol, side, qty)

        # 2) si token expiré / 401 / message explicite -> re-login et retry 1 fois
        if r.status_code == 401 or ("Expired Access Token" in r.text):
            print("Token expired -> re-auth and retry once")
            get_access_token(force=True)
            r = place_order(symbol, side, qty)

        print("Tradovate response:", r.status_code, r.text)

        if r.status_code >= 300:
            return jsonify({"status": "error", "tradovate_status": r.status_code, "tradovate": r.text}), 502

        return jsonify({"status": "ok", "tradovate_status": r.status_code})

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"status": "error", "error": str(e)}), 500
