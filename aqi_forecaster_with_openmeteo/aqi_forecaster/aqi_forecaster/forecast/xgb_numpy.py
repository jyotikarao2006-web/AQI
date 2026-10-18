"""Minimal pure-numpy evaluator for an XGBoost gbtree regression model saved as JSON.

Used as a fallback when the installed xgboost cannot load the model file.
Supports numeric splits only (no categorical features), which is what this model uses.
"""
import json

import numpy as np


class TreeEnsemble:
    def __init__(self, path):
        with open(path, encoding="utf-8") as f:
            learner = json.load(f)["learner"]
        param = learner["learner_model_param"]
        self.base_score = float(str(param["base_score"]).strip("[]"))
        self.n_features = int(param["num_feature"])
        self.trees = []
        for t in learner["gradient_booster"]["model"]["trees"]:
            self.trees.append((
                np.asarray(t["left_children"], dtype=np.int64),
                np.asarray(t["right_children"], dtype=np.int64),
                np.asarray(t["split_indices"], dtype=np.int64),
                np.asarray(t["split_conditions"], dtype=np.float32),
                np.asarray(t["default_left"]).astype(bool),
            ))

    def predict(self, X) -> np.ndarray:
        X = np.asarray(X, dtype=np.float32)
        rows = np.arange(len(X))
        out = np.full(len(X), self.base_score, dtype=np.float64)
        for left, right, feat, cond, dleft in self.trees:
            node = np.zeros(len(X), dtype=np.int64)
            while True:
                nxt_left = left[node]
                active = nxt_left != -1
                if not active.any():
                    break
                x = X[rows, feat[node]]
                go_left = np.where(np.isnan(x), dleft[node], x < cond[node])
                node = np.where(active, np.where(go_left, nxt_left, right[node]), node)
            out += cond[node]  # leaf value is stored in split_conditions
        return out
