#!/usr/bin/env python3
"""E-paper weather display: Waveshare 2.9" b/w/red (V3) on a Raspberry Pi.

python3 weather.py            fetch weather, draw it, update the display
python3 weather.py --preview  fetch weather, save preview.png, leave the display alone
python3 weather.py --demo     same as --preview, with fake data (works offline)
"""
import json, math, os, sys, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageOps

# ---------------- settings ----------------
LAT, LON, TZ = 47.36, 7.98, "Europe/Zurich"
HERE = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(HERE, "weather/icons")
LIB_DIR = os.path.expanduser("~/e-Paper/RaspberryPi_JetsonNano/python/lib")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
RED_ICONS = set()      # e.g. {"sun", "cloud-lightning"} to draw those icons in red
PROB_SOLID = 70        # rain probability (%) from which a bar is solid; below = checkerboard
MIN_RAIN_MM = 0.1      # smaller hourly amounts are not drawn

W, H = 296, 128
AX_L, AX_R = 143, 276  # axis x positions
PX0, PX1 = 144, 275    # plot area, x range
PY0, PY1 = 48, 106     # plot area, top and baseline


# ---------------- data ----------------
def fetch_weather():
    url = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
           "&current=temperature_2m"
           "&hourly=temperature_2m,precipitation,precipitation_probability,weather_code"
           "&timezone=%s&forecast_days=1" % (LAT, LON, TZ.replace("/", "%2F")))
    with urllib.request.urlopen(url, timeout=20) as r:
        d = json.load(r)
    h = d["hourly"]
    return {"now": d["current"]["temperature_2m"], "temp": h["temperature_2m"],
            "rain": h["precipitation"], "prob": h["precipitation_probability"],
            "code": h["weather_code"]}


def demo_weather():
    temp = [11 + 9 * math.exp(-((h - 14) / 4.5) ** 2) for h in range(24)]
    rain, prob = [0.0] * 24, [0] * 24
    for h, (mm, p) in {16: (1.0, 40), 17: (2.5, 60), 18: (4.0, 80),
                       19: (2.0, 85), 20: (1.2, 50), 21: (0.6, 30)}.items():
        rain[h], prob[h] = mm, p
    code = [0] * 7 + [1] * 5 + [2] * 4 + [80] * 3 + [61] * 2 + [3] * 3
    return {"now": 20.2, "temp": temp, "rain": rain, "prob": prob, "code": code}


# ---------------- icon choice ----------------
def pick_icon(codes):
    """Icon for the majority weather between 06:00 and 21:59."""
    day = codes[6:22]
    n = len(day)
    clear = sum(c in (0, 1) for c in day)
    partly = sum(c == 2 for c in day)
    cloudy = sum(c == 3 for c in day)
    fog = sum(c in (45, 48) for c in day)
    drizzle = sum(51 <= c <= 57 for c in day)
    rain = sum(61 <= c <= 67 or 80 <= c <= 82 for c in day)
    snow = sum(71 <= c <= 77 or c in (85, 86) for c in day)
    wet = drizzle + rain
    wet_icon = "cloud-drizzle" if drizzle > rain else "cloud-rain"
    sunny_dry = clear + partly > cloudy + fog

    if any(c >= 95 for c in day):
        return "cloud-lightning"
    if snow / n >= 0.5:
        return "cloud-snow"
    if wet / n >= 0.5:
        return wet_icon
    if snow / n >= 0.1 and snow >= wet:
        return "sun-snow" if sunny_dry else "cloud-snow"
    if wet / n >= 0.1:
        return "cloud-sun-rain" if sunny_dry else wet_icon
    if fog / n >= 0.5:
        return "cloud-fog"
    best = max((clear, 2), (partly, 1), (cloudy, 0))  # ties prefer the sunnier icon
    return ["cloud", "cloud-sun", "sun"][best[1]]


# ---------------- drawing helpers ----------------
def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def temp_axis(temps):
    lo = 5 * math.floor(min(temps) / 5)
    hi = 5 * math.ceil(max(temps) / 5)
    while hi - lo < 10 or (hi - lo) % 10:
        hi += 5
    return lo, hi


def rain_axis(rain):
    top = max(rain)
    for m in (5, 10, 20, 40):
        if top <= m:
            return m
    return math.ceil(top / 20) * 20


def paste_icon(layer, name, xy):
    icon = Image.open(os.path.join(ICON_DIR, name + ".png")).convert("L")
    mask = ImageOps.invert(icon).point(lambda p: 255 if p > 127 else 0)
    layer.paste(0, xy, mask)


# ---------------- layout ----------------
def render(data):
    black = Image.new("1", (W, H), 1)
    red = Image.new("1", (W, H), 1)
    b, r = ImageDraw.Draw(black), ImageDraw.Draw(red)
    f_small = font(FONT, 9)

    # icon, top left
    icon = pick_icon(data["code"])
    paste_icon(red if icon in RED_ICONS else black, icon, (16, 2))

    # current temperature, bottom left
    txt, size = "%d°" % round(data["now"]), 40
    while True:
        f_big = font(FONT_BOLD, size)
        print(size)
        if b.textlength(txt, font=f_big) <= 120 or size <= 24:
            break
        size -= 2
    b.text((12, 72), txt, font=f_big, fill=0)

    # chart scales
    temp, rain, prob = data["temp"], data["rain"], data["prob"]
    lo, hi = temp_axis(temp)
    rmax = rain_axis(rain)
    slot = (PX1 - PX0) / 24
    ty = lambda t: PY1 - (t - lo) / (hi - lo) * (PY1 - PY0)

    # rain bars (black, in the background)
    for h in range(24):
        mm = rain[h] or 0
        if mm < MIN_RAIN_MM:
            continue
        height = max(2, round(min(mm, rmax) / rmax * (PY1 - PY0)))
        x0 = PX0 + round(h * slot)
        x1 = PX0 + round((h + 1) * slot) - 2
        y0, y1 = PY1 - height, PY1 - 1
        p = prob[h]
        if p is None or p >= PROB_SOLID:
            b.rectangle([x0, y0, x1, y1], fill=0)
        else:  # uncertain: 1 px checkerboard
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    if (x + y) % 2 == 0:
                        b.point((x, y), fill=0)

    # temperature curve (red) with a white halo through the bars
    pts = [(PX0 + (h + 0.5) * slot, ty(temp[h])) for h in range(24)]
    b.line(pts, fill=1, width=5, joint="curve")
    r.line(pts, fill=0, width=3, joint="curve")

    # axes, baseline, arrows
    for ax in (AX_L, AX_R):
        b.line([(ax, PY0 - 4), (ax, PY1 + 3)], fill=0)
        b.line([(ax - 3, PY0), (ax, PY0 - 4), (ax + 3, PY0)], fill=0)
    b.line([(AX_L, PY1), (AX_R, PY1)], fill=0)

    # scale labels: temperature left, rain right (both linear, 3 ticks)
    for i in range(3):
        y = round(PY1 - i * (PY1 - PY0) / 2)
        b.text((AX_L - 5, y), "%g" % (lo + i * (hi - lo) / 2), font=f_small, fill=0, anchor="rm")
        b.text((AX_R + 4, y), "%g" % (i * rmax / 2), font=f_small, fill=0, anchor="lm")
    b.text((AX_L - 12, 36), "[°C]", font=f_small, fill=0, anchor="mm")
    b.text((W - 1, 36), "[mm]", font=f_small, fill=0, anchor="rm")

    # hour labels
    for hr in (0, 6, 12, 18, 24):
        x = round(PX0 + (PX1 - PX0) * hr / 24)
        b.line([(x, PY1), (x, PY1 + 2)], fill=0)
        b.text((x, 117), "%02d" % hr, font=f_small, fill=0, anchor="mm")

    return black, red


# ---------------- output ----------------
def save_preview(black, red, path):
    img = Image.new("RGB", (W, H), "white")
    img.paste((0, 0, 0), mask=ImageOps.invert(black.convert("L")))
    img.paste((200, 0, 0), mask=ImageOps.invert(red.convert("L")))
    img.resize((W * 3, H * 3), Image.NEAREST).save(path)


def show(black, red):
    sys.path.append(LIB_DIR)
    from waveshare_epd import epd2in9b_V3
    epd = epd2in9b_V3.EPD()
    epd.init()
    epd.display(epd.getbuffer(black), epd.getbuffer(red))
    epd.sleep()


def main():
    args = sys.argv[1:]
    try:
        data = demo_weather() if "--demo" in args else fetch_weather()
    except Exception as e:  # no Wi-Fi etc.: keep the last image on the screen
        print("Weather fetch failed:", e)
        sys.exit(1)
    black, red = render(data)
    if "--preview" in args or "--demo" in args:
        save_preview(black, red, os.path.join(HERE, "preview.png"))
        print("saved preview.png")
    else:
        show(black, red)


if __name__ == "__main__":
    main()
