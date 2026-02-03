# -*- coding: utf-8 -*-
import os
import re
import requests
import xml.etree.ElementTree as ET
from flask import Flask, render_template_string

app = Flask(__name__)

# ======================
# ZEBRA CONFIG
# ======================
ZEBRA_GET_URL = os.getenv(
    "ZEBRA_GET_URL",
    "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
)
ZEBRA_USER = os.getenv("ZEBRA_USER", "")
ZEBRA_PASS = os.getenv("ZEBRA_PASS", "")
ZEBRA_CARD_TYPE = os.getenv("ZEBRA_CARD_TYPE_FILTER", "EVEFAM")

# ======================
# XML
# ======================
def zebra_request_xml():
    return f"""<?xml version="1.0" encoding="utf-8"?>
<ROOT>
    <PERMISSION>
        <USERNAME>{ZEBRA_USER}</USERNAME>
        <PASSWORD>{ZEBRA_PASS}</PASSWORD>
    </PERMISSION>

    <CARD_TYPE_FILTER>{ZEBRA_CARD_TYPE}</CARD_TYPE_FILTER>
    <CARD_TYPE>{ZEBRA_CARD_TYPE}</CARD_TYPE>

    <FIELDS>
        <EV_N></EV_N>
        <EV_D></EV_D>
        <EVE_HOUR></EVE_HOUR>
        <EVE_LOC></EVE_LOC>
        <EVE_ORDER></EVE_ORDER>
        <STA_EV></STA_EV>
    </FIELDS>

    <ID></ID>
</ROOT>
"""

# ======================
# PARSE
# ======================
def extract_cards_safe(xml_text):
    cards = []
    for m in re.finditer(r"<CARD>(.*?)</CARD>", xml_text, re.DOTALL):
        xml = "<CARD>" + m.group(1) + "</CARD>"
        xml = re.sub(r"&(?!(amp;|lt;|gt;|quot;|apos;))", "&amp;", xml)
        try:
            cards.append(ET.fromstring(xml))
        except Exception:
            pass
    return cards

def zebra_get_events():
    resp = requests.post(
        ZEBRA_GET_URL,
        data=zebra_request_xml().encode("utf-8"),
        headers={"Content-Type": "text/xml; charset=utf-8"},
        timeout=40
    )
    resp.raise_for_status()

    cards = extract_cards_safe(resp.text)

    all_events = []
    active_events = []

    for c in cards:
        fields = c.find(".//FIELDS")
        if fields is None:
            continue

        def get(tag):
            el = fields.find(tag)
            return (el.text or "").strip() if el is not None else ""

        ev = {
            "name": get("EV_N"),
            "date": get("EV_D"),
            "hour": get("EVE_HOUR"),
            "loc": get("EVE_LOC"),
            "sta": get("STA_EV"),
        }

        all_events.append(ev)
        if ev["sta"] == "1":
            active_events.append(ev)

    return all_events, active_events

# ======================
# UI
# ======================
HTML = """
<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<title>בדיקת אירועים</title>
<style>
body{font-family:Arial;background:#f4f6f8}
.wrap{max-width:900px;margin:auto;padding:16px}
.card{background:#fff;padding:12px;margin-bottom:10px;border-radius:12px}
.debug{background:#fff3cd;padding:10px;border-radius:10px;margin-bottom:15px}
</style>
</head>
<body>
<div class="wrap">

<div class="debug">
סה״כ אירועים מהזברה: {{ total }}<br>
אירועים פעילים (STA_EV=1): {{ active }}
</div>

{% for e in events %}
<div class="card">
<strong>{{ e.name }}</strong><br>
📅 {{ e.date }} | ⏰ {{ e.hour }}<br>
📍 {{ e.loc }}<br>
סטטוס: {{ e.sta }}
</div>
{% endfor %}

</div>
</body>
</html>
"""

@app.route("/")
def index():
    all_events, active_events = zebra_get_events()
    return render_template_string(
        HTML,
        events=active_events,
        total=len(all_events),
        active=len(active_events)
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
