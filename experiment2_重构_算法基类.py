from abc import ABC, abstractmethod


class BaseAlgorithm(ABC):
    """
    所有招募算法的统一父类。
    """

    def __init__(self, config):
        self.config = config
        self.name = "base"
        self.loader_mode = "base"
        self.selection_mode = "base_algorithm"

    @abstractmethod
    def run_round(self, context):
        """
        每一轮调用一次算法。

        输入：
            context: 当前轮信息

        输出：
            decision: 本轮选择结果
        """
        pass

    def update(self, feedback):
        """
        每轮结束后更新算法状态。
        默认不做事，返回空字典。
        """
        return {}
