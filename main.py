from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import sqlite3
import requests

app = FastAPI(title="Pumpehuset API")

app.mount("/static", StaticFiles(directory="/home/knut/mitt-prosjekt/static"), name="static")

DB = "/home/knut/shelly/data.db"

SHELLY_IP = "192.168.6.27"


@app.get("/api/pump/status")
def pump_status():
    try:
        response = requests.get(
            f"http://{SHELLY_IP}/rpc/Switch.GetStatus?id=0",
            timeout=3
        )
        response.raise_for_status()
        return response.json()

    except requests.RequestException:
        return {
            "output": None,
            "available": False
        }

@app.get("/api/pump/set")
def pump_set(on: bool):
    response = requests.get(
        f"http://{SHELLY_IP}/rpc/Switch.Set?id=0&on={str(on).lower()}",
        timeout=3
    )
    return response.json()

@app.get("/api/met/history")
def met_history(hours: int = 24):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT timestamp, temperature
        FROM met_readings
        WHERE datetime(timestamp) >= datetime('now', ?)
        ORDER BY datetime(timestamp) ASC
    """, (f"-{hours} hours",)).fetchall()

    result = [dict(row) for row in rows]

    conn.close()
    return result

def get_rows(table, limit=100):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()

    result = [dict(row) for row in rows]
    conn.close()
    return result


@app.get("/")
def root():
    return FileResponse("/home/knut/mitt-prosjekt/static/index.html")


@app.get("/api/plug")
def plug_readings(limit: int = 100):
    return get_rows("plug_readings", limit)


@app.get("/api/plug/latest")
def plug_latest():
    rows = get_rows("plug_readings", 1)
    return rows[0] if rows else {}


@app.get("/api/temperature")
def temperature_readings(limit: int = 100):
    return get_rows("readings", limit)


@app.get("/api/temperature/latest")
def temperature_latest():
    rows = get_rows("readings", 1)
    return rows[0] if rows else {}


@app.get("/api/em/latest")
def em_latest():
    rows = get_rows("em_readings", 100)

    for row in rows:
        if row.get("em0_current") is not None and row.get("em1_current") is not None:
            return {
                "total_voltage": row.get("em0_voltage"),
                "total_current": row.get("em0_current"),
                "total_power": row.get("em0_power"),
                "total_apparent_power": row.get("em0_apparent_power"),
                "total_power_factor": row.get("em0_power_factor"),
                "total_frequency": row.get("em0_frequency"),
                "total_energy": row.get("em0_energy"),

                "pump_voltage": row.get("em1_voltage"),
                "pump_current": row.get("em1_current"),
                "pump_power": row.get("em1_power"),
                "pump_apparent_power": row.get("em1_apparent_power"),
                "pump_power_factor": row.get("em1_power_factor"),
                "pump_frequency": row.get("em1_frequency"),
                "pump_energy": row.get("em1_energy"),

                "timestamp": row.get("timestamp")
            }

    return {}


@app.get("/api/em")
def em_readings(limit: int = 100):
    return get_rows("em_readings", limit)


@app.get("/api/em/energy")
def em_energy(period: str = "week", year: int = None):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    if period == "week":
        start_condition = "datetime(timestamp) >= datetime('now', '-7 days')"
    elif period == "month":
        start_condition = "strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now')"
    elif period == "year":
        start_condition = "strftime('%Y', timestamp) = strftime('%Y', 'now')"
    elif period == "selected_year" and year:
        start_condition = "strftime('%Y', timestamp) = ?"
    else:
        conn.close()
        return {"error": "Ugyldig periode"}

    if period == "selected_year" and year:
        rows = conn.execute(f"""
            SELECT timestamp, em0_energy, em1_energy
            FROM em_readings
            WHERE {start_condition}
              AND em0_energy IS NOT NULL
              AND em1_energy IS NOT NULL
            ORDER BY datetime(timestamp) ASC
        """, (str(year),)).fetchall()
    else:
        rows = conn.execute(f"""
            SELECT timestamp, em0_energy, em1_energy
            FROM em_readings
            WHERE {start_condition}
              AND em0_energy IS NOT NULL
              AND em1_energy IS NOT NULL
            ORDER BY datetime(timestamp) ASC
        """).fetchall()

    conn.close()

    if len(rows) < 2:
        return {
            "period": period,
            "total_kwh": None,
            "pump_kwh": None,
            "message": "Ikke nok historikk"
        }

    first = rows[0]
    last = rows[-1]

    total_kwh = (last["em0_energy"] - first["em0_energy"]) / 1000
    pump_kwh = (last["em1_energy"] - first["em1_energy"]) / 1000

    return {
        "period": period,
        "total_kwh": round(total_kwh, 3),
        "pump_kwh": round(pump_kwh, 3),
        "from": first["timestamp"],
        "to": last["timestamp"]
    }

@app.get("/api/temperature/count")
def temperature_count():
    conn = sqlite3.connect(DB)
    result = conn.execute("SELECT COUNT(*) FROM readings").fetchone()
    conn.close()
    return result[0]

@app.get("/api/temperature/history")
def temperature_history(hours: int = 24):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT timestamp, temperature, humidity
        FROM readings
        WHERE datetime(timestamp) >= datetime('now', ?)
        ORDER BY datetime(timestamp) ASC
    """, (f"-{hours} hours",)).fetchall()

    result = [dict(row) for row in rows]
    conn.close()
    return result
