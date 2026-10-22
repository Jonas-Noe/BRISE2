import pandas as pd
from abc import ABC, abstractmethod
from reconfiguration.monitoring.monitorable import MonitorableABC

class CandidateSelector(MonitorableABC):
    def __init__(self, candidate_selector_description: dict):
        self.candidate_selector_description = candidate_selector_description
        self.feature_name = list(candidate_selector_description.keys())[0]
        self.number_of_points = candidate_selector_description[self.feature_name]["NumberOfPoints"]

        super().__init__()

    @abstractmethod
    def select_candidates(self, candidates: pd.DataFrame) -> pd.DataFrame:
        pass
