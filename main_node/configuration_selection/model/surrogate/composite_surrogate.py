import pandas as pd
from typing import Tuple

import logging
import traceback

from configuration_selection.model.surrogate.surrogate_abs import Surrogate


class CompositeSurrogate(Surrogate):
    def __init__(self, surrogates: Tuple[Surrogate], region: Tuple, no_monitoring=False, model_name:str="Model"):
        self.surrogates = surrogates
        self.model_name = model_name # Only for monitoring

        #logging.getLogger("monitor_logger").info("Created Composite Surrogate. ID: %s Stack: %s", id(self), "".join(traceback.format_stack()))

        objectives = {}
        surrogate_description = {}

        for s in surrogates:
            key = f"{s.feature_name}_{'_'.join(s.objectives.keys())}"
            surrogate_description[key] = s.surrogate_description
            for o, o_value in s.objectives.items():
                objectives[o] = o_value

        super().__init__(surrogate_description, region, objectives, no_monitoring=no_monitoring)

        self.multi_objective = True
        if surrogates:
            self.mapping_config_transformer_parameter = surrogates[0].mapping_config_transformer_parameter

    @Surrogate.monitor_runtime()
    def create(self, features: pd.DataFrame, labels: pd.DataFrame) -> bool:
        is_built = []
        for s in self.surrogates:
            i_b = s.create(features, labels[list(s.objectives.keys())])
            is_built.append(i_b)
        return all(is_built) is True

    def predict(self, cfg: pd.Series, transform: bool = True) -> pd.DataFrame:
        result = pd.DataFrame()

        for s in self.surrogates:
            if result.empty:
                result = s.predict(cfg, transform)
            else:
                temp = s.predict(cfg, transform)
                result = result.join(temp)
        return result
