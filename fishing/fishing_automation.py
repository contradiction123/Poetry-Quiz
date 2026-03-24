"""
钓鱼游戏自动化核心模块
整合识别、跟踪、决策、数据记录等功能
"""
from typing import Dict, Optional, Callable
from PIL import Image
import time

from .fishing_detector import FishingDetector
from .fishing_tracker import FishTracker, HookTracker
from .fishing_decision import FishingDecision
from .fishing_database import FishingDatabase


class FishingAutomation:
    """钓鱼游戏自动化类"""
    
    def __init__(self, config: dict = None):
        """
        初始化自动化系统
        参数:
            config: 配置字典
        """
        self.config = config or {}
        
        # 初始化各个模块
        self.detector = FishingDetector(config)
        self.fish_tracker = FishTracker(max_history=10)
        hook_track_cfg = (self.config.get('hook_tracking', {}) or {})
        self.hook_tracker = HookTracker(
            miss_grace_seconds=hook_track_cfg.get('miss_grace_seconds', 0.6),
            drop_threshold_px=hook_track_cfg.get('drop_threshold_px', 5.0)
        )
        self.decision = FishingDecision(config)
        self.database = FishingDatabase(
            self.config.get('database_path', 'fishing_records.db')
        )
        
        # 游戏状态
        self.current_score = 0
        self.total_fish_caught = 0
        
        # 日志回调函数
        self.log_callback: Optional[Callable[[str], None]] = None
    
    def set_log_callback(self, callback: Callable[[str], None]):
        """设置日志回调函数"""
        self.log_callback = callback
    
    def log(self, message: str):
        """输出日志"""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(f"[FishingAutomation] {message}")
    
    def get_game_state(self, image: Image.Image, is_region_capture: bool = False) -> Dict:
        """
        获取游戏状态
        参数:
            image: 截图
            is_region_capture: 是否为区域截图
        返回: 游戏状态字典
        """
        # 提取水域区域
        water_image = self.detector.extract_water_region(image)
        water_height = water_image.height
        
        # 识别鱼
        fish_list = self.detector.detect_fish(water_image)
        self.log(f"识别到 {len(fish_list)} 条鱼")
        
        # 跟踪鱼的运动
        timestamp = time.time()
        enhanced_fish = self.fish_tracker.update(fish_list, timestamp)
        
        # 识别鱼钩
        hook_info = self.detector.detect_hook(water_image)
        enhanced_hook = self.hook_tracker.update(hook_info, timestamp)
        
        # 识别特殊物品
        special_items = self.detector.detect_special_items(water_image)
        
        # 计算每条鱼的深度
        for fish in enhanced_fish:
            fish['depth'] = self.fish_tracker.calculate_depth(fish, water_height)
        
        return {
            'fish': enhanced_fish,
            'hook': enhanced_hook,
            'special_items': special_items,
            'water_height': water_height,
            'timestamp': timestamp
        }
    
    def make_decision(self, game_state: Dict) -> Optional[Dict]:
        """
        做出决策
        参数:
            game_state: 游戏状态
        返回: 决策信息 {
            'action': 'cast' or 'wait',
            'target': Dict or None,
            'reason': str
        }
        """
        fish_list = game_state.get('fish', [])
        hook_info = game_state.get('hook', {})
        water_height = game_state.get('water_height', 1)
        debris_list = game_state.get('special_items', {}).get('debris', [])
        
        # 如果鱼钩正在下降，等待
        if hook_info.get('is_dropping', False):
            return {
                'action': 'wait',
                'target': None,
                'reason': '鱼钩正在下降中'
            }
        
        # 选择最佳目标
        target_info = self.decision.select_best_target(
            fish_list, hook_info, water_height, debris_list
        )
        
        if target_info:
            fish = target_info['fish']
            collision_info = target_info['collision_info']
            
            # 检查是否会碰到杂物（低等级鱼钩）
            if collision_info.get('will_hit_debris', False) and self.decision.hook_level == 1:
                return {
                    'action': 'wait',
                    'target': None,
                    'reason': '目标路径上有杂物，低等级鱼钩无法穿过'
                }
            
            return {
                'action': 'cast',
                'target': target_info,
                'reason': f"选择目标鱼 (价值: {target_info['value']:.2f}, 效率: {target_info['efficiency']:.2f})"
            }
        else:
            return {
                'action': 'wait',
                'target': None,
                'reason': '未找到合适的目标'
            }
    
    def record_game_data(
        self,
        game_state: Dict,
        decision: Dict,
        result: Dict
    ):
        """
        记录游戏数据
        参数:
            game_state: 游戏状态
            decision: 决策信息
            result: 结果信息
        """
        rod_level = self.decision.rod_level
        hook_level = self.decision.hook_level
        score = result.get('score_gained', 0)
        
        # 准备游戏状态数据（简化版，只保留关键信息）
        game_state_data = {
            'fish_count': len(game_state.get('fish', [])),
            'hook_detected': game_state.get('hook', {}).get('detected', False),
            'special_items_count': {
                'scare': len(game_state.get('special_items', {}).get('scare_items', [])),
                'freeze': len(game_state.get('special_items', {}).get('freeze_items', [])),
                'debris': len(game_state.get('special_items', {}).get('debris', []))
            }
        }
        
        # 准备决策数据
        decision_data = {
            'action': decision.get('action'),
            'target_fish_id': decision.get('target', {}).get('fish', {}).get('id') if decision.get('target') else None,
            'reason': decision.get('reason')
        }
        
        # 记录到数据库
        try:
            self.database.add_record(
                rod_level=rod_level,
                hook_level=hook_level,
                game_state=game_state_data,
                decision=decision_data,
                result=result,
                score=score
            )
        except Exception as e:
            self.log(f"记录数据失败: {e}")
    
    def set_rod_level(self, level: int):
        """设置鱼竿等级"""
        self.decision.set_rod_level(level)
        self.log(f"鱼竿等级已设置为: {level}")
    
    def set_hook_level(self, level: int):
        """设置鱼钩等级"""
        self.decision.set_hook_level(level)
        self.log(f"鱼钩等级已设置为: {level}")
    
    def get_fishing_icon_position(self, image: Image.Image) -> Optional[tuple]:
        """
        获取鱼竿图标位置（用于点击）
        参数:
            image: 截图
        返回: (x, y) 或 None
        """
        fishing_icon_region = self.config.get('fishing_icon_region', {})
        if not fishing_icon_region:
            return None
        
        width, height = image.size
        x = int(width * fishing_icon_region.get('x', 0.85))
        y = int(height * fishing_icon_region.get('y', 0.85))
        w = int(width * fishing_icon_region.get('width', 0.1))
        h = int(height * fishing_icon_region.get('height', 0.1))
        
        # 返回图标中心位置
        return (x + w // 2, y + h // 2)
    
    def reset(self):
        """重置状态"""
        self.fish_tracker.clear_history()
        self.hook_tracker.reset()
        self.current_score = 0
        self.total_fish_caught = 0
