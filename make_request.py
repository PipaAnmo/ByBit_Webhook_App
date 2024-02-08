import requests

# Define the URL
url = 'http://127.0.0.1:8080/webhook'
# url = 'https://bybit-webhook-app.onrender.com/webhook'


# Define the data to be sent as text
data = 'buy BTCUSDT q=0.001'
# data = 'sell BTCUSDT q=1'
# data = 'close BTCUSDT'

# Make the POST request
response = requests.post(url, data=data)

# Check the response
if response.status_code == 200:
    print('POST request successful!')
    print('Response:', response.text)
else:
    print('POST request failed with status code:', response.status_code)
