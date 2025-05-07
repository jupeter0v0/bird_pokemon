import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import numpy as np
import cv2
import json
import qrcode
from datetime import datetime
import tempfile
import re
import os
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
class FontRenderer:
    def __init__(self, zh_font_path, en_font_path, font_size):
        try:
            self.zh_font = ImageFont.truetype(zh_font_path, font_size)
            self.en_font = ImageFont.truetype(en_font_path, font_size-5)
        except:
            # 字体加载失败时使用默认字体
            default_font = ImageFont.load_default()
            self.zh_font = self.en_font = default_font

    def _is_chinese(self, char):
        """判断字符是否为中文（包含中文标点）"""
        cp = ord(char)
        return  (0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF) or  (0x20000 <= cp <= 0x2A6DF) or  (0x2A700 <= cp <= 0x2B73F) or (0x2B740 <= cp <= 0x2B81F) or  (0x2B820 <= cp <= 0x2CEAF) or  (0xF900 <= cp <= 0xFAFF) or (0x2F800 <= cp <= 0x2FA1F) or(0x0030 <= cp <= 0x0039) or (cp == 0x002E)

    def split_text(self, text):
        """分割混合文本"""
        parts = []
        current_part = []
        current_font = self.zh_font

        for char in text:
            is_chinese = self._is_chinese(char)
            target_font = self.zh_font if is_chinese else self.en_font

            if target_font != current_font and current_part:
                parts.append(("".join(current_part), current_font))
                current_part = []

            current_font = target_font
            current_part.append(char)

        if current_part:
            parts.append(("".join(current_part), current_font))

        return parts


def draw_watermark(
        img: Image.Image,
        order: str,
        family: str,
        species: str,
        date: datetime,
        location: str,
        zh_font_path: str,
        en_font_path: str,
        font_size: int,
        spacing: int,
        color: str
) -> Image.Image:
    """
    增强版水印绘制函数，支持中英文字体自动切换

    参数：
    - zh_font_path: 中文字体路径
    - en_font_path: 英文字体路径
    - 其他参数同原函数
    """
    draw = ImageDraw.Draw(img)
    renderer = FontRenderer(zh_font_path, en_font_path, font_size)

    def draw_centered_mixed_text(text, y_offset, vertical_align='center'):
        # 分割文本为多个片段
        parts = renderer.split_text(text)

        # 计算每个片段的尺寸
        sizes = [draw.textbbox((0, 0), p[0], font=p[1]) for p in parts]
        heights = [s[3] - s[1] for s in sizes]
        max_height = max(heights)

        # 计算总宽度
        total_width = sum(s[2] - s[0] for s in sizes)

        # 起始位置（水平居中）
        start_x = (img.width - total_width) // 2
        base_y = img.height - y_offset - max_height  # 基线参考点为底部对齐的 y

        # 根据垂直对齐方式调整 y 偏移
        def get_y_offset(box_height):
            if vertical_align == 'top':
                return base_y
            elif vertical_align == 'center':
                return base_y + (max_height - box_height) // 2
            elif vertical_align == 'bottom':
                return base_y + (max_height - box_height)
            else:
                raise ValueError("vertical_align must be 'top', 'center', or 'bottom'")

        # 绘制所有片段
        x = start_x
        bboxes = []
        for (text_part, font), box in zip(parts, sizes):
            box_height = box[3] - box[1]
            y = get_y_offset(box_height)
            bbox = draw.textbbox((x, y), text_part, font=font)
            draw.text((x, y), text_part, font=font, fill=color)
            x = bbox[2]
            bboxes.append(bbox)

        # 返回合并后的边界框
        return (
            min(b[0] for b in bboxes),
            min(b[1] for b in bboxes),
            max(b[2] for b in bboxes),
            max(b[3] for b in bboxes)
        )
    # 绘制三行水印
    line1 = f"{order} ———— {family}"
    line2 = species
    line3 = f"{location}       {date.strftime('%Y.%m.%d')}"

    draw_centered_mixed_text(line1, font_size * 4)
    draw_centered_mixed_text(line2, font_size * 8 // 3)
    draw_centered_mixed_text(line3, font_size * 4 // 3)

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
    uploaded_file = st.file_uploader("step1.上传图片文件", type=["jpg", "jpeg", "png"])

    # 加载物种数据
    with open("物种列表更新.json", "r", encoding="utf-8") as f:
        species_data = json.load(f)

    # 查询与选择
    col1, col2 = st.columns(2)
    query = col1.text_input("step2.🔍 输入物种关键词*",placeholder='必填')
    matches = [s for s in species_data if query in s["种"]] if query else []
    species_name = col2.selectbox("step3.选择匹配物种", [s["种"] for s in matches]) if matches else None
    selected_species = next((s for s in species_data if s["种"] == species_name), None)

    col1, col2, col3 = st.columns(3)
    location = col2.text_input("📍 拍摄地点",placeholder='选填')
    shoot_date = col3.date_input("📅 拍摄日期", value=datetime.today())
    author=col1.text_input("署名",placeholder='选填')
    if len(author) >0:
        author='@'+author+'       '


    # 设置参数
    with st.expander("🎨 文字设置"):
        font_size = st.slider("字体大小", 1, 50, 12)
        fontdir='./Fonts'
        col1,col2=st.columns(2)
        cn_font_select = col1.selectbox("中文字体路径", os.listdir(fontdir))
        en_font_select = col2.selectbox("英文字体路径", os.listdir(fontdir))
        cn_font_select=os.path.join(fontdir,cn_font_select)
        en_font_select = os.path.join(fontdir, en_font_select)

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

    if uploaded_file and species_name is not None:

        img_raw = Image.open(uploaded_file)
        img=img_raw.convert('RGB')
        cornered_img = round_image_corners(img, img.width / 50 * corner_radius / 5)
        blurred_bg = adjust_exposure(img_raw, 0.4)
        del img_raw
        final_img = apply_blurred_background(blurred_bg, scale_factor, 1.0, alpha, blur)

        # 阴影处理
        shadow_img = create_shadow(cornered_img, corner_radius, shadow_opacity)


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
            # 在中文和非中文之间加空格
            # 两边分别处理“中文紧挨非中文” 和 “非中文紧挨中文”的情况
            text_spaced = re.sub(
                r'([\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\U00020000-\U0002CEAF])([^\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\U00020000-\U0002CEAF])',
                r'\1 \2',  selected_species.get("种", ""))
            text_spaced = re.sub(
                r'([^\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\U00020000-\U0002CEAF])([\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\U00020000-\U0002CEAF])',
                r'\1 \2', text_spaced)
            # 替换多余空格为单个空格，去除首尾空格
            text_cleaned = re.sub(r'\s+', ' ', text_spaced).strip()
            
            final_img = draw_watermark(
                final_img,
                selected_species.get("目", ""),
                selected_species.get("科", ""),
                text_cleaned,
                shoot_date,
                author+location,
                cn_font_select,
                en_font_select,
                int(final_img.width / 45.2 * font_size / 10),
                spacing,
                text_color,
            )
            # 二维码
            col1,col2=st.columns([1,3])
            dongniao_mark = col1.checkbox("是否添加懂鸟二维码", value=True)
            if dongniao_mark:
                try:
                    qr_size = col2.slider('二维码尺寸',min_value=0, max_value=int(min(final_img.width * 0.30, final_img.height * 0.30)), value=int(min(final_img.width * 0.15, final_img.height * 0.15)))
                    qr_img = generate_qr_code(selected_species.get("href"),size=qr_size)
                    qr_pos = (final_img.width - qr_img.width - 10, final_img.height - qr_img.height - 10)
                    final_img.paste(qr_img, qr_pos, qr_img)
                except Exception as e:
                    st.warning("二维码生成失败")
        pattern = re.compile(
            r'[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\U00020000-\U0002CEAF]+',
            flags=re.UNICODE
        )

        matches = pattern.findall(selected_species.get("种", ""))
        chinese_text = ''.join(matches)

        status=st.warning('图片生成中，请稍等........')
        st.image(final_img, caption="✅ 完成图像预览", use_container_width=True)
        status.success('图片生成成功！')
        # 保存到临时文件并提供下载按钮
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
            final_img.save(tmp_file, format="PNG")
            tmp_file.seek(0)
            btn = st.download_button(
                label="点击下载图片",
                data=tmp_file.read(),
                file_name=f"{chinese_text}-{location}-{shoot_date}.png",
                mime="image/png"
            )
if __name__ == "__main__":
    main()
