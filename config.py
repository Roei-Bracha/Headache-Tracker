import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()


def _fail(key: str):
    raise RuntimeError(f"Missing required environment variable: {key}")


TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN") or _fail("TELEGRAM_BOT_TOKEN")
OWM_API_KEY: str = os.getenv("OWM_API_KEY") or _fail("OWM_API_KEY")
AUTHORIZED_USER_ID: int = int(os.getenv("AUTHORIZED_USER_ID") or _fail("AUTHORIZED_USER_ID"))
TZ = ZoneInfo(os.getenv("TZ", "Asia/Jerusalem"))
DB_PATH: str = os.getenv("DB_PATH", "/app/data/headaches.db")
OWM_LAT: float = 32.0556
OWM_LON: float = 34.8550
HEAD_MAP_PATH: str = "./data/head_map.jpg"
CHECKIN_HOUR: int = 18
CHECKIN_MINUTE: int = 0

# Enum values stored in DB / used as callback_data (English only)
LOCATIONS = ["frontal", "temporal", "behind_eye", "occipital", "top", "band", "one_side"]
PAIN_TYPES = ["throbbing", "sharp", "dull"]
MEDICATIONS = ["none", "ibuprofen_200", "ibuprofen_512", "optalgin_1", "optalgin_2"]
HYDRATION_UNITS = ["liters", "cups"]
LITERS_OPTIONS = ["1", "1.5", "2", "2.5", "3", "3.5", "4"]
COFFEE_OPTIONS = ["0", "1", "2", "3", "4", "5"]

# Hebrew label maps: callback_data -> Hebrew button text
LOCATION_LABELS = {
    "frontal": "מצח",
    "temporal": "רקות",
    "behind_eye": "מאחורי העין",
    "occipital": "עורף",
    "top": "קדקוד",
    "band": "כטבעת הראש",
    "one_side": "צד אחד",
}

PAIN_TYPE_LABELS = {
    "throbbing": "פועם",
    "sharp": "חד",
    "dull": "לחץ עמום",
}

MEDICATION_LABELS = {
    "none": "לא",
    "ibuprofen_200": "איבופרופן 200",
    "ibuprofen_512": "איבופרופן 512",
    "optalgin_1": "אופטלגין 1",
    "optalgin_2": "אופטלגין 2",
}
