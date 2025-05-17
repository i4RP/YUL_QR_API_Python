from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import qrcode
import svgwrite
import math
import cairosvg
import io
import cloudinary
import cloudinary.uploader

app = FastAPI()

# ---------- リクエストモデル ----------
class QRRequest(BaseModel):
    type: str
    url: str

# ---------- 星型の座標を計算 ----------
def create_star_points(cx, cy, r_outer, r_inner, points=5):
    angle = math.pi / points
    coords = []
    for i in range(2 * points):
        r = r_outer if i % 2 == 0 else r_inner
        theta = i * angle - math.pi / 2
        x = cx + r * math.cos(theta)
        y = cy + r * math.sin(theta)
        coords.append((x, y))
    return coords

# ---------- 背景に星を敷き詰める ----------
def fill_background_with_stars(dwg, qr_size, offset, box_size, color, group):
    expanded_size = int(qr_size * 1.5)
    spacing = int(box_size * 0.9)

    for y in range(0, expanded_size, spacing):
        for x in range(0, expanded_size, spacing):
            if offset <= x < offset + qr_size - spacing and offset <= y < offset + qr_size - spacing:
                continue

            r_outer = box_size * 0.33
            r_inner = r_outer * 0.5
            star = create_star_points(x + box_size / 2, y + box_size / 2, r_outer, r_inner)
            group.add(dwg.polygon(points=star, fill=color))

# ---------- QRコード + 星背景 + 円形マスク生成 ----------
def generate_star_qr_svg(url, box_size=10, border=0, color="#007a78"):
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=border
    )
    qr.add_data(url)
    qr.make(fit=True)

    matrix = qr.get_matrix()
    size = len(matrix)
    qr_size = (size + 2 * border) * box_size
    expanded_size = int(qr_size * 1.5)
    offset = (expanded_size - qr_size) // 2

    # 円形マスクの中心と半径
    circle_radius = qr_size / 1.4
    circle_cx = offset + qr_size / 2
    circle_cy = offset + qr_size / 2

    dwg = svgwrite.Drawing(size=(expanded_size, expanded_size))

    # 背景白
    dwg.add(dwg.rect(insert=(0, 0), size=(expanded_size, expanded_size), fill='white'))

    # 星 + QRコード を入れるグループ
    content_group = dwg.g()

    # 背景星
    fill_background_with_stars(dwg, qr_size, offset, box_size, color, content_group)

    # QRコード本体
    finder_positions = [(0, 0), (size - 7, 0), (0, size - 7)]
    finder_range = set()
    for fx, fy in finder_positions:
        for dy in range(7):
            for dx in range(7):
                finder_range.add((fx + dx, fy + dy))

    for y, row in enumerate(matrix):
        for x, val in enumerate(row):
            if not val:
                continue

            px = (x + border) * box_size + offset
            py = (y + border) * box_size + offset
            cx = px + box_size / 2
            cy = py + box_size / 2

            if (x, y) in finder_range:
                content_group.add(dwg.rect(
                    insert=(px, py),
                    size=(box_size, box_size),
                    fill=color
                ))
            else:
                r_outer = box_size * 0.65
                r_inner = r_outer * 0.55
                star = create_star_points(cx, cy, r_outer, r_inner)
                content_group.add(dwg.polygon(points=star, fill=color))

    # クリップパス（円形に切り抜く）
    clip_id = "circle-clip"
    clip_path = dwg.defs.add(dwg.clipPath(id=clip_id))
    clip_path.add(dwg.circle(center=(circle_cx, circle_cy), r=circle_radius))

    # グループに適用
    content_group['clip-path'] = f"url(#{clip_id})"
    dwg.add(content_group)

    return dwg

# ---------- SVG → PNG ----------
def svg_to_png_bytes(svg: svgwrite.Drawing):
    svg_str = svg.tostring()
    return cairosvg.svg2png(bytestring=svg_str.encode("utf-8"))

# ---------- エンドポイント ----------
@app.post("/generate")
async def generate_qr(req: QRRequest):
    if req.type != "star":
        raise HTTPException(status_code=400, detail="Only 'star' type is supported.")

    cloudinary.config(
        cloud_name="dpxafahfu",
        api_key="114534797426773",
        api_secret="jnJsWE0MQm4Af0EXmsVHeh0OmUQ"
    )

    svg = generate_star_qr_svg(req.url)
    png_bytes = svg_to_png_bytes(svg)

    upload_result = cloudinary.uploader.upload(
        io.BytesIO(png_bytes),
        folder="qrcodes",
        overwrite=True,
        resource_type="image"
    )

    return {"url": upload_result["secure_url"]}
