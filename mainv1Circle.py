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

# ---------- 星型QRコードをSVGで生成（円形マスク） ----------
def generate_star_qr_svg(url, box_size=10, border=4, color="#007a78"):
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=border
    )
    qr.add_data(url)
    qr.make(fit=True)

    matrix = qr.get_matrix()
    size = len(matrix)
    total_size = (size + 2 * border) * box_size
    center = total_size / 2

    dwg = svgwrite.Drawing(size=(total_size, total_size))
    dwg.add(dwg.rect(insert=(0, 0), size=(total_size, total_size), fill='white'))

    # 円形マスク作成
    clip_path = dwg.defs.add(dwg.clipPath(id="clipCircle"))
    clip_path.add(dwg.circle(center=(center, center), r=total_size / 2))

    qr_group = dwg.g(clip_path="url(#clipCircle)", fill=color)

    for y, row in enumerate(matrix):
        for x, val in enumerate(row):
            if val:
                cx = (x + border + 0.5) * box_size
                cy = (y + border + 0.5) * box_size

                # 星型をセルサイズに最大化してしっかり接触させる
                r_outer = box_size * 0.5         # 最大サイズ
                r_inner = r_outer * 0.6          # 詰まった星型（穴が小さい）
                points = create_star_points(cx, cy, r_outer, r_inner)
                qr_group.add(dwg.polygon(points=points))

    dwg.add(qr_group)
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

    # Cloudinary設定（毎回）
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
