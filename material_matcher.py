"""
材料匹配游戏自动化模块
识别修真材料并自动匹配消除
"""
import time
import numpy as np
from PIL import Image, ImageStat, ImageDraw, ImageFont
from typing import List, Tuple, Dict, Optional, Set, Any
from collections import defaultdict
import cv2
import os
import json
import hashlib
from datetime import datetime


class MaterialMatcher:
    """材料匹配游戏自动化类"""
    
    def __init__(self, config=None):
        """
        初始化材料匹配器
        参数:
            config: 配置对象
        """
        self.config = config
        # 材料网格配置
        self.grid_rows = 5  # 默认4行
        self.grid_cols = 10  # 默认4列
        # 游戏区域配置（相对坐标 0-1）
        self.game_region = {
            "x": 0.1,
            "y": 0.2,
            "w": 0.4,
            "h": 0.5
        }
        # 分数区域配置
        self.score_region = {
            "x": 0.55,
            "y": 0.2,
            "w": 0.35,
            "h": 0.3
        }
        # 时间区域配置
        self.time_region = {
            "x": 0.1,
            "y": 0.75,
            "w": 0.8,
            "h": 0.1
        }
        # 材料类型缓存（用于识别）
        self.material_templates = {}
        # 已识别的材料网格
        self.material_grid = None
        # 当前分数
        self.current_score = 0
        # 目标分数
        self.target_score = 50
        # 剩余时间（秒）
        self.remaining_time = 90
        # 点击延迟
        self.click_delay = 0.3
        # 轮廓匹配配置
        self.contour_match_enabled = False
        self.contour_similarity_threshold = 0.3
        self.min_contour_area = 100
        # 存储轮廓数据
        self.contour_cache = {}  # {(row, col): contour}
        # 单元格中心裁剪比例（与 extract_cell_image 对齐）
        self.cell_margin_ratio = 0.15  # 每边去掉 15% 的边框
        # 轮廓可视化配置
        self.debug_visualize = True  # 是否保存轮廓可视化图像
        self.debug_output_dir = "./debug_contours"  # 调试图像输出目录
        # 指纹匹配配置
        self.fingerprint_match_enabled = True  # 默认启用指纹匹配
        self.fingerprint_dh_bits = 64  # dHash位数（8x8=64）
        self.fingerprint_hamming_threshold = 5  # 汉明距离阈值
        self.fingerprint_color_weight = 0.3  # 颜色距离权重
        self.fingerprint_hash_weight = 0.7  # 哈希距离权重
        self.fingerprint_min_group_size = 2  # 最小分组大小
        self.fingerprint_auto_collect = True  # 自动收集模板
        self.fingerprint_verify_empty_after_click = True  # 点击后校验空格
        # 指纹缓存（当前识别轮次）
        self.fingerprint_cache = {}  # {(row, col): fingerprint_dict}
        # 模板库
        self.template_library = None  # TemplateLibrary实例

    def _get_cell_margins(self, w: int, h: int) -> Tuple[int, int]:
        """根据单元格尺寸计算中心裁剪的 margin（与 extract_cell_image 一致）"""
        margin_x = int(w * self.cell_margin_ratio)
        margin_y = int(h * self.cell_margin_ratio)
        return margin_x, margin_y
    
    def set_config(self, config: dict):
        """设置配置"""
        if config:
            self.game_region = config.get("game_region", self.game_region)
            self.score_region = config.get("score_region", self.score_region)
            self.time_region = config.get("time_region", self.time_region)
            self.grid_rows = config.get("grid_rows", self.grid_rows)
            self.grid_cols = config.get("grid_cols", self.grid_cols)
            self.click_delay = config.get("click_delay", self.click_delay)
            self.target_score = config.get("target_score", self.target_score)
            # 轮廓匹配配置
            contour_config = config.get("contour_match", {})
            # 调试：打印配置内容
            print(f"[材料匹配器] 接收到的配置: contour_match={contour_config}")
            self.contour_match_enabled = contour_config.get("enabled", False)
            self.contour_similarity_threshold = contour_config.get("similarity_threshold", 0.3)
            self.min_contour_area = contour_config.get("min_contour_area", 100)
            # 调试日志
            print(f"[材料匹配器] 轮廓匹配已{'启用' if self.contour_match_enabled else '禁用'}, 相似度阈值: {self.contour_similarity_threshold}, 最小轮廓面积: {self.min_contour_area}")
            # 指纹匹配配置
            fp_config = config.get("fingerprint_match", {})
            self.fingerprint_match_enabled = fp_config.get("enabled", True)
            self.fingerprint_dh_bits = fp_config.get("dh_bits", 64)
            self.fingerprint_hamming_threshold = fp_config.get("hamming_threshold", 5)
            self.fingerprint_color_weight = fp_config.get("color_weight", 0.3)
            self.fingerprint_hash_weight = fp_config.get("hash_weight", 0.7)
            self.fingerprint_min_group_size = fp_config.get("min_group_size", 2)
            self.fingerprint_auto_collect = fp_config.get("auto_collect", True)
            self.fingerprint_verify_empty_after_click = fp_config.get("verify_empty_after_click", True)
            # 初始化模板库
            if self.fingerprint_match_enabled:
                self.template_library = TemplateLibrary()
                print(f"[材料匹配器] 指纹匹配已启用，汉明阈值: {self.fingerprint_hamming_threshold}")
            # 指纹匹配配置
            fp_config = config.get("fingerprint_match", {})
            self.fingerprint_match_enabled = fp_config.get("enabled", True)
            self.fingerprint_dh_bits = fp_config.get("dh_bits", 64)
            self.fingerprint_hamming_threshold = fp_config.get("hamming_threshold", 5)
            self.fingerprint_color_weight = fp_config.get("color_weight", 0.3)
            self.fingerprint_hash_weight = fp_config.get("hash_weight", 0.7)
            self.fingerprint_min_group_size = fp_config.get("min_group_size", 2)
            self.fingerprint_auto_collect = fp_config.get("auto_collect", True)
            self.fingerprint_verify_empty_after_click = fp_config.get("verify_empty_after_click", True)
            # 初始化模板库
            if self.fingerprint_match_enabled:
                self.template_library = TemplateLibrary()
                print(f"[材料匹配器] 指纹匹配已启用，汉明阈值: {self.fingerprint_hamming_threshold}")
    
    def extract_game_region(self, image: Image.Image, is_region_capture: bool = False) -> Image.Image:
        """
        提取游戏区域
        参数:
            image: 完整截图（可能是用户设置的区域截图，也可能是全屏截图）
            is_region_capture: 是否为区域截图（如果是，则直接使用整个图像作为游戏区域）
        返回: 游戏区域图像
        """
        # 如果是区域截图，直接使用整个图像作为游戏区域
        if is_region_capture:
            return image
        
        width, height = image.size
        
        # 如果游戏区域配置使用的是相对坐标（0-1），则按比例提取
        # 如果使用的是绝对坐标，则直接使用
        if self.game_region.get("use_absolute", False):
            # 使用绝对坐标
            x = int(self.game_region["x"])
            y = int(self.game_region["y"])
            w = int(self.game_region["w"])
            h = int(self.game_region["h"])
        else:
            # 使用相对坐标（0-1）
            x = int(self.game_region["x"] * width)
            y = int(self.game_region["y"] * height)
            w = int(self.game_region["w"] * width)
            h = int(self.game_region["h"] * height)
        
        # 确保坐标在图像范围内
        x = max(0, min(x, width - 1))
        y = max(0, min(y, height - 1))
        w = min(w, width - x)
        h = min(h, height - y)
        
        return image.crop((x, y, x + w, y + h))
    
    def extract_score_region(self, image: Image.Image) -> Image.Image:
        """提取分数区域"""
        width, height = image.size
        x = int(self.score_region["x"] * width)
        y = int(self.score_region["y"] * height)
        w = int(self.score_region["w"] * width)
        h = int(self.score_region["h"] * height)
        
        return image.crop((x, y, x + w, y + h))
    
    def extract_time_region(self, image: Image.Image) -> Image.Image:
        """提取时间区域"""
        width, height = image.size
        x = int(self.time_region["x"] * width)
        y = int(self.time_region["y"] * height)
        w = int(self.time_region["w"] * width)
        h = int(self.time_region["h"] * height)
        
        return image.crop((x, y, x + w, y + h))
    
    def get_cell_region(self, row: int, col: int, game_image: Image.Image) -> Tuple[int, int, int, int]:
        """
        获取网格单元格区域
        参数:
            row, col: 行列索引（从0开始）
            game_image: 游戏区域图像
        返回: (x, y, width, height)
        """
        img_width, img_height = game_image.size
        # 采用按比例切分，避免整除导致最后一列/行误差累积（尤其是 5x10 这种）
        x0 = int(col * img_width / self.grid_cols)
        x1 = int((col + 1) * img_width / self.grid_cols)
        y0 = int(row * img_height / self.grid_rows)
        y1 = int((row + 1) * img_height / self.grid_rows)

        # 兜底：保证至少 1 像素宽高
        if x1 <= x0:
            x1 = min(img_width, x0 + 1)
        if y1 <= y0:
            y1 = min(img_height, y0 + 1)

        return (x0, y0, x1 - x0, y1 - y0)
    
    def get_cell_center(self, row: int, col: int, game_image: Image.Image, 
                       screen_offset: Tuple[int, int] = (0, 0), log_callback=None) -> Tuple[int, int]:
        """
        获取单元格中心坐标（屏幕坐标）
        参数:
            row, col: 行列索引
            game_image: 游戏区域图像
            screen_offset: 游戏区域在屏幕上的偏移量
            log_callback: 日志回调函数
        返回: (x, y) 屏幕坐标
        """
        x, y, w, h = self.get_cell_region(row, col, game_image)
        # 单元格中心（相对于游戏区域）
        center_x = x + w // 2
        center_y = y + h // 2
        
        # 转换为屏幕坐标
        screen_x = screen_offset[0] + center_x
        screen_y = screen_offset[1] + center_y
        
        if log_callback:
            img_width, img_height = game_image.size
            log_callback(
                f"  [坐标计算] 单元格 ({row},{col}): 图像尺寸=({img_width},{img_height}), "
                f"单元格区域=({x},{y},{w},{h}), 中心相对坐标=({center_x},{center_y}), "
                f"屏幕偏移=({screen_offset[0]},{screen_offset[1]}), 最终坐标=({screen_x},{screen_y})"
            )
        
        return (screen_x, screen_y)

    def get_cell_click_point_by_contour(self, row: int, col: int, game_image: Image.Image,
                                        screen_offset: Tuple[int, int] = (0, 0), log_callback=None) -> Tuple[int, int]:
        """
        获取单元格内物品的点击点（优先轮廓质心），返回屏幕坐标。
        注意：轮廓是在 extract_cell_image 的中心裁剪图上提取的，因此需要加回 margin 偏移。
        """
        contour = self.contour_cache.get((row, col))
        if contour is None or len(contour) == 0:
            if log_callback:
                log_callback(f"  [坐标计算] 单元格 ({row},{col}) 无轮廓缓存，回退到格子中心")
            return self.get_cell_center(row, col, game_image, screen_offset, log_callback)

        m = cv2.moments(contour)
        if abs(m.get("m00", 0.0)) < 1e-6:
            if log_callback:
                log_callback(f"  [坐标计算] 单元格 ({row},{col}) 轮廓 m00≈0，回退到格子中心")
            return self.get_cell_center(row, col, game_image, screen_offset, log_callback)

        cx = int(m["m10"] / m["m00"])
        cy = int(m["m01"] / m["m00"])

        cell_x, cell_y, w, h = self.get_cell_region(row, col, game_image)
        margin_x, margin_y = self._get_cell_margins(w, h)

        # 轮廓坐标系是“中心裁剪图”，需要加回 margin 才能回到 game_image 坐标系
        gx = cell_x + margin_x + cx
        gy = cell_y + margin_y + cy

        screen_x = screen_offset[0] + gx
        screen_y = screen_offset[1] + gy

        if log_callback:
            log_callback(
                f"  [坐标计算] 单元格 ({row},{col}) 轮廓质心=({cx},{cy}), "
                f"cell=({cell_x},{cell_y},{w},{h}), margin=({margin_x},{margin_y}), "
                f"game坐标=({gx},{gy}), 屏幕坐标=({screen_x},{screen_y})"
            )

        return (screen_x, screen_y)
    
    def extract_cell_image(self, row: int, col: int, game_image: Image.Image) -> Image.Image:
        """提取单元格图像（只提取中心区域，排除边框）"""
        x, y, w, h = self.get_cell_region(row, col, game_image)
        # 增大margin，只提取中心区域，排除边框和背景
        # 使用更大的margin比例，确保只提取物品本身
        margin_x, margin_y = self._get_cell_margins(w, h)
        return game_image.crop((x + margin_x, y + margin_y, x + w - margin_x, y + h - margin_y))
    
    def extract_contour(self, cell_image: Image.Image, log_callback=None) -> Optional[np.ndarray]:
        """
        提取单元格中物品的轮廓（关键：排除方框轮廓）
        参数:
            cell_image: 已排除边框的单元格中心区域图像
            log_callback: 日志回调函数
        返回: 物品轮廓（numpy数组），如果提取失败返回None
        """
        try:
            if cell_image.size[0] == 0 or cell_image.size[1] == 0:
                return None
            
            # 转换为numpy数组
            img_array = np.array(cell_image)
            
            # 转换为灰度图
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array
            
            # 使用自适应二值化，更好地分离物品和背景
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY_INV, 11, 2
            )
            
            # 形态学操作去除噪声和小边框残留
            kernel = np.ones((3, 3), np.uint8)
            binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
            
            # 查找所有轮廓
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                if log_callback:
                    log_callback("未找到轮廓")
                return None
            
            # 过滤轮廓，排除方框轮廓
            valid_contours = []
            cell_area = cell_image.size[0] * cell_image.size[1]
            
            for contour in contours:
                # 计算轮廓面积
                area = cv2.contourArea(contour)
                
                # 过滤面积太小的轮廓（噪声）
                if area < self.min_contour_area:
                    continue
                
                # 过滤面积太大的轮廓（可能是整个单元格）
                if area > cell_area * 0.8:
                    continue
                
                # 计算边界矩形
                x, y, w, h = cv2.boundingRect(contour)
                rect_area = w * h
                
                # 计算轮廓面积与边界矩形面积的比值
                # 如果接近1，说明轮廓很接近矩形，可能是方框
                area_ratio = area / rect_area if rect_area > 0 else 0
                
                # 计算宽高比
                aspect_ratio = w / h if h > 0 else 1
                
                # 计算凸包
                hull = cv2.convexHull(contour)
                hull_area = cv2.contourArea(hull)
                hull_ratio = area / hull_area if hull_area > 0 else 0
                
                # 过滤规则：排除接近矩形的轮廓（可能是方框）
                # 1. 面积比接近1（轮廓填充了大部分矩形区域）
                # 2. 宽高比接近1（接近正方形）
                # 3. 凸包比接近1（形状规则）
                is_rectangular = (
                    area_ratio > 0.85 and  # 轮廓填充了大部分矩形
                    0.7 < aspect_ratio < 1.3 and  # 接近正方形
                    hull_ratio > 0.9  # 形状规则
                )
                
                if is_rectangular:
                    if log_callback:
                        log_callback(f"过滤掉矩形轮廓: 面积={area:.0f}, 面积比={area_ratio:.2f}, 宽高比={aspect_ratio:.2f}")
                    continue
                
                # 计算轮廓点数（矩形轮廓点数通常较少）
                contour_points = len(contour)
                # 如果轮廓点数太少，可能是简单的矩形
                if contour_points < 8 and area_ratio > 0.8:
                    if log_callback:
                        log_callback(f"过滤掉简单矩形轮廓: 点数={contour_points}, 面积比={area_ratio:.2f}")
                    continue
                
                valid_contours.append((contour, area))
            
            if not valid_contours:
                if log_callback:
                    log_callback("过滤后没有有效轮廓")
                return None
            
            # 选择面积最大的非矩形轮廓（物品主体）
            valid_contours.sort(key=lambda x: x[1], reverse=True)
            best_contour, best_area = valid_contours[0]
            
            if log_callback:
                log_callback(f"提取到物品轮廓: 面积={best_area:.0f}, 轮廓点数={len(best_contour)}")
            
            # 轮廓近似，减少点数，提高匹配速度
            epsilon = 0.02 * cv2.arcLength(best_contour, True)
            approx_contour = cv2.approxPolyDP(best_contour, epsilon, True)
            # 防止近似后轮廓退化成线段（面积接近 0），导致 matchShapes 大量 0.0 假匹配
            approx_area = cv2.contourArea(approx_contour)
            if approx_area <= 1.0:
                if log_callback:
                    log_callback(f"近似轮廓退化(面积={approx_area:.1f})，回退使用原始轮廓")
                return best_contour

            return approx_contour
            
        except Exception as e:
            if log_callback:
                log_callback(f"轮廓提取失败: {e}")
            return None
    
    def calculate_image_hash(self, image: Image.Image) -> str:
        """
        计算图像哈希值（用于识别相同材料）
        使用感知哈希（pHash）
        """
        try:
            # 转换为灰度图
            gray = image.convert('L')
            # 缩放到8x8
            gray = gray.resize((8, 8), Image.Resampling.LANCZOS)
            # 计算平均值
            pixels = list(gray.getdata())
            avg = sum(pixels) / len(pixels)
            # 生成哈希
            hash_bits = ''.join(['1' if p >= avg else '0' for p in pixels])
            return hash_bits
        except Exception:
            return ""
    
    def calculate_color_hash(self, image: Image.Image) -> str:
        """
        计算颜色哈希（基于主要颜色，排除背景色）
        只关注物品本身的颜色特征
        """
        try:
            if image.size[0] == 0 or image.size[1] == 0:
                return ""
            
            # 缩放到较小尺寸以加快计算
            small = image.resize((32, 32), Image.Resampling.LANCZOS)
            
            # 转换为numpy数组以便处理
            import numpy as np
            img_array = np.array(small)
            
            # 排除接近白色的背景像素（可能是边框或背景）
            # 计算每个像素的亮度
            gray = np.dot(img_array[...,:3], [0.299, 0.587, 0.114])
            # 排除过亮的像素（可能是背景）
            mask = gray < 240  # 排除接近白色的像素
            
            if not np.any(mask):
                # 如果没有有效像素，使用全部像素
                mask = np.ones_like(gray, dtype=bool)
            
            # 只使用非背景像素计算颜色
            valid_pixels = img_array[mask]
            if len(valid_pixels) == 0:
                # 如果没有有效像素，使用全部像素
                valid_pixels = img_array.reshape(-1, img_array.shape[-1])
            
            # 计算RGB平均值（只考虑有效像素）
            r_mean = np.mean(valid_pixels[:, 0]) if len(valid_pixels) > 0 else 128
            g_mean = np.mean(valid_pixels[:, 1]) if len(valid_pixels) > 0 else 128
            b_mean = np.mean(valid_pixels[:, 2]) if len(valid_pixels) > 0 else 128
            
            # 量化到更细的级别（16级），提高识别精度
            r_q = int(r_mean / 16)
            g_q = int(g_mean / 16)
            b_q = int(b_mean / 16)
            
            # 同时计算颜色的方差，作为辅助特征
            r_std = int(np.std(valid_pixels[:, 0]) / 8) if len(valid_pixels) > 0 else 0
            g_std = int(np.std(valid_pixels[:, 1]) / 8) if len(valid_pixels) > 0 else 0
            b_std = int(np.std(valid_pixels[:, 2]) / 8) if len(valid_pixels) > 0 else 0
            
            # 组合颜色特征和方差特征
            return f"{r_q:02d}{g_q:02d}{b_q:02d}{r_std:02d}{g_std:02d}{b_std:02d}"
        except Exception as e:
            # 如果出错，回退到简单方法
            try:
                stat = ImageStat.Stat(image)
                r, g, b = stat.mean
                r_q = int(r / 32)
                g_q = int(g / 32)
                b_q = int(b / 32)
                return f"{r_q:03d}{g_q:03d}{b_q:03d}"
            except Exception:
                return ""
    
    def calculate_combined_hash(self, image: Image.Image) -> str:
        """计算组合哈希（图像+颜色）"""
        img_hash = self.calculate_image_hash(image)
        color_hash = self.calculate_color_hash(image)
        return f"{img_hash}_{color_hash}"
    
    def calculate_contour_hash(self, contour: np.ndarray) -> str:
        """
        计算轮廓特征哈希
        使用Hu矩作为特征
        参数:
            contour: 轮廓（numpy数组）
        返回: 轮廓特征字符串
        """
        try:
            if contour is None or len(contour) == 0:
                return ""
            
            # 计算Hu矩
            moments = cv2.moments(contour)
            hu_moments = cv2.HuMoments(moments).flatten()
            
            # 将Hu矩转换为可比较的字符串
            # 使用对数变换使数值更稳定，然后量化
            hu_str = ""
            for hu in hu_moments:
                # 使用对数变换（取绝对值后加1，避免log(0)）
                log_hu = np.log10(abs(hu) + 1e-10)
                # 量化到整数
                quantized = int(log_hu * 100)
                hu_str += f"{quantized:06d}"
            
            return hu_str
        except Exception as e:
            return ""
    
    def match_contours(self, contour1: np.ndarray, contour2: np.ndarray) -> float:
        """
        匹配轮廓相似度
        参数:
            contour1, contour2: 两个轮廓
        返回: 相似度分数（0-1，越小越相似）
        """
        try:
            if contour1 is None or contour2 is None:
                return 1.0
            
            if len(contour1) == 0 or len(contour2) == 0:
                return 1.0
            
            # 使用cv2.matchShapes计算轮廓相似度
            # 返回值：0表示完全相同，值越大差异越大
            similarity = cv2.matchShapes(contour1, contour2, cv2.CONTOURS_MATCH_I2, 0)
            return similarity
        except Exception as e:
            return 1.0
    
    def recognize_materials(self, image: Image.Image, log_callback=None, is_region_capture: bool = False) -> Optional[Dict[Tuple[int, int], str]]:
        """
        识别材料网格
        参数:
            image: 完整截图
            log_callback: 日志回调函数，用于输出详细日志
            is_region_capture: 是否为区域截图
        返回: {(row, col): material_hash} 字典，如果识别失败返回None
        """
        try:
            # 提取游戏区域
            game_image = self.extract_game_region(image, is_region_capture)
            if log_callback:
                log_callback(f"游戏区域提取完成，尺寸: {game_image.size} (区域截图: {is_region_capture})")
            
            # 识别每个单元格
            material_grid = {}
            empty_cells = []
            self.contour_cache = {}  # 清空轮廓缓存
            self.fingerprint_cache = {}  # 清空指纹缓存
            
            # 判断使用哪种识别方法（优先级：指纹 > 轮廓 > 颜色哈希）
            use_fingerprint = self.fingerprint_match_enabled
            use_contour = self.contour_match_enabled and not use_fingerprint
            if log_callback:
                mode_name = "指纹匹配" if use_fingerprint else ("轮廓匹配" if use_contour else "颜色哈希")
                log_callback(f"[材料识别] 识别模式: {mode_name}")
            
            start_time = time.time()
            # 如果提供了已点击位置集合，在识别时直接跳过这些位置（避免重复识别）
            clicked_positions = getattr(self, '_clicked_positions_for_recognition', set())
            
            for row in range(self.grid_rows):
                for col in range(self.grid_cols):
                    # 如果这个位置在已点击集合中，直接跳过（不识别）
                    if (row, col) in clicked_positions:
                        empty_cells.append((row, col))
                        if log_callback:
                            log_callback(f"单元格 ({row},{col}) 在已点击集合中，跳过识别")
                        continue
                    
                    cell_image = self.extract_cell_image(row, col, game_image)
                    # 检查单元格是否为空（通过检查是否主要是空白）
                    is_empty = self.is_cell_empty(cell_image)
                    if is_empty:
                        empty_cells.append((row, col))
                        if log_callback:
                            log_callback(f"单元格 ({row},{col}) 为空，跳过")
                        continue
                    
                    if use_fingerprint:
                        # 使用指纹匹配
                        fingerprint = self.compute_fingerprint(cell_image)
                        self.fingerprint_cache[(row, col)] = fingerprint
                        # 生成一个临时哈希用于material_grid（后续会被分组替代）
                        fp_hash = f"fp_{fingerprint['dhash'][:16]}"
                        material_grid[(row, col)] = fp_hash
                    elif use_contour:
                        # 使用轮廓匹配
                        def cell_log(msg):
                            if log_callback:
                                log_callback(f"单元格 ({row},{col}): {msg}")
                        
                        contour = self.extract_contour(cell_image, cell_log)
                        if contour is not None and len(contour) > 0:
                            # 计算轮廓哈希
                            contour_hash = self.calculate_contour_hash(contour)
                            material_grid[(row, col)] = contour_hash
                            self.contour_cache[(row, col)] = contour
                            if log_callback:
                                area = cv2.contourArea(contour)
                                log_callback(f"单元格 ({row},{col}) 识别到材料轮廓，面积={area:.0f}, 轮廓哈希前12位: {contour_hash[:12] if contour_hash else 'N/A'}")
                            
                            # 可视化轮廓（如果启用）
                            if self.debug_visualize:
                                self.visualize_contour(row, col, cell_image, contour, log_callback)
                        else:
                            # 轮廓提取失败，回退到颜色哈希
                            if log_callback:
                                log_callback(f"单元格 ({row},{col}) 轮廓提取失败，回退到颜色哈希")
                            color_hash = self.calculate_color_hash(cell_image)
                            material_grid[(row, col)] = color_hash
                    else:
                        # 使用颜色哈希（原有方法）
                        color_hash = self.calculate_color_hash(cell_image)
                        img_hash = self.calculate_image_hash(cell_image)
                        material_hash = color_hash
                        material_grid[(row, col)] = material_hash
                        if log_callback:
                            log_callback(f"单元格 ({row},{col}) 识别到材料，颜色哈希: {color_hash}, 图像哈希前8位: {img_hash[:8] if img_hash else 'N/A'}")
            
            elapsed = time.time() - start_time
            if log_callback:
                method_name = "指纹匹配" if use_fingerprint else ("轮廓匹配" if use_contour else "颜色哈希")
                log_callback(f"材料识别完成 ({method_name}): 识别到 {len(material_grid)} 个材料，空单元格 {len(empty_cells)} 个，耗时 {elapsed:.2f}秒")
                if empty_cells:
                    log_callback(f"空单元格位置: {empty_cells}")
                if material_grid:
                    if use_fingerprint:
                        # 指纹匹配模式下，进行分组
                        groups = self.group_by_fingerprint(self.fingerprint_cache, log_callback)
                        # 自动收集模板
                        if self.fingerprint_auto_collect and self.template_library:
                            for group in groups:
                                if len(group) >= 2:
                                    # 使用第一个作为代表
                                    rep_pos = group[0]
                                    rep_fp = self.fingerprint_cache[rep_pos]
                                    # 检查模板库中是否已有
                                    template_id = self.template_library.find_best_match(rep_fp, threshold=0.15)
                                    if template_id:
                                        self.template_library.update_template(template_id, len(group), log_callback)
                                    else:
                                        # 新增模板
                                        rep_cell_image = self.extract_cell_image(rep_pos[0], rep_pos[1], game_image)
                                        self.template_library.add_template(rep_fp, rep_cell_image, len(group), log_callback)
                    elif use_contour:
                        # 轮廓匹配模式下，显示轮廓信息
                        log_callback(f"轮廓缓存: {len(self.contour_cache)} 个轮廓")
                        # 显示每个轮廓的详细信息
                        for pos, contour in self.contour_cache.items():
                            area = cv2.contourArea(contour)
                            perimeter = cv2.arcLength(contour, True)
                            x, y, w, h = cv2.boundingRect(contour)
                            log_callback(f"  轮廓 {pos}: 面积={area:.0f}, 周长={perimeter:.1f}, 边界=({x},{y},{w},{h})")
                    else:
                        # 颜色哈希模式下，显示分组信息
                        from collections import defaultdict
                        groups = defaultdict(list)
                        for pos, hash_val in material_grid.items():
                            groups[hash_val].append(pos)
                        log_callback(f"材料分组: {len(groups)} 种不同的材料")
                        for hash_val, positions in sorted(groups.items(), key=lambda x: len(x[1]), reverse=True):
                            if len(positions) >= 2:
                                log_callback(f"  匹配组 (颜色哈希: {hash_val}): {positions} (共{len(positions)}个)")
                            else:
                                log_callback(f"  单材料 (颜色哈希: {hash_val}): {positions}")
            
            # 如果启用可视化，创建合成图像
            if self.debug_visualize and use_contour and self.contour_cache:
                self.create_contour_grid_visualization(game_image, log_callback)
            
            self.material_grid = material_grid
            return material_grid
        except Exception as e:
            error_msg = f"识别材料失败: {e}"
            if log_callback:
                log_callback(error_msg)
            print(error_msg)
            return None
    
    def is_cell_empty(self, cell_image: Image.Image, threshold: float = 0.85) -> bool:
        """
        判断单元格是否为空
        参数:
            cell_image: 单元格图像
            threshold: 空白阈值（如果空白像素占比超过此值则认为为空）
        """
        try:
            if cell_image.size[0] == 0 or cell_image.size[1] == 0:
                return True
            
            # 转换为灰度
            gray = cell_image.convert('L')
            # 计算空白像素占比（接近白色的像素，阈值降低到220，因为可能有浅色背景）
            pixels = list(gray.getdata())
            if not pixels:
                return True
            
            # 使用更宽松的阈值，因为游戏背景可能不是纯白色
            white_count = sum(1 for p in pixels if p > 220)
            white_ratio = white_count / len(pixels)
            
            # 同时检查像素值的方差，如果方差很小，说明颜色很单一，可能是空白
            if len(pixels) > 1:
                mean_pixel = sum(pixels) / len(pixels)
                variance = sum((p - mean_pixel) ** 2 for p in pixels) / len(pixels)
                # 如果方差很小（<100），且平均像素值很高（>200），可能是空白
                if variance < 100 and mean_pixel > 200:
                    return True
            
            return white_ratio > threshold
        except Exception as e:
            # 出错时默认认为不为空，避免误判
            return False
    
    def find_matching_pairs(self, material_grid: Dict[Tuple[int, int], str], log_callback=None, 
                           temp_threshold: Optional[int] = None) -> List[Tuple[Tuple[int, int], Tuple[int, int], float]]:
        """
        找到所有匹配的材料对
        参数:
            material_grid: {(row, col): material_hash} 字典
            log_callback: 日志回调函数
            temp_threshold: 临时阈值（用于渐进式匹配），如果为None则使用默认阈值
        返回: [(pos1, pos2, similarity), ...] 匹配对列表，包含相似度分数
        """
        pairs = []
        
        if log_callback:
            log_callback(f"[匹配] 指纹匹配: {self.fingerprint_match_enabled}, 轮廓匹配: {self.contour_match_enabled}, 指纹缓存: {len(self.fingerprint_cache)}, 轮廓缓存: {len(self.contour_cache) if self.contour_cache else 0}")
        
        # 优先使用指纹匹配
        if self.fingerprint_match_enabled and self.fingerprint_cache:
            # 使用临时阈值或默认阈值
            threshold_to_use = temp_threshold if temp_threshold is not None else self.fingerprint_hamming_threshold
            if log_callback:
                if temp_threshold is not None:
                    log_callback(f"[匹配] 使用指纹匹配模式，临时汉明阈值: {temp_threshold} (默认: {self.fingerprint_hamming_threshold})")
                else:
                    log_callback(f"[匹配] 使用指纹匹配模式，汉明阈值: {self.fingerprint_hamming_threshold}")
            
            # 只使用 material_grid 中的位置对应的指纹（过滤掉已移除的位置）
            filtered_fingerprints = {pos: fp for pos, fp in self.fingerprint_cache.items() 
                                    if pos in material_grid}
            
            if log_callback:
                log_callback(f"[匹配] 过滤后的指纹数量: {len(filtered_fingerprints)} (原始: {len(self.fingerprint_cache)})")
            
            # 临时保存原始阈值
            original_threshold = self.fingerprint_hamming_threshold
            try:
                # 如果提供了临时阈值，临时修改阈值
                if temp_threshold is not None:
                    self.fingerprint_hamming_threshold = temp_threshold
                
                # 分组（只对剩余位置进行分组）
                groups = self.group_by_fingerprint(filtered_fingerprints, log_callback)
                # 提取配对
                pairs = self.find_pairs_by_groups(groups, log_callback)
            finally:
                # 恢复原始阈值
                if temp_threshold is not None:
                    self.fingerprint_hamming_threshold = original_threshold
            
            if log_callback:
                log_callback(f"[匹配] 指纹匹配完成: 找到 {len(pairs)} 个匹配对")
        elif self.contour_match_enabled and self.contour_cache:
            # 使用轮廓匹配
            if log_callback:
                log_callback(f"使用轮廓匹配模式，相似度阈值: {self.contour_similarity_threshold}")
            
            positions = list(material_grid.keys())
            total_comparisons = len(positions) * (len(positions) - 1) // 2
            if log_callback:
                log_callback(f"开始比较 {total_comparisons} 对轮廓...")
            
            matched_count = 0
            for i in range(len(positions)):
                for j in range(i + 1, len(positions)):
                    pos1, pos2 = positions[i], positions[j]
                    contour1 = self.contour_cache.get(pos1)
                    contour2 = self.contour_cache.get(pos2)
                    
                    if contour1 is not None and contour2 is not None:
                        similarity = self.match_contours(contour1, contour2)
                        if log_callback and (similarity <= self.contour_similarity_threshold or similarity <= 0.5):
                            # 只记录匹配的或接近匹配的，避免日志过多
                            status = "✓匹配" if similarity <= self.contour_similarity_threshold else "接近"
                            log_callback(f"  {status}: {pos1} <-> {pos2}, 相似度={similarity:.4f}")
                        
                        if similarity <= self.contour_similarity_threshold:
                            pairs.append((pos1, pos2, similarity))
                            matched_count += 1
            
            if log_callback:
                log_callback(f"轮廓匹配完成: 找到 {matched_count} 个匹配对（共比较 {total_comparisons} 对）")
        else:
            # 使用精确哈希匹配（原有方法）
            if log_callback:
                log_callback("使用颜色哈希精确匹配模式")
            
            material_groups = defaultdict(list)
            for pos, material_hash in material_grid.items():
                material_groups[material_hash].append(pos)
            
            for material_hash, positions in material_groups.items():
                if len(positions) >= 2:
                    # 找到所有可能的配对
                    for i in range(len(positions)):
                        for j in range(i + 1, len(positions)):
                            pairs.append((positions[i], positions[j], 0.0))  # 精确匹配，相似度为0
                    if log_callback:
                        log_callback(f"  精确匹配组: {positions} (共{len(positions)}个)")
        
        return pairs
    
    def find_best_match(self, material_grid: Dict[Tuple[int, int], str], log_callback=None, 
                       temp_threshold: Optional[int] = None) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """
        找到最佳匹配对（优先选择距离较近的，轮廓匹配时优先选择相似度最高的）
        参数:
            material_grid: 材料网格（只包含剩余未点击的位置）
            log_callback: 日志回调函数
            temp_threshold: 临时阈值（用于渐进式匹配），如果为None则使用默认阈值
        返回: (pos1, pos2) 或 None
        """
        pairs = self.find_matching_pairs(material_grid, log_callback, temp_threshold)
        if not pairs:
            return None
        
        # 双重保险：过滤掉不在 material_grid 中的配对（防止返回已移除的位置）
        valid_pairs = [(p1, p2, sim) for p1, p2, sim in pairs 
                      if p1 in material_grid and p2 in material_grid]
        
        if not valid_pairs:
            if log_callback:
                log_callback("[匹配] 所有配对都包含已移除的位置，返回 None")
            return None
        
        if self.contour_match_enabled:
            # 轮廓匹配模式：优先选择相似度最高的（相似度越小越好）
            best_pair = min(valid_pairs, key=lambda p: p[2])  # p[2]是相似度
            if log_callback:
                log_callback(f"最佳匹配: {best_pair[0]} <-> {best_pair[1]}, 相似度={best_pair[2]:.4f}")
            return (best_pair[0], best_pair[1])
        else:
            # 精确匹配模式：优先选择距离最近的
            def distance(pos1: Tuple[int, int], pos2: Tuple[int, int]) -> float:
                r1, c1 = pos1
                r2, c2 = pos2
                return ((r1 - r2) ** 2 + (c1 - c2) ** 2) ** 0.5
            
            best_pair = min(valid_pairs, key=lambda p: distance(p[0], p[1]))
            if log_callback:
                log_callback(f"最佳匹配: {best_pair[0]} <-> {best_pair[1]}, 距离={distance(best_pair[0], best_pair[1]):.2f}")
            return (best_pair[0], best_pair[1])
    
    def parse_score(self, score_image: Image.Image) -> Optional[int]:
        """
        解析分数（使用OCR或图像识别）
        参数:
            score_image: 分数区域图像
        返回: 分数值或None
        """
        # TODO: 实现OCR识别分数
        # 这里先返回None，后续可以集成OCR
        return None
    
    def parse_time(self, time_image: Image.Image) -> Optional[int]:
        """
        解析剩余时间（秒）
        参数:
            time_image: 时间区域图像
        返回: 剩余秒数或None
        """
        # TODO: 实现OCR识别时间
        return None
    
    def get_game_state(self, image: Image.Image, log_callback=None, is_region_capture: bool = False) -> Dict:
        """
        获取游戏状态
        参数:
            image: 完整截图
            log_callback: 日志回调函数
            is_region_capture: 是否为区域截图
        返回: 游戏状态字典
        """
        state = {
            "score": None,
            "time": None,
            "materials": None,
            "is_game_over": False
        }
        
        try:
            if log_callback:
                log_callback(f"开始识别游戏状态，截图尺寸: {image.size} (区域截图: {is_region_capture})")
            
            # 识别材料
            materials = self.recognize_materials(image, log_callback, is_region_capture)
            state["materials"] = materials
            
            # 识别分数
            score_image = self.extract_score_region(image)
            state["score"] = self.parse_score(score_image)
            
            # 识别时间
            time_image = self.extract_time_region(image)
            state["time"] = self.parse_time(time_image)
            
            # 判断游戏是否结束
            if state["score"] is not None and state["score"] >= self.target_score:
                state["is_game_over"] = True
            elif state["time"] is not None and state["time"] <= 0:
                state["is_game_over"] = True
            elif materials is not None and len(materials) == 0:
                state["is_game_over"] = True
            
        except Exception as e:
            print(f"获取游戏状态失败: {e}")
        
        return state
    
    def get_click_positions(self, pair: Tuple[Tuple[int, int], Tuple[int, int]], 
                           image: Image.Image, is_region_capture: bool = False, log_callback=None) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        获取点击位置（屏幕坐标）
        参数:
            pair: ((row1, col1), (row2, col2)) 匹配对
            image: 完整截图
            is_region_capture: 是否为区域截图
            log_callback: 日志回调函数
        返回: ((x1, y1), (x2, y2)) 屏幕坐标（相对于截图的坐标，区域截图模式下需要加上capture_region偏移）
        """
        game_image = self.extract_game_region(image, is_region_capture)
        width, height = image.size
        
        if log_callback:
            log_callback(f"[坐标计算] 输入图像尺寸: ({width},{height}), 游戏区域图像尺寸: {game_image.size}, 区域截图模式: {is_region_capture}")
        
        # 如果是区域截图，屏幕偏移为0（因为坐标已经是相对于区域的）
        if is_region_capture:
            screen_offset = (0, 0)
            if log_callback:
                log_callback(f"[坐标计算] 区域截图模式，屏幕偏移设为 (0, 0)，返回的坐标需要加上 capture_region 偏移")
        else:
            # 全屏截图时，需要计算游戏区域的屏幕偏移
            if self.game_region.get("use_absolute", False):
                screen_offset = (int(self.game_region["x"]), int(self.game_region["y"]))
            else:
                screen_offset = (
                    int(self.game_region["x"] * width),
                    int(self.game_region["y"] * height)
                )
            if log_callback:
                log_callback(f"[坐标计算] 全屏截图模式，屏幕偏移: ({screen_offset[0]}, {screen_offset[1]})")
        
        pos1, pos2 = pair
        # 轮廓匹配模式下优先使用轮廓质心点击（更稳，不会点到边框/留白）
        if self.contour_match_enabled and self.contour_cache:
            center1 = self.get_cell_click_point_by_contour(pos1[0], pos1[1], game_image, screen_offset, log_callback)
            center2 = self.get_cell_click_point_by_contour(pos2[0], pos2[1], game_image, screen_offset, log_callback)
        else:
            center1 = self.get_cell_center(pos1[0], pos1[1], game_image, screen_offset, log_callback)
            center2 = self.get_cell_center(pos2[0], pos2[1], game_image, screen_offset, log_callback)
        
        if log_callback:
            log_callback(f"[坐标计算] 返回坐标: pos1={center1}, pos2={center2} (区域截图模式下需要加上 capture_region 偏移)")
        
        return (center1, center2)
    
    def visualize_contour(self, row: int, col: int, cell_image: Image.Image, 
                          contour: np.ndarray, log_callback=None):
        """
        可视化单个单元格的轮廓
        参数:
            row, col: 单元格位置
            cell_image: 单元格图像
            contour: 轮廓数据
            log_callback: 日志回调函数
        """
        try:
            # 创建输出目录
            os.makedirs(self.debug_output_dir, exist_ok=True)
            
            # 将PIL图像转换为numpy数组
            img_array = np.array(cell_image)
            if len(img_array.shape) == 2:
                # 灰度图转RGB
                img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
            elif img_array.shape[2] == 4:
                # RGBA转RGB
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
            
            # 绘制轮廓（绿色，线宽2）
            cv2.drawContours(img_array, [contour], -1, (0, 255, 0), 2)
            
            # 绘制边界矩形（蓝色，线宽1）
            x, y, w, h = cv2.boundingRect(contour)
            cv2.rectangle(img_array, (x, y), (x + w, y + h), (255, 0, 0), 1)
            
            # 计算并显示面积
            area = cv2.contourArea(contour)
            cv2.putText(img_array, f"Area:{int(area)}", (5, 15), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
            
            # 保存图像
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.debug_output_dir, f"cell_{row}_{col}_{timestamp}.png")
            Image.fromarray(img_array).save(filename)
            
            if log_callback:
                log_callback(f"  [可视化] 已保存轮廓图像: {filename}")
        except Exception as e:
            if log_callback:
                log_callback(f"  [可视化] 保存轮廓图像失败: {e}")
    
    def create_contour_grid_visualization(self, game_image: Image.Image, log_callback=None):
        """
        创建整个网格的轮廓可视化图像
        参数:
            game_image: 游戏区域图像
            log_callback: 日志回调函数
        """
        try:
            # 创建输出目录
            os.makedirs(self.debug_output_dir, exist_ok=True)
            
            # 将PIL图像转换为numpy数组
            img_array = np.array(game_image)
            if len(img_array.shape) == 2:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
            elif img_array.shape[2] == 4:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
            
            # 绘制所有轮廓
            for (row, col), contour in self.contour_cache.items():
                # 获取单元格区域
                x, y, w, h = self.get_cell_region(row, col, game_image)
                margin_x, margin_y = self._get_cell_margins(w, h)
                
                # 将轮廓坐标转换为游戏区域坐标
                # 轮廓是相对于“中心裁剪图”的，需要加上单元格偏移 + margin 偏移
                contour_global = contour.copy()
                if len(contour_global.shape) == 3:
                    contour_global[:, :, 0] += (x + margin_x)  # x坐标
                    contour_global[:, :, 1] += (y + margin_y)  # y坐标
                else:
                    # 如果是2D数组，需要reshape
                    contour_global = contour_global.reshape(-1, 1, 2)
                    contour_global[:, :, 0] += (x + margin_x)
                    contour_global[:, :, 1] += (y + margin_y)
                
                # 绘制轮廓（绿色，线宽2）
                cv2.drawContours(img_array, [contour_global], -1, (0, 255, 0), 2)
                
                # 绘制单元格边界（黄色，线宽1）
                cv2.rectangle(img_array, (x, y), (x + w, y + h), (255, 255, 0), 1)
                
                # 绘制位置标签
                label = f"({row},{col})"
                cv2.putText(img_array, label, (x + 5, y + 15), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            
            # 保存合成图像
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.debug_output_dir, f"grid_all_contours_{timestamp}.png")
            Image.fromarray(img_array).save(filename)
            
            if log_callback:
                log_callback(f"[可视化] 已保存网格轮廓合成图像: {filename}")
        except Exception as e:
            if log_callback:
                log_callback(f"[可视化] 创建网格轮廓可视化失败: {e}")
            import traceback
            traceback.print_exc()
    
    def compute_fingerprint(self, cell_image: Image.Image) -> Dict[str, Any]:
        """
        计算单元格图像的指纹（dHash + 颜色分箱 + 边缘密度）
        参数:
            cell_image: 单元格中心裁剪图像
        返回: 指纹字典
        """
        try:
            # 1. dHash（差异哈希，对边缘/形状变化更鲁棒）
            gray = cell_image.convert('L')
            # 缩放到9x8（9列8行，用于计算水平差异）
            small = gray.resize((9, 8), Image.Resampling.LANCZOS)
            pixels = np.array(small)
            hash_bits = []
            for i in range(8):
                for j in range(8):
                    if pixels[i, j] < pixels[i, j + 1]:
                        hash_bits.append('1')
                    else:
                        hash_bits.append('0')
            dhash = ''.join(hash_bits)
            
            # 2. 颜色分箱（RGB均值，排除背景）
            img_array = np.array(cell_image)
            if len(img_array.shape) == 2:
                gray_arr = img_array
                mask = gray_arr < 240
            else:
                gray_arr = np.dot(img_array[..., :3], [0.299, 0.587, 0.114])
                mask = gray_arr < 240
            
            if not np.any(mask):
                mask = np.ones_like(gray_arr, dtype=bool)
            
            if len(img_array.shape) == 3:
                valid_pixels = img_array[mask]
                if len(valid_pixels) > 0:
                    r_mean = int(np.mean(valid_pixels[:, 0]) / 16)  # 16级量化
                    g_mean = int(np.mean(valid_pixels[:, 1]) / 16)
                    b_mean = int(np.mean(valid_pixels[:, 2]) / 16)
                else:
                    r_mean = g_mean = b_mean = 0
            else:
                r_mean = g_mean = b_mean = int(np.mean(gray_arr[mask]) / 16) if np.any(mask) else 0
            
            # 3. 边缘密度（帮助区分物品和空白）
            edges = cv2.Canny(np.array(gray), 50, 150)
            edge_density = np.sum(edges > 0) / (edges.shape[0] * edges.shape[1])
            
            return {
                "dhash": dhash,
                "color": (r_mean, g_mean, b_mean),
                "edge_density": edge_density,
                "area": cell_image.size[0] * cell_image.size[1]
            }
        except Exception as e:
            return {
                "dhash": "",
                "color": (0, 0, 0),
                "edge_density": 0.0,
                "area": 0
            }
    
    def fingerprint_distance(self, fp1: Dict[str, Any], fp2: Dict[str, Any]) -> float:
        """
        计算两个指纹的距离（越小越相似）
        参数:
            fp1, fp2: 指纹字典
        返回: 距离值（0-1之间，0表示完全相同）
        """
        try:
            # 1. dHash汉明距离
            hamming = sum(c1 != c2 for c1, c2 in zip(fp1["dhash"], fp2["dhash"]))
            hamming_norm = hamming / max(len(fp1["dhash"]), 1)  # 归一化到0-1
            
            # 2. 颜色距离（欧氏距离）
            color_dist = np.sqrt(
                sum((a - b) ** 2 for a, b in zip(fp1["color"], fp2["color"]))
            ) / (16 * np.sqrt(3))  # 归一化到0-1
            
            # 3. 边缘密度差异
            edge_diff = abs(fp1["edge_density"] - fp2["edge_density"])
            
            # 加权组合
            total_dist = (
                self.fingerprint_hash_weight * hamming_norm +
                self.fingerprint_color_weight * color_dist +
                0.1 * edge_diff  # 边缘密度权重较小
            )
            
            return total_dist
        except Exception:
            return 1.0
    
    def group_by_fingerprint(self, fingerprints: Dict[Tuple[int, int], Dict[str, Any]], 
                            log_callback=None) -> List[List[Tuple[int, int]]]:
        """
        根据指纹对格子进行分组（相似指纹归为一组）
        参数:
            fingerprints: {(row, col): fingerprint_dict}
            log_callback: 日志回调
        返回: 分组列表，每个组是 [(row, col), ...]
        """
        if not fingerprints:
            return []
        
        positions = list(fingerprints.keys())
        groups = []
        used = set()
        
        # 使用阈值进行分组（避免O(n^2)全量比较，使用最近邻策略）
        threshold = self.fingerprint_hamming_threshold / 64.0  # 转换为归一化阈值
        
        for pos in positions:
            if pos in used:
                continue
            
            # 创建新组
            group = [pos]
            used.add(pos)
            fp = fingerprints[pos]
            
            # 查找相似指纹
            for other_pos in positions:
                if other_pos in used:
                    continue
                
                other_fp = fingerprints[other_pos]
                dist = self.fingerprint_distance(fp, other_fp)
                
                if dist <= threshold:
                    group.append(other_pos)
                    used.add(other_pos)
            
            if len(group) >= self.fingerprint_min_group_size:
                groups.append(group)
        
        if log_callback:
            log_callback(f"[指纹分组] 共 {len(positions)} 个格子，分组得到 {len(groups)} 组（每组至少 {self.fingerprint_min_group_size} 个）")
            for i, group in enumerate(groups):
                log_callback(f"  组 {i+1}: {group} (共{len(group)}个)")
        
        return groups
    
    def find_pairs_by_groups(self, groups: List[List[Tuple[int, int]]], 
                            log_callback=None) -> List[Tuple[Tuple[int, int], Tuple[int, int], float]]:
        """
        从分组中提取所有配对
        参数:
            groups: 分组列表
            log_callback: 日志回调
        返回: [(pos1, pos2, confidence), ...] 配对列表，confidence为置信度（距离的倒数）
        """
        pairs = []
        for group in groups:
            if len(group) < 2:
                continue
            # 每组内两两配对
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    pairs.append((group[i], group[j], 1.0))  # 同组内置信度为1.0
        
        if log_callback:
            log_callback(f"[配对提取] 从 {len(groups)} 组中提取到 {len(pairs)} 个配对")
        
        return pairs


class TemplateLibrary:
    """模板库：自动收集和管理物品模板"""
    
    def __init__(self, base_dir: str = "./material_templates"):
        self.base_dir = base_dir
        self.templates_file = os.path.join(base_dir, "templates.json")
        self.images_dir = os.path.join(base_dir, "images")
        self.templates = {}  # {template_id: template_dict}
        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.images_dir, exist_ok=True)
        self.load()
    
    def load(self):
        """加载模板库"""
        try:
            if os.path.exists(self.templates_file):
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    self.templates = json.load(f)
                print(f"[模板库] 加载了 {len(self.templates)} 个模板")
        except Exception as e:
            print(f"[模板库] 加载失败: {e}")
            self.templates = {}
    
    def save(self):
        """保存模板库"""
        try:
            with open(self.templates_file, 'w', encoding='utf-8') as f:
                json.dump(self.templates, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[模板库] 保存失败: {e}")
    
    def find_best_match(self, fingerprint: Dict[str, Any], threshold: float = 0.2) -> Optional[str]:
        """
        在模板库中查找最佳匹配
        参数:
            fingerprint: 当前指纹
            threshold: 距离阈值
        返回: template_id 或 None
        """
        best_id = None
        best_dist = float('inf')
        
        for template_id, template in self.templates.items():
            template_fp = template.get("fingerprint", {})
            if not template_fp:
                continue
            
            # 计算距离（简化版，只比较dHash和颜色）
            hamming = sum(c1 != c2 for c1, c2 in zip(
                fingerprint.get("dhash", ""),
                template_fp.get("dhash", "")
            )) / max(len(fingerprint.get("dhash", "")), 1)
            
            color_dist = np.sqrt(
                sum((a - b) ** 2 for a, b in zip(
                    fingerprint.get("color", (0, 0, 0)),
                    template_fp.get("color", (0, 0, 0))
                ))
            ) / (16 * np.sqrt(3))
            
            dist = 0.7 * hamming + 0.3 * color_dist
            
            if dist < best_dist and dist <= threshold:
                best_dist = dist
                best_id = template_id
        
        return best_id
    
    def add_template(self, fingerprint: Dict[str, Any], cell_image: Image.Image, 
                     group_size: int = 2, log_callback=None) -> str:
        """
        添加新模板（自动收集）
        参数:
            fingerprint: 指纹
            cell_image: 单元格图像
            group_size: 该物品在本次识别中的出现次数（用于判断置信度）
            log_callback: 日志回调
        返回: template_id
        """
        # 生成模板ID（基于指纹的哈希）
        fp_str = f"{fingerprint.get('dhash', '')}_{fingerprint.get('color', (0,0,0))}"
        template_id = hashlib.md5(fp_str.encode()).hexdigest()[:8]
        
        # 保存图像
        image_filename = os.path.join(self.images_dir, f"{template_id}.png")
        cell_image.save(image_filename)
        
        # 保存模板信息
        self.templates[template_id] = {
            "fingerprint": fingerprint,
            "image_file": image_filename,
            "first_seen": datetime.now().isoformat(),
            "count": group_size,  # 出现次数
            "last_updated": datetime.now().isoformat()
        }
        
        self.save()
        
        if log_callback:
            log_callback(f"[模板库] 新增模板 {template_id}，出现次数: {group_size}")
        
        return template_id
    
    def update_template(self, template_id: str, group_size: int, log_callback=None):
        """更新模板统计信息"""
        if template_id in self.templates:
            self.templates[template_id]["count"] += group_size
            self.templates[template_id]["last_updated"] = datetime.now().isoformat()
            self.save()
            if log_callback:
                log_callback(f"[模板库] 更新模板 {template_id}，总出现次数: {self.templates[template_id]['count']}")