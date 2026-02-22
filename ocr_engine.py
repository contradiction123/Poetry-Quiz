"""
OCR识别模块
使用 PaddleOCR(PaddleX Pipeline) 进行文字识别

性能优化点：
- 支持开启 MKL-DNN(oneDNN) 与设置 CPU 线程数（CPU 下可显著提速）
- 失败自动回退（加速不可用时仍能工作）
- 将旧参数 use_angle_cls 映射为 use_textline_orientation（可按需关闭提速）
"""

import os
from PIL import Image
from typing import List, Tuple, Dict, Optional, Any
import numpy as np


class OCREngine:
    """OCR识别引擎"""
    
    def __init__(
        self,
        language: str = 'ch',
        use_angle_cls: bool = True,
        use_gpu: bool = False,
        *,
        device: str = "cpu",
        ocr_version: Optional[str] = None,
        fast_rec: Optional[Dict[str, Any]] = None,
        enable_mkldnn: Optional[bool] = None,
        mkldnn_cache_capacity: int = 10,
        cpu_threads: Optional[int] = None,
        enable_hpi: Optional[bool] = None,
        text_det_limit_side_len: Optional[int] = None,
        text_det_limit_type: Optional[str] = None,
        input_max_side: Optional[int] = None,
        input_scale: Optional[float] = None,
        debug_timing: bool = False,
    ):
        """
        初始化OCR引擎
        参数:
            language: 识别语言，'ch'表示中文
            use_angle_cls: 是否使用角度分类器（PaddleOCR 3.4.0已移除此参数，保留用于兼容）
            use_gpu: 是否使用GPU加速（PaddleOCR 3.4.0已移除此参数，保留用于兼容）
            device: 推理设备，通常为 "cpu" 或 "gpu"
            enable_mkldnn: 是否开启 MKL-DNN(oneDNN)（CPU 下可提速）。None 表示使用库默认值
            mkldnn_cache_capacity: MKL-DNN cache 容量
            cpu_threads: CPU 推理线程数。None 表示使用库默认值
            enable_hpi: 是否开启高性能推理（HPI）。None 表示使用库默认值
            text_det_limit_side_len/text_det_limit_type: 文本检测输入限制（可选）
        """
        # 记录推理参数（供 predict 时使用）
        self.language = language
        self.device = device
        self.ocr_version = ocr_version
        self.use_textline_orientation = bool(use_angle_cls)
        self.text_det_limit_side_len = text_det_limit_side_len
        self.text_det_limit_type = text_det_limit_type
        self.input_max_side = input_max_side
        self.input_scale = input_scale
        self.debug_timing = bool(debug_timing)
        self.last_timing: Dict[str, float] = {}

        # fast_rec（方案C）：固定ROI裁剪 + 仅识别(rec-only)
        self.fast_rec_cfg = fast_rec or {}
        self.fast_rec_enabled = bool(self.fast_rec_cfg.get("enabled", False))
        self.fast_rec_last: Dict[str, Any] = {}
        self._text_rec = None

        # Paddle / PaddleX 在 import 时会读取部分 flags；这里延迟 import，允许我们先设置 env
        # PIR 相关：保留关闭以减少兼容问题
        os.environ.setdefault("FLAGS_enable_pir_api", "0")
        os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")

        # 如显式关闭 MKL-DNN，则通过 env + paddle flags 双重关闭，避免被默认值打开
        if enable_mkldnn is False:
            os.environ["FLAGS_use_mkldnn"] = "0"

        print("正在初始化OCR引擎，首次运行会下载模型文件，请稍候...")
        try:
            import paddle  # noqa: F401
            from paddleocr import PaddleOCR

            # 尽量按用户配置设置 paddle flags（仅在可用时）
            if enable_mkldnn is False:
                try:
                    paddle.set_flags({"FLAGS_use_mkldnn": 0})
                except Exception:
                    pass

            self.ocr = self._create_ocr(
                PaddleOCR,
                lang=language,
                device=device,
                ocr_version=ocr_version,
                enable_mkldnn=enable_mkldnn,
                mkldnn_cache_capacity=mkldnn_cache_capacity,
                cpu_threads=cpu_threads,
                enable_hpi=enable_hpi,
            )

            # 初始化 fast_rec（失败允许回退）
            if self.fast_rec_enabled:
                try:
                    self._init_fast_rec(
                        language=language,
                        enable_mkldnn=enable_mkldnn,
                        mkldnn_cache_capacity=mkldnn_cache_capacity,
                        cpu_threads=cpu_threads,
                        enable_hpi=enable_hpi,
                    )
                except Exception:
                    # 不抛出，运行时会自动回退到全流程OCR
                    self._text_rec = None
            print("OCR引擎初始化完成")
        except Exception as e:
            raise Exception(f"OCR引擎初始化失败: {e}")

    def _init_fast_rec(
        self,
        *,
        language: str,
        enable_mkldnn: Optional[bool],
        mkldnn_cache_capacity: int,
        cpu_threads: Optional[int],
        enable_hpi: Optional[bool],
    ):
        """
        初始化 rec-only 识别器（TextRecognition）。失败时不影响全流程OCR。
        """
        # 延迟 import：避免未安装依赖时影响主OCR初始化
        from paddleocr import TextRecognition

        model_name = self.fast_rec_cfg.get("model_name") or "PP-OCRv4_mobile_rec"
        device = self.fast_rec_cfg.get("device") or "cpu"
        # gpu 优先失败回退 cpu
        devices_to_try = [device]
        if device.startswith("gpu") and "cpu" not in devices_to_try:
            devices_to_try.append("cpu")

        last_err = None
        for dev in devices_to_try:
            try:
                kwargs: Dict[str, Any] = {
                    "model_name": model_name,
                    "device": dev,
                }
                if enable_hpi is not None:
                    kwargs["enable_hpi"] = enable_hpi
                if cpu_threads is not None:
                    kwargs["cpu_threads"] = cpu_threads
                if enable_mkldnn is not None:
                    kwargs["enable_mkldnn"] = enable_mkldnn
                    if enable_mkldnn:
                        kwargs["mkldnn_cache_capacity"] = mkldnn_cache_capacity
                self._text_rec = TextRecognition(**kwargs)
                # 记录实际设备（便于日志）
                self.fast_rec_cfg["device_used"] = dev
                return
            except Exception as e:
                last_err = e
                continue

        raise RuntimeError(f"fast_rec 初始化失败: {last_err}")

    def _default_fast_rois(self) -> Dict[str, Dict[str, float]]:
        """
        基于当前界面布局的默认 ROI（相对坐标 0~1）。
        这些值可在 config.json 的 ocr.fast_rec.rois 中覆盖。
        """
        return {
            "title": {"x": 0.06, "y": 0.02, "w": 0.88, "h": 0.12},
            "question": {"x": 0.06, "y": 0.14, "w": 0.88, "h": 0.22},
            "A": {"x": 0.04, "y": 0.46, "w": 0.44, "h": 0.20},
            "B": {"x": 0.52, "y": 0.46, "w": 0.44, "h": 0.20},
            "C": {"x": 0.04, "y": 0.70, "w": 0.44, "h": 0.20},
            "D": {"x": 0.52, "y": 0.70, "w": 0.44, "h": 0.20},
        }

    def _clip01(self, v: float) -> float:
        if v < 0.0:
            return 0.0
        if v > 1.0:
            return 1.0
        return v

    def _roi_abs_box(self, roi: Dict[str, float], w: int, h: int) -> Tuple[int, int, int, int]:
        x = int(self._clip01(float(roi.get("x", 0))) * w)
        y = int(self._clip01(float(roi.get("y", 0))) * h)
        rw = int(self._clip01(float(roi.get("w", 1))) * w)
        rh = int(self._clip01(float(roi.get("h", 1))) * h)
        x2 = max(x + 1, min(w, x + rw))
        y2 = max(y + 1, min(h, y + rh))
        x1 = max(0, min(w - 1, x))
        y1 = max(0, min(h - 1, y))
        return x1, y1, x2, y2

    def _box_to_quad(self, x1: int, y1: int, x2: int, y2: int) -> List[List[int]]:
        return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]

    def _strip_option_prefix(self, s: str) -> str:
        import re

        s = (s or "").strip()
        if not s:
            return s
        s = s.replace("．", ".").replace("：", ":")
        s = re.sub(r"^[ABCDabcd][\.\、:：\s]*", "", s).strip()
        s = re.sub(r"^[1-4][\.\、:：\s]*", "", s).strip()
        s = re.sub(r"^(IV|III|II|I)[\.\、:：\s]*", "", s, flags=re.IGNORECASE).strip()
        return s

    def recognize_fast_rec(self, image: Image.Image) -> Optional[Dict[str, Any]]:
        """
        方案C：固定ROI裁剪 + rec-only。\n
        成功返回：{\n
          question: str,\n
          options: {A:{text,center,text_center,score}, ...},\n
          ocr_results: [(text, bbox), ...],\n
          timing: {total, rec_only, crop_to_np}\n
        }\n
        失败返回 None（调用方应回退到全流程OCR）
        """
        if not self.fast_rec_enabled or self._text_rec is None:
            return None

        import time

        t_all0 = time.perf_counter()
        w, h = image.size

        rois_cfg = self.fast_rec_cfg.get("rois") or {}
        rois = self._default_fast_rois()
        # 覆盖默认
        for k, v in rois_cfg.items():
            if isinstance(v, dict) and k in rois:
                rois[k] = {**rois[k], **v}

        order = ["title", "question", "A", "B", "C", "D"]
        crop_imgs_bgr = []
        boxes = {}

        t_crop0 = time.perf_counter()
        for name in order:
            box = self._roi_abs_box(rois[name], w, h)
            boxes[name] = box
            x1, y1, x2, y2 = box
            crop = image.crop((x1, y1, x2, y2))
            # TextRec 的 ReadImage(format="RGB") 会把输入当 BGR 再转 RGB，所以这里传 BGR
            arr_rgb = np.array(crop)
            if arr_rgb.ndim == 3 and arr_rgb.shape[2] >= 3:
                arr_bgr = arr_rgb[:, :, ::-1].copy()
            else:
                # 灰度图也兼容
                arr_bgr = arr_rgb.copy()
            crop_imgs_bgr.append(arr_bgr)
        t_crop1 = time.perf_counter()

        # 批量 rec-only
        batch_size = int(self.fast_rec_cfg.get("batch_size", len(crop_imgs_bgr)) or len(crop_imgs_bgr))
        t_rec0 = time.perf_counter()
        rec_results = self._text_rec.predict(crop_imgs_bgr, batch_size=batch_size)
        t_rec1 = time.perf_counter()

        # 解析结果
        texts: Dict[str, str] = {}
        scores: Dict[str, float] = {}
        for name, res in zip(order, rec_results):
            try:
                txt = (res.get("rec_text") if hasattr(res, "get") else res["rec_text"])  # type: ignore[index]
                sc = (res.get("rec_score") if hasattr(res, "get") else res["rec_score"])  # type: ignore[index]
            except Exception:
                txt = ""
                sc = 0.0
            texts[name] = (txt or "").strip()
            try:
                scores[name] = float(sc) if sc is not None else 0.0
            except Exception:
                scores[name] = 0.0

        def looks_valid_text(s: str) -> bool:
            # 经验规则：包含中文（或较长的非空文本）就认为可用，避免因为 score 偏低而回退
            s = (s or "").strip()
            if not s:
                return False
            cjk = sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff")
            return cjk >= 2 or len(s) >= 4

        min_score = float(self.fast_rec_cfg.get("min_score", 0.5) or 0.5)
        # 关键字段：允许 score 低，但文本看起来有效时不回退
        critical = ["question", "A", "B", "C", "D"]
        low_keys = []
        invalid_keys = []
        for k in critical:
            raw = texts.get(k, "")
            cleaned = self._strip_option_prefix(raw)
            if scores.get(k, 0.0) < min_score:
                low_keys.append(k)
            if not looks_valid_text(cleaned):
                invalid_keys.append(k)

        # 只有在“文本明显无效”时才回退；否则即使低分也继续走 fast_rec
        if invalid_keys:
            self.fast_rec_last = {
                "ok": False,
                "reason": f"low_score_invalid:{','.join(invalid_keys)}",
                "texts": texts,
                "scores": scores,
                "min_score": min_score,
            }
            return None

        question_text = self._strip_option_prefix(texts.get("question", ""))

        # options 按固定位置映射 A/B/C/D
        options = {}
        for key in ["A", "B", "C", "D"]:
            x1, y1, x2, y2 = boxes[key]
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            # 点击点向下轻微偏移（沿用现有 offset_y 思路，但不在引擎里强耦合配置）
            options[key] = {
                "text": self._strip_option_prefix(texts.get(key, "")),
                "text_center": (cx, cy),
                "center": (cx, cy),  # main.py 会再根据 click.offset_y 做偏移
                "score": scores.get(key, 0.0),
            }

        # 输出兼容的伪 ocr_results，便于沿用日志与后续处理
        ocr_results: List[Tuple[str, List[List[int]]]] = []
        for name in order:
            x1, y1, x2, y2 = boxes[name]
            ocr_results.append((texts.get(name, ""), self._box_to_quad(x1, y1, x2, y2)))

        t_all1 = time.perf_counter()
        timing = {
            "crop_to_np": t_crop1 - t_crop0,
            "rec_only": t_rec1 - t_rec0,
            "total": t_all1 - t_all0,
        }

        self.fast_rec_last = {
            "ok": True,
            "texts": texts,
            "scores": scores,
            "timing": timing,
            "device_used": self.fast_rec_cfg.get("device_used") or self.fast_rec_cfg.get("device"),
            "model_name": self.fast_rec_cfg.get("model_name") or "PP-OCRv4_mobile_rec",
            "min_score": min_score,
            "low_keys": low_keys,
        }

        return {
            "question": question_text,
            "options": options,
            "ocr_results": ocr_results,
            "timing": timing,
            "fast_rec_last": self.fast_rec_last,
        }

    def _create_ocr(
        self,
        PaddleOCR,
        *,
        lang: str,
        device: str,
        ocr_version: Optional[str],
        enable_mkldnn: Optional[bool],
        mkldnn_cache_capacity: int,
        cpu_threads: Optional[int],
        enable_hpi: Optional[bool],
    ):
        """
        创建 PaddleOCR 实例：优先尝试加速参数，失败则回退到保守配置。
        """
        # 仅传递 paddleocr 可识别的 common args；None 则不传，使用库默认
        # 规范化数值参数（避免 0/负数 导致初始化报错）
        _cpu_threads = None
        if cpu_threads is not None:
            try:
                t = int(cpu_threads)
                if t > 0:
                    _cpu_threads = t
            except Exception:
                _cpu_threads = None

        _mkldnn_cache_capacity = 10
        try:
            c = int(mkldnn_cache_capacity)
            if c > 0:
                _mkldnn_cache_capacity = c
        except Exception:
            _mkldnn_cache_capacity = 10

        base_kwargs = {
            "lang": lang,
            "device": device,
        }
        if ocr_version:
            base_kwargs["ocr_version"] = ocr_version
        if enable_hpi is not None:
            base_kwargs["enable_hpi"] = enable_hpi
        if _cpu_threads is not None:
            base_kwargs["cpu_threads"] = _cpu_threads

        # 如果明确指定 enable_mkldnn，则优先用它
        if enable_mkldnn is not None:
            base_kwargs["enable_mkldnn"] = bool(enable_mkldnn)
            if bool(enable_mkldnn):
                base_kwargs["mkldnn_cache_capacity"] = _mkldnn_cache_capacity
            return PaddleOCR(**base_kwargs)

        # 未明确指定：先尝试开启 MKL-DNN（通常更快），失败自动回退关闭
        try:
            return PaddleOCR(
                **{
                    **base_kwargs,
                    "enable_mkldnn": True,
                    "mkldnn_cache_capacity": _mkldnn_cache_capacity,
                }
            )
        except Exception:
            return PaddleOCR(**{**base_kwargs, "enable_mkldnn": False})
    
    def recognize(self, image: Image.Image) -> List[Tuple[str, List[List[int]]]]:
        """
        识别图片中的文字
        参数:
            image: PIL.Image对象
        返回:
            list: [(文字, 坐标框), ...]
            坐标框格式: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        """
        try:
            import time
            t_all0 = time.perf_counter()

            # fast_rec 尝试（失败则回退全流程OCR）
            if self.fast_rec_enabled and self._text_rec is not None:
                fast = self.recognize_fast_rec(image)
                if fast and isinstance(fast.get("ocr_results"), list):
                    # fast_rec 路径不提供多边形检测框，这里返回伪 bbox
                    return fast["ocr_results"]

            # 可选：对输入做等比缩放以提速（坐标会缩放回原图）
            orig_w, orig_h = image.size
            scale_x = 1.0
            scale_y = 1.0
            resized_image = image

            # 1) input_scale 优先（0<scale<=1 建议）
            if self.input_scale is not None:
                try:
                    s = float(self.input_scale)
                    if 0 < s < 1.0:
                        new_w = max(1, int(orig_w * s))
                        new_h = max(1, int(orig_h * s))
                        if new_w != orig_w or new_h != orig_h:
                            resized_image = image.resize((new_w, new_h), Image.BILINEAR)
                            scale_x = orig_w / new_w
                            scale_y = orig_h / new_h
                except Exception:
                    pass

            # 2) input_max_side：限制最大边（在 input_scale 未触发缩放时再尝试）
            if resized_image is image and self.input_max_side is not None:
                try:
                    m = int(self.input_max_side)
                    if m > 0:
                        max_side = max(orig_w, orig_h)
                        if max_side > m:
                            s = m / float(max_side)
                            new_w = max(1, int(orig_w * s))
                            new_h = max(1, int(orig_h * s))
                            resized_image = image.resize((new_w, new_h), Image.BILINEAR)
                            scale_x = orig_w / new_w
                            scale_y = orig_h / new_h
                except Exception:
                    pass

            # 将PIL Image转换为numpy数组
            t0 = time.perf_counter()
            img_array = np.array(resized_image)
            t1 = time.perf_counter()

            # PaddleOCR 3.4.0 使用 predict() 方法
            # use_angle_cls(旧) -> use_textline_orientation(新)
            t2 = time.perf_counter()
            result = self.ocr.predict(
                img_array,
                use_textline_orientation=self.use_textline_orientation,
                text_det_limit_side_len=self.text_det_limit_side_len,
                text_det_limit_type=self.text_det_limit_type,
            )
            t3 = time.perf_counter()
            
            # 处理结果
            t4 = time.perf_counter()
            ocr_results = []
            if result:
                for item in result:
                    # PaddleOCR 3.4.0 返回结果格式为字典列表
                    if hasattr(item, 'get') or isinstance(item, dict):
                        # 新版 API 返回字典格式
                        rec_texts = item.get('rec_texts', item.get('rec_text', []))
                        rec_scores = item.get('rec_scores', item.get('rec_score', []))
                        dt_polys = item.get('dt_polys', item.get('dt_poly', []))
                        
                        if isinstance(rec_texts, str):
                            rec_texts = [rec_texts]
                            rec_scores = [rec_scores]
                            dt_polys = [dt_polys]
                        
                        for text, score, poly in zip(rec_texts, rec_scores, dt_polys):
                            if text:
                                # 将多边形转换为 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] 格式
                                bbox = []
                                poly_array = np.array(poly)
                                if len(poly_array.shape) == 2:
                                    for point in poly_array:
                                        # 坐标缩放回原图
                                        bbox.append([int(point[0] * scale_x), int(point[1] * scale_y)])
                                else:
                                    bbox = [[0,0], [0,0], [0,0], [0,0]]
                                ocr_results.append((text, bbox))
                    elif isinstance(item, (list, tuple)):
                        # 兼容旧版 API 格式
                        if item and isinstance(item[0], (list, tuple)):
                            for line in item:
                                if line:
                                    bbox = line[0]
                                    text_info = line[1]
                                    text = text_info[0] if isinstance(text_info, (list, tuple)) else text_info
                                    # 旧格式 bbox 也做缩放回原图
                                    try:
                                        scaled_bbox = [
                                            [int(p[0] * scale_x), int(p[1] * scale_y)] for p in bbox
                                        ]
                                    except Exception:
                                        scaled_bbox = bbox
                                    ocr_results.append((text, scaled_bbox))
            t5 = time.perf_counter()

            if self.debug_timing:
                self.last_timing = {
                    "to_numpy": t1 - t0,
                    "predict": t3 - t2,
                    "postprocess": t5 - t4,
                    "total": t5 - t_all0,
                }
            
            return ocr_results
        except Exception as e:
            raise Exception(f"OCR识别失败: {e}")
    
    def recognize_text_only(self, image: Image.Image) -> List[str]:
        """
        只返回文字，不返回坐标（简化版）
        参数:
            image: PIL.Image对象
        返回:
            list: 文字列表
        """
        results = self.recognize(image)
        return [text for text, _ in results]
    
    def find_text_region(self, image: Image.Image, keyword: str) -> Optional[Dict]:
        """
        查找包含关键词的区域
        参数:
            image: PIL.Image对象
            keyword: 要查找的关键词
        返回:
            dict: {'text': 文字, 'bbox': 坐标框, 'center': 中心点}
            如果未找到则返回None
        """
        results = self.recognize(image)
        
        for text, bbox in results:
            if keyword in text:
                # 计算中心点
                center = self._calculate_center(bbox)
                return {
                    'text': text,
                    'bbox': bbox,
                    'center': center
                }
        
        return None
    
    def find_text_regions(self, image: Image.Image, keywords: List[str]) -> Dict[str, Optional[Dict]]:
        """
        查找多个关键词的区域
        参数:
            image: PIL.Image对象
            keywords: 关键词列表
        返回:
            dict: {关键词: 区域信息}，未找到的返回None
        """
        results = self.recognize(image)
        found_regions = {keyword: None for keyword in keywords}
        
        for text, bbox in results:
            for keyword in keywords:
                if keyword in text and found_regions[keyword] is None:
                    center = self._calculate_center(bbox)
                    found_regions[keyword] = {
                        'text': text,
                        'bbox': bbox,
                        'center': center
                    }
        
        return found_regions
    
    def _calculate_center(self, bbox: List[List[int]]) -> Tuple[int, int]:
        """
        计算坐标框的中心点
        参数:
            bbox: 坐标框 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        返回:
            (x, y): 中心点坐标
        """
        x_coords = [point[0] for point in bbox]
        y_coords = [point[1] for point in bbox]
        
        center_x = int(sum(x_coords) / len(x_coords))
        center_y = int(sum(y_coords) / len(y_coords))
        
        return (center_x, center_y)
    
    def filter_by_confidence(self, results: List[Tuple[str, List[List[int]]]], 
                            min_confidence: float = 0.5) -> List[Tuple[str, List[List[int]]]]:
        """
        根据置信度过滤结果
        参数:
            results: OCR识别结果
            min_confidence: 最小置信度
        返回:
            过滤后的结果
        """
        # 注意：PaddleOCR返回的结果中置信度信息需要从原始结果中提取
        # 这里简化处理，实际使用时可能需要调整
        return results


# 测试代码
if __name__ == "__main__":
    from screen_capture import ScreenCapture
    
    print("初始化OCR引擎...")
    ocr = OCREngine(language='ch', use_angle_cls=True, use_gpu=False)
    
    print("截图...")
    capture = ScreenCapture()
    image = capture.capture_full_screen()
    
    print("开始OCR识别（可能需要一些时间）...")
    results = ocr.recognize(image)
    
    print(f"\n识别到 {len(results)} 个文本区域：")
    for i, (text, bbox) in enumerate(results[:10], 1):  # 只显示前10个
        center = ocr._calculate_center(bbox)
        print(f"{i}. 文字: {text}")
        print(f"   中心点: {center}")
        print(f"   坐标框: {bbox}")
        print()
