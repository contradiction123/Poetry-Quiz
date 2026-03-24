"""
钓鱼游戏决策算法模块
目标选择、时机计算、碰撞预测
"""
from typing import List, Dict, Optional, Tuple
import math
import time


class FishingDecision:
    """钓鱼决策算法类"""
    
    def __init__(self, config: dict = None):
        """
        初始化决策器
        参数:
            config: 配置字典
        """
        self.config = config or {}
        
        # 鱼竿等级配置
        depth_zones = self.config.get('depth_zones', {})
        self.depth_zones = {
            1: depth_zones.get('level_1', {'min': 0.0, 'max': 0.33}),
            2: depth_zones.get('level_2', {'min': 0.33, 'max': 0.66}),
            3: depth_zones.get('level_3', {'min': 0.66, 'max': 1.0})
        }
        
        # 当前装备等级
        self.rod_level = self.config.get('rod_level', 3)
        self.hook_level = self.config.get('hook_level', 1)
        
        # 鱼钩下降速度（像素/秒），需要根据实际情况调整
        self.hook_speed = self.config.get('hook_speed', 200)  # 默认200像素/秒
        
        # 价值计算权重
        self.depth_weight = self.config.get('depth_weight', 0.7)  # 深度权重
        self.size_weight = self.config.get('size_weight', 0.3)    # 大小权重
    
    def set_rod_level(self, level: int):
        """设置鱼竿等级"""
        self.rod_level = level
    
    def set_hook_level(self, level: int):
        """设置鱼钩等级"""
        self.hook_level = level
    
    def get_reachable_depth_range(self) -> Tuple[float, float]:
        """
        根据鱼竿等级获取可到达的深度范围
        返回: (min_depth, max_depth) 深度比例（0-1）
        """
        zone = self.depth_zones.get(self.rod_level, self.depth_zones[3])
        return (zone['min'], zone['max'])
    
    def calculate_fish_value(self, fish: Dict, water_height: int) -> float:
        """
        计算鱼的价值
        参数:
            fish: 鱼的信息
            water_height: 水域高度
        返回: 价值分数
        """
        # 计算深度（越深价值越高）
        center_y = fish.get('center_y', 0)
        depth_ratio = center_y / water_height if water_height > 0 else 0
        
        # 计算大小（越大价值越高）
        size = fish.get('size', 0)
        max_size = self.config.get('max_fish_area', 5000)
        size_ratio = min(size / max_size, 1.0)
        
        # 综合价值 = 深度权重 * 深度 + 大小权重 * 大小
        value = self.depth_weight * depth_ratio + self.size_weight * size_ratio
        
        return value
    
    def predict_collision(
        self,
        hook_x: float,
        hook_y: float,
        fish: Dict,
        water_height: int,
        debris_list: List[Dict] = None
    ) -> Optional[Dict]:
        """
        预测鱼钩和鱼的碰撞
        参数:
            hook_x, hook_y: 鱼钩当前位置
            fish: 鱼的信息
            water_height: 水域高度
            debris_list: 杂物列表
        返回: 碰撞信息 {
            'collision_point': (x, y),
            'time_to_collision': float,
            'fish_position_at_collision': (x, y),
            'will_hit_debris': bool,
            'debris_hit': Dict or None
        } 或 None（如果无法碰撞）
        """
        # 获取可到达深度范围
        min_depth, max_depth = self.get_reachable_depth_range()
        fish_depth = fish.get('center_y', 0) / water_height if water_height > 0 else 0
        
        # 检查鱼是否在可到达范围内
        if fish_depth < min_depth or fish_depth > max_depth:
            return None
        
        # 获取鱼的移动信息
        fish_x = fish.get('center_x', 0)
        fish_y = fish.get('center_y', 0)
        fish_speed = float(fish.get('speed', 0) or 0)
        fish_vx = float(fish.get('vx', 0) or 0)  # 像素/秒（由 tracker 提供）
        fish_vy = float(fish.get('vy', 0) or 0)
        
        # 计算鱼钩到达鱼的深度所需时间
        target_y = fish_y
        distance_to_target = abs(target_y - hook_y)
        time_to_reach_depth = distance_to_target / self.hook_speed if self.hook_speed > 0 else 0

        # 预测鱼在该时刻的位置：使用 tracker 提供的 vx/vy（真实 dt）
        pred_fish_x = fish_x + fish_vx * time_to_reach_depth
        pred_fish_y = fish_y + fish_vy * time_to_reach_depth

        # 检查是否会碰撞（鱼钩水平位置不变）
        hook_x_at_collision = hook_x
        distance_horizontal = abs(pred_fish_x - hook_x_at_collision)

        fish_width = fish.get('width', 50)
        collision_threshold = fish_width * 1.5  # 1.5倍鱼宽作为碰撞阈值

        # 若缺少速度信息（首帧/刚出现），做保守判断：只在“当前x已对齐”时才判定可碰撞
        if fish_speed <= 0 and abs(fish_vx) <= 1e-6 and abs(fish_vy) <= 1e-6:
            if distance_horizontal > collision_threshold:
                return None

        if distance_horizontal <= collision_threshold:
            # 检查是否会碰到杂物
            will_hit_debris = False
            debris_hit = None

            if debris_list and self.hook_level == 1:  # 低等级鱼钩需要避开杂物
                for debris in debris_list:
                    debris_x = debris.get('center_x', 0)
                    debris_y = debris.get('center_y', 0)

                    # 检查鱼钩路径是否会经过杂物（简化：y范围 + x容差）
                    if min(hook_y, pred_fish_y) <= debris_y <= max(hook_y, pred_fish_y):
                        if abs(debris_x - hook_x_at_collision) < 30:  # 30像素容差
                            will_hit_debris = True
                            debris_hit = debris
                            break

            return {
                'collision_point': (hook_x_at_collision, pred_fish_y),
                'time_to_collision': time_to_reach_depth,
                'fish_position_at_collision': (pred_fish_x, pred_fish_y),
                'will_hit_debris': will_hit_debris,
                'debris_hit': debris_hit,
                'feasible': not (will_hit_debris and self.hook_level == 1)
            }
        
        return None
    
    def select_best_target(
        self,
        fish_list: List[Dict],
        hook_info: Dict,
        water_height: int,
        debris_list: List[Dict] = None
    ) -> Optional[Dict]:
        """
        选择最佳目标鱼
        参数:
            fish_list: 鱼列表
            hook_info: 鱼钩信息
            water_height: 水域高度
            debris_list: 杂物列表
        返回: 最佳目标信息 {
            'fish': Dict,
            'collision_info': Dict,
            'value': float,
            'efficiency': float  # 价值/时间比
        } 或 None
        """
        if not fish_list:
            return None
        
        hook_x = hook_info.get('center_x', 0)
        hook_y = hook_info.get('center_y', 0)
        
        candidates = []
        
        for fish in fish_list:
            # 计算价值
            value = self.calculate_fish_value(fish, water_height)
            
            # 预测碰撞
            collision_info = self.predict_collision(
                hook_x, hook_y, fish, water_height, debris_list
            )
            
            if collision_info and collision_info.get('feasible', True):
                time_to_collision = collision_info.get('time_to_collision', 999)
                
                # 计算效率（价值/时间）
                efficiency = value / time_to_collision if time_to_collision > 0 else 0
                
                candidates.append({
                    'fish': fish,
                    'collision_info': collision_info,
                    'value': value,
                    'efficiency': efficiency,
                    'time_to_collision': time_to_collision
                })
        
        if not candidates:
            return None
        
        # 按效率排序，选择效率最高的
        candidates.sort(key=lambda x: x['efficiency'], reverse=True)
        return candidates[0]
    
    def should_cast_now(
        self,
        target_info: Dict,
        hook_info: Dict
    ) -> bool:
        """
        判断是否应该现在放钩
        参数:
            target_info: 目标信息
            hook_info: 鱼钩信息
        返回: 是否应该放钩
        """
        # 如果鱼钩正在下降，不应该再次放钩
        if hook_info.get('is_dropping', False):
            return False
        
        # 如果找到了可行目标，可以放钩
        if target_info:
            return True
        
        return False
