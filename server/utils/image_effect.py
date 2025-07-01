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
        """
        平滑的平移和缩放效果，可防止图像拉伸。
        通过正确计算缩放比例来确保图像在适应平移范围的同时保持其原始宽高比。
        """
        output_w, output_h = params['output_size']
        pan_range = params.get('pan_range', (0.3, 0))
        segment_index = params.get('segment_index', 0)
        h_range, v_range = pan_range

        # 确定移动方向
        use_horizontal = True
        if h_range > 0 and v_range > 0:
            use_horizontal = segment_index % 2 == 0
        elif v_range > 0:
            use_horizontal = False
        
        # 如果没有平移，直接将图片居中裁剪
        if h_range <= 0 and v_range <= 0:
            img_aspect = image.width / image.height
            out_aspect = output_w / output_h
            
            if img_aspect > out_aspect:
                new_height = output_h
                new_width = int(new_height * img_aspect)
                scaled_img = image.resize((new_width, new_height), Image.LANCZOS)
                left = (new_width - output_w) // 2
                return scaled_img.crop((left, 0, left + output_w, output_h))
            else:
                new_width = output_w
                new_height = int(new_width / img_aspect)
                scaled_img = image.resize((new_width, new_height), Image.LANCZOS)
                top = (new_height - output_h) // 2
                return scaled_img.crop((0, top, output_w, top + output_h))

        # 计算缩放比例，保持宽高比
        img_w, img_h = image.width, image.height
        
        if use_horizontal:
            # 为横向平移计算缩放比例
            required_width = output_w * (1 + h_range)
            ratio_w = required_width / img_w
            ratio_h = output_h / img_h
            scale_ratio = max(ratio_w, ratio_h)
        else:  # Vertical pan
            required_height = output_h * (1 + v_range)
            ratio_h = required_height / img_h
            ratio_w = output_w / img_w
            scale_ratio = max(ratio_w, ratio_h)
            
        new_width = int(img_w * scale_ratio)
        new_height = int(img_h * scale_ratio)
        
        scaled_img = image.resize((new_width, new_height), Image.LANCZOS)
        
        # 使用缓动函数计算移动进度
        progress = ImageEffects._ease_in_out_progress(time_val / duration)
        
        # 计算裁剪框位置
        if use_horizontal:
            max_x_offset = scaled_img.width - output_w
            x_offset = int(max_x_offset * progress)
            y_offset = (scaled_img.height - output_h) // 2
        else:  # Vertical pan
            max_y_offset = scaled_img.height - output_h
            y_offset = int(max_y_offset * progress)
            x_offset = (scaled_img.width - output_w) // 2
        
        return scaled_img.crop((
            x_offset, y_offset,
            x_offset + output_w, y_offset + output_h
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