"""
题目解析模块
解析OCR识别的结果，提取题目和选项
"""
from typing import List, Tuple, Dict, Optional
from config import Config


class QuestionParser:
    """题目解析器"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        初始化解析器
        参数:
            config: 配置对象，如果为None则创建新实例
        """
        if config is None:
            config = Config()
        self.config = config
        
        # 从配置中获取关键词
        self.question_keywords = self.config.get(
            'automation.question_detection_keywords',
            ["题目一", "题目二", "题目三", "题目四", "题目五", "题目六", "题目七", "题目八", "题目九", "题目十"]
        )
        self.option_keywords = self.config.get(
            'automation.option_keywords',
            ["A", "B", "C", "D"]
        )
        self.offset_y = self.config.get('click.offset_y', 20)
    
    def parse(self, ocr_results: List[Tuple[str, List[List[int]]]]) -> Optional[Dict]:
        """
        解析OCR结果
        参数:
            ocr_results: OCR识别返回的列表，格式为 [(文字, 坐标框), ...]
        返回:
            dict: {
                'question': '题目文字',
                'options': {
                    'A': {'text': '选项A文字', 'center': (x, y)},
                    'B': {'text': '选项B文字', 'center': (x, y)},
                    'C': {'text': '选项C文字', 'center': (x, y)},
                    'D': {'text': '选项D文字', 'center': (x, y)}
                }
            }
            如果解析失败则返回None
        """
        try:
            # 提取题目
            question = self.extract_question(ocr_results)
            if not question:
                return None
            
            # 提取选项（不强依赖 A/B/C/D 前缀，优先按位置推断）
            options = self.extract_options(ocr_results, question)
            if not options or len(options) < 4:
                return None
            
            return {
                'question': question['text'],
                'question_center': question.get('center'),
                'options': options
            }
        except Exception as e:
            print(f"解析失败: {e}")
            return None
    
    def extract_question(self, ocr_results: List[Tuple[str, List[List[int]]]]) -> Optional[Dict]:
        """
        提取题目
        参数:
            ocr_results: OCR识别结果
        返回:
            dict: {'text': 题目文字, 'center': 中心点} 或 None
        """
        # 查找包含题目关键词的行
        question_line = None
        question_index = -1
        
        for i, (text, bbox) in enumerate(ocr_results):
            for keyword in self.question_keywords:
                if keyword in text:
                    question_line = (text, bbox)
                    question_index = i
                    break
            if question_line:
                break
        
        if not question_line:
            return None
        
        # 查找题目文字（通常在题目关键词下方）
        # 策略：查找题目关键词下方最近的文字行
        question_text = ""
        question_bbox = question_line[1]
        question_y = self._get_bbox_bottom(question_bbox)
        
        # 查找题目关键词下方1-3行的文字
        candidate_lines = []
        for text, bbox in ocr_results:
            bbox_top = self._get_bbox_top(bbox)
            # 在题目关键词下方，且距离不太远
            if question_y < bbox_top < question_y + 200:
                candidate_lines.append((text, bbox, bbox_top))
        
        # 按Y坐标排序，取最接近的几行
        candidate_lines.sort(key=lambda x: x[2])
        
        # 合并连续的文本行作为题目
        if candidate_lines:
            # 取前几行作为题目（根据实际情况调整）
            question_parts = []
            last_y = None
            for text, bbox, y in candidate_lines[:5]:  # 最多取5行
                if last_y is None or y - last_y < 50:  # 如果行距不太远
                    question_parts.append(text)
                    last_y = y
                else:
                    break
            
            if question_parts:
                question_text = "".join(question_parts).strip()
                # 去除题目编号等无关文字
                for keyword in self.question_keywords:
                    question_text = question_text.replace(keyword, "").strip()
                # 去除数字和标点（如 "1/10"）
                import re
                question_text = re.sub(r'\(\d+/\d+\)', '', question_text).strip()
        
        if not question_text:
            return None
        
        # 计算题目中心点（使用第一个候选行的坐标）
        question_bbox_for_pos = candidate_lines[0][1] if candidate_lines else question_bbox
        if candidate_lines:
            question_center = self._calculate_center(question_bbox_for_pos)
        else:
            question_center = self._calculate_center(question_bbox)
        
        return {
            'text': question_text,
            'center': question_center,
            # 提供题目区域底部，供选项区域筛选使用
            'bbox_bottom': self._get_bbox_bottom(question_bbox_for_pos)
        }
    
    def extract_options(self, ocr_results: List[Tuple[str, List[List[int]]]], question: Optional[Dict] = None) -> Dict[str, Dict]:
        """
        提取选项
        参数:
            ocr_results: OCR识别结果
            question: extract_question 返回的结构（用于限定选项区域）
        返回:
            dict: {
                'A': {'text': '选项A文字', 'center': (x, y)},
                ...
            }
        """
        import re

        def strip_prefix(s: str) -> str:
            s = (s or "").strip()
            if not s:
                return s
            # 统一常见全角符号
            s = s.replace("．", ".").replace("：", ":")
            # A/B/C/D
            s = re.sub(r'^[ABCDabcd][\.\、:：\s]*', '', s).strip()
            # 1-4（常见 OCR 把 A 识别成 1）
            s = re.sub(r'^[1-4][\.\、:：\s]*', '', s).strip()
            # 罗马数字 I/II/III/IV
            s = re.sub(r'^(IV|III|II|I)[\.\、:：\s]*', '', s, flags=re.IGNORECASE).strip()
            return s

        # 计算题目区域底部，用来筛选“选项区域”的候选行
        q_bottom = None
        if isinstance(question, dict):
            q_bottom = question.get("bbox_bottom")
        if q_bottom is None:
            # fallback：再次用题目关键词定位
            for text, bbox in ocr_results:
                for keyword in self.question_keywords:
                    if keyword in (text or ""):
                        try:
                            q_bottom = self._get_bbox_bottom(bbox)
                        except Exception:
                            q_bottom = None
                        break
                if q_bottom is not None:
                    break

        # 构造候选行（不依赖前缀）
        candidates = []
        for text, bbox in ocr_results:
            t = (text or "").strip()
            if not t:
                continue
            # 排除题目关键词行
            if any(k in t for k in self.question_keywords):
                continue
            # 排除 (1/10) 之类的计数
            if re.fullmatch(r'[\(\（]?\s*\d+\s*/\s*\d+\s*[\)\）]?', t):
                continue
            try:
                top = self._get_bbox_top(bbox)
                bottom = self._get_bbox_bottom(bbox)
                left = self._get_bbox_left(bbox)
                right = self._get_bbox_right(bbox)
            except Exception:
                continue

            # 题目下方才认为是选项
            if q_bottom is not None and top < q_bottom - 10:
                continue

            stripped = strip_prefix(t)
            # 太短/无内容的行过滤掉
            if len(stripped) < 2:
                continue

            cx, cy = self._calculate_center(bbox)
            candidates.append(
                {
                    "text": t,
                    "text_stripped": stripped,
                    "bbox": bbox,
                    "top": top,
                    "bottom": bottom,
                    "left": left,
                    "right": right,
                    "cx": cx,
                    "cy": cy,
                    "h": max(1, bottom - top),
                }
            )

        if len(candidates) < 4:
            return {}

        # 如果候选多于4个，挑出“最像一组答案”的4行：纵向跨度尽可能小且内容尽可能多
        chosen = candidates
        if len(candidates) > 4:
            candidates_sorted = sorted(candidates, key=lambda x: (x["top"], x["left"]))
            best_window = None
            best_score = None
            # 只看前 N 行避免噪声过多
            N = min(len(candidates_sorted), 12)
            for i in range(0, N - 3):
                window = candidates_sorted[i : i + 4]
                span = max(w["bottom"] for w in window) - min(w["top"] for w in window)
                text_len = sum(len(w["text_stripped"]) for w in window)
                score = span / (text_len + 1)
                if best_score is None or score < best_score:
                    best_score = score
                    best_window = window
            if best_window is not None:
                chosen = best_window

        # 按位置映射到 A/B/C/D：优先 2 行 2 列，其次按纵向顺序
        chosen_by_y = sorted(chosen, key=lambda x: (x["cy"], x["cx"]))
        heights = sorted([c["h"] for c in chosen_by_y])
        median_h = heights[len(heights) // 2] if heights else 30
        row_th = max(15, int(median_h * 0.6))

        rows = []
        for c in chosen_by_y:
            if not rows:
                rows.append([c])
                continue
            if abs(c["cy"] - rows[-1][0]["cy"]) <= row_th:
                rows[-1].append(c)
            else:
                rows.append([c])

        for r in rows:
            r.sort(key=lambda x: x["cx"])
        rows.sort(key=lambda r: r[0]["cy"])
        ordered = [c for r in rows for c in r]

        if len(ordered) < 4:
            return {}
        ordered = ordered[:4]

        final_options = {}
        keys = ["A", "B", "C", "D"]
        for key, c in zip(keys, ordered):
            # 选项按钮点击点：在文本中心基础上做“受限偏移”，避免偏移过大点出按钮区域
            dy = min(int(self.offset_y), int(c["h"] * 0.4))
            click_center = (c["cx"], c["cy"] + dy)
            final_options[key] = {
                "text": c["text_stripped"],
                "center": click_center,
                "text_center": (c["cx"], c["cy"]),
            }

        return final_options
    
    def format_for_ai(self, question_data: Dict) -> str:
        """
        格式化为AI提示词
        参数:
            question_data: parse()方法返回的数据
        返回:
            str: 格式化后的提示词
        """
        question = question_data['question']
        options = question_data['options']
        
        prompt = f"""你是一个诗词专家。请根据给出的诗词上句，从以下四个选项中选择正确的下句。

题目：{question}

选项：
A. {options['A']['text']}
B. {options['B']['text']}
C. {options['C']['text']}
D. {options['D']['text']}

请只返回选项字母（A、B、C或D），不要返回其他内容。"""
        
        return prompt
    
    def _calculate_center(self, bbox: List[List[int]]) -> Tuple[int, int]:
        """计算坐标框的中心点"""
        x_coords = [point[0] for point in bbox]
        y_coords = [point[1] for point in bbox]
        
        center_x = int(sum(x_coords) / len(x_coords))
        center_y = int(sum(y_coords) / len(y_coords))
        
        return (center_x, center_y)
    
    def _get_bbox_top(self, bbox: List[List[int]]) -> int:
        """获取坐标框的顶部Y坐标"""
        return min(point[1] for point in bbox)
    
    def _get_bbox_bottom(self, bbox: List[List[int]]) -> int:
        """获取坐标框的底部Y坐标"""
        return max(point[1] for point in bbox)
    
    def _get_bbox_left(self, bbox: List[List[int]]) -> int:
        """获取坐标框的左侧X坐标"""
        return min(point[0] for point in bbox)
    
    def _get_bbox_right(self, bbox: List[List[int]]) -> int:
        """获取坐标框的右侧X坐标"""
        return max(point[0] for point in bbox)


# 测试代码
if __name__ == "__main__":
    # 模拟OCR结果进行测试
    test_results = [
        ("题目一 (1/10)", [[100, 50], [200, 50], [200, 80], [100, 80]]),
        ("兰陵美酒郁金香", [[100, 100], [300, 100], [300, 130], [100, 130]]),
        ("A. 玉碗盛来琥珀光", [[100, 200], [400, 200], [400, 230], [100, 230]]),
        ("B. 夜泊秦淮近酒家", [[100, 250], [400, 250], [400, 280], [100, 280]]),
        ("C. 碧天如水夜云轻", [[100, 300], [400, 300], [400, 330], [100, 330]]),
        ("D. 依旧烟笼十里堤", [[100, 350], [400, 350], [400, 380], [100, 380]]),
    ]
    
    parser = QuestionParser()
    result = parser.parse(test_results)
    
    if result:
        print("解析成功！")
        print(f"题目: {result['question']}")
        print("选项:")
        for key, option in result['options'].items():
            print(f"  {key}. {option['text']} (点击坐标: {option['center']})")
        
        print("\nAI提示词:")
        print(parser.format_for_ai(result))
    else:
        print("解析失败")
