import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import numpy as np
from io import BytesIO

st.set_page_config(layout='wide')


# 图片倒角处理函数
def round_corners(image, radius):
    """ 给图片添加倒角效果 """
    width, height = image.size
    rounded = Image.new("RGBA", (width, height), (255, 255, 255, 0))

    # 使用一个掩膜进行倒角处理
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, width, height], radius, fill=255)
    rounded.paste(image, (0, 0), mask=mask)
    return rounded


# 高斯模糊背景生成
def create_blurred_background(image, scale_factor, contrast_factor, alpha_factor, GaussianBlur_factor):
    """ 生成高斯模糊背景并放大背景图像，同时调整对比度和透明度 """
    width, height = image.size
    enlarged_width = int(width * scale_factor)
    enlarged_height = int(height * scale_factor)

    # 放大图像
    enlarged_image = image.resize((enlarged_width, enlarged_height))

    # 高斯模糊
    blurred_image = enlarged_image.filter(ImageFilter.GaussianBlur(GaussianBlur_factor))

    # 调整对比度
    enhancer = ImageEnhance.Contrast(blurred_image)
    blurred_image = enhancer.enhance(contrast_factor)

    # 调整透明度
    blurred_image = adjust_alpha(blurred_image, alpha_factor)

    # 裁剪到原始尺寸
    blurred_image = blurred_image.crop((0, 0, enlarged_width, enlarged_height))
    return blurred_image


# 调整图像透明度
def adjust_alpha(image, alpha_factor):
    """ 调整图像的透明度 """
    if image.mode != 'RGBA':
        image = image.convert('RGBA')

    # 获取图像的 alpha 通道
    data = np.array(image)

    # 修改 alpha 通道的透明度
    data[..., 3] = data[..., 3] * alpha_factor  # alpha 通道的调整

    # 保证透明度不超过255
    data[..., 3] = np.clip(data[..., 3], 0, 255)

    return Image.fromarray(data)


# 创建阴影效果
def add_shadow(image,corner_radius):
    """ 添加一个偏移的黑色阴影图层 """
    width, height = image.size
    # 创建一个与前景图像一样大的透明图层
    shadow = Image.new("RGBA", (int(width*1.1),int( height*1.1)), (0, 0, 0,0))
    shadow_width,shadow_height=shadow.size
    # 创建一个黑色的矩形，并设置透明度
    shadow_draw = ImageDraw.Draw(shadow)

    shadow_draw.rounded_rectangle([shadow_width/2-width/2, shadow_height/2-height/2, shadow_width/2+width/2,shadow_height/2+height/2],radius=image.width/50* corner_radius/5, fill=(0, 0, 0, 255))
    #st.write([shadow_width/2-width/2, shadow_height/2-height/2, shadow_width/2+width/2,shadow_height/2+height/2])

    return shadow

def add_watermark(image, mu,ke,zhong,time,loaction, font_path, font_size, spacing, text_color):
    """ 在图像底部添加水印文本 """
    width, height = image.size
    draw = ImageDraw.Draw(image)
    #st.write(font_size)
    # 使用给定字体和大小
    font = ImageFont.truetype(font_path, font_size)
    def drawtext(text,position_y):
        # 获取文本的边界框并计算宽度和高度
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]  # bbox[2] 是右下角，bbox[0] 是左上角
        text_height = bbox[3] - bbox[1]  # bbox[3] 是右下角，bbox[1] 是左上角

        # 计算文本的显示位置（居中）
        position = ((width - text_width) // 2, height - text_height - position_y)

        # 绘制文本，使用用户选择的颜色
        draw.text(position, text, font=font, fill=text_color)
    drawtext(mu + '————' + ke, font_size * 4)
    drawtext(zhong,font_size* 4/3*2)

    drawtext(loaction+'       '+time.strftime('%Y.%m.%d'), font_size*4/3*1)

    return image


def descend_exp(uploaded_file, exposure_factor):
    import cv2

    # 转换为 OpenCV 格式
    open_cv_image = np.array(uploaded_file)
    open_cv_image = open_cv_image[:, :, ::-1].copy()  # RGB 转 BGR

    # 调整曝光度（通过改变 alpha 值）
    lowered_exposure_image = cv2.convertScaleAbs(open_cv_image, alpha=exposure_factor, beta=0)

    # 将图像转换回 PIL 格式并显示
    lowered_exposure_pil = Image.fromarray(cv2.cvtColor(lowered_exposure_image, cv2.COLOR_BGR2RGB))
    return lowered_exposure_pil
# Streamlit界面
def main():
    import json
    import qrcode

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )

    st.title("图片倒角和水印处理")
    # 水印设置
    uploaded_file = st.file_uploader("上传图片", type=["png", "jpg", "jpeg"])
    col1, col2, col3,col4 = st.columns([1,1, 1, 1])
    with open('物种列表更新.json', 'r',encoding='utf-8') as f:
        data = json.load(f)
    # 用户输入关键字进行模糊搜索（针对“种”字段）
    query = col1.text_input("请输入物种名关键词（如：非洲）")

    # 过滤结果（模糊匹配“种”字段）
    filtered_data = [item for item in data if query in item["种"]] if query else []

    # 构造选择列表
    options = [item["种"] for item in filtered_data]

    # 选择结果
    selected_name = col2.selectbox("请选择物种（模糊匹配结果）", options) if options else None

    # 查找对应的 dict
    if selected_name:
        for idx, item in enumerate(data):
            if item["种"] == selected_name:
                result = {"index": idx, **item}
                break
        #st.subheader("匹配到的完整数据：")
        #st.json(result)


    qr.add_data(f'{result.get("href")}')  # 可以换成任意字符串或链接
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    #st.write(qr_img)

    location = col3.text_input("拍摄地点")
    time = col4.date_input('拍摄时间')
    bird_name = result.get("种")
    with st.expander('文字设置'):
        font_size = st.slider("选择水印字体大小", 1, 50, 12)
        font_path = st.text_input("选择字体", "NotoSansSC-VariableFont_wght.ttf")
        spacing = st.slider("设置水印字间距", 0, 10, 2)
        text_color = st.color_picker("选择水印文字颜色", "#FFFFFF")

    with st.expander('细节调整'):

        # 选择倒角半径
        corner_radius = st.slider("选择倒角系数", min_value=0, max_value=20, value=8)
        # 选择背景图像放大比例
        scale_factor = st.slider("选择背景图像放大比例", min_value=1.0, max_value=2.0, value=1.25, step=0.05)
        # 选择透明度调整
        alpha_factor = st.slider("选择背景透明度", min_value=0.0, max_value=1.0, value=1.0, step=0.05)
        GaussianBlur_factor = st.slider("选择高斯模糊程度", min_value=1, max_value=25, value=50, step=1)
        # 阴影设置：阴影图层与前景图像大小相同
        shadow_offset_x = st.slider("阴影偏移X", min_value=-10.0, max_value=10.0, value=1.0, step=0.5)
        shadow_offset_y = st.slider("阴影偏移Y", min_value=-10.0, max_value=10.0, value=2.0, step=0.5)
        shadow_opacity = st.slider("阴影透明度", min_value=0.0, max_value=2.0, value=0.8)



    st.divider()
    if uploaded_file:
        image_raw = Image.open(uploaded_file)
        image=image_raw.convert("RGBA")

        #st.write(image.width)



        # 生成倒角图片
        image_with_corners1 = round_corners(image,image.width/50* corner_radius/5)



        # 选择对比度调整
        contrast_factor =1.0 # 固定为1，因为对比度未调整


        # 生成模糊背景并进行对比度和透明度调整
        blurred_background = descend_exp(image_raw, 0.4)
        blurred_background = create_blurred_background(blurred_background, scale_factor, contrast_factor, alpha_factor, GaussianBlur_factor)
        # 读取图片



        background_width, background_height = blurred_background.size


        # 创建阴影

        shadow_image = add_shadow(image_with_corners1,corner_radius)

        shadow_image = shadow_image.filter(ImageFilter.GaussianBlur(15))
        shadow_image =adjust_alpha(shadow_image,shadow_opacity)

        # 最终合成图像
        final_image = blurred_background.copy()
        # 将阴影与背景合并


        # 计算放置倒角图像的位置，确保它居中
        bg_width, bg_height = final_image.size
        fg_width, fg_height = image_with_corners1.size
        position = ((bg_width - fg_width) // 2, int((bg_height - fg_height) // 2*0.5))

        position1 = (int((bg_width - fg_width*1.1) // 2+fg_width*shadow_offset_x*0.01), int(((bg_height - fg_height*1.1) // 2-bg_height*shadow_offset_y*0.01)*0.5))
        final_image.paste(shadow_image,position1, shadow_image)
        # 将前景图像粘贴到合成图像上
        final_image.paste(image_with_corners1, position, image_with_corners1)
        #st.write(final_image.width)

        if bird_name:
            final_image = add_watermark(final_image,result.get('目'), result.get('科'),result.get('种'),time,location, font_path,final_image.width/45.2 *font_size/10, spacing, text_color)

        # 3. 缩放二维码（如有需要）
        qr_size=int(min(blurred_background.width*0.15,blurred_background.height*0.15))
        #st.write(qr_size)
        qr_img = qr_img.resize((qr_size, qr_size) ) # 调整二维码尺寸

        # 4. 粘贴二维码到背景图上（如右下角）
        position = (final_image.width - qr_img.width - 10, final_image.height - qr_img.height - 10)
        final_image.paste(qr_img, position, qr_img)
        # 显示处理后的图片
        st.image(final_image, caption="处理后的图片", use_container_width=True)


if __name__ == "__main__":
   main()

