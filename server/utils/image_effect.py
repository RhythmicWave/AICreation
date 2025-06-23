# image_effects.py
import numpy as np
from PIL import Image, ImageEnhance, ImageChops
import random
import math
from typing import Dict, Tuple

class ImageEffects:
    @staticmethod
    def fade_effect(image: Image.Image, time_val: float, duration: float, params: Dict) -> Image.Image:
        """淡入淡出效果
        使用亮度调整代替透明度，确保与MoviePy兼容
        """
        if params.get('fade_duration', 0) <= 0:
            return image
            
        fade_duration = params['fade_duration']
        brightness = 1.0
        
        # 淡入阶段
        if time_val < fade_duration:
            brightness = time_val / fade_duration
        # 淡出阶段
        elif duration - time_val < fade_duration:
            brightness = (duration - time_val) / fade_duration
            
        # 使用亮度调整实现淡入淡出，而不是透明度
        if brightness < 1.0:
            enhancer = ImageEnhance.Brightness(image)
            image = enhancer.enhance(brightness)
            
        return image

    @staticmethod
    def pan_effect(image: Image.Image, time_val: float, duration: float, params: Dict) -> Image.Image:
        """平滑的平移效果
        支持横向和纵向移动，可交替使用
        """
        output_w, output_h = params['output_size']
        pan_range = params.get('pan_range', (0.3, 0))  # (水平范围, 垂直范围)
        
        # 获取当前片段的移动方向
        segment_index = params.get('segment_index', 0)
        h_range, v_range = pan_range
        
        # 确定当前片段移动方向
        use_horizontal = True
        
        # 根据横纵向参数决定移动方式
        if h_range > 0 and v_range > 0:
            # 两个参数都不为0，则交替使用
            if segment_index % 2 == 0:
                use_horizontal = True

            else:
                use_horizontal = False

        elif h_range > 0:
            # 只有水平参数不为0，则全部使用水平移动
            use_horizontal = True

        elif v_range > 0:
            # 只有垂直参数不为0，则全部使用垂直移动
            use_horizontal = False
        else:
            # 如果两个都为0，默认使用水平移动
            use_horizontal = True

        
        # 计算原始图像的宽高比
        aspect_ratio = image.width / image.height
        
        # 根据移动方向缩放图片
        if use_horizontal:
            # 横向移动：确保高度完全匹配输出高度
            new_height = output_h
            # 保持宽高比，并确保宽度有足够的移动空间
            new_width = max(int(new_height * aspect_ratio), int(output_w * (1 + h_range)))
        else:
            # 纵向移动：确保宽度完全匹配输出宽度
            new_width = output_w
            # 保持宽高比，并确保高度有足够的移动空间
            new_height = max(int(new_width / aspect_ratio), int(output_h * (1 + v_range)))
            
        # 应用缩放
        scaled_img = image.resize((new_width, new_height), Image.BICUBIC)
        
        # 使用缓动函数计算移动进度，使动画更平滑
        progress = ImageEffects._ease_in_out_progress(time_val / duration)
        
        # 计算裁剪位置
        x_offset = 0
        y_offset = 0
        
        if use_horizontal:
            # 横向移动：从左到右
            max_x_offset = scaled_img.width - output_w
            x_offset = int(max_x_offset * progress)
            # 高度应该精确匹配输出高度，无需额外裁剪
        else:
            # 纵向移动：从上到下
            max_y_offset = scaled_img.height - output_h
            y_offset = int(max_y_offset * progress)
            # 宽度应该精确匹配输出宽度，无需额外裁剪
        
        # 安全裁剪
        return scaled_img.crop((
            x_offset, 
            y_offset,
            x_offset + output_w,
            y_offset + output_h
        ))

    @staticmethod
    def _ease_in_out_progress(progress: float) -> float:
        """平滑的缓动函数，使移动更自然"""
        # 使用正弦缓动函数
        return 0.5 * (1 - math.cos(math.pi * progress))


    @classmethod
    def apply_effects(cls, image: Image.Image, time_val: float, duration: float, params: Dict) -> Image.Image:
        """应用所有特效"""
        # 效果执行顺序
        effect_chain = []
        
        # 先应用平移效果，防止淡入淡出被重置
        if params.get('use_pan', True):
            effect_chain.append(cls.pan_effect)
            
        # 淡入淡出应该是最后一步应用
        effect_chain.append(cls.fade_effect)
        
        processed_image = image.copy()
        for effect in effect_chain:
            processed_image = effect(processed_image, time_val, duration, params)
            # 这里不再对每个效果进行裁剪，因为每个效果函数内部已经处理好了尺寸
        
        return processed_image