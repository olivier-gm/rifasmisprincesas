import os

DATA_DIR = os.environ.get("DATA_DIR", "/home/data")
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(DATA_DIR, "comprobantes"))
IMG_DIR = os.environ.get("IMG_DIR", os.path.join(DATA_DIR, "img"))

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

CONFIG_DB_PATH = os.path.join(DATA_DIR, "config.db")
RIFA_DB_PATH = os.path.join(DATA_DIR, "rifa.db")
RIFA2_DB_PATH = os.path.join(DATA_DIR, "rifa2.db")
RIFA3_DB_PATH = os.path.join(DATA_DIR, "rifa3.db")
