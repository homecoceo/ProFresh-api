"""
Pro-Fresh Houston — Post-Service Report Generator
Flask API that accepts job data and returns a PDF
"""

from flask import Flask, request, jsonify, send_file

import io
import os
import base64
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from PIL import Image as PILImage

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response



# ── Font registration ─────────────────────────────────────────────────────
def register_fonts():
    font_paths = [
        ('Sans',   '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'),
        ('SansB',  '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'),
        ('SansI',  '/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf'),
        ('SerifB', '/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf'),
        ('LoraI',  '/usr/share/fonts/truetype/google-fonts/Lora-Italic-Variable.ttf'),
    ]
    for name, path in font_paths:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(name, path))

register_fonts()

# ── Helpers ──────────────────────────────────────────────────────────────────
def format_date(date_str):
    """Convert 2026-06-01 to June 1, 2026"""
    if not date_str or date_str == '—':
        return date_str
    try:
        parts = date_str.split('-')
        if len(parts) == 3:
            months = ['January','February','March','April','May','June',
                      'July','August','September','October','November','December']
            return months[int(parts[1])-1] + ' ' + str(int(parts[2])) + ', ' + parts[0]
    except:
        pass
    return date_str

# ── Colors ────────────────────────────────────────────────────────────────
NAVY      = colors.HexColor('#0F1E36')
NAVY2     = colors.HexColor('#162844')
TEAL      = colors.HexColor('#0D6E63')
SKY       = colors.HexColor('#3AAFB9')
SEAFOAM   = colors.HexColor('#E6F5F4')
GOLD      = colors.HexColor('#C8972A')
GOLD_L    = colors.HexColor('#FDF6E3')
IVORY     = colors.HexColor('#F8F7F4')
MID       = colors.HexColor('#6B7280')
LIGHT     = colors.HexColor('#E5E7EB')
WHITE     = colors.white
GREEN     = colors.HexColor('#1A7A4A')
GREEN_L   = colors.HexColor('#E8F5EE')
TEAL2     = colors.HexColor('#1A6B7A')
TEAL2_L   = colors.HexColor('#E6F4F7')
PURPLE    = colors.HexColor('#5B3FA6')
PURPLE_L  = colors.HexColor('#EEE8FF')

W, H = letter
M = 0.5 * inch
CW = W - 2 * M

STATUS_COLORS = {
    'Cleaned':      (GREEN,  GREEN_L),
    'Treated':      (TEAL2,  TEAL2_L),
    'Replaced':     (GOLD,   GOLD_L),
    'Encapsulated': (PURPLE, PURPLE_L),
    'Sanitized':    (GREEN,  GREEN_L),
    'Inspected':    (MID,    IVORY),
    'N/A':          (MID,    IVORY),
}

# ── Drawing helpers ───────────────────────────────────────────────────────
def rr(c, x, y, w, h, r, fill=None, stroke=None, sw=0.5):
    p = c.beginPath()
    p.moveTo(x+r, y); p.lineTo(x+w-r, y); p.arcTo(x+w-r, y, x+w, y+r, 270, 90)
    p.lineTo(x+w, y+h-r); p.arcTo(x+w-r, y+h-r, x+w, y+h, 0, 90)
    p.lineTo(x+r, y+h); p.arcTo(x, y+h-r, x+r, y+h, 90, 90)
    p.lineTo(x, y+r); p.arcTo(x, y, x+r, y+r, 180, 90); p.close()
    if fill: c.setFillColor(fill)
    if stroke: c.setStrokeColor(stroke); c.setLineWidth(sw)
    if fill and stroke: c.drawPath(p, fill=1, stroke=1)
    elif fill: c.drawPath(p, fill=1, stroke=0)
    elif stroke: c.drawPath(p, fill=0, stroke=1)

def pill(c, x, y, w, h, text, bg, fg, size=7):
    rr(c, x, y, w, h, h/2, fill=bg)
    c.setFillColor(fg); c.setFont('SansB', size)
    c.drawCentredString(x+w/2, y+h/2-size*0.35, text)

def crop_image(img_data, ratio):
    """Crop PIL image to target aspect ratio"""
    iw, ih = img_data.size
    sr = iw / ih
    if sr > ratio:
        nw = int(ih * ratio)
        off = (iw - nw) // 2
        img_data = img_data.crop((off, 0, off+nw, ih))
    else:
        nh = int(iw / ratio)
        off = (ih - nh) // 2
        img_data = img_data.crop((0, off, iw, off+nh))
    buf = io.BytesIO()
    img_data.convert('RGB').save(buf, 'JPEG', quality=88)
    buf.seek(0)
    return ImageReader(buf)

def load_logo():
    logo_path = os.path.join(os.path.dirname(__file__), 'logo.png')
    if os.path.exists(logo_path):
        return open(logo_path, 'rb').read()
    return None

# ── Header ────────────────────────────────────────────────────────────────
def draw_header(c, job, page, total_pages):
    logo_data = load_logo()
    c.setFillColor(NAVY)
    c.rect(0, H-1.08*inch, W, 1.08*inch, fill=1, stroke=0)
    c.setFillColor(SKY)
    c.rect(0, H-0.05*inch, W, 0.05*inch, fill=1, stroke=0)

    tx = M
    if logo_data:
        buf = io.BytesIO(logo_data)
        lh = 0.72*inch; lw = lh * (300/246)
        c.drawImage(ImageReader(buf), M, H-0.96*inch, width=lw, height=lh, mask='auto')
        tx = M + lw + 0.16*inch

    c.setFont('SerifB', 17); c.setFillColor(WHITE)
    c.drawString(tx, H-0.46*inch, 'PRO-FRESH HOUSTON')
    c.setFont('LoraI', 8); c.setFillColor(SKY)
    c.drawString(tx, H-0.65*inch, 'We put the "Pro-Fresh" in Professional Cleaning')
    c.setFont('Sans', 8); c.setFillColor(colors.HexColor('#9CA3AF'))
    c.drawRightString(W-M, H-0.46*inch, 'profreshhouston.com')
    c.drawRightString(W-M, H-0.62*inch, '713-632-4949')

    c.setFillColor(TEAL)
    c.rect(0, H-1.28*inch, W, 0.20*inch, fill=1, stroke=0)
    c.setFont('SansB', 8.5); c.setFillColor(WHITE)
    labels = {
        1: 'HVAC POST-SERVICE REPORT — JOB SUMMARY & SERVICES',
        2: 'HVAC POST-SERVICE REPORT — NOTES & RECOMMENDATIONS'
    }
    c.drawString(M, H-1.21*inch, labels.get(page, 'HVAC POST-SERVICE REPORT'))
    c.setFont('Sans', 8); c.setFillColor(colors.HexColor('#B2E4E0'))
    tech = job.get('tech', '—')
    date = format_date(job.get('date', '—'))
    c.drawRightString(W-M, H-1.21*inch, f'{date}   ·   Tech: {tech}   ·   Page {page} of {total_pages}')

def draw_footer(c):
    c.setStrokeColor(LIGHT); c.setLineWidth(0.5)
    c.line(M, 0.48*inch, W-M, 0.48*inch)
    c.setFont('Sans', 7); c.setFillColor(MID)
    c.drawString(M, 0.32*inch, 'Pro-Fresh Houston  ·  713-632-4949  ·  profreshhouston.com')
    c.drawRightString(W-M, 0.32*inch, 'Thank you for choosing Pro-Fresh Houston!')

def sec_hdr(c, y, title):
    c.setFillColor(TEAL)
    c.rect(M, y-0.03*inch, 0.032*inch, 0.20*inch, fill=1, stroke=0)
    c.setFont('SansB', 9.5); c.setFillColor(NAVY)
    c.drawString(M+0.09*inch, y, title)
    c.setStrokeColor(LIGHT); c.setLineWidth(0.4)
    c.line(M, y-0.07*inch, W-M, y-0.07*inch)
    return y - 0.20*inch

# ── Info cards ────────────────────────────────────────────────────────────
def info_cards(c, y, job):
    cw = (CW - 3*0.09*inch) / 4
    ch = 0.54*inch
    cards = [
        ('CLIENT',   job.get('clientName', '—'),   ''),
        ('ADDRESS',  job.get('address', '—'),       job.get('cityZip', '')),
        ('SERVICE',  job.get('service', '—'),       job.get('unitsVents', '')),
        ('PHONE',    job.get('phone', '—'),         format_date(job.get('date', ''))),
    ]
    for i, (lbl, val, sub) in enumerate(cards):
        cx = M + i*(cw+0.09*inch)
        rr(c, cx, y-ch, cw, ch, 5, fill=IVORY, stroke=LIGHT, sw=0.5)
        c.setFont('SansB', 6.5); c.setFillColor(TEAL)
        c.drawString(cx+0.1*inch, y-0.17*inch, lbl)
        # Smart wrapping - find natural break point
        max_w = cw - 0.2*inch
        c.setFont('SansB', 8); c.setFillColor(NAVY)
        if c.stringWidth(val, 'SansB', 8) > max_w:
            # Try to break at a space
            words = val.split(' ')
            line1 = ''; line2 = ''
            for word in words:
                test = (line1 + ' ' + word).strip()
                if c.stringWidth(test, 'SansB', 8) <= max_w:
                    line1 = test
                else:
                    line2 = (line2 + ' ' + word).strip()
            c.drawString(cx+0.1*inch, y-0.28*inch, line1)
            c.setFont('Sans', 7.5); c.setFillColor(NAVY)
            c.drawString(cx+0.1*inch, y-0.38*inch, line2[:24])
            if sub:
                c.setFont('Sans', 7); c.setFillColor(MID)
                c.drawString(cx+0.1*inch, y-0.48*inch, sub[:22])
        else:
            c.drawString(cx+0.1*inch, y-0.32*inch, val)
            if sub:
                c.setFont('Sans', 7.5); c.setFillColor(MID)
                c.drawString(cx+0.1*inch, y-0.44*inch, sub[:22])
    return y - ch - 0.14*inch

# ── Services table ────────────────────────────────────────────────────────
def services_table(c, y, services):
    cols = [M, M+2.05*inch, M+3.4*inch, M+4.75*inch]
    rh = 0.245*inch; hh = 0.265*inch
    hdrs = ['COMPONENT / AREA', 'PRIOR CONDITION', 'SERVICE PERFORMED', 'STATUS']

    c.setFillColor(NAVY)
    c.rect(M, y-hh, CW, hh, fill=1, stroke=0)
    c.setFont('SansB', 7.5); c.setFillColor(WHITE)
    for i, h in enumerate(hdrs):
        c.drawString(cols[i]+0.07*inch, y-hh+0.09*inch, h)
    y -= hh

    for ri, row in enumerate(services):
        comp  = row.get('comp', '—')
        prior = row.get('prior', '—')
        svc   = row.get('svc', '—')
        status = row.get('status', 'Cleaned')
        fg, bg = STATUS_COLORS.get(status, (MID, IVORY))

        c.setFillColor(IVORY if ri%2==0 else WHITE)
        c.rect(M, y-rh, CW, rh, fill=1, stroke=0)
        c.setStrokeColor(LIGHT); c.setLineWidth(0.3)
        c.line(M, y-rh, M+CW, y-rh)

        c.setFont('SansB', 8); c.setFillColor(NAVY)
        c.drawString(cols[0]+0.07*inch, y-rh+0.085*inch, comp[:28])
        c.setFont('SansI', 7.5); c.setFillColor(MID)
        c.drawString(cols[1]+0.07*inch, y-rh+0.085*inch, prior[:20])
        c.setFont('Sans', 7.5); c.setFillColor(colors.HexColor('#374151'))
        c.drawString(cols[2]+0.07*inch, y-rh+0.085*inch, svc[:22])

        pw = 0.88*inch; ph = 0.165*inch
        px = cols[3]+0.06*inch; py = y-rh+(rh-ph)/2
        pill(c, px, py, pw, ph, status, bg, fg, size=6.8)
        y -= rh

    c.setStrokeColor(TEAL); c.setLineWidth(0.8)
    c.line(M, y, M+CW, y)
    return y - 0.13*inch

# ── Photo pairs ───────────────────────────────────────────────────────────
def photo_pair(c, y, title, before_data, after_data, before_cap, after_cap, ph):
    pw = (CW - 0.15*inch) / 2
    ratio = pw / ph
    cap_h = 0.20*inch; lbl_h = 0.13*inch

    c.setFont('SansB', 8); c.setFillColor(NAVY)
    c.drawString(M, y, title)
    c.setStrokeColor(LIGHT); c.setLineWidth(0.3)
    tw = c.stringWidth(title, 'SansB', 8)
    c.line(M+tw+6, y+3, M+CW, y+3)
    y -= lbl_h

    pairs = [(before_data, before_cap, True), (after_data, after_cap, False)]
    for i, (img_data, cap, is_before) in enumerate(pairs):
        px = M + i*(pw+0.15*inch)
        iy = y - ph
        rr(c, px-0.02*inch, iy-cap_h-0.03*inch, pw+0.04*inch, ph+cap_h+0.06*inch, 5, fill=IVORY, stroke=LIGHT, sw=0.5)

        if img_data:
            try:
                ir = crop_image(img_data, ratio)
                c.drawImage(ir, px, iy, width=pw, height=ph, preserveAspectRatio=False)
            except:
                rr(c, px, iy, pw, ph, 0, fill=LIGHT)
        else:
            rr(c, px, iy, pw, ph, 0, fill=colors.HexColor('#F3F4F6'))
            c.setFont('Sans', 8); c.setFillColor(MID)
            c.drawCentredString(px+pw/2, iy+ph/2, 'No photo')

        badge_bg = colors.HexColor('#DC2626') if is_before else GREEN
        pill(c, px+0.07*inch, iy+ph-0.22*inch, 0.52*inch, 0.165*inch,
             'BEFORE' if is_before else 'AFTER', badge_bg, WHITE, size=6.3)

        c.setFillColor(NAVY)
        c.rect(px, iy-cap_h, pw, cap_h, fill=1, stroke=0)
        c.setFont('SansB', 7.5); c.setFillColor(WHITE)
        c.drawCentredString(px+pw/2, iy-cap_h+0.067*inch, cap[:35])

    return y - ph - cap_h - 0.14*inch

def single_photo(c, y, img_data, cap, ph):
    pw = (CW - 0.15*inch) / 2
    ratio = pw / ph
    cap_h = 0.20*inch
    px = M
    iy = y - ph
    rr(c, px-0.02*inch, iy-cap_h-0.03*inch, pw+0.04*inch, ph+cap_h+0.06*inch, 5, fill=IVORY, stroke=LIGHT, sw=0.5)
    if img_data:
        try:
            ir = crop_image(img_data, ratio)
            c.drawImage(ir, px, iy, width=pw, height=ph, preserveAspectRatio=False)
        except:
            pass
    c.setFillColor(NAVY)
    c.rect(px, iy-cap_h, pw, cap_h, fill=1, stroke=0)
    c.setFont('SansB', 7.5); c.setFillColor(WHITE)
    c.drawCentredString(px+pw/2, iy-cap_h+0.067*inch, cap[:35])
    return y - ph - cap_h - 0.14*inch

# ── Notes box ─────────────────────────────────────────────────────────────
def notes_box(c, y, text):
    if not text:
        text = 'No notes entered.'
    words = text.split()
    lines = []; line = ''
    c.setFont('Sans', 8.5)
    for w in words:
        t = (line+' '+w).strip()
        if c.stringWidth(t, 'Sans', 8.5) < CW-0.3*inch:
            line = t
        else:
            lines.append(line); line = w
    if line: lines.append(line)
    bh = 0.22*inch + len(lines)*0.165*inch + 0.12*inch
    rr(c, M, y-bh, CW, bh, 5, fill=SEAFOAM, stroke=TEAL, sw=0.8)
    c.setFillColor(TEAL); c.rect(M, y-bh, 0.038*inch, bh, fill=1, stroke=0)
    c.setFont('SansB', 8); c.setFillColor(TEAL)
    c.drawString(M+0.13*inch, y-0.165*inch, 'TECHNICIAN NOTES')
    c.setFont('Sans', 8.5); c.setFillColor(colors.HexColor('#1F2937'))
    ty = y-0.165*inch-0.17*inch
    for l in lines:
        c.drawString(M+0.13*inch, ty, l); ty -= 0.165*inch
    return y - bh - 0.13*inch

# ── Rec cards ─────────────────────────────────────────────────────────────
def rec_cards(c, y, job):
    cw = (CW - 2*0.12*inch) / 3
    ch = 0.62*inch
    recs = [
        ('RECOMMENDED INSPECTION', job.get('recInspection', '—'), TEAL, SEAFOAM),
        ('NEXT CLEANING',          job.get('nextClean', '—'),     TEAL, SEAFOAM),
        ('NEXT FILTER CHANGE',     job.get('filterDue', '—'),     GOLD, GOLD_L),
    ]
    for i, (title, val, accent, bg) in enumerate(recs):
        cx = M + i*(cw+0.12*inch)
        rr(c, cx, y-ch, cw, ch, 6, fill=bg, stroke=accent, sw=1)
        c.setFont('SansB', 6.5); c.setFillColor(accent)
        c.drawString(cx+0.12*inch, y-0.18*inch, title)
        c.setFont('SerifB', 11); c.setFillColor(NAVY)
        c.drawString(cx+0.12*inch, y-0.42*inch, val[:20])
    return y - ch - 0.14*inch

# ── Signature ─────────────────────────────────────────────────────────────
def sig_line(c, y, job):
    c.setStrokeColor(LIGHT); c.setLineWidth(0.6)
    c.line(M, y, M+2.2*inch, y)
    c.setFont('Sans', 7.5); c.setFillColor(MID)
    tech = job.get('tech', '—')
    date = format_date(job.get('date', '—'))
    c.drawString(M, y-0.14*inch, f'Technician: {tech}  ·  {date}')

# ── Main PDF builder ──────────────────────────────────────────────────────
def build_pdf(job):
    """
    Build a 2-page PDF report from job data dict.
    Returns bytes of the PDF.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle(f'Pro-Fresh Houston — Post-Service Report — {job.get("clientName", "Client")}')

    services = job.get('services', [])
    photos = job.get('photos', [])  # list of {src: base64, label: str}

    # Convert base64 photos to PIL images - resize large images for performance
    pil_photos = []
    for p in photos:
        try:
            src = p.get('src', '')
            if ',' in src:
                src = src.split(',')[1]
            img_bytes = base64.b64decode(src)
            img = PILImage.open(io.BytesIO(img_bytes)).convert('RGB')
            # Resize if too large (max 1200px wide) to prevent memory issues
            if img.width > 1200:
                ratio = 1200 / img.width
                new_h = int(img.height * ratio)
                img = img.resize((1200, new_h), PILImage.LANCZOS)
            pil_photos.append({'img': img, 'label': p.get('label', '')})
        except Exception as e:
            print(f"Photo error: {e}")
            pil_photos.append(None)

    # ── PAGE 1: Header + Info + Services + Photos ──────────────────────
    draw_header(c, job, page=1, total_pages=2)
    draw_footer(c)
    y = H - 1.44*inch

    y = sec_hdr(c, y, 'Job Information')
    y -= 0.07*inch
    y = info_cards(c, y, job)
    y -= 0.12*inch

    y = sec_hdr(c, y, 'Services Performed')
    y -= 0.07*inch
    if services:
        y = services_table(c, y, services)
    y -= 0.10*inch

    y = sec_hdr(c, y, 'Photo Documentation')
    y -= 0.09*inch

    # Calculate photo height to fill remaining space
    footer_reserve = 0.65*inch
    cap_h = 0.20*inch; lbl_h = 0.13*inch; pair_gap = 0.14*inch

    # Group photos into pairs for before/after display
    valid_photos = [p for p in pil_photos if p is not None]

    if valid_photos:
        n_pairs = (len(valid_photos) + 1) // 2
        available = y - footer_reserve
        ph = (available - n_pairs*(lbl_h + cap_h + pair_gap)) / n_pairs

        i = 0
        while i < len(valid_photos):
            if i+1 < len(valid_photos):
                before = valid_photos[i]
                after = valid_photos[i+1]
                pair_title = before['label'].replace(' before','').replace(' Before','').replace(' before','').strip()
                y = photo_pair(c, y, pair_title,
                    before['img'], after['img'],
                    before['label'], after['label'], ph)
                i += 2
            else:
                sole = valid_photos[i]
                y = single_photo(c, y, sole['img'], sole['label'], ph)
                i += 1
    else:
        c.setFont('SansI', 9); c.setFillColor(MID)
        c.drawString(M, y-0.3*inch, 'No photos uploaded for this job.')
        y -= 0.5*inch

    # ── PAGE 2: Notes + Recommendations + Signature ────────────────────
    c.showPage()
    draw_header(c, job, page=2, total_pages=2)
    draw_footer(c)
    y = H - 1.44*inch

    y = sec_hdr(c, y, 'Technician Notes')
    y -= 0.08*inch
    y = notes_box(c, y, job.get('notes', ''))
    y -= 0.22*inch

    y = sec_hdr(c, y, 'Recommendations')
    y -= 0.10*inch
    y = rec_cards(c, y, job)
    y -= 0.22*inch

    y = sec_hdr(c, y, 'Technician Sign-Off')
    y -= 0.14*inch
    sig_line(c, y, job)

    c.save()
    buf.seek(0)
    return buf

# ── Routes ────────────────────────────────────────────────────────────────
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'Pro-Fresh PDF Generator'})

@app.route('/generate-report', methods=['POST', 'OPTIONS'])
def generate_report():
    if request.method == 'OPTIONS':
        return '', 200
    """
    Accepts JSON job data, returns PDF file.

    Expected JSON structure:
    {
        "clientName": "Fiona Black",
        "address": "13425 Preston Cliff Ct",
        "cityZip": "Houston, TX 77095",
        "phone": "713-492-7146",
        "date": "June 2, 2026",
        "tech": "Bryce",
        "service": "Air Duct Cleaning",
        "unitsVents": "22 vents / 1 unit",
        "services": [
            {"comp": "Supply Air Ducts", "prior": "Dusty", "svc": "Cleaned & Vacuumed", "status": "Cleaned"}
        ],
        "photos": [
            {"src": "data:image/jpeg;base64,...", "label": "Before - Evap Coil"}
        ],
        "notes": "System found with microbial growth...",
        "recInspection": "6 months",
        "nextClean": "12 months",
        "filterDue": "October 6, 2026"
    }
    """
    try:
        job = request.get_json()
        if not job:
            return jsonify({'error': 'No data received'}), 400

        pdf_buf = build_pdf(job)
        client_name = job.get('clientName', 'Client').replace(' ', '_')
        filename = f'ProFresh_Report_{client_name}.pdf'

        return send_file(
            pdf_buf,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
