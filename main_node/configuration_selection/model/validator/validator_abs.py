import pandas as pd
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict

from configuration_selection.model.surrogate.surrogate_abs import Surrogate

from reconfiguration.monitoring.monitorable import MonitorableABC

class Validator(MonitorableABC):
    def __init__(self, validator_description: Dict, region: Tuple, objectives: Dict):
        self.validator_description = validator_description
        self.region = region
        self.objectives = objectives

        super().__init__()

    @abstractmethod
    def validate(self, surrogate: Surrogate, features: pd.DataFrame, labels: pd.DataFrame) -> Tuple[bool, float]:
        pass

    @abstractmethod
    def train_test_split(self, features: pd.DataFrame, labels: pd.DataFrame) -> Tuple[List[pd.DataFrame], List[pd.DataFrame], List[pd.DataFrame], List[pd.DataFrame]]:
        pass
