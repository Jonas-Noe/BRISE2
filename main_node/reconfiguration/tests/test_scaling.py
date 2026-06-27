import pytest
import timeit
import os

from reconfiguration.reconfiguration_module import ReconfigurationModule
from reconfiguration.effector import Effector
from core_entities.experiment import Experiment
from configuration_selection.configuration_selection import ConfigurationSelection

ITERATIONS = [1, 10, 20, 40, 60, 80, 100, 200, 400, 600, 800, 1000]
REPEATS = 5

class TestApproachPerformance:

    @pytest.fixture(scope='function')
    def reconf_module(self, get_experiment):
        return self._get_reconf_module(get_experiment)
    
    @pytest.fixture(scope='function')
    def reconf_module_multi_models(self, get_experiment):
        return self._get_reconf_module(get_experiment, experiment_num=8)
    
    @pytest.fixture(scope='function')
    def reconf_module_multi_features_single_model(self, get_experiment):
        return self._get_reconf_module(get_experiment, experiment_num=3)

    def _get_reconf_module(self, get_experiment, experiment_num:int = 0):
        """Make a separate function out of it to reuse it for diffrent experiment numbers"""
        Effector.clear_all()

        experiment_description, search_space = get_experiment(experiment_num)
        experiment = Experiment(experiment_description, search_space)
        cs = ConfigurationSelection(experiment)
        return ReconfigurationModule(experiment, cs)
    
    def test_change_model_with_one_surrogate(self, reconf_module:ReconfigurationModule):
        desc = {
            "Surrogate": {
                "ConfigurationTransformers": {
                    "FloatTransformer": {
                        "SklearnFloatMinMaxScaler": {
                            "Type": "sklearn_float_transformer",
                            "Class": "sklearn.MinMaxScaler"
                        }
                    }
                },
                "Instance": {
                    "TreeParzenEstimator": {
                        "MultiObjective": False,
                        "Parameters": {
                            "top_n_percent": 30,
                            "random_fraction": 0.1,
                            "bandwidth_factor": 3.0,
                            "min_bandwidth": 0.001
                        },
                        "Type": "tree_parzen_estimator"
                    }
                }
            },
            "Optimizer": {
                "ConfigurationTransformers": {
                    "FloatTransformer": {
                        "SklearnFloatMinMaxScaler": {
                            "Type": "sklearn_float_transformer",
                            "Class": "sklearn.MinMaxScaler"
                        }
                    }
                },
                "ValueTransformers": {
                    "AcquisitionFunction": {
                        "TPE_EI": {
                            "Type": "tpe_ei"
                        }
                    }
                },
                "Instance": {
                    "MOEA": {
                        "Generations": 10,
                        "PopulationSize": 100,
                        "Algorithms": {
                            "GACO": {
                                "MultiObjective": False
                            }
                        },
                        "Type": "moea"
                    }
                }
            },
            "Validator": {
                "ExternalValidator": {
                    "MockValidator": {
                        "Type": "mock_validator"
                    }
                }
            },
            "CandidateSelector": {
                "BestMultiPointProposal": {
                    "NumberOfPoints": 1,
                    "Type": "best_multi_point"
                }
            }
        }

        # Change
        self._perform_test(desc, "Model", "model_change_single_surrogate", reconf_module)

    def test_change_model_with_multiple_surrogates(self, reconf_module_multi_models:ReconfigurationModule):
        reconf_module = reconf_module_multi_models

        desc = {
                "MultiObjectiveHandling": {
                    "SurrogateType": {
                        "Portfolio": {}
                    }
                },
                "Optimizer": {
                    "Instance": {
                        "RandomSearch": {
                            "SamplingSize": 500,
                            "MultiObjective": True,
                            "Type": "random_search"
                        }
                    }
                },
                "Validator": {
                    "ExternalValidator": {
                        "QualityValidator": {
                            "Split": {
                                "HoldOut": {
                                    "TrainingSet": 0.5
                                }
                            },
                            "QualityThreshold": -10000,
                            "Type": "quality_validator"
                        }
                    },
                    "InternalValidator": {
                        "QualityValidator": {
                            "Split": {
                                "KFold": {
                                    "NumberOfFolds": 4
                                }
                            },
                            "QualityThreshold": -10000,
                            "Type": "quality_validator"
                        }
                    }
                },
                "CandidateSelector": {
                    "RandomMultiPointProposal": {
                        "NumberOfPoints": 1,
                        "Type": "random_multi_point"
                    }
                },
                "Surrogate_0": {
                    "ConfigurationTransformers": {
                        "OrdinalTransformer": {
                            "SklearnOrdinalEncoder": {
                                "Type": "sklearn_ordinal_transformer",
                                "Class": "sklearn.OrdinalEncoder"
                            }
                        },
                        "NominalTransformer": {
                            "BinaryEncoder": {
                                "Type": "binary_transformer",
                                "Class": "brise.BinaryEncoder"
                            }
                        },
                        "IntegerTransformer": {
                            "SklearnIntMinMaxScaler": {
                                "Type": "sklearn_integer_transformer",
                                "Class": "sklearn.MinMaxScaler"
                            }
                        },
                        "FloatTransformer": {
                            "SklearnFloatMinMaxScaler": {
                                "Type": "sklearn_float_transformer",
                                "Class": "sklearn.MinMaxScaler"
                            }
                        }
                    },
                    "Instance": {
                        "LinearRegression": {
                            "MultiObjective": False,
                            "Type": "sklearn_model_wrapper",
                            "Class": "sklearn.linear_model.LinearRegression"
                        }
                    }
                },
                "Surrogate_1": {
                    "ConfigurationTransformers": {
                        "OrdinalTransformer": {
                            "SklearnOrdinalEncoder": {
                                "Type": "sklearn_ordinal_transformer",
                                "Class": "sklearn.OrdinalEncoder"
                            }
                        },
                        "NominalTransformer": {
                            "BinaryEncoder": {
                                "Type": "binary_transformer",
                                "Class": "brise.BinaryEncoder"
                            }
                        },
                        "IntegerTransformer": {
                            "SklearnIntMinMaxScaler": {
                                "Type": "sklearn_integer_transformer",
                                "Class": "sklearn.MinMaxScaler"
                            }
                        },
                        "FloatTransformer": {
                            "SklearnFloatMinMaxScaler": {
                                "Type": "sklearn_float_transformer",
                                "Class": "sklearn.MinMaxScaler"
                            }
                        }
                    },
                    "Instance": {
                        "GradientBoostingRegressor": {
                            "MultiObjective": False,
                            "Parameters": {
                                "n_estimators": 4
                            },
                            "Type": "sklearn_model_wrapper",
                            "Class": "sklearn.ensemble.GradientBoostingRegressor"
                        }
                    }
                },
                "Surrogate_2": {
                    "ConfigurationTransformers": {
                        "OrdinalTransformer": {
                            "SklearnOrdinalEncoder": {
                                "Type": "sklearn_ordinal_transformer",
                                "Class": "sklearn.OrdinalEncoder"
                            }
                        },
                        "NominalTransformer": {
                            "BinaryEncoder": {
                                "Type": "binary_transformer",
                                "Class": "brise.BinaryEncoder"
                            }
                        },
                        "IntegerTransformer": {
                            "SklearnIntMinMaxScaler": {
                                "Type": "sklearn_integer_transformer",
                                "Class": "sklearn.MinMaxScaler"
                            }
                        },
                        "FloatTransformer": {
                            "SklearnFloatMinMaxScaler": {
                                "Type": "sklearn_float_transformer",
                                "Class": "sklearn.MinMaxScaler"
                            }
                        }
                    },
                    "Instance": {
                        "BayesianRidgeRegression": {
                            "MultiObjective": False,
                            "Parameters": {
                                "max_iter": 10,
                                "tol": 1.0
                            },
                            "Type": "sklearn_model_wrapper",
                            "Class": "sklearn.linear_model.BayesianRidge"
                        }
                    }
                },
                "Surrogate_3": {
                    "Instance": {
                        "ModelMock": {
                            "MultiObjective": True,
                            "Type": "model_mock"
                        }
                    }
                }
            }
        
        self._perform_test(desc, "Model_1", "model_change_multiple_surrogates", reconf_module)

    def test_change_model_with_multiple_surrogates_and_optimizers(self, reconf_module_multi_features_single_model:ReconfigurationModule):
        desc = {
            "MultiObjectiveHandling": {
                "SurrogateType": {
                    "Compositional": {}
                }
            },
            "Validator": {
                "ExternalValidator": {
                    "MockValidator": {
                        "Type": "mock_validator"
                    }
                }
            },
            "CandidateSelector": {
                "BestMultiPointProposal": {
                    "NumberOfPoints": 1,
                    "Type": "best_multi_point"
                }
            },
            "Surrogate_0": {
                "ConfigurationTransformers": {
                    "OrdinalTransformer": {
                        "SklearnOrdinalEncoder": {
                            "Type": "sklearn_ordinal_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    },
                    "NominalTransformer": {
                        "SklearnBinaryEncoder": {
                            "Type": "sklearn_binary_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    },
                    "IntegerTransformer": {
                        "SklearnIntMinMaxScaler": {
                            "Type": "sklearn_integer_transformer",
                            "Class": "sklearn.MinMaxScaler"
                        }
                    },
                    "FloatTransformer": {
                        "SklearnFloatMinMaxScaler": {
                            "Type": "sklearn_float_transformer",
                            "Class": "sklearn.MinMaxScaler"
                        }
                    }
                },
                "Instance": {
                    "TreeParzenEstimator": {
                        "MultiObjective": False,
                        "Parameters": {
                            "top_n_percent": 30,
                            "random_fraction": 0.0,
                            "bandwidth_factor": 1.0,
                            "min_bandwidth": 0.001
                        },
                        "Type": "tree_parzen_estimator"
                    }
                }
            },
            "Surrogate_1": {
                "ConfigurationTransformers": {
                    "OrdinalTransformer": {
                        "SklearnOrdinalEncoder": {
                            "Type": "sklearn_ordinal_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    },
                    "NominalTransformer": {
                        "SklearnBinaryEncoder": {
                            "Type": "sklearn_binary_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    },
                    "IntegerTransformer": {
                        "SklearnIntMinMaxScaler": {
                            "Type": "sklearn_integer_transformer",
                            "Class": "sklearn.MinMaxScaler"
                        }
                    },
                    "FloatTransformer": {
                        "SklearnFloatMinMaxScaler": {
                            "Type": "sklearn_float_transformer",
                            "Class": "sklearn.MinMaxScaler"
                        }
                    }
                },
                "Instance": {
                    "TreeParzenEstimator": {
                        "MultiObjective": False,
                        "Parameters": {
                            "top_n_percent": 30,
                            "random_fraction": 0.0,
                            "bandwidth_factor": 1.0,
                            "min_bandwidth": 0.001
                        },
                        "Type": "tree_parzen_estimator"
                    }
                }
            },
            "Surrogate_2": {
                "ConfigurationTransformers": {
                    "OrdinalTransformer": {
                        "SklearnOrdinalEncoder": {
                            "Type": "sklearn_ordinal_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    },
                    "NominalTransformer": {
                        "SklearnBinaryEncoder": {
                            "Type": "sklearn_binary_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    },
                    "IntegerTransformer": {
                        "SklearnIntMinMaxScaler": {
                            "Type": "sklearn_integer_transformer",
                            "Class": "sklearn.MinMaxScaler"
                        }
                    },
                    "FloatTransformer": {
                        "SklearnFloatMinMaxScaler": {
                            "Type": "sklearn_float_transformer",
                            "Class": "sklearn.MinMaxScaler"
                        }
                    }
                },
                "Instance": {
                    "TreeParzenEstimator": {
                        "MultiObjective": False,
                        "Parameters": {
                            "top_n_percent": 30,
                            "random_fraction": 0.0,
                            "bandwidth_factor": 1.0,
                            "min_bandwidth": 0.001
                        },
                        "Type": "tree_parzen_estimator"
                    }
                }
            },
            "Surrogate_3": {
                "ConfigurationTransformers": {
                    "OrdinalTransformer": {
                        "SklearnOrdinalEncoder": {
                            "Type": "sklearn_ordinal_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    },
                    "NominalTransformer": {
                        "SklearnBinaryEncoder": {
                            "Type": "sklearn_binary_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    },
                    "IntegerTransformer": {
                        "SklearnIntMinMaxScaler": {
                            "Type": "sklearn_integer_transformer",
                            "Class": "sklearn.MinMaxScaler"
                        }
                    },
                    "FloatTransformer": {
                        "SklearnFloatMinMaxScaler": {
                            "Type": "sklearn_float_transformer",
                            "Class": "sklearn.MinMaxScaler"
                        }
                    }
                },
                "Instance": {
                    "TreeParzenEstimator": {
                        "MultiObjective": False,
                        "Parameters": {
                            "top_n_percent": 30,
                            "random_fraction": 0.0,
                            "bandwidth_factor": 1.0,
                            "min_bandwidth": 0.001
                        },
                        "Type": "tree_parzen_estimator"
                    }
                }
            },
            "Surrogate_4": {
                "ConfigurationTransformers": {
                    "OrdinalTransformer": {
                        "SklearnOrdinalEncoder": {
                            "Type": "sklearn_ordinal_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    },
                    "NominalTransformer": {
                        "SklearnBinaryEncoder": {
                            "Type": "sklearn_binary_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    },
                    "IntegerTransformer": {
                        "SklearnIntMinMaxScaler": {
                            "Type": "sklearn_integer_transformer",
                            "Class": "sklearn.MinMaxScaler"
                        }
                    },
                    "FloatTransformer": {
                        "SklearnFloatMinMaxScaler": {
                            "Type": "sklearn_float_transformer",
                            "Class": "sklearn.MinMaxScaler"
                        }
                    }
                },
                "Instance": {
                    "TreeParzenEstimator": {
                        "MultiObjective": False,
                        "Parameters": {
                            "top_n_percent": 30,
                            "random_fraction": 0.0,
                            "bandwidth_factor": 1.0,
                            "min_bandwidth": 0.001
                        },
                        "Type": "tree_parzen_estimator"
                    }
                }
            },
            "Optimizer_0": {
                "ConfigurationTransformers": {
                    "OrdinalTransformer": {
                        "SklearnOrdinalEncoder": {
                            "Type": "sklearn_ordinal_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    },
                    "NominalTransformer": {
                        "SklearnBinaryEncoder": {
                            "Type": "sklearn_binary_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    }
                },
                "ValueTransformers": {
                    "AcquisitionFunction": {
                        "TPE_EI": {
                            "Type": "tpe_ei"
                        }
                    }
                },
                "Instance": {
                    "MOEA": {
                        "Generations": 5,
                        "PopulationSize": 80,
                        "Algorithms": {
                            "GACO": {
                                "MultiObjective": False
                            }
                        },
                        "Type": "moea"
                    }
                }
            },
            "Optimizer_1": {
                "ConfigurationTransformers": {
                    "OrdinalTransformer": {
                        "SklearnOrdinalEncoder": {
                            "Type": "sklearn_ordinal_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    },
                    "NominalTransformer": {
                        "SklearnBinaryEncoder": {
                            "Type": "sklearn_binary_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    }
                },
                "ValueTransformers": {
                    "AcquisitionFunction": {
                        "TPE_EI": {
                            "Type": "tpe_ei"
                        }
                    }
                },
                "Instance": {
                    "MOEA": {
                        "Generations": 5,
                        "PopulationSize": 80,
                        "Algorithms": {
                            "GACO": {
                                "MultiObjective": False
                            }
                        },
                        "Type": "moea"
                    }
                }
            },
            "Optimizer_2": {
                "ConfigurationTransformers": {
                    "OrdinalTransformer": {
                        "SklearnOrdinalEncoder": {
                            "Type": "sklearn_ordinal_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    },
                    "NominalTransformer": {
                        "SklearnBinaryEncoder": {
                            "Type": "sklearn_binary_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    }
                },
                "ValueTransformers": {
                    "AcquisitionFunction": {
                        "TPE_EI": {
                            "Type": "tpe_ei"
                        }
                    }
                },
                "Instance": {
                    "MOEA": {
                        "Generations": 5,
                        "PopulationSize": 80,
                        "Algorithms": {
                            "GACO": {
                                "MultiObjective": False
                            }
                        },
                        "Type": "moea"
                    }
                }
            },
            "Optimizer_3": {
                "ConfigurationTransformers": {
                    "OrdinalTransformer": {
                        "SklearnOrdinalEncoder": {
                            "Type": "sklearn_ordinal_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    },
                    "NominalTransformer": {
                        "SklearnBinaryEncoder": {
                            "Type": "sklearn_binary_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    }
                },
                "ValueTransformers": {
                    "AcquisitionFunction": {
                        "TPE_EI": {
                            "Type": "tpe_ei"
                        }
                    }
                },
                "Instance": {
                    "MOEA": {
                        "Generations": 5,
                        "PopulationSize": 80,
                        "Algorithms": {
                            "GACO": {
                                "MultiObjective": False
                            }
                        },
                        "Type": "moea"
                    }
                }
            },
            "Optimizer_4": {
                "ConfigurationTransformers": {
                    "OrdinalTransformer": {
                        "SklearnOrdinalEncoder": {
                            "Type": "sklearn_ordinal_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    },
                    "NominalTransformer": {
                        "SklearnBinaryEncoder": {
                            "Type": "sklearn_binary_transformer",
                            "Class": "sklearn.OrdinalEncoder"
                        }
                    }
                },
                "ValueTransformers": {
                    "AcquisitionFunction": {
                        "TPE_EI": {
                            "Type": "tpe_ei"
                        }
                    }
                },
                "Instance": {
                    "MOEA": {
                        "Generations": 5,
                        "PopulationSize": 80,
                        "Algorithms": {
                            "GACO": {
                                "MultiObjective": False
                            }
                        },
                        "Type": "moea"
                    }
                }
            }
        }

        self._perform_test(desc, "Model", "model_change_5_surrogates_5_optimizer", reconf_module_multi_features_single_model)

    def _perform_test(self, desc, vp, test_name, reconf_module):
        # Ramp up scaling
        for iterations in ITERATIONS:
            times = []

            # Repeat multiple times
            for _ in range(REPEATS):
                start = timeit.default_timer()

                # Perform reconfiguraions x times
                for _ in range(iterations):
                    reconf_module.change_variant(vp, desc)
                    reconf_module.done().reconfigure()

                times.append(timeit.default_timer() - start)
            
            self.save_result(test_name, iterations, times)

    def save_result(self, test_name, total_changes, times):
        path = os.path.dirname(os.path.abspath(__file__))

        # Write CSV
        with open(path + "/performance_results.csv", "a", encoding="utf-8") as file:
            file.write(f"{test_name}, {total_changes}, {', '.join([str(t) for t in times])}\n")
            file.close()