import websocket

url = "ws://127.0.0.1:8000/ws/bookings/3de88a0a-6252-4ede-98cf-0fc49ffb6e0f/"

ws = websocket.create_connection(url)

print("CONNECTED")
print("Waiting for real-time booking status updates...")
print("Press Ctrl+C to stop.")

while True:
    message = ws.recv()
    print("MESSAGE:", message)