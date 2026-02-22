"""
屏幕截图模块
使用mss库进行高性能截图
"""
import mss
from PIL import Image
from typing import Optional, Tuple
import os


class ScreenCapture:
    """屏幕截图类"""
    
    def __init__(self):
        """初始化截图实例"""
        pass
    
    def _get_mss(self):
        """获取mss实例"""
        return mss.mss()
    
    def capture_full_screen(self) -> Image.Image:
        """
        全屏截图
        返回: PIL.Image对象
        """
        try:
            with self._get_mss() as sct:
                # 获取主显示器
                monitor = sct.monitors[1]  # 0是所有显示器，1是主显示器
                
                # 截图
                screenshot = sct.grab(monitor)
                
                # 转换为PIL Image
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                
                return img
        except Exception as e:
            raise Exception(f"截图失败: {e}")
    
    def capture_region(self, x: int, y: int, width: int, height: int) -> Image.Image:
        """
        区域截图
        参数:
            x, y: 左上角坐标
            width, height: 宽度和高度
        返回: PIL.Image对象
        """
        try:
            with self._get_mss() as sct:
                monitor = {
                    "top": y,
                    "left": x,
                    "width": width,
                    "height": height
                }
                
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                
                return img
        except Exception as e:
            raise Exception(f"区域截图失败: {e}")
    
    def capture_window(self, window_title: str) -> Optional[Image.Image]:
        """
        捕获指定窗口（需要pygetwindow支持）
        参数:
            window_title: 窗口标题关键词
        返回: PIL.Image对象，如果找不到窗口则返回None
        """
        try:
            import pygetwindow as gw
            
            # 查找窗口
            windows = gw.getWindowsWithTitle(window_title)
            if not windows:
                return None
            
            window = windows[0]
            
            # 获取窗口位置和大小
            monitor = {
                "top": window.top,
                "left": window.left,
                "width": window.width,
                "height": window.height
            }
            
            with self._get_mss() as sct:
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                
                return img
        except Exception as e:
            print(f"窗口截图失败: {e}")
            return None
    
    def save_screenshot(self, image: Image.Image, filepath: str):
        """
        保存截图到文件
        参数:
            image: PIL.Image对象
            filepath: 保存路径
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
            image.save(filepath)
        except Exception as e:
            print(f"保存截图失败: {e}")
    
    def get_screen_size(self) -> Tuple[int, int]:
        """
        获取屏幕尺寸
        返回: (宽度, 高度)
        """
        with self._get_mss() as sct:
            monitor = sct.monitors[1]
            return monitor["width"], monitor["height"]


# 测试代码
if __name__ == "__main__":
    capture = ScreenCapture()
    
    # 测试全屏截图
    print("正在截图...")
    image = capture.capture_full_screen()
    print(f"截图成功，尺寸: {image.size}")
    
    # 测试保存截图
    test_path = "test_screenshot.png"
    capture.save_screenshot(image, test_path)
    print(f"截图已保存到: {test_path}")
    
    # 获取屏幕尺寸
    width, height = capture.get_screen_size()
    print(f"屏幕尺寸: {width}x{height}")
