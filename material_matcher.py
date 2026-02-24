"""
材料匹配游戏自动化模块
识别修真材料并自动匹配消除
"""
import time
import numpy as np
from PIL import Image, ImageStat
from typing import List, Tuple, Dict, Optional, Set
from collections import defaultdict


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
        self.grid_rows = 4  # 默认4行
        self.grid_cols = 4  # 默认4列
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
    
    def extract_game_region(self, image: Image.Image) -> Image.Image:
        """
        提取游戏区域
        参数:
            image: 完整截图
        返回: 游戏区域图像
        """
        width, height = image.size
        x = int(self.game_region["x"] * width)
        y = int(self.game_region["y"] * height)
        w = int(self.game_region["w"] * width)
        h = int(self.game_region["h"] * height)
        
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
        cell_width = img_width // self.grid_cols
        cell_height = img_height // self.grid_rows
        
        x = col * cell_width
        y = row * cell_height
        
        return (x, y, cell_width, cell_height)
    
    def get_cell_center(self, row: int, col: int, game_image: Image.Image, 
                       screen_offset: Tuple[int, int] = (0, 0)) -> Tuple[int, int]:
        """
        获取单元格中心坐标（屏幕坐标）
        参数:
            row, col: 行列索引
            game_image: 游戏区域图像
            screen_offset: 游戏区域在屏幕上的偏移量
        返回: (x, y) 屏幕坐标
        """
        img_width, img_height = game_image.size
        cell_width = img_width // self.grid_cols
        cell_height = img_height // self.grid_rows
        
        # 单元格中心（相对于游戏区域）
        center_x = col * cell_width + cell_width // 2
        center_y = row * cell_height + cell_height // 2
        
        # 转换为屏幕坐标
        screen_x = screen_offset[0] + center_x
        screen_y = screen_offset[1] + center_y
        
        return (screen_x, screen_y)
    
    def extract_cell_image(self, row: int, col: int, game_image: Image.Image) -> Image.Image:
        """提取单元格图像"""
        x, y, w, h = self.get_cell_region(row, col, game_image)
        # 稍微缩小一点，避免边框干扰
        margin = 5
        return game_image.crop((x + margin, y + margin, x + w - margin, y + h - margin))
    
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
        计算颜色哈希（基于主要颜色）
        """
        try:
            # 缩放到较小尺寸以加快计算
            small = image.resize((16, 16), Image.Resampling.LANCZOS)
            # 获取主要颜色
            stat = ImageStat.Stat(small)
            # 使用RGB平均值作为特征
            r, g, b = stat.mean
            # 量化到8级
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
    
    def recognize_materials(self, image: Image.Image) -> Optional[Dict[Tuple[int, int], str]]:
        """
        识别材料网格
        参数:
            image: 完整截图
        返回: {(row, col): material_hash} 字典，如果识别失败返回None
        """
        try:
            # 提取游戏区域
            game_image = self.extract_game_region(image)
            
            # 识别每个单元格
            material_grid = {}
            for row in range(self.grid_rows):
                for col in range(self.grid_cols):
                    cell_image = self.extract_cell_image(row, col, game_image)
                    # 检查单元格是否为空（通过检查是否主要是空白）
                    if self.is_cell_empty(cell_image):
                        continue
                    # 计算哈希
                    material_hash = self.calculate_combined_hash(cell_image)
                    material_grid[(row, col)] = material_hash
            
            self.material_grid = material_grid
            return material_grid
        except Exception as e:
            print(f"识别材料失败: {e}")
            return None
    
    def is_cell_empty(self, cell_image: Image.Image, threshold: float = 0.9) -> bool:
        """
        判断单元格是否为空
        参数:
            cell_image: 单元格图像
            threshold: 空白阈值（如果空白像素占比超过此值则认为为空）
        """
        try:
            # 转换为灰度
            gray = cell_image.convert('L')
            # 计算空白像素占比（接近白色的像素）
            pixels = list(gray.getdata())
            white_count = sum(1 for p in pixels if p > 240)
            white_ratio = white_count / len(pixels) if pixels else 0
            return white_ratio > threshold
        except Exception:
            return False
    
    def find_matching_pairs(self, material_grid: Dict[Tuple[int, int], str]) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """
        找到所有匹配的材料对
        参数:
            material_grid: {(row, col): material_hash} 字典
        返回: [(pos1, pos2), ...] 匹配对列表
        """
        # 按材料类型分组
        material_groups = defaultdict(list)
        for pos, material_hash in material_grid.items():
            material_groups[material_hash].append(pos)
        
        # 找到所有匹配对
        pairs = []
        for material_hash, positions in material_groups.items():
            if len(positions) >= 2:
                # 找到所有可能的配对
                for i in range(len(positions)):
                    for j in range(i + 1, len(positions)):
                        pairs.append((positions[i], positions[j]))
        
        return pairs
    
    def find_best_match(self, material_grid: Dict[Tuple[int, int], str]) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """
        找到最佳匹配对（优先选择距离较近的）
        参数:
            material_grid: 材料网格
        返回: (pos1, pos2) 或 None
        """
        pairs = self.find_matching_pairs(material_grid)
        if not pairs:
            return None
        
        # 计算每对的距离，选择距离最近的
        def distance(pos1: Tuple[int, int], pos2: Tuple[int, int]) -> float:
            r1, c1 = pos1
            r2, c2 = pos2
            return ((r1 - r2) ** 2 + (c1 - c2) ** 2) ** 0.5
        
        best_pair = min(pairs, key=lambda p: distance(p[0], p[1]))
        return best_pair
    
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
    
    def get_game_state(self, image: Image.Image) -> Dict:
        """
        获取游戏状态
        参数:
            image: 完整截图
        返回: 游戏状态字典
        """
        state = {
            "score": None,
            "time": None,
            "materials": None,
            "is_game_over": False
        }
        
        try:
            # 识别材料
            materials = self.recognize_materials(image)
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
                           image: Image.Image) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        获取点击位置（屏幕坐标）
        参数:
            pair: ((row1, col1), (row2, col2)) 匹配对
            image: 完整截图
        返回: ((x1, y1), (x2, y2)) 屏幕坐标
        """
        game_image = self.extract_game_region(image)
        width, height = image.size
        screen_offset = (
            int(self.game_region["x"] * width),
            int(self.game_region["y"] * height)
        )
        
        pos1, pos2 = pair
        center1 = self.get_cell_center(pos1[0], pos1[1], game_image, screen_offset)
        center2 = self.get_cell_center(pos2[0], pos2[1], game_image, screen_offset)
        
        return (center1, center2)
