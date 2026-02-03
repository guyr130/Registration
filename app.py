# -*- coding: utf-8 -*-
import os
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, date
from flask import Flask, render_template_string

app = Flask(__name__)

# ======================
# ZEBRA CONFIG (ENV ב-Render)
# ======================
ZEBRA_GET_URL = os.getenv(
    "ZEBRA_GET_URL",
    "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
)
ZEBRA_USER = os.getenv("ZEBRA_USER", "")
ZEBRA_PASS = os.getenv("ZEBRA_PASS", "")
ZEBRA_CARD_TYPE_FILTER = os.getenv("ZEBRA_CARD_TYPE_FILTER", "EVEFAM")

# ======================
# HELPERS
# ======================
def parse_date_ddmmyyyy(s):
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%d/%m/%Y").date()
    except Exception:
        return None

def safe_int(x, default=9999):
    try:
        return int(str(x).strip())
    except Exception:
        return default

def zebra_request_xml():
    return f"""<?xml version="1.0" encoding="utf-8"?>
<ROOT>
  <PERMISSION>
    <USERNAME>{ZEBRA_USER}</USERNAME>
    <PASSWORD>{ZEBRA_PASS}</PASSWORD>
  </PERMISSION>

  <CARD_TYPE_FILTER>{ZEBRA_CARD_TYPE_FILTER}</CARD_TYPE_FILTER>

  <FIELDS>
    <EV_N></EV_N>
    <EV_D></EV_D>
    <EVE_HOUR></EVE_HOUR>
    <EVE_LOC></EVE_LOC>
    <EVE_ORDER></EVE_ORDER>
    <STA_EV></STA_EV>
  </FIELDS>

  <ID></ID>
  <CARD_TYPE></CARD_TYPE>
</ROOT>
"""

def extract_cards_safe(xml_text):
    cards = []
    for m in re.finditer(r"<CARD>(.*?)</CARD>", xml_text, re.DOTALL):
        card_xml = "<CARD>" + m.group(1) + "</CARD>"
        # ניקוי & לא חוקי
        card_xml = re.sub(r"&(?!(amp;|lt;|gt;|quot;|apos;))", "&amp;", card_xml)
        try:
            cards.append(ET.fromstring(card_xml))
        except Exception:
            continue
    return cards

def zebra_get_events():
    if not ZEBRA_USER or not ZEBRA_PASS:
        raise RuntimeError("חסרים ZEBRA_USER / ZEBRA_PASS ב-ENV")

    resp = requests.post(
        ZEBRA_GET_URL,
        data=zebra_request_xml().encode("utf-8"),
        headers={"Content-Type": "application/xml; charset=utf-8"},
        timeout=40
    )
    resp.raise_for_status()

    cards = extract_cards_safe(resp.text)
    today = date.today()

    events = []

    for c in cards:
        fields = c.find(".//FIELDS")
        if fields is None:
            continue

        def get(tag):
            el = fields.find(tag)
            return (el.text or "").strip() if el is not None else ""

        ev_date = parse_date_ddmmyyyy(get("EV_D"))
        sta_ev = get("STA_EV")

        # ===== סינון קריטי =====
        if sta_ev != "1":
            continue
        if not ev_date:
            continue
        if ev_date < today:
            continue

        events.append({
            "id": (c.findtext("ID") or "").strip(),
            "name": get("EV_N"),
            "date_raw": get("EV_D"),
            "date_obj": ev_date,
            "hour": get("EVE_HOUR"),
            "loc": get("EVE_LOC"),
            "order": safe_int(get("EVE_ORDER")),
        })

    # מיון: סדר הצגה ואז תאריך
    events.sort(key=lambda x: (x["order"], x["date_obj"]))
    return events

# ======================
# UI
# ======================
HTML = """
<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<title>אירועים פתוחים</title>
<style>
body{font-family:Arial;background:#f4f6f8;margin:0}
.wrap{max-width:900px;margin:auto;padding:16px}
.card{background:#fff;border-radius:14px;padding:14px;margin-bottom:12px;
box-shadow:0 6px 20px rgba(0,0,0,.06)}
.title{font-size:18px;font-weight:700}
.meta{margin-top:6px;font-size:14px}
.btn{margin-top:10px;padding:12px;border-radius:10px;
border:none;background:#e5e7eb;color:#6b7280;font-weight:700}
</style>
</head>
<body>
<div class="wrap">
<h2>אירועים פתוחים</h2>

{% if events %}
  {% for e in events %}
    <div class="card">
      <div class="title">{{ e.name }}</div>
      <div class="meta">📅 {{ e.date_raw }} | ⏰ {{ e.hour }}</div>
      <div class="meta">📍 {{ e.loc }}</div>
      <button class="btn" disabled>רישום לאירוע (בקרוב)</button>
    </div>
  {% endfor %}
{% else %}
  <div class="card">אין כרגע אירועים פעילים עתידיים</div>
{% endif %}

</div>
</body>
</html>
"""

@app.route("/")
def index():
    events = zebra_get_events()
    return render_template_string(HTML, events=events)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
