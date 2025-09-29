from PIL import Image
import os
import shutil
import sys
from PIL import ImageFile

# -------------------------- 可自定义参数 --------------------------
TARGET_WIDTH = 600          # 目标宽度：宽度＞此值的图片会缩放
JPG_QUALITY = 60            # 压缩质量（70=兼顾体积和质量）
KEEP_EXIF = False           # 是否保留元数据（False=减小体积）
# --------------------------------------------------------------------------------

# 解决大尺寸/损坏图片读取问题
ImageFile.LOAD_TRUNCATED_IMAGES = True

def final_compress(folder):
    processed_count = 0
    skipped_count = 0
    supported_formats = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff', '.heic', '.svg')

    print(f"📁 已定位处理文件夹：{folder}\n")
    print("🔍 开始扫描图片文件...\n")

    for filename in os.listdir(folder):
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in supported_formats:
            print(f"✓ 跳过：{filename}（格式{file_ext}不支持，仅处理图片）")
            skipped_count += 1
            continue

        file_path = os.path.join(folder, filename)
        if os.path.isdir(file_path):
            print(f"✓ 跳过：{filename}（是文件夹，仅处理文件）")
            skipped_count += 1
            continue

        try:
            with Image.open(file_path) as img:
                # 处理SVG矢量图
                if file_ext == '.svg':
                    original_width = 600
                    original_height = int(img.height * (600 / img.width)) if img.width != 0 else 400
                else:
                    original_width, original_height = img.size

                original_size = os.path.getsize(file_path)
                final_width, final_height = original_width, original_height
                need_resize = False
                need_compress = False

                # 核心处理逻辑：宽度≥600px必处理
                if original_width > TARGET_WIDTH:
                    need_resize = True
                    need_compress = True
                    scale_ratio = TARGET_WIDTH / original_width
                    final_height = int(original_height * scale_ratio)
                    final_width = TARGET_WIDTH
                elif original_width == TARGET_WIDTH:
                    need_resize = False
                    need_compress = True
                else:
                    print(f"✓ 跳过：{filename}（宽度{original_width}px＜600px，无需处理）")
                    skipped_count += 1
                    continue

                # 执行缩放（兼容旧版Pillow的LANCZOS位置）
                lanczos = Image.Resampling.LANCZOS if hasattr(Image.Resampling, 'LANCZOS') else Image.LANCZOS
                if need_resize:
                    resized_img = img.resize((final_width, final_height), lanczos)
                    print(f"🔄 缩放完成：{filename} → 尺寸：{original_width}x{original_height} → {final_width}x{final_height}")
                else:
                    resized_img = img.convert('RGB') if img.mode != 'RGB' else img
                    print(f"🔄 无需缩放：{filename}（宽度=600px，直接压缩）")

                # 处理透明通道（转为白色背景，适配JPG）
                if resized_img.mode in ('RGBA', 'LA') or (resized_img.mode == 'P' and 'transparency' in resized_img.info):
                    background = Image.new('RGB', (final_width, final_height), (255, 255, 255))
                    alpha_mask = resized_img.split()[-1] if resized_img.mode == 'RGBA' else None
                    background.paste(resized_img, mask=alpha_mask)
                    resized_img = background
                    print(f"🔄 透明处理：{filename} → 已添加白色背景")

                # -------------------------- 终极修复：彻底移除subsampling参数 --------------------------
                # 直接转为YCbCr（旧版/新版Pillow都支持，默认4:2:0子采样，压缩率不变）
                ycbcr_img = resized_img.convert('YCbCr')
                # --------------------------------------------------------------------------------

                # 生成输出路径（统一JPG）
                base_name = os.path.splitext(filename)[0]
                new_file_path = os.path.join(folder, f"{base_name}.jpg")
                temp_path = os.path.join(folder, f".temp_{base_name}.jpg")

                # 深度压缩保存
                save_params = {
                    'format': 'JPEG',
                    'quality': JPG_QUALITY,
                    'optimize': True,          # 优化编码，减小体积
                    'qtables': 'web_high',     # 网页专用压缩表，提升压缩率
                    'exif': img.info.get('exif', b'') if KEEP_EXIF else b''
                }
                ycbcr_img.save(temp_path, **save_params)

                # 替换原文件（安全处理）
                if os.path.exists(file_path):
                    os.remove(file_path)
                if os.path.exists(new_file_path):
                    os.remove(new_file_path)
                shutil.move(temp_path, new_file_path)

                # 计算压缩效果
                new_size = os.path.getsize(new_file_path)
                compress_ratio = (1 - new_size / original_size) * 100
                processed_count += 1

                # 输出详细结果
                print(f"✅ 处理完成：{filename}")
                print(f"    体积变化：{original_size//1024}KB → {new_size//1024}KB（压缩{compress_ratio:.1f}%）")
                print(f"    输出文件：{new_file_path}\n")

        except Exception as e:
            # 捕获并显示错误信息
            print(f"❌ 处理失败：{filename}")
            print(f"    错误原因：{str(e)}\n")
            skipped_count += 1
            # 清理临时文件
            temp_path = os.path.join(folder, f".temp_{os.path.splitext(filename)[0]}.jpg")
            if os.path.exists(temp_path):
                os.remove(temp_path)

    # 处理结束：统计报告
    print("=" * 80)
    print("🎉 图片压缩任务全部完成！")
    print(f"📊 处理统计：")
    print(f"    总文件数：{processed_count + skipped_count} 个")
    print(f"    成功处理：{processed_count} 张图片（缩放+压缩 / 仅压缩）")
    print(f"    跳过文件：{skipped_count} 个（格式不支持/宽度＜600px/处理失败）")
    print(f"💡 压缩参数：目标宽度{TARGET_WIDTH}px | 压缩质量{JPG_QUALITY}")
    print("=" * 80)

    # 暂停查看输出
    #print("\n⚠️  按任意键退出窗口...")
    #if sys.platform.startswith('win'):
    #    os.system('pause')
    #else:
    #    os.system('read -n 1 -s -p "Press any key to exit..."')

# 主程序：自动定位当前文件夹
if __name__ == "__main__":
    current_folder = os.path.dirname(os.path.abspath(__file__))
    
    # 启动信息
    print("=" * 80)
    print("📸 图片压缩工具（终极版：无subsampling依赖+暂停查看）")
    print("=" * 80)
    print("🔧 核心规则：")
    print(f"    1. 宽度＞{TARGET_WIDTH}px → 按比例缩至{TARGET_WIDTH}px宽 + 深度压缩（无裁剪）")
    print(f"    2. 宽度={TARGET_WIDTH}px → 不缩放，仅深度压缩（减小体积）")
    print(f"    3. 宽度＜{TARGET_WIDTH}px → 完全跳过，不处理")
    print("🔧 支持格式：png/jpg/webp/bmp/gif/tiff/heic/svg")
    print("=" * 80)

    # 执行压缩
    final_compress(current_folder)