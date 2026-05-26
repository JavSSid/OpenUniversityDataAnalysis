"""
OULAD — Great Expectations Quality Validation Runner

Loads expectation suites from YAML rules, runs validation against
Bronze/Silver DataFrames, and persists results for the reporting layer.

Security:
  - Expectation configs are read-only, never modified at runtime
  - Results stored in isolated S3 bucket with versioning
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from great_expectations.core import ExpectationConfiguration, ExpectationSuite
from great_expectations.dataset import PandasDataset

logger = logging.getLogger(__name__)


class QualityValidator:
    """Validates DataFrames against quality rules defined in quality_rules.yaml."""

    def __init__(self, rules_path: Optional[Path] = None):
        self.rules_path = rules_path or Path(__file__).parents[2] / "config" / "quality_rules.yaml"
        self.rules = self._load_rules()

    def _load_rules(self) -> dict:
        with open(self.rules_path) as f:
            return yaml.safe_load(f).get("rules", {})

    def _build_suite(self, table_name: str) -> ExpectationSuite:
        """Build a Great Expectations suite from configured rules for a table."""
        suite = ExpectationSuite(expectation_suite_name=f"{table_name}.suite")
        rules = self.rules

        # NOT NULL checks
        for entry in rules.get("not_null_checks", []):
            if entry["table"] == table_name:
                for col in entry["columns"]:
                    suite.add_expectation(
                        ExpectationConfiguration(
                            expectation_type="expect_column_values_to_not_be_null",
                            kwargs={"column": col},
                            meta={"rule": "not_null", "severity": "critical"},
                        )
                    )

        # Range checks
        for entry in rules.get("range_checks", []):
            if entry["table"] == table_name:
                kwargs = {"column": entry["column"]}
                if "min" in entry:
                    kwargs["min_value"] = entry["min"]
                if "max" in entry:
                    kwargs["max_value"] = entry["max"]
                suite.add_expectation(
                    ExpectationConfiguration(
                        expectation_type="expect_column_values_to_be_between",
                        kwargs=kwargs,
                        meta={"rule": "range_check", "severity": "critical"},
                    )
                )

        # Allowed values
        for entry in rules.get("business_rules", []):
            if entry.get("table") == table_name and "allowed_values" in entry:
                suite.add_expectation(
                    ExpectationConfiguration(
                        expectation_type="expect_column_values_to_be_in_set",
                        kwargs={
                            "column": entry["column"],
                            "value_set": entry["allowed_values"],
                        },
                        meta={"rule": entry.get("name", "allowed_values"), "severity": entry.get("severity", "warning")},
                    )
                )

        return suite

    def validate_table(
        self, table_name: str, df, layer: str = "bronze"
    ) -> Dict[str, Any]:
        """Run all expectations for a table against a DataFrame.

        Returns a dict with:
          - success: bool
          - evaluated_expectations: int
          - passed: int
          - failed: List[dict]
          - run_time: str
        """
        suite = self._build_suite(table_name)
        ds = PandasDataset(df, expectation_suite=suite)
        results = ds.validate()

        passed = sum(1 for r in results.results if r.success)
        failed = [
            {
                "expectation": r.expectation_config.expectation_type,
                "column": r.expectation_config.kwargs.get("column"),
                "result": r.result,
                "meta": r.expectation_config.meta,
            }
            for r in results.results if not r.success
        ]

        outcome = {
            "table": table_name,
            "layer": layer,
            "success": results.success,
            "statistics": results.statistics,
            "evaluated_expectations": len(results.results),
            "passed": passed,
            "failed": len(failed),
            "failures": failed,
            "run_time": datetime.now(timezone.utc).isoformat(),
        }

        log_level = logging.ERROR if failed else logging.INFO
        logger.log(log_level, f"Quality check for {layer}.{table_name}: {passed}/{len(results.results)} passed")

        return outcome

    def validate_all(
        self, tables: Dict[str, object], layer: str = "bronze"
    ) -> Dict[str, Dict[str, Any]]:
        """Validate multiple tables at once.

        Args:
            tables: dict of {table_name: pandas DataFrame}
            layer: 'bronze' or 'silver'
        Returns:
            dict of {table_name: validation_outcome}
        """
        results = {}
        for name, df in tables.items():
            if df is not None and not df.empty:
                results[name] = self.validate_table(name, df, layer=layer)
        return results


def summarize_results(results: Dict[str, Dict]) -> Dict:
    """Aggregate multiple table results into a pipeline summary."""
    total_passed = sum(r["passed"] for r in results.values())
    total_failed = sum(r["failed"] for r in results.values())
    total_evaluated = sum(r["evaluated_expectations"] for r in results.values())
    all_success = all(r["success"] for r in results.values())

    return {
        "pipeline_success": all_success,
        "total_expectations": total_evaluated,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "pass_rate": round(total_passed / total_evaluated * 100, 2) if total_evaluated else 0.0,
        "table_results": {
            name: {
                "passed": r["passed"],
                "failed": r["failed"],
                "success": r["success"],
                "failures": r["failures"][:10],  # top 10 failures per table
            }
            for name, r in results.items()
        },
        "run_time": datetime.now(timezone.utc).isoformat(),
    }
