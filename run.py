import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    # Defaults to 5000 (matches the README). Override locally if that port is
    # already taken - e.g. on macOS, AirPlay Receiver often squats on 5000:
    #   PORT=5001 python run.py
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, port=port)