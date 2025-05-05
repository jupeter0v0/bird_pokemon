import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import numpy as np
from io import BytesIO
import cv2
import json
import qrcode
from datetime import datetime

st.set_page_config(layout='wide')


# ---------------- 图像处理工具 ---------------- #
def round_image_corners(img: Image.Image, radius: float) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, *img.size], radius, fill=255)
    rounded = Image.new("RGBA", img.size, (255, 255, 255, 0))
    rounded.paste(img, (0, 0), mask=mask)
    return rounded


def apply_blurred_background(img: Image.Image, scale: float, contrast: float, alpha: float, blur_radius: int) -> Image.Image:
    enlarged = img.resize((int(img.width * scale), int(img.height * scale)))
    blurred = enlarged.filter(ImageFilter.GaussianBlur(blur_radius))
    blurred = ImageEnhance.Contrast(blurred).enhance(contrast)
    return adjust_alpha(blurred, alpha)


def adjust_alpha(img: Image.Image, alpha: float) -> Image.Image:
    img = img.convert("RGBA")
    data = np.array(img)
    data[..., 3] = np.clip(data[..., 3] * alpha, 0, 255)
    return Image.fromarray(data)


def create_shadow(img: Image.Image, radius: float, opacity: float) -> Image.Image:
    shadow = Image.new("RGBA", (int(img.width * 1.1), int(img.height * 1.1)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    draw.rounded_rectangle(
        [shadow.width/2 - img.width/2, shadow.height/2 - img.height/2,
         shadow.width/2 + img.width/2, shadow.height/2 + img.height/2],
        radius=img.width / 50 * radius / 5,
        fill=(0, 0, 0, 255)
    )
    return adjust_alpha(shadow.filter(ImageFilter.GaussianBlur(15)), opacity)


def adjust_exposure(img: Image.Image, factor: float) -> Image.Image:
    cv_img = np.array(img)[:, :, ::-1].copy()
    cv_adjusted = cv2.convertScaleAbs(cv_img, alpha=factor, beta=0)
    return Image.fromarray(cv2.cvtColor(cv_adjusted, cv2.COLOR_BGR2RGB))


# ---------------- 水印与二维码 ---------------- #
def draw_watermark(img: Image.Image, order: str, family: str, species: str, date, location: str,
                   font_path: str, font_size: int, spacing: int, color: str) -> Image.Image:
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, font_size)

    def centered_text(text, y_offset):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (img.width - text_width) // 2
        y = img.height - y_offset - text_height
        draw.text((x, y), text, font=font, fill=color)

    centered_text(f"{order} ———— {family}", font_size * 4)
    centered_text(species, font_size * 8 // 3)
    centered_text(f"{location}       {date.strftime('%Y.%m.%d')}", font_size * 4 // 3)
    return img


def generate_qr_code(data: str, size: int = 200) -> Image.Image:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    return img.resize((size, size))


# ---------------- 主界面 ---------------- #
def main():
    st.title("📷 鸟类便捷归档")

    # 文件上传
    uploaded_file = st.file_uploader("上传图片文件", type=["jpg", "jpeg", "png"])

    # 加载物种数据
    with open("物种列表更新.json", "r", encoding="utf-8") as f:
        species_data = json.load(f)

    # 查询与选择
    col1, col2, col3, col4 = st.columns(4)
    query = col1.text_input("🔍 输入物种关键词")
    location = col3.text_input("📍 拍摄地点")
    shoot_date = col4.date_input("📅 拍摄日期", value=datetime.today())

    matches = [s for s in species_data if query in s["种"]] if query else []
    species_name = col2.selectbox("选择匹配物种", [s["种"] for s in matches]) if matches else None
    selected_species = next((s for s in species_data if s["种"] == species_name), None)

    # 设置参数
    with st.expander("🎨 文字设置"):
        font_size = st.slider("字体大小", 1, 50, 12)
        font_path = st.text_input("字体路径", "NotoSansSC-VariableFont_wght.ttf")
        spacing = st.slider("字间距", 0, 10, 2)
        text_color = st.color_picker("文字颜色", "#FFFFFF")

    with st.expander("🛠️ 图像处理设置"):
        corner_radius = st.slider("倒角系数", 0, 20, 8)
        scale_factor = st.slider("背景放大", 1.0, 2.0, 1.25, 0.05)
        alpha = st.slider("背景透明度", 0.0, 1.0, 1.0, 0.05)
        blur = st.slider("模糊强度", 1, 25, 10)
        shadow_x = st.slider("阴影偏移X", -10.0, 10.0, 1.0)
        shadow_y = st.slider("阴影偏移Y", -10.0, 10.0, 2.0)
        shadow_opacity = st.slider("阴影透明度", 0.0, 2.0, 0.8)

    st.divider()

    if uploaded_file:
        img_raw = Image.open(uploaded_file)
        img=img_raw.convert('RGBA')
        cornered_img = round_image_corners(img, img.width / 50 * corner_radius / 5)
        blurred_bg = adjust_exposure(img_raw, 0.4)
        blurred_bg = apply_blurred_background(blurred_bg, scale_factor, 1.0, alpha, blur)

        # 阴影处理
        shadow_img = create_shadow(cornered_img, corner_radius, shadow_opacity)

        # 合成背景 + 阴影 + 正图
        final_img = blurred_bg.copy()
        bg_w, bg_h = final_img.size
        fg_w, fg_h = cornered_img.size

        pos_fg = ((bg_w - fg_w) // 2, int((bg_h - fg_h) // 2 * 0.5))
        pos_shadow = (
            int((bg_w - fg_w * 1.1) // 2 + fg_w * shadow_x * 0.01),
            int(((bg_h - fg_h * 1.1) // 2 - bg_h * shadow_y * 0.01) * 0.5)
        )

        final_img.paste(shadow_img, pos_shadow, shadow_img)
        final_img.paste(cornered_img, pos_fg, cornered_img)

        if selected_species:
            final_img = draw_watermark(
                final_img,
                selected_species.get("目", ""),
                selected_species.get("科", ""),
                selected_species.get("种", ""),
                shoot_date,
                location,
                font_path,
                int(final_img.width / 45.2 * font_size / 10),
                spacing,
                text_color,
            )
            # 二维码
            try:
                qr_img = generate_qr_code(selected_species.get("href"))
                qr_pos = (final_img.width - qr_img.width - 10, final_img.height - qr_img.height - 10)
                final_img.paste(qr_img, qr_pos, qr_img)
            except Exception as e:
                st.warning("二维码生成失败")

        st.image(final_img, caption="✅ 完成图像预览", use_container_width=True)


if __name__ == "__main__":
    main()
