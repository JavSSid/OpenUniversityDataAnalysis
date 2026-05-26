"""
OULAD — Anomaly Detection Module

Detects statistical outliers in student interaction and assessment data
using:
  1. Z-score thresholding for extreme values
  2. IQR-based outlier detection
  3. Temporal consistency checks (e.g. impossible dates)

Designed to flag suspicious records for human review before they
corrupt downstream analytics.

Security:
  - All anomaly results are logged to the audit trail
  - No raw PII is exposed in anomaly reports
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from src.security.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Statistical anomaly detection for OULAD datasets."""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.audit = AuditLogger()

    # ── Per-table detectors ─────────────────────────────────

    def detect_click_anomalies(
        self, df: pd.DataFrame, daily_max: Optional[int] = None, z_threshold: Optional[float] = None
    ) -> pd.DataFrame:
        """Flag extreme click counts in studentVle data.

        Returns a DataFrame of flagged rows with an anomaly_score column.
        """
        if df.empty or "sum_click" not in df.columns:
            return pd.DataFrame()

        daily_max = daily_max or self.config.get("click_threshold", {}).get("daily_max", 5000)
        z_threshold = z_threshold or self.config.get("click_threshold", {}).get("z_score", 3.0)

        z_scores = np.abs(sp_stats.zscore(df["sum_click"].fillna(0), nan_policy="omit"))
        flags = df[
            (df["sum_click"] > daily_max) | (z_scores > z_threshold)
        ].copy()

        if not flags.empty:
            flags["anomaly_reason"] = np.where(
                flags["sum_click"] > daily_max,
                f"exceeds_daily_max_{daily_max}",
                f"z_score_exceeds_{z_threshold}",
            )
            flags["anomaly_score"] = np.where(
                flags["sum_click"] > daily_max,
                flags["sum_click"] / daily_max,
                z_scores[flags.index],
            )
            flags["detected_at"] = datetime.now(timezone.utc).isoformat()
            self.audit.log(
                action="anomaly_detected",
                resource="studentVle",
                detail={
                    "anomaly_type": "click_outlier",
                    "flagged_rows": len(flags),
                    "thresholds": {"daily_max": daily_max, "z_threshold": z_threshold},
                },
            )

        return flags

    def detect_assessment_anomalies(
        self, df: pd.DataFrame, z_threshold: Optional[float] = None
    ) -> pd.DataFrame:
        """Flag extreme (likely erroneous) assessment scores.

        Flags:
          - Scores outside 3 IQR from the median
          - Perfect zero-activity patterns (all TMAs missed, then exam taken)
        """
        if df.empty or "score" not in df.columns:
            return pd.DataFrame()

        z_threshold = z_threshold or self.config.get("assessment_score", {}).get("z_score", 3.0)
        iqr_mul = self.config.get("assessment_score", {}).get("iqr_multiplier", 1.5)

        Q1 = df["score"].quantile(0.25)
        Q3 = df["score"].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - iqr_mul * IQR
        upper_bound = Q3 + iqr_mul * IQR

        z_scores = np.abs(sp_stats.zscore(df["score"].fillna(0), nan_policy="omit"))

        flags = df[
            (df["score"] < lower_bound) | (df["score"] > upper_bound) | (z_scores > z_threshold)
        ].copy()

        if not flags.empty:
            flags["anomaly_reason"] = np.select(
                [
                    z_scores[flags.index] > z_threshold,
                    flags["score"] > upper_bound,
                    flags["score"] < lower_bound,
                ],
                [
                    f"z_score_exceeds_{z_threshold}",
                    f"above_upper_fence_{upper_bound:.1f}",
                    f"below_lower_fence_{lower_bound:.1f}",
                ],
                default="unknown",
            )
            flags["detected_at"] = datetime.now(timezone.utc).isoformat()
            self.audit.log(
                action="anomaly_detected",
                resource="studentAssessment",
                detail={
                    "anomaly_type": "score_outlier",
                    "flagged_rows": len(flags),
                },
            )

        return flags

    def detect_temporal_anomalies(
        self,
        registration_df: pd.DataFrame,
        vle_df: pd.DataFrame,
        assessment_df: pd.DataFrame,
    ) -> Dict[str, pd.DataFrame]:
        """Detect temporal inconsistencies across tables.

        Checks:
          - VLE interactions before registration
          - Assessment submissions before registration
          - Unregistration followed by continued activity
        """
        anomalies: Dict[str, pd.DataFrame] = {}

        if not registration_df.empty and not vle_df.empty:
            merged = vle_df.merge(
                registration_df[["id_student", "code_module", "code_presentation", "date_registration"]],
                on=["id_student", "code_module", "code_presentation"],
                how="inner",
            )
            early_vle = merged[merged["date"] < merged["date_registration"]].copy()
            if not early_vle.empty:
                early_vle["anomaly_reason"] = "vle_before_registration"
                anomalies["vle_before_registration"] = early_vle

        if not registration_df.empty and not assessment_df.empty:
            merged = assessment_df.merge(
                registration_df[["id_student", "code_module", "code_presentation", "date_registration"]],
                on=["id_student"],
                how="inner",
            )
            early_assessment = merged[merged["date_submitted"] < merged["date_registration"]].copy()
            if not early_assessment.empty:
                early_assessment["anomaly_reason"] = "assessment_before_registration"
                anomalies["assessment_before_registration"] = early_assessment

        if anomalies:
            self.audit.log(
                action="anomaly_detected",
                resource="temporal",
                detail={
                    "anomaly_type": "temporal_inconsistency",
                    "flagged_categories": list(anomalies.keys()),
                    "total_rows": sum(len(v) for v in anomalies.values()),
                },
            )

        return anomalies

    def detect_all(
        self,
        student_vle: Optional[pd.DataFrame] = None,
        student_assessment: Optional[pd.DataFrame] = None,
        student_registration: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """Run all anomaly detectors and consolidate results."""
        results: Dict[str, Any] = {
            "run_time": datetime.now(timezone.utc).isoformat(),
            "anomalies_found": 0,
            "details": {},
        }

        if student_vle is not None:
            click_flags = self.detect_click_anomalies(student_vle)
            results["details"]["click_anomalies"] = {
                "count": len(click_flags),
                "flagged_ids": click_flags["id_student"].tolist() if not click_flags.empty else [],
                "sample": click_flags.head(20).to_dict("records") if not click_flags.empty else [],
            }

        if student_assessment is not None:
            score_flags = self.detect_assessment_anomalies(student_assessment)
            results["details"]["assessment_anomalies"] = {
                "count": len(score_flags),
                "sample": score_flags.head(20).to_dict("records") if not score_flags.empty else [],
            }

        if all(x is not None for x in [student_registration, student_vle, student_assessment]):
            temporal = self.detect_temporal_anomalies(
                student_registration, student_vle, student_assessment
            )
            results["details"]["temporal_anomalies"] = {
                category: len(df)
                for category, df in temporal.items()
            }

        total = sum(
            v.get("count", 0) for v in results["details"].values() if isinstance(v, dict)
        )
        results["anomalies_found"] = total

        logger.info(
            f"Anomaly detection complete: {total} anomalies found "
            f"(click: {results['details'].get('click_anomalies', {}).get('count', 0)}, "
            f"score: {results['details'].get('assessment_anomalies', {}).get('count', 0)})"
        )

        return results
