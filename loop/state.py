import json, os

STATE_PATH = os.getenv("STATE_PATH", "state.json")

# (ticker, name, sector, side, entry_price, shares)  shares negative = short
DEFAULT_BOOK = [
    ("LLY", "Eli Lilly", "drug_maker", "long", 812.0, 10),
    ("NVO", "Novo Nordisk", "drug_maker", "long", 62.0, 100),
    ("VKTX", "Viking Therapeutics", "drug_maker", "long", 34.0, 100),
    ("GPCR", "Structure Therapeutics", "drug_maker", "long", 28.0, 100),
    ("HSY", "Hershey", "snacks", "short", 168.0, -20),
    ("MDLZ", "Mondelez", "snacks", "short", 66.0, -50),
    ("STZ", "Constellation Brands", "alcohol", "short", 240.0, -10),
    ("DEO", "Diageo", "alcohol", "short", 128.0, -20),
    ("RMD", "ResMed", "sleep_apnea", "short", 233.0, -10),
    ("INSP", "Inspire Medical", "sleep_apnea", "short", 195.0, -10),
    ("DVA", "DaVita", "dialysis", "short", 145.0, -10),
]


def init_state():
    positions = [
        dict(ticker=t, name=n, sector=s, side=sd, entry=e, price=e, shares=sh, pnl=0.0)
        for (t, n, s, sd, e, sh) in DEFAULT_BOOK
    ]
    return {
        "tick": 0,
        "status": "running",
        "catalyst": None,
        "active_sectors": [],
        "log": [{"level": "info", "text": "loop initialized · book flat"}],
        "positions": positions,
        "pnl_total": 0.0,
        "watchlist": ["GPCR", "LLY"],
        "seen_catalysts": [],
    }


def load():
    if os.path.exists(STATE_PATH):
        return json.load(open(STATE_PATH))
    s = init_state()
    save(s)
    return s


def save(s):  # LOOP-ENG: state persisted outside the model
    json.dump(s, open(STATE_PATH, "w"), indent=2)
