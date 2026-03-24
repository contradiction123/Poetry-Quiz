"""
钓鱼游戏运动跟踪模块
跟踪鱼的运动轨迹，计算速度和方向
"""
from typing import List, Dict, Optional, Tuple
import time
import math


class FishTracker:
    """鱼的运动跟踪类"""
    
    def __init__(self, max_history: int = 10):
        """
        初始化跟踪器
        参数:
            max_history: 保留的历史帧数
        """
        self.max_history = max_history
        # 存储每条鱼(轨迹)的历史位置 {(track_id): [(timestamp, x, y), ...]}
        self.fish_history: Dict[int, List[Tuple[float, float, float]]] = {}
        # 轨迹最近一次出现 {(track_id): timestamp}
        self.last_seen: Dict[int, float] = {}
        # 轨迹下一可用 id
        self._next_track_id: int = 1
        # 关联阈值（像素）：新检测点与已有轨迹的最大匹配距离
        self.max_match_distance: float = 120.0
        # 当前帧的时间戳
        self.current_time = time.time()
    
    def update(self, fish_list: List[Dict], timestamp: float = None) -> List[Dict]:
        """
        更新鱼的位置并计算运动信息
        参数:
            fish_list: 当前帧检测到的鱼列表
            timestamp: 当前时间戳，如果为None则使用当前时间
        返回: 增强的鱼列表，包含 direction, speed, depth 等信息
        """
        if timestamp is None:
            timestamp = time.time()
        
        self.current_time = timestamp
        
        enhanced_fish = []

        # -------- 1) 用“最近邻”把本帧检测结果关联到已有轨迹，生成稳定 track_id --------
        detections: List[Tuple[int, float, float]] = []
        for i, fish in enumerate(fish_list):
            detections.append((i, float(fish.get('center_x', 0)), float(fish.get('center_y', 0))))

        # 当前活跃轨迹（最近 2 秒出现过）
        active_track_ids: List[int] = [
            tid for tid, last_t in self.last_seen.items()
            if (timestamp - last_t) <= 2.0 and tid in self.fish_history and self.fish_history[tid]
        ]

        track_last_pos: Dict[int, Tuple[float, float]] = {}
        for tid in active_track_ids:
            _, lx, ly = self.fish_history[tid][-1]
            track_last_pos[tid] = (lx, ly)

        # 计算所有 (track, det) 距离并按距离排序，做贪心匹配
        pairs: List[Tuple[float, int, int]] = []
        for tid, (tx, ty) in track_last_pos.items():
            for det_idx, dx, dy in detections:
                dist = math.hypot(dx - tx, dy - ty)
                pairs.append((dist, tid, det_idx))
        pairs.sort(key=lambda x: x[0])

        assigned_tracks: Dict[int, int] = {}  # det_idx -> track_id
        used_tracks: set = set()
        used_dets: set = set()
        for dist, tid, det_idx in pairs:
            if dist > self.max_match_distance:
                break
            if tid in used_tracks or det_idx in used_dets:
                continue
            used_tracks.add(tid)
            used_dets.add(det_idx)
            assigned_tracks[det_idx] = tid

        # 未匹配的 detection 新建轨迹
        for det_idx, _, _ in detections:
            if det_idx not in assigned_tracks:
                assigned_tracks[det_idx] = self._next_track_id
                self._next_track_id += 1

        # -------- 2) 更新轨迹历史并计算运动学信息（dx/dy, vx/vy, speed, direction）--------
        for det_idx, center_x, center_y in detections:
            fish = fish_list[det_idx]
            track_id = assigned_tracks[det_idx]

            if track_id not in self.fish_history:
                self.fish_history[track_id] = []
            self.fish_history[track_id].append((timestamp, center_x, center_y))
            if len(self.fish_history[track_id]) > self.max_history:
                self.fish_history[track_id].pop(0)
            self.last_seen[track_id] = timestamp

            # 用稳定 track_id 覆盖/输出（后续决策/记录用这个 id 才有意义）
            fish['id'] = track_id
            fish['track_id'] = track_id

            history = self.fish_history[track_id]
            if len(history) >= 2:
                prev_time, prev_x, prev_y = history[-2]
                curr_time, curr_x, curr_y = history[-1]
                dt = curr_time - prev_time
                if dt > 0:
                    dx = curr_x - prev_x
                    dy = curr_y - prev_y
                    vx = dx / dt
                    vy = dy / dt
                    speed = math.hypot(vx, vy)

                    if vx != 0 or vy != 0:
                        angle = math.degrees(math.atan2(vy, vx))
                        if angle < 0:
                            angle += 360
                    else:
                        angle = 0

                    if abs(vx) > abs(vy):
                        direction = 'right' if vx > 0 else 'left'
                    else:
                        direction = 'down' if vy > 0 else 'up'

                    fish['direction'] = direction
                    fish['speed'] = speed
                    fish['angle'] = angle
                    # dx/dy 仍保留“本帧位移”，vx/vy 是“像素/秒”
                    fish['dx'] = dx
                    fish['dy'] = dy
                    fish['vx'] = vx
                    fish['vy'] = vy
                    fish['dt'] = dt
                else:
                    fish['direction'] = 'unknown'
                    fish['speed'] = 0
                    fish['angle'] = 0
                    fish['dx'] = 0
                    fish['dy'] = 0
                    fish['vx'] = 0
                    fish['vy'] = 0
                    fish['dt'] = 0
            else:
                fish['direction'] = 'unknown'
                fish['speed'] = 0
                fish['angle'] = 0
                fish['dx'] = 0
                fish['dy'] = 0
                fish['vx'] = 0
                fish['vy'] = 0
                fish['dt'] = 0

            enhanced_fish.append(fish)

        # -------- 3) 清理过期轨迹 --------
        expired_ids = [
            tid for tid, last_t in self.last_seen.items()
            if (timestamp - last_t) > 2.0
        ]
        for tid in expired_ids:
            self.last_seen.pop(tid, None)
            self.fish_history.pop(tid, None)

        return enhanced_fish
    
    def predict_position(self, fish: Dict, future_time: float) -> Optional[Tuple[float, float]]:
        """
        预测鱼在未来时间的位置
        参数:
            fish: 鱼的信息（包含 speed, dx, dy 等）
            future_time: 未来时间（秒）
        返回: (x, y) 预测位置，如果无法预测则返回None
        """
        if 'speed' not in fish or fish['speed'] == 0:
            return None
        
        center_x = fish.get('center_x', 0)
        center_y = fish.get('center_y', 0)
        
        # 使用当前速度预测
        dx = fish.get('dx', 0)
        dy = fish.get('dy', 0)
        
        # 计算单位时间内的位移
        history = self.fish_history.get(fish.get('id'), [])
        if len(history) >= 2:
            prev_time, prev_x, prev_y = history[-2]
            curr_time, curr_x, curr_y = history[-1]
            dt = curr_time - prev_time
            
            if dt > 0:
                # 计算速度向量
                vx = dx / dt
                vy = dy / dt
                
                # 预测未来位置
                pred_x = center_x + vx * future_time
                pred_y = center_y + vy * future_time
                
                return (pred_x, pred_y)
        
        return None
    
    def calculate_depth(self, fish: Dict, water_height: int) -> float:
        """
        计算鱼的深度（相对深度，0-1）
        参数:
            fish: 鱼的信息
            water_height: 水域高度（像素）
        返回: 深度比例（0-1），0表示最上层，1表示最下层
        """
        center_y = fish.get('center_y', 0)
        # 假设水域从y=0开始
        depth_ratio = center_y / water_height if water_height > 0 else 0
        return min(max(depth_ratio, 0.0), 1.0)
    
    def clear_history(self):
        """清空所有历史记录"""
        self.fish_history.clear()


class HookTracker:
    """鱼钩跟踪类"""
    
    def __init__(self, miss_grace_seconds: float = 0.6, drop_threshold_px: float = 5.0):
        """初始化鱼钩跟踪器
        参数:
            miss_grace_seconds: 允许短时间漏检而不重置状态（秒）
            drop_threshold_px: y 方向移动超过该阈值才认为状态变化（像素）
        """
        self.hook_history = []  # [(timestamp, x, y), ...]
        self.is_dropping = False
        self.drop_start_time = None
        self.last_position = None
        self.last_seen_time: Optional[float] = None
        self.miss_grace_seconds = float(miss_grace_seconds)
        self.drop_threshold_px = float(drop_threshold_px)
    
    def update(self, hook_info: Optional[Dict], timestamp: float = None) -> Dict:
        """
        更新鱼钩状态
        参数:
            hook_info: 鱼钩信息，如果为None表示未检测到
            timestamp: 当前时间戳
        返回: 增强的鱼钩信息，包含 is_dropping, drop_time 等
        """
        if timestamp is None:
            timestamp = time.time()
        
        if hook_info is None:
            # 未检测到鱼钩：允许短时间漏检，避免 dropping 状态抖动
            if self.last_seen_time is not None and (timestamp - self.last_seen_time) <= self.miss_grace_seconds:
                drop_time = 0
                if self.is_dropping and self.drop_start_time:
                    drop_time = timestamp - self.drop_start_time
                return {
                    'detected': False,
                    'is_dropping': self.is_dropping,
                    'drop_time': drop_time
                }

            # 漏检超过宽限时间才重置
            self.is_dropping = False
            self.drop_start_time = None
            self.last_position = None
            self.last_seen_time = None
            return {'detected': False, 'is_dropping': False}
        
        center_x = hook_info.get('center_x', 0)
        center_y = hook_info.get('center_y', 0)
        current_pos = (center_x, center_y)
        self.last_seen_time = timestamp
        
        # 判断是否在下降
        if self.last_position is not None:
            last_x, last_y = self.last_position
            # 如果y坐标增加（向下移动），说明在下降
            if center_y > last_y + self.drop_threshold_px:
                if not self.is_dropping:
                    self.is_dropping = True
                    self.drop_start_time = timestamp
            elif center_y < last_y - self.drop_threshold_px:  # 向上移动，说明在上升（可能钓到鱼了）
                self.is_dropping = False
                self.drop_start_time = None
        
        self.last_position = current_pos
        
        # 计算下降时间
        drop_time = 0
        if self.is_dropping and self.drop_start_time:
            drop_time = timestamp - self.drop_start_time
        
        result = {
            'detected': True,
            'is_dropping': self.is_dropping,
            'drop_time': drop_time,
            'center_x': center_x,
            'center_y': center_y,
            **hook_info
        }
        
        return result
    
    def reset(self):
        """重置跟踪状态"""
        self.is_dropping = False
        self.drop_start_time = None
        self.last_position = None
        self.last_seen_time = None
        self.hook_history.clear()
