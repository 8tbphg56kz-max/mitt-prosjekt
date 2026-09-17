import sqlite3
import requests
from datetime import datetime, timezone

DB = "/home/knut/shelly/data.db"

LAT = 60.4050
LON = 6.6695

URL = (
    "https://api.met.no/weatherapi/locationforecast/2.0/compact"
    f"?lat={LAT}&lon={LON}"
)

HEADERS = {
    "User-Agent": "PumpehusApp/1.0"
}


def fetch_met_temperature():
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    data = response.json()

    timeseries = data["properties"]["timeseries"]

    now = datetime.now(timezone.utc)

    conn = sqlite3.connect(DB)

    for point in timeseries:
        timestamp = datetime.fromisoformat(
            point["time"].replace("Z", "+00:00")
        )

        # Ikke lagre fremtidige prognoser
        if timestamp > now:
            continue

        temperature = point["data"]["instant"]["details"]["air_temperature"]

        conn.execute(
            """
            INSERT INTO met_readings (timestamp, temperature)
            SELECT ?, ?
            WHERE NOT EXISTS (
                SELECT 1
                FROM met_readings
                WHERE timestamp = ?
            )
            """,
            (
                point["time"],
                temperature,
                point["time"],
            ),
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    fetch_met_temperature()
