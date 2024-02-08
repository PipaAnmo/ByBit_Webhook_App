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
# IyzVWgeWdvUg3QV2VR
# 0cSlfmPMKcvcsJYPsngCpIjVsjWDWS3Xs3b3
TESTNET = True
ORDER_TYPE = "Market"
ACCOUNT_CATEGORY = "linear"
BYBIT_API_KEY = "IyzVWgeWdvUg3QV2VR"
BYBIT_API_SECRET = "0cSlfmPMKcvcsJYPsngCpIjVsjWDWS3Xs3b3"
# ABHI TEST NET API DETAILS
# BYBIT_API_KEY = "RZ73KwoTw8NmYjhXl2"
# BYBIT_API_SECRET = "c9nbQM327HDKS0i101QBAozbUV2O7zelyA1R"
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
Subject: IG trading Script: Bybit

{error_message}"""

    logger.info(f"[I] SENDING AN EMAIL MSG:- {message}")
    print(f"[I] SENDING AN EMAIL MSG:- {message}")

    server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message)
    logger.info("[+] EMAIL HAS BEEN SENT")
    print("[+] EMAIL HAS BEEN SENT")
    server.quit()

def create_order(client:HTTP, order_data):
    order_data = [d.strip() for d in order_data.split(' ')]
    symbol = order_data[1].replace("-", "").replace("/", "").replace("\\", "").strip()
    direction = "Sell" if order_data[0].lower() == "sell" else "Buy"
    size = "".join([d for d in order_data[2] if d.isdigit() or d in ",."])

    logger.info(f"[I] PLACING A {direction} ORDER OF {size} FOR {symbol}")
    print(f"[I] PLACING A {direction} ORDER OF {size} FOR {symbol}")

    try:
        client.switch_position_mode(category=ACCOUNT_CATEGORY, symbol=symbol, mode=0)
    except:
        pass

    try:
        order = client.place_order(category=ACCOUNT_CATEGORY, symbol=symbol, side=direction, orderType=ORDER_TYPE, qty=size)
        if order["retCode"] == 0:
            order_id = order["result"]["orderId"]
            logger.info(f"[+] ORDER PLACE WITH ORDER ID: {order_id}")
            print(f"[+] ORDER PLACE WITH ORDER ID: {order_id}")
            return f"[+] ORDER PLACE WITH ORDER ID: {order_id}"
        else:
            logger.info(f"[!] COULD NOT PLACE AN ORDER: {order}")
            print(f"[!] COULD NOT PLACE AN ORDER: {order}")
            return f"[!] COULD NOT PLACE AN ORDER: {order}"
    except Exception as e:
        error = str(e).split('(ErrCode:')[0]
        logger.info(f"[!] COULD NOT PLACE AN ORDER: {error}")
        print(f"[!] COULD NOT PLACE AN ORDER: {error}")
        return f"[!] COULD NOT PLACE AN ORDER {error}"


def close_order(client:HTTP, order_data):
    order_data = [d.strip() for d in order_data.split(' ')]
    symbol = order_data[1].replace("-", "").replace("/", "").replace("\\", "").strip()
    logger.info(f"[I] CLOSING AN ORDER FOR {symbol}")
    print(f"[I] CLOSING AN ORDER FOR {symbol}")

    result = client.get_positions(category=ACCOUNT_CATEGORY, symbol=symbol)
    if result["retCode"] == 0:
        positions = result["result"]["list"]
        logger.info(f"[I] THERE ARE {len(positions)} OPEN POSITION WILL FIND POSITION TO CLOSE FOR {symbol}")
        print(f"[I] THERE ARE {len(positions)} OPEN POSITION WILL FIND POSITION TO CLOSE FOR {symbol}")
        for position in positions:
            close_size = str(position['size'])
            close_pos_direction = "Sell" if position['side'] == 'Buy' else "Buy"
            print(f"[I] CLOSING A POSITION SIZE OF {close_size} FOR SYMBOL: {symbol} SIDE: {close_pos_direction}")
            order = client.place_order(category=ACCOUNT_CATEGORY, symbol=symbol, side=close_pos_direction, orderType=ORDER_TYPE, qty=close_size)
            print(order)

        if len(positions) == 0:
            return f"No open positions to close orders for {symbol}"

        return f"Deleted orders for {symbol}"
    else:
        logger.info("[!] COULD NOT GET OPEN POSITIONS TO CLOSE")
        print("[!] COULD NOT GET OPEN POSITIONS TO CLOSE")
        return "COULD NOT GET OPEN POSITIONS TO CLOSE"


@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == "POST":
        data = request.data.decode("utf-8").strip()
        if len(data) > 10:
            write_webhook(data)
            print("[+] GOT ALERT DATA:- ", data)
            client = HTTP(api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET, testnet=TESTNET)

            if "close" not in data: # This means that its a buy/sell webhook request
                order_data = create_order(client, data)
                send_email(f"{data} ::: {order_data}")
                return order_data

            if "close" in data: # This means that its a close webhook request
                order_data = close_order(client, data)
                send_email(f"{data} ::: {order_data}")
                return order_data

    if request.method == "GET":
        return {"status": 200, "msg" : datetime.utcnow()}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
    # # buy TICKER q=4  or sell TICKER q=2 or close TICKER 
    # client = HTTP(api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET, testnet=TESTNET)
    # # create_order(client, "sell BTC-USDT q=4")
    # order_data = close_order(client, "close BTC-USDT")

    # # print(client.get_positions(category=ACCOUNT_CATEGORY, symbol="BTCUSDT"))