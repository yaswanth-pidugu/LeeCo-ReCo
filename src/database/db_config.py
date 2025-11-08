import mysql.connector
import json
import os

def get_db_connection():
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        config_path = os.path.join(base_dir, "config.json")

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"config.json not found at: {config_path}")

        with open(config_path) as f:
            config = json.load(f)

        conn = mysql.connector.connect(
            host="localhost",
            user=config["MYSQL_USER"],
            password=config["MYSQL_PASSWORD"],
            database=config["MYSQL_DB"]
        )
        return conn
    except Exception as e:
        return {"error": str(e)}
