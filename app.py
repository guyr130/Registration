# -*- coding: utf-8 -*-
import re
import requests
import xml.etree.ElementTree as ET
from flask import Flask, render_template_string

app = Flask(__name__)

# ======================
# ZEBRA CONFIG – זמנית בקוד
# ======================
ZEBRA_GET_URL = "https://25098.zebracrm.com/ext_interface.php?b=get_multi_cards_details"
ZEBRA_USER = "IVAPP"
ZEBRA_PASS = "1q2w3e4r"
ZEBRA_CARD_TYPE = "EVEFAM"

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
        data=zebra_request_xml(),
        headers={"Content-Type": "text/xml"},
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
<title>אירועים פתוחים</title>
<style>
body{
    font-family:Arial;
    background:#f4f6f8;
    margin:0;
}
.container{
    max-width:720px;
    margin:0 auto;
    padding:20px;
}
.card{
    background:#fff;
    border-radius:16px;
    padding:16px;
    margin-bottom:16px;
    box-shadow:0 6px 20px rgba(0,0,0,.08);
    display:flex;
    flex-direction:column;
}
.title{
    font-size:18px;
    font-weight:700;
    margin-bottom:8px;
}
.meta{
    font-size:14px;
    margin:4px 0;
}
.spacer{
    flex:1;
}
.btn{
    margin-top:14px;
    padding:14px;
    border-radius:12px;
    border:none;
    background:#e5e7eb;
    color:#6b7280;
    font-size:15px;
    font-weight:700;
    cursor:not-allowed;
}
.debug{
    background:#fff3cd;
    padding:12px;
    border-radius:12px;
    margin-bottom:20px;
    font-size:14px;
}
</style>
</head>
<body>

<div class="container">

<div class="debug">
סה״כ אירועים מהזברה: {{ total }}<br>
אירועים פעילים (STA_EV=1): {{ active }}
</div>

{% for e in events %}
<div class="card">
    <div class="title">{{ e.name }}</div>
    <div class="meta">📅 {{ e.date }} | ⏰ {{ e.hour }}</div>
    <div class="meta">📍 {{ e.loc }}</div>

    <div class="spacer"></div>

    <button class="btn" disabled>רישום לאירוע (בקרוב)</button>
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
    app.run(host="0.0.0.0", port=10000)
