import os
import ssl
import json
import time
import logging
import smtplib
import requests
from datetime import datetime
from pybit.unified_trading import HTTP
from flask import Flask, request, Response

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ORDERS_FILE = os.path.join(BASE_DIR, "orders.csv")
WEBHOOKS_FILE = os.path.join(BASE_DIR, "webhooks.txt")
LOGS_FILE = os.path.join(BASE_DIR, "logs.txt")

#############################
###### SMTP DETAILS #########
#############################
SMTP_PORT = 587
SMTP_SERVER = "smtp.gmail.com"
SENDER_EMAIL = "amorfati.ch@gmail.com"
RECEIVER_EMAIL = "hugchri@gmail.com"
EMAIL_PASSWORD = "qgxx rjux yvnp svim"
#############################
#############################

#############################
###### BYBIT API DETAILS #######
#############################
ACCOUNT_CATEGORY = "linear"
TESTNET = True
BYBIT_API_KEY = "RZ73KwoTw8NmYjhXl2"
BYBIT_API_SECRET = "c9nbQM327HDKS0i101QBAozbUV2O7zelyA1R"
#############################
#############################


logging.basicConfig(filename=LOGS_FILE,filemode='a',
                    format='%(asctime)s,%(msecs)d %(levelname)s %(message)s',
                    datefmt='%D %H:%M:%S', level=logging.INFO)

logger = logging.getLogger(__name__)
app = Flask(__name__)


def write_webhook(data):
    with open(WEBHOOKS_FILE, "a+") as f:
        f.write(datetime.now().strftime("%D %H:%M:%S") + "," + data + "\n")


def send_email(error_message):
    # Create a secure SSL context
    context = ssl.create_default_context()

    if SMTP_PORT == 465:
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context)
    else:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls(context=context)  # Upgrade to a secure connection if using TLS
    server.ehlo()  # Can be omitted
    server.login(SENDER_EMAIL, EMAIL_PASSWORD)

    message = f"""\
Subject: IG trading Script

{error_message}"""

    logger.info(f"[I] SENDING AN EMAIL MSG:- {message}")
    print(f"[I] SENDING AN EMAIL MSG:- {message}")

    server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message)
    logger.info("[+] EMAIL HAS BEEN SENT")
    print("[+] EMAIL HAS BEEN SENT")
    server.quit()

def create_order(access_token, order_data):
    order_data = [d.strip() for d in order_data.split(' ')]
    epic = order_data[1]
    direction = order_data[0].lower()
    direction = "SELL" if direction == "sell" or direction  == "long" else "BUY"
    size = "".join([d for d in order_data[2] if d.isdigit() or d in ",."])

    logger.info(f"[I] PLACING A {direction} ORDER OF {size} FOR {epic}")
    print(f"[I] PLACING A {direction} ORDER OF {size} FOR {epic}")

    payload = {
        "currencyCode" : "USD",
        "direction" : direction,
        "guaranteedStop": False,
        "epic": epic,
        "orderType" : "MARKET",
        "size" : size,
        "timeInForce" : "EXECUTE_AND_ELIMINATE",
        "trailingStop" : False,
        "trailingStopIncrement" : None,
        "expiry" : "-",
        "forceOpen": False
    }

    headers = AUTH_HEADERS.copy()
    headers["Authorization"] = f'Bearer {access_token}'
    headers["Version"] = "2"

    resp = requests.post(CREATE_ORDER_URL, data=json.dumps(payload), headers=headers)
    logging.info(f"CREATE ORDER RESP:- {resp.text}")
    if resp.status_code == 200:
        data = resp.json()
        if "dealReference" in data:
            logger.info(f"[+] ORDER HAS BEEN CREATED WITH REF ID:- {data['dealReference']}")
            print(f"[+] ORDER HAS BEEN CREATED WITH REF ID:- {data['dealReference']}")
            time.sleep(2)
            check, status, reason = check_deal_status(access_token, data['dealReference'])
            if check:
                return f"ORDER CREATED STATUS: {status} | REASON: {reason} | REF ID: {data['dealReference']}"
            else:
                logger.info(f"[!] ORDER NOT  CREATED {status} | REASON: {reason} | REF ID: {data['dealReference']}")
                print(f"[!] ORDER COULD BNOT E CREATED {status} | REASON: {reason} | REF ID: {data['dealReference']}")
                return f"ORDER COULD NOT BE CREATED STATUS: {status} | REASON: {reason} | REF ID: {data['dealReference']}"
        else:
            logger.info(f"[!] ORDER COULD NOT BE CREATED: {resp.text}")
            print(f"[!] ORDER COULD NOT BE CREATED: {resp.text}")
            return f"ORDER COULD NOT BE NOT CREATED: {resp.text}"
    else:
        logger.info(f"[!] ORDER COULDNOT  BE CREATED: {resp.text}")
        print(f"[!] ORDER COULD NOT BE CREATED: {resp.text}")
        return f"ORDER COULD NOT BE CREATED: {resp.text}"


def close_order(access_token, order_data):
    order_data = [d.strip() for d in order_data.split(' ')]
    epic = order_data[1]
    logger.info(f"[I] CLOSING AN ORDER FOR {epic}")
    print(f"[I] CLOSING AN ORDER FOR {epic}")

    headers = AUTH_HEADERS.copy()
    headers["Authorization"] = f'Bearer {access_token}'
    headers["Version"] = "1"

    resp = requests.get(GET_ORDERS_URL, headers=headers)
    logging.info(f"CLOSE ORDER RESP:- {resp.text}")
    if resp.status_code == 200:
        positions = resp.json()["positions"]
        closed_pos_count = 0
        logger.info(f"[I] THERE ARE {len(positions)} OPEN POSITION WILL FIND POSITION TO CLOSE FOR {epic}")
        print(f"[I] THERE ARE {len(positions)} OPEN POSITION WILL FIND POSITION TO CLOSE FOR {epic}")
        closing_size = 0
        for position in positions:
            if position['market']['epic'] == epic:
                closing_size = str(position['position']['dealSize'])
                close_pos_direction = "BUY" if position['position']['direction'] == 'SELL' else "SELL"
                print(f"{closing_size = }, {close_pos_direction = }")
                payload = {
                    "dealId": position['position']['dealId'],
                    "direction": close_pos_direction,
                    "size": closing_size,
                    "orderType": "MARKET",
                    "expiry": "-",
                }

                headers["_method"] = "DELETE"
                resp = requests.post(CLOSE_ORDER_URL, headers=headers, data=json.dumps(payload))
                if resp.status_code == 200:
                    data = resp.json()
                    if "dealReference" in data:
                        closed_pos_count+=1
                        logger.info(f"[+] ORDER HAS BEEN CLOSED WITH REF ID:- {data['dealReference']}")
                        print(f"[+] ORDER HAS BEEN CLOSED WITH REF ID:- {data['dealReference']}")
                    else:
                        logger.info("[!] ORDER COULD NOT  BE CLOSED")
                        print("[!] ORDER COULD NOT BE CLOSED")
                else:
                    logger.info(f"[!] ORDER COULD NOT BE CLOSED:- {resp.text}")
                    print(f"[!] ORDER COULD NOT BE CLOSED:- {resp.text}")

        if closed_pos_count == 0:
            return f"No open positions to close orders for {epic}"

        return f"Deleted {closed_pos_count} orders for {epic}"
    else:
        logger.info("[!] COULD NOT GET OPEN POSITIONS TO CLOSE")
        print("[!] COULD NOT GET OPEN POSITIONS TO CLOSE")
        return "COULD NOT GET OPEN POSITIONS TO CLOSE"


def generate_token():
    payload = {"identifier": "chris_hug", "password": "Abcdefg1"}
    resp = requests.post(CREATE_SESSION_URL, json=payload, headers=REQ_HEADERS)
    logging.info(f"GENERATE ACCESS TOKEN RESP:- {resp.text}")

    if resp.status_code == 200: # This means that login was successful
        data = resp.json()
        if "clientId" in data:
            logger.info("[+] LOGGED IN AND ACCESS TOKEN HAS BEEN CREATED")
            print("[+] LOGGED IN AND ACCESS TOKEN HAS BEEN CREATED")
            return data['oauthToken']['access_token']
        else:
            logger.info("[!] COULD NOT CREATE ACCESS TOKEN, PLEASE CHECK YOUR LOGIN DETAILS")
            print("[!] COULD NOT CREATE ACCESS TOKEN, PLEASE CHECK YOUR LOGIN DETAILS")
            return None
    else:
        logger.info("[!] COULD NOT CREATE ACCESS TOKEN, PLEASE CHECK YOUR LOGIN DETAIS")
        print("[!] COULD NOT CREATE ACCESS TOKEN, PLEASE CHECK YOUR LOGIN DETAIS")
        return None


def check_deal_status(access_token, deal_id):
    url = STATUS_ORDER_URL + deal_id if STATUS_ORDER_URL.endswith("/") else STATUS_ORDER_URL + "/" + deal_id
    headers = AUTH_HEADERS.copy()
    headers["Authorization"] = f'Bearer {access_token}'
    headers["Version"] = "1"

    logger.info(f"[I] CHECKING DEAL STATUS FOR ID:- {deal_id}")
    print(f"[I] CHECKING DEAL STATUS FOR ID:- {deal_id}")
    resp = requests.get(url, headers=headers)
    logging.info(f"CHECK DEAL STATUS RESP:- {resp.text}")

    if resp.status_code == 200:
        data = resp.json()
        reason = data["reason"]
        status = data["status"]

        logger.info(f"[+] DEAD STATUS: {status} FOR ID: {deal_id} | REASON: {reason}")
        print(f"[+] DEAD STATUS: {status} FOR ID: {deal_id} | REASON: {reason}")
        if status in ['OPEN', 'CLOSED', 'PARTIALLY_CLOSED', 'PARTIALLY_OPENED']:
            return True, status, reason
        else:
            return False, status, reason
    else:
        data = resp.json()
        logger.info(f"[!] COULD NOT GET DEAL INFO:- {data['errorCode']}")
        print(f"[!] COULD NOT GET DEAL INFO:- {data['errorCode']}")


@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == "POST":
        data = request.data.decode("utf-8").strip()
        if len(data) > 10:
            write_webhook(data)
            access_token = generate_token()
            print("[+] GOT ALERT DATA:- ", data)

            if "close" not in data: # This means that its a buy/sell webhook request
                order_id = create_order(access_token, data)
                send_email(f"{data} ::: {order_id}")
                return order_id

            if "close" in data: # This means that its a close webhook request
                order_data = close_order(access_token, data)
                send_email(f"{data} ::: {order_data}")
                return order_data

    if request.method == "GET":
        return {"status": 200, "msg" : "datetime updated"}


if __name__ == "__main__":
    # app.run(host="0.0.0.0", port=8080, debug=True)
    client = HTTP(api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET, testnet=TESTNET)
    print(client.get_account_info())
    order = client.place_order(category=ACCOUNT_CATEGORY, symbol="BTCUSDT", side="Buy", orderType="Market",qty="0.1")
    print(order)