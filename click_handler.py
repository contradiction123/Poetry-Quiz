"""
点击控制模块
使用pyautogui模拟鼠标点击
"""
import pyautogui
import time
from typing import Tuple
from config import Config


class ClickHandler:
    """鼠标点击控制类"""
    
    def __init__(self, config: Config = None):
        """
        初始化点击处理器
        参数:
            config: 配置对象，如果为None则创建新实例
        """
        if config is None:
            config = Config()
        self.config = config
        
        self.delay_before = self.config.get('click.delay_before_click', 0.5)
        self.delay_after = self.config.get('click.delay_after_click', 1.0)
        self.click_duration = self.config.get('click.click_duration', 0.1)
        
        # 设置pyautogui安全设置
        pyautogui.FAILSAFE = True  # 鼠标移到屏幕角落会触发异常，防止失控
        pyautogui.PAUSE = 0.1  # 每次操作后暂停0.1秒
    
    def click(self, x: int, y: int, button: str = 'left'):
        """
        在指定坐标点击
        参数:
            x, y: 点击坐标
            button: 'left' 或 'right'，默认为 'left'
        """
        try:
            # 点击前延迟
            if self.delay_before > 0:
                time.sleep(self.delay_before)
            
            # 执行点击
            pyautogui.click(x, y, button=button, duration=self.click_duration)
            
            # 点击后延迟
            if self.delay_after > 0:
                time.sleep(self.delay_after)
        except Exception as e:
            raise Exception(f"点击失败: {e}")
    
    def click_option(self, option_center: Tuple[int, int]):
        """
        点击选项
        参数:
            option_center: (x, y) 坐标元组
        """
        self.click(option_center[0], option_center[1])
    
    def safe_click(self, x: int, y: int, max_retry: int = 3) -> bool:
        """
        安全点击（带重试）
        参数:
            x, y: 点击坐标
            max_retry: 最大重试次数
        返回:
            bool: 是否成功
        """
        for i in range(max_retry):
            try:
                self.click(x, y)
                return True
            except Exception as e:
                if i == max_retry - 1:
                    print(f"点击失败，已重试{max_retry}次: {e}")
                    return False
                time.sleep(0.5)
        return False
    
    def move_to(self, x: int, y: int, duration: float = 0.5):
        """
        移动鼠标到指定位置（不点击）
        参数:
            x, y: 目标坐标
            duration: 移动持续时间（秒）
        """
        try:
            pyautogui.moveTo(x, y, duration=duration)
        except Exception as e:
            raise Exception(f"移动鼠标失败: {e}")
    
    def get_mouse_position(self) -> Tuple[int, int]:
        """
        获取当前鼠标位置
        返回:
            (x, y): 鼠标坐标
        """
        return pyautogui.position()


# 测试代码
if __name__ == "__main__":
    print("点击控制模块测试")
    print("注意：此测试会实际移动和点击鼠标，请小心！")
    
    handler = ClickHandler()
    
    # 获取当前鼠标位置
    pos = handler.get_mouse_position()
    print(f"当前鼠标位置: {pos}")
    
    # 测试移动鼠标（不点击）
    print("\n3秒后将鼠标移动到屏幕中心...")
    time.sleep(3)
    
    import pyautogui
    screen_width, screen_height = pyautogui.size()
    center_x = screen_width // 2
    center_y = screen_height // 2
    
    handler.move_to(center_x, center_y)
    print(f"鼠标已移动到屏幕中心: ({center_x}, {center_y})")
    
    print("\n测试完成。如需测试点击功能，请取消下面的注释：")
    # handler.click(center_x, center_y)
    # print("已点击屏幕中心")
