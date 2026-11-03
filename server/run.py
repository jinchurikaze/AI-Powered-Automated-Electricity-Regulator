"""Starts the Electricity Regulator server: python run.py  (then open http://localhost:5000)."""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # host 0.0.0.0 lets a phone on the same Wi-Fi reach the server at http://<laptop IP>:5000
    app.run(host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("DEBUG") == "1")
