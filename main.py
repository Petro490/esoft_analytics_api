from dotenv import load_dotenv
load_dotenv()

from app import create_app

app = create_app()

if __name__ == "__main__":
    import os
    debug = os.getenv("FLASK_DEBUG", "True").lower() in ("1", "true", "yes")
    app.run(host="127.0.0.1", port=5000, debug=debug)