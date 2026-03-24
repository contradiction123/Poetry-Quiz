"""
钓鱼游戏图像识别模块
识别鱼、鱼钩、特殊物品
"""
import cv2
import numpy as np
from PIL import Image
from typing import List, Dict, Tuple, Optional
import time


class FishingDetector:
    """钓鱼游戏图像识别类"""
    
    def __init__(self, config: dict = None):
        """
        初始化识别器
        参数:
            config: 配置字典
        """
        self.config = config or {}
        
        # 鱼识别配置
        fish_config = self.config.get('fish_detection', {})
        self.min_fish_area = fish_config.get('min_fish_area', 100)
        self.max_fish_area = fish_config.get('max_fish_area', 5000)
        color_ranges = fish_config.get('color_ranges', {})
        self.fish_hue_min = color_ranges.get('hue_min', 0)
        self.fish_hue_max = color_ranges.get('hue_max', 180)
        self.fish_sat_min = color_ranges.get('saturation_min', 50)
        self.fish_sat_max = color_ranges.get('saturation_max', 255)
        self.fish_val_min = color_ranges.get('value_min', 50)
        self.fish_val_max = color_ranges.get('value_max', 255)
        
        # 鱼钩识别配置
        hook_config = self.config.get('hook_detection', {})
        hook_color = hook_config.get('color_range', {})
        self.hook_brightness_min = hook_color.get('brightness_min', 200)
        self.hook_brightness_max = hook_color.get('brightness_max', 255)
        self.hook_min_size = hook_config.get('min_size', 10)
        
        # 特殊物品配置
        special_config = self.config.get('special_items', {})
        # 驱赶道具（蓝色漩涡）
        scare_color = special_config.get('scare_item_color', {})
        self.scare_hue_min = scare_color.get('hue_min', 100)
        self.scare_hue_max = scare_color.get('hue_max', 130)
        self.scare_sat_min = scare_color.get('saturation_min', 100)
        self.scare_sat_max = scare_color.get('saturation_max', 255)
        # 冻结道具（发光蓝色物体）
        freeze_color = special_config.get('freeze_item_color', {})
        self.freeze_hue_min = freeze_color.get('hue_min', 100)
        self.freeze_hue_max = freeze_color.get('hue_max', 130)
        self.freeze_brightness_min = freeze_color.get('brightness_min', 200)
        # 杂物
        debris_config = special_config.get('debris', {})
        seaweed_color = debris_config.get('seaweed_color', {})
        self.seaweed_hue_min = seaweed_color.get('hue_min', 40)
        self.seaweed_hue_max = seaweed_color.get('hue_max', 80)
        wood_color = debris_config.get('wood_color', {})
        self.wood_hue_min = wood_color.get('hue_min', 10)
        self.wood_hue_max = wood_color.get('hue_max', 30)
        
        # 水域区域配置
        water_region = self.config.get('water_region', {})
        self.water_x = water_region.get('x', 0.1)
        self.water_y = water_region.get('y', 0.3)
        self.water_w = water_region.get('width', 0.8)
        self.water_h = water_region.get('height', 0.6)
    
    def extract_water_region(self, image: Image.Image) -> Image.Image:
        """
        提取水域区域
        参数:
            image: 完整截图
        返回: 水域区域图像
        """
        width, height = image.size
        x = int(width * self.water_x)
        y = int(height * self.water_y)
        w = int(width * self.water_w)
        h = int(height * self.water_h)
        return image.crop((x, y, x + w, y + h))
    
    def detect_fish(self, image: Image.Image) -> List[Dict]:
        """
        识别鱼
        参数:
            image: 图像（可以是完整截图或水域区域）
        返回: 鱼列表，每个鱼包含 {id, x, y, size, center_x, center_y}
        """
        # 转换为OpenCV格式
        img_array = np.array(image)
        if len(img_array.shape) == 3:
            img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        else:
            img_cv = img_array
        
        # 转换为HSV颜色空间
        hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)
        
        # 创建颜色掩码（鱼的典型颜色范围）
        lower_bound = np.array([self.fish_hue_min, self.fish_sat_min, self.fish_val_min])
        upper_bound = np.array([self.fish_hue_max, self.fish_sat_max, self.fish_val_max])
        mask = cv2.inRange(hsv, lower_bound, upper_bound)
        
        # 形态学操作，去除噪声
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        # 查找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        fish_list = []
        for idx, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            if self.min_fish_area <= area <= self.max_fish_area:
                # 计算中心点
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    center_x = int(M["m10"] / M["m00"])
                    center_y = int(M["m01"] / M["m00"])
                    
                    # 获取边界框
                    x, y, w, h = cv2.boundingRect(contour)
                    
                    fish_list.append({
                        'id': idx,
                        'x': x,
                        'y': y,
                        'width': w,
                        'height': h,
                        'size': area,
                        'center_x': center_x,
                        'center_y': center_y,
                        'contour': contour
                    })
        
        return fish_list
    
    def detect_hook(self, image: Image.Image) -> Optional[Dict]:
        """
        识别鱼钩位置
        参数:
            image: 图像
        返回: 鱼钩信息 {x, y, center_x, center_y, size} 或 None
        """
        # 转换为OpenCV格式
        img_array = np.array(image)
        if len(img_array.shape) == 3:
            img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        else:
            gray = img_array
        
        # 使用亮度阈值检测发光的鱼钩
        _, mask = cv2.threshold(gray, self.hook_brightness_min, 255, cv2.THRESH_BINARY)
        
        # 形态学操作
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        # 查找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 找到最大的明亮区域（可能是鱼钩）
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest_contour)
            
            if area >= self.hook_min_size:
                M = cv2.moments(largest_contour)
                if M["m00"] != 0:
                    center_x = int(M["m10"] / M["m00"])
                    center_y = int(M["m01"] / M["m00"])
                    
                    x, y, w, h = cv2.boundingRect(largest_contour)
                    
                    return {
                        'x': x,
                        'y': y,
                        'width': w,
                        'height': h,
                        'center_x': center_x,
                        'center_y': center_y,
                        'size': area
                    }
        
        return None
    
    def detect_special_items(self, image: Image.Image) -> Dict[str, List[Dict]]:
        """
        识别特殊物品
        参数:
            image: 图像
        返回: {
            'scare_items': [...],  # 驱赶道具
            'freeze_items': [...], # 冻结道具
            'debris': [...]        # 杂物
        }
        """
        # 转换为OpenCV格式
        img_array = np.array(image)
        if len(img_array.shape) == 3:
            img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        else:
            img_cv = img_array
        
        hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        result = {
            'scare_items': [],
            'freeze_items': [],
            'debris': []
        }
        
        # 检测驱赶道具（蓝色漩涡）
        lower_scare = np.array([self.scare_hue_min, self.scare_sat_min, 50])
        upper_scare = np.array([self.scare_hue_max, self.scare_sat_max, 255])
        mask_scare = cv2.inRange(hsv, lower_scare, upper_scare)
        contours_scare, _ = cv2.findContours(mask_scare, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours_scare:
            area = cv2.contourArea(contour)
            if area > 50:  # 最小面积阈值
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    center_x = int(M["m10"] / M["m00"])
                    center_y = int(M["m01"] / M["m00"])
                    result['scare_items'].append({
                        'center_x': center_x,
                        'center_y': center_y,
                        'size': area
                    })
        
        # 检测冻结道具（发光蓝色物体）
        lower_freeze = np.array([self.freeze_hue_min, 50, self.freeze_brightness_min])
        upper_freeze = np.array([self.freeze_hue_max, 255, 255])
        mask_freeze = cv2.inRange(hsv, lower_freeze, upper_freeze)
        # 同时检查亮度
        _, bright_mask = cv2.threshold(gray, self.freeze_brightness_min, 255, cv2.THRESH_BINARY)
        mask_freeze = cv2.bitwise_and(mask_freeze, bright_mask)
        contours_freeze, _ = cv2.findContours(mask_freeze, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours_freeze:
            area = cv2.contourArea(contour)
            if area > 50:
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    center_x = int(M["m10"] / M["m00"])
                    center_y = int(M["m01"] / M["m00"])
                    result['freeze_items'].append({
                        'center_x': center_x,
                        'center_y': center_y,
                        'size': area
                    })
        
        # 检测杂物（水草、木头）
        # 水草（绿色）
        lower_seaweed = np.array([self.seaweed_hue_min, 50, 50])
        upper_seaweed = np.array([self.seaweed_hue_max, 255, 255])
        mask_seaweed = cv2.inRange(hsv, lower_seaweed, upper_seaweed)
        contours_seaweed, _ = cv2.findContours(mask_seaweed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours_seaweed:
            area = cv2.contourArea(contour)
            if area > 30:
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    center_x = int(M["m10"] / M["m00"])
                    center_y = int(M["m01"] / M["m00"])
                    result['debris'].append({
                        'type': 'seaweed',
                        'center_x': center_x,
                        'center_y': center_y,
                        'size': area
                    })
        
        # 木头（棕色）
        lower_wood = np.array([self.wood_hue_min, 50, 50])
        upper_wood = np.array([self.wood_hue_max, 255, 255])
        mask_wood = cv2.inRange(hsv, lower_wood, upper_wood)
        contours_wood, _ = cv2.findContours(mask_wood, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours_wood:
            area = cv2.contourArea(contour)
            if area > 30:
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    center_x = int(M["m10"] / M["m00"])
                    center_y = int(M["m01"] / M["m00"])
                    result['debris'].append({
                        'type': 'wood',
                        'center_x': center_x,
                        'center_y': center_y,
                        'size': area
                    })
        
        return result
