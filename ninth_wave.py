#!/usr/bin/env python3
"""«Девятый вал» — чистовая версия: плотная волна + золотой просвет."""
import math
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageChops

W, H = 1600, 1080
random.seed(101)
np.random.seed(101)


def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / max(1e-6, e1 - e0)))
    return t * t * (3 - 2 * t)


def fbm(w, h, octaves=5, persistence=0.55, base=0.005):
    result = np.zeros((h, w), dtype=np.float64)
    amp, freq = 1.0, base
    for _ in range(octaves):
        lh, lw = max(2, int(h * freq * 12)), max(2, int(w * freq * 12))
        low = np.random.rand(lh, lw)
        yi = np.linspace(0, lh - 1, h)
        xi = np.linspace(0, lw - 1, w)
        y0 = np.clip(yi.astype(int), 0, lh - 2)
        x0 = np.clip(xi.astype(int), 0, lw - 2)
        fy = (yi - y0)[:, None]
        fx = (xi - x0)[None, :]
        interp = (low[np.ix_(y0, x0)]*(1-fy)*(1-fx) + low[np.ix_(y0, x0+1)]*fy*(1-fx) +
                  low[np.ix_(y0+1, x0)]*(1-fy)*fx + low[np.ix_(y0+1, x0+1)]*fy*fx)
        result += amp * interp
        amp *= persistence
        freq *= 2.0
    mx = result.max()
    return result / mx if mx > 0 else result


# ============================================================
# 1. НЕБО
# ============================================================
horizon = int(H * 0.45)
sky = np.zeros((H, W, 3), dtype=np.float64)

stops = [
    (0.00, (28, 22, 54)),
    (0.18, (68, 40, 78)),
    (0.38, (138, 76, 90)),
    (0.55, (192, 108, 76)),
    (0.72, (228, 148, 70)),
    (0.86, (246, 188, 108)),
    (1.00, (250, 222, 158)),
]
for y in range(horizon + 1):
    t = y / horizon
    col = stops[-1][1]
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t0 <= t <= t1:
            col = lerp(c0, c1, (t - t0) / (t1 - t0))
            break
    sky[y, :] = col

cloud_n = fbm(W, horizon + 1, octaves=5, persistence=0.6, base=0.004)
ymask = np.linspace(1.1, 0.0, horizon + 1)[:, None]
cmask = np.clip(cloud_n * ymask * 1.5, 0, 1)
for y in range(horizon + 1):
    for x in range(W):
        cm = cmask[y, x]
        if cm > 0.3:
            depth = (cm - 0.3) / 0.7
            sundist = math.exp(-((x - W*0.48)**2)/(2*(W*0.35)**2))
            warm = sundist * (y / horizon)
            dk = np.array([38, 28, 56])
            wm = np.array([162, 90, 74]) + np.array([48, 38, 16])*warm
            cc = dk + (wm - dk)*min(1, warm*1.3)
            sky[y, x] = sky[y, x]*(1-depth*0.6) + cc*(depth*0.6)

img = Image.fromarray(np.clip(sky, 0, 255).astype(np.uint8), "RGB")
img = img.filter(ImageFilter.GaussianBlur(2))

# Солнце
sun_x, sun_y = int(W*0.48), int(H*0.38)
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd = ImageDraw.Draw(glow)
for r, amax, c0, c1 in [(400, 20, (220,110,50),(245,175,90)),
                        (170, 42, (240,155,65),(250,215,140)),
                        (42, 170, (250,205,120),(255,252,240))]:
    for rr in range(r, 0, -2 if r > 100 else -1):
        t = 1 - rr/r
        col = lerp(c0, c1, t**1.4)
        gd.ellipse([sun_x-rr, sun_y-rr, sun_x+rr, sun_y+rr], fill=col+(int(amax*t**1.8),))

img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")

# ============================================================
# 2. МОРЕ — базовая заливка + слои
# ============================================================
# Сплошная заливка моря
sea = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sbd = ImageDraw.Draw(sea)
sbd.rectangle([0, horizon, W, H], fill=(14, 52, 88, 255))
img = Image.alpha_composite(img.convert("RGBA"), sea).convert("RGB")


def wave_y(x, base, comps):
    y = base
    for amp, freq, ph in comps:
        y += amp*math.sin(x*freq+ph)
    return y


# Дальнее море — тонкие слои
far_layers = [
    (horizon+0,  [(1.5,0.025,0.0),(0.8,0.058,1.0)], (160,210,200),(55,138,155)),
    (horizon+5,  [(2,0.020,0.5),(1.2,0.050,1.8)],   (145,205,195),(48,125,148)),
    (horizon+13, [(3,0.016,1.0),(1.8,0.042,2.6)],   (128,195,186),(40,112,140)),
    (horizon+25, [(5,0.013,1.5),(2.8,0.036,0.2)],   (112,185,178),(34,102,132)),
    (horizon+42, [(8,0.011,2.0),(4,0.030,1.0)],     (96,176,170), (28,92,125)),
    (horizon+64, [(12,0.009,2.5),(5.5,0.026,1.8)],  (82,168,162), (24,84,118)),
]

for base, comps, crest, body in far_layers:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    pts = [(x, wave_y(x, base, comps)) for x in range(-8, W+12, 4)]
    ld.polygon(pts+[(W+20, H+20), (-20, H+20)], fill=body+(255,))
    bh = 8
    for x, y in pts:
        sun_b = 0.2+0.8*math.exp(-((x-sun_x)**2)/(2*(W*0.45)**2))
        for dy in range(bh):
            t = 1-dy/bh
            col = lerp(body, crest, t**1.1)
            col = tuple(int(c*(0.5+0.7*sun_b*t)) for c in col)
            ld.point((x, y+dy), fill=col+(255,))
    img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")

# ============================================================
# 3. ДЕВЯТЫЙ ВАЛ
# ============================================================
peak_x = W * 0.60


def ninth_top(x):
    if x < peak_x:
        u = max(0.0, (x - W*0.06)/(peak_x - W*0.06))
        g = u**1.7
    else:
        u = max(0.0, (W*0.98-x)/(W*0.98-peak_x))
        g = u**0.55
    ripple = (0.05*math.sin(x*0.022) + 0.03*math.sin(x*0.055+1.5) +
              0.018*math.sin(x*0.11+3.0) + 0.01*math.sin(x*0.21+0.7))
    h = H*0.30*g*(1+ripple)
    if x < W*0.05: h *= x/(W*0.05)
    if x > W*0.96: h *= (W-x)/(W*0.04)
    return horizon+3-h


# Тело волны: сплошной полигон
pts9 = [(float(x), ninth_top(x)) for x in range(-4, W+8, 2)]
wave = Image.new("RGBA", (W, H), (0, 0, 0, 0))
wd = ImageDraw.Draw(wave)
poly9 = pts9 + [(W+20, H+20), (-20, H+20)]
wd.polygon(poly9, fill=(20, 78, 115, 255))

# numpy-градиент по столбцам — плавный, без ступеней
wave_arr = np.array(wave, dtype=np.float64)
for x, y_top in pts9:
    xi = int(x)
    if not (0 <= xi < W): continue
    g_peak = math.exp(-((x-peak_x)**2)/(2*(W*0.28)**2))
    depth = H - y_top
    crest_c = np.array([55, 150, 165], dtype=np.float64)
    mid_c = np.array([28, 95, 128], dtype=np.float64)
    base_c = np.array([12, 45, 78], dtype=np.float64)
    # Заполняем каждый пиксель столбца плавным градиентом
    for yi in range(int(max(0, y_top)), H):
        t = (yi - y_top) / depth if depth > 0 else 1.0
        if t < 0.3:
            u = t / 0.3
            col = crest_c*(1-u) + mid_c*u
        else:
            u = (t-0.3)/0.7
            col = mid_c*(1-u) + base_c*u
        # Мягкая фактура
        struct = 0.94 + 0.06*math.sin(x*0.03 + t*4)
        col = col * struct
        wave_arr[yi, xi] = np.clip(col, 0, 255).tolist() + [255.0]
        # Заполняем и следующий пиксель, чтобы не было полос
        if xi+1 < W:
            wave_arr[yi, xi+1] = np.clip(col, 0, 255).tolist() + [255.0]

wave = Image.fromarray(np.clip(wave_arr, 0, 255).astype(np.uint8), "RGBA")

# ПРОСВЕТ — ЯРКИЙ золотистый свет на гребне (сигнатурный эффект Айвазовского)
transl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
td = ImageDraw.Draw(transl)
for x, y_top in pts9:
    g_peak = math.exp(-((x-peak_x)**2)/(2*(W*0.34)**2))
    sun_b = math.exp(-((x-sun_x)**2)/(2*(W*0.38)**2))
    # Толщина просвета:显著 больше на пике
    th = int(30 + 160*g_peak*(0.3+0.7*sun_b))
    for dy in range(th):
        t = dy/th
        # Градиент: яркое белое золото → тёплое золото → бирюза → тело
        c0 = np.array([255, 252, 245], dtype=np.float64)  # белое золото
        c1 = np.array([255, 230, 170], dtype=np.float64)  # тёплое золото
        c2 = np.array([180, 230, 215], dtype=np.float64)  # светлая бирюза
        c3 = np.array([55, 150, 165], dtype=np.float64)   # тело волны
        if t < 0.15:
            u = t/0.15
            col = c0*(1-u) + c1*u
        elif t < 0.45:
            u = (t-0.15)/0.3
            col = c1*(1-u) + c2*u
        else:
            u = (t-0.45)/0.55
            col = c2*(1-u) + c3*u
        boost = 0.7+0.3*sun_b  # ярче в любом случае
        col = col * boost
        a = int(235*(1-0.35*t))  # менее быстрое затухание
        td.point((x, y_top+dy), fill=tuple(int(c) for c in np.clip(col,0,255))+(a,))

transl = transl.filter(ImageFilter.GaussianBlur(2.5))
wave = Image.alpha_composite(wave, transl)

# Ещё более яркий золотой блик на самой кромке —最强ший акцент
crest_l = Image.new("RGBA", (W, H), (0, 0, 0, 0))
cld = ImageDraw.Draw(crest_l)
for x, y_top in pts9:
    g_peak = math.exp(-((x-peak_x)**2)/(2*(W*0.36)**2))
    sun_b = 0.2+0.8*math.exp(-((x-sun_x)**2)/(2*(W*0.44)**2))
    th = int(5+35*g_peak*sun_b)  # толще блик
    for dy in range(th):
        t = 1-dy/max(1, th)
        # От тёплого золота к холодному белому
        col_gold = (255, 250, 220)
        col_white = (255, 255, 255)
        col = lerp(col_white, col_gold, sun_b*0.7)
        # Вниз по блику — лёгкая бирюзовая примесь
        col = lerp(col, (200, 240, 235), dy/max(1,th)*0.3)
        a = int(245*t)  # почти непрозрачный блик
        cld.point((x, y_top+dy), fill=col+(a,))

crest_l = crest_l.filter(ImageFilter.GaussianBlur(0.8))
wave = Image.alpha_composite(wave, crest_l)

# Пена
foam = Image.new("RGBA", (W, H), (0, 0, 0, 0))
fd = ImageDraw.Draw(foam)
for _ in range(14000):
    x = random.randint(0, W-1)
    y_t = ninth_top(x)
    g_peak = math.exp(-((x-peak_x)**2)/(2*(W*0.24)**2))
    if random.random() > 0.03+0.9*g_peak: continue
    y = y_t+random.randint(-3, int(15+42*g_peak))
    if y < 0: continue
    r = random.randint(1,5)
    sh = random.randint(215,255)
    fd.ellipse([x-r, y-r, x+r, y+r], fill=(sh, sh, min(255, sh+10), random.randint(190,250)))

for _ in range(2800):
    x = random.gauss(peak_x, W*0.14)
    if not (0 <= x < W): continue
    y_t = ninth_top(x)
    y = y_t-random.randint(5,140)
    if y < 0: continue
    r = random.randint(1,3)
    sh = random.randint(205,255)
    fd.ellipse([x-r, y-r, x+r, y+r], fill=(sh, sh, 255, random.randint(55,150)))

for _ in range(450):
    x = random.gauss(peak_x, W*0.08)
    if not (0 <= x < W): continue
    y_t = ninth_top(x)
    y = y_t-random.randint(20,200)
    if y < 0: continue
    r = random.randint(2,7)
    sh = random.randint(220,255)
    fd.ellipse([x-r, y-r, x+r, y+r], fill=(sh, sh, 255, random.randint(150,230)))

foam = foam.filter(ImageFilter.GaussianBlur(0.6))
wave = Image.alpha_composite(wave, foam)

img = Image.alpha_composite(img.convert("RGBA"), wave).convert("RGB")

# Дорожка солнца на воде — мягкое отражение (только в дальних слоях моря)
sun_path = Image.new("RGBA", (W, H), (0, 0, 0, 0))
spd = ImageDraw.Draw(sun_path)
for y in range(horizon+70, int(H*0.55)):  # только зона за волной
    t = (y - horizon - 70) / (int(H*0.55) - horizon - 70)
    width = int(40 + 120*t)
    alpha = int(20 * (1-t*0.5))
    x_off = int(15*math.sin(y*0.015) * t)
    spd.rectangle([sun_x-width+x_off, y, sun_x+width+x_off, y+1],
                  fill=(255, 215, 150, alpha))
sun_path = sun_path.filter(ImageFilter.GaussianBlur(18))
# Маска — только зона моря, исключая волну
sp_mask = Image.new("L", (W, H), 0)
spmd = ImageDraw.Draw(sp_mask)
# Просто горизонтальная полоса между горизонт+70 и H*0.55
spmd.rectangle([0, horizon+70, W, int(H*0.55)], fill=255)
sun_path.putalpha(Image.composite(sun_path.split()[3], Image.new("L", (W, H), 0), sp_mask))
img = Image.alpha_composite(img.convert("RGBA"), sun_path).convert("RGB")

# ============================================================
# 4. ОБЛОМКИ + ФИГУРЫ (крупные, контрастные)
# ============================================================
# Сначала — контровое свечение позади обломков
backlight = Image.new("RGBA", (W, H), (0, 0, 0, 0))
bcd = ImageDraw.Draw(backlight)
bx, by = int(W*0.38), int(H*0.80)
for r in range(200, 0, -2):
    t = 1 - r/200
    col = lerp((255, 170, 90), (255, 220, 160), t)
    a = int(30*(t**2))
    bcd.ellipse([bx-r*2, by-r, bx+r*2, by+r], fill=col+(a,))
backlight = backlight.filter(ImageFilter.GaussianBlur(28))
bl_mask = Image.new("L", (W, H), 0)
bld = ImageDraw.Draw(bl_mask)
bld.rectangle([0, int(H*0.68), W, H], fill=180)
backlight.putalpha(Image.composite(backlight.split()[3], Image.new("L", (W, H), 0), bl_mask))
img = Image.alpha_composite(img.convert("RGBA"), backlight).convert("RGB")

# Теперь — силуэты обломков ПОВЕРХ свечения
sil = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(sil)
dk = (8, 5, 4, 255)

# Мачта
sd.line([(int(W*0.14), int(H*0.86)), (int(W*0.58), int(H*0.70))], fill=dk, width=20)
sd.line([(int(W*0.25), int(H*0.79)), (int(W*0.48), int(H*0.97))], fill=dk, width=13)
sd.line([(int(W*0.52), int(H*0.83)), (int(W*0.66), int(H*0.77))], fill=dk, width=10)
# Парус
sd.polygon([(int(W*0.28), int(H*0.77)), (int(W*0.42), int(H*0.82)),
            (int(W*0.39), int(H*0.95)), (int(W*0.27), int(H*0.89))], fill=(18,13,24,245))
sd.polygon([(int(W*0.44), int(H*0.81)), (int(W*0.51), int(H*0.84)),
            (int(W*0.49), int(H*0.92)), (int(W*0.43), int(H*0.88))], fill=(14,10,20,215))


def figure(dd, cx, cy, s=1.0, lean=0):
    hr = max(3, int(8*s))
    dd.ellipse([cx-hr, cy-int(36*s), cx+hr, cy-int(22*s)], fill=dk)
    tx = cx+int(lean*5*s)
    dd.line([(cx, cy-int(22*s)), (tx, cy+int(6*s))], fill=dk, width=max(3, int(6*s)))
    ax, ay = int(18*s), int(20*s)
    dd.line([(cx, cy-int(17*s)), (cx-ax, cy-int(17*s)-ay)], fill=dk, width=max(2, int(3.5*s)))
    dd.line([(cx, cy-int(17*s)), (cx+ax, cy-int(17*s)-ay+int(5*s))], fill=dk, width=max(2, int(3.5*s)))
    dd.line([(tx, cy+int(6*s)), (cx-int(10*s), cy+int(25*s))], fill=dk, width=max(2, int(3.5*s)))
    dd.line([(tx, cy+int(6*s)), (cx+int(12*s), cy+int(23*s))], fill=dk, width=max(2, int(3.5*s)))


for args in [
    (int(W*0.18), int(H*0.83), 1.4, -1), (int(W*0.25), int(H*0.77), 1.25, 1),
    (int(W*0.32), int(H*0.80), 1.35, 0), (int(W*0.39), int(H*0.74), 1.2, -1),
    (int(W*0.45), int(H*0.77), 1.15, 1), (int(W*0.51), int(H*0.81), 1.25, 0),
    (int(W*0.56), int(H*0.79), 1.1, -1),
]:
    figure(sd, *args)

img = Image.alpha_composite(img.convert("RGBA"), sil).convert("RGB")

# ============================================================
# 5. СРЕДНЕЕ МОРЕ
# ============================================================
mid_layers = [
    (horizon+100, [(15,0.008,3.0),(7,0.022,2.2),(4,0.045,0.8)],  (65,155,148), (20,74,110)),
    (horizon+155, [(20,0.007,3.8),(9,0.020,3.2),(5,0.041,1.8)],  (56,146,140), (17,66,102)),
    (horizon+215, [(25,0.006,4.5),(11,0.018,4.0),(6,0.038,2.8)], (49,138,133), (14,58,94)),
    (horizon+285, [(30,0.006,5.2),(13,0.016,0.5),(7,0.035,3.8)], (42,130,125), (12,50,86)),
    (horizon+365, [(35,0.005,0.5),(15,0.014,1.5),(8,0.032,4.8)], (36,122,118), (10,43,79)),
    (horizon+455, [(40,0.005,1.5),(16,0.013,2.5),(9,0.030,0.5)], (31,114,110), (8,37,73)),
]

for base, comps, crest, body in mid_layers:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    # Добавляем случайную вариацию для органичности
    base_off = random.randint(-8, 8)
    phase_off = random.uniform(0, 2*math.pi)
    comps_var = [(amp, freq, ph+phase_off) for amp, freq, ph in comps]
    pts = [(x, wave_y(x, base+base_off, comps_var)) for x in range(-8, W+12, 4)]
    ld.polygon(pts+[(W+20, H+20), (-20, H+20)], fill=body+(255,))
    bh = 8
    for x, y in pts:
        sun_b = 0.15+0.85*math.exp(-((x-sun_x)**2)/(2*(W*0.45)**2))
        for dy in range(bh):
            t = 1-dy/bh
            col = lerp(body, crest, t**1.3)
            col = tuple(int(c*(0.4+0.6*sun_b*t)) for c in col)
            ld.point((x, y+dy), fill=col+(255,))
        # Пена — более разреженная, разного размера
        if random.random() < 0.3:
            n_dots = random.randint(1, 4)
            for _ in range(n_dots):
                fx,fy = x+random.randint(-5,5), y+random.randint(-2,5)
                r = random.randint(1,4)
                sh = random.randint(185,250)
                ld.ellipse([fx-r, fy-r, fx+r, fy+r], fill=(sh, sh, min(255, sh+10), random.randint(120,170)))
    img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")

# ============================================================
# 6. ПЕРЕДНИЙ ПЛАН
# ============================================================
fg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
fgd = ImageDraw.Draw(fg)
for base, comps, alpha in [
    (H*0.90, [(13,0.013,0.5),(6,0.027,2.0)], 250),
    (H*0.96, [(19,0.011,3.2),(9,0.021,0.3)], 253),
]:
    pts_fg = [(x, wave_y(x, base, comps)) for x in range(-8, W+12, 4)]
    fgd.polygon(pts_fg+[(W+20, H+20), (-20, H+20)], fill=(2, 9, 22, alpha))
    for x, y in pts_fg:
        if random.random() < 0.5:
            for _ in range(random.randint(1, 3)):
                r = random.randint(1, 3)
                sh = random.randint(180, 240)
                dy = random.randint(-2, 3)
                fgd.ellipse([x-r, y-r+dy, x+r, y+r+dy], fill=(sh, sh, min(255, sh+8), random.randint(110, 180)))

img = Image.alpha_composite(img.convert("RGBA"), fg).convert("RGB")

# ============================================================
# 7. ПОСТ-ОБРАБОТКА
# ============================================================
img = ImageEnhance.Color(img).enhance(1.22)
img = ImageEnhance.Contrast(img).enhance(1.14)
img = ImageEnhance.Brightness(img).enhance(1.05)

oil = img.filter(ImageFilter.SMOOTH_MORE).filter(ImageFilter.GaussianBlur(0.8))
img = Image.blend(img, oil, 0.2)

noise = Image.effect_noise((W, H), 6).convert("L").point(lambda p: 128+(p-128)//7)
img = ImageChops.overlay(img, Image.merge("RGB", (noise, noise, noise)))

vig = Image.new("L", (W, H), 0)
vd = ImageDraw.Draw(vig)
vd.rectangle([0, 0, W, H], fill=255)
vd.ellipse([-int(W*0.1), -int(H*0.1), int(W*1.1), int(H*1.1)], fill=0)
vig = vig.filter(ImageFilter.GaussianBlur(80))
img = Image.composite(Image.new("RGB", (W, H), (10, 6, 18)), img, vig)

img = img.filter(ImageFilter.SHARPEN)

# Сохраняем рядом со скриптом в подпапку output/
import os
script_dir = os.path.dirname(os.path.abspath(__file__))
out_dir = os.path.join(script_dir, "output")
os.makedirs(out_dir, exist_ok=True)
out = os.path.join(out_dir, "ninth_wave_pil.png")
img.save(out, "PNG", quality=95)
print(f"Saved: {out} ({W}x{H})")
