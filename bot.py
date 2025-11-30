import os
import requests
import asyncio
from telegram import Bot
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WORK_LATITUDE = float(os.getenv("WORK_LATITUDE"))
WORK_LONGITUDE = float(os.getenv("WORK_LONGITUDE"))
HOME_LATITUDE = float(os.getenv("HOME_LATITUDE"))
HOME_LONGITUDE = float(os.getenv("HOME_LONGITUDE"))
bot = Bot(token=TOKEN)

LOCATIONS = [
    {"name": "Work", "lat": WORK_LATITUDE, "lon": WORK_LONGITUDE},
    {"name": "Home", "lat": HOME_LATITUDE, "lon": HOME_LONGITUDE}
]

PH_TZ = pytz.timezone("Asia/Manila")

def fetch_weather(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,precipitation_probability&timezone=Asia/Manila"
    r = requests.get(url)
    return r.json()

def build_message():
    now = datetime.now(PH_TZ).strftime("%A, %B %#d, %Y")
    today_str = datetime.now(PH_TZ).strftime("%Y-%m-%d")

    will_rain = False
    location_data = []

    # Fetch data for all locations
    for loc in LOCATIONS:
        data = fetch_weather(loc["lat"], loc["lon"])

        # Safely get hourly data
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        rains = hourly.get("precipitation_probability", [])

        filtered_times = []
        filtered_temps = []
        filtered_rains = []

        for i in range(len(times)):
            if times[i].startswith(today_str):
                hour = int(times[i][11:13])
                if 8 <= hour <= 20:
                    filtered_times.append(times[i])
                    filtered_temps.append(temps[i] if i < len(temps) else None)
                    filtered_rains.append(rains[i] if i < len(rains) else None)
                    if rains[i] >= 30:
                        will_rain = True

        location_data.append({
            "name": loc["name"],
            "times": filtered_times,
            "temps": filtered_temps,
            "rains": filtered_rains
        })

    weather_emoji = "🌦️" if will_rain else "☀️"
    msg = f"{now} {weather_emoji}\n\n"

    for loc in location_data:
        msg += f"{loc['name']}:\n"
        for i in range(len(loc["times"])):
            time_str = loc["times"][i][11:16]
            temp = round(loc["temps"][i]) if loc["temps"][i] is not None else "N/A"
            rain = round(loc["rains"][i]) if loc["rains"][i] is not None else "N/A"
            msg += f"{time_str} - {temp}°C, {rain}%\n"
        msg += "\n"

    return msg


async def main():
    """Run a daily loop that sends the weather message at 06:00 Asia/Manila every day.

    The function computes the next 06:00 PH time, sleeps until then, sends the message,
    and repeats. KeyboardInterrupt (Ctrl+C) will stop the loop gracefully.
    """
    try:
        while True:
            # Calculate next 06:00 AM in Philippines time
            now_ph = datetime.now(PH_TZ)
            target_naive = datetime(now_ph.year, now_ph.month, now_ph.day, 6, 0, 0)
            try:
                target_ph = PH_TZ.localize(target_naive)
            except Exception:
                target_ph = target_naive.replace(tzinfo=PH_TZ)

            if now_ph >= target_ph:
                # Schedule for next day
                target_ph = target_ph + timedelta(days=1)

            # Compute seconds to wait (use UTC to avoid DST edge cases)
            now_utc = datetime.now(pytz.utc)
            target_utc = target_ph.astimezone(pytz.utc)
            delay_seconds = (target_utc - now_utc).total_seconds()

            print(f"Current PH time: {now_ph.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"Scheduling next message at: {target_ph.strftime('%Y-%m-%d %H:%M:%S %Z')} (in {int(delay_seconds)} seconds)")

            # Wait until target time, then build and send message
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)

            message = build_message()
            try:
                await bot.send_message(chat_id=CHAT_ID, text=message)
                print("Message sent!")
            except Exception as e:
                # Log the exception and continue to schedule next day
                print(f"Failed to send message: {e}")
                # Small delay to avoid tight retry loop if send keeps failing
                await asyncio.sleep(10)

    # Loop will automatically schedule for the next day's 06:00
    except KeyboardInterrupt:
        print("Stopped by user (KeyboardInterrupt)")

if __name__ == "__main__":
    asyncio.run(main())
