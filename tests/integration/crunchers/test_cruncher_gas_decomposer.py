import re

import numpy as np
import pandas as pd
import pyam
import pytest
from silicone.utils import convert_units_to_MtCO2_equiv
from base import _DataBaseCruncherTester
from pyam import IamDataFrame

from silicone.database_crunchers import DatabaseCruncherGasDecomposeTimeDepRatio

_msa = ["model_a", "scen_a"]
_msb = ["model_a", "scen_b"]


class TestDatabaseCruncherGasDecomposeTimeDepRatio(_DataBaseCruncherTester):
    tclass = DatabaseCruncherGasDecomposeTimeDepRatio
    tdb = pd.DataFrame(
        [
            _msa + ["World", "Emissions|HFC|C5F12", "kt C5F12/yr", 2, 3],
            _msa + ["World", "Emissions|HFC|C2F6", "kt C2F6/yr", 0.5, 1.5],
        ],
        columns=["model", "scenario", "region", "variable", "unit", 2010, 2015],
    )
    irregular_msa = ["model_b", "scen_a"]
    unequal_df = pd.DataFrame(
        [
            _msa + ["World", "Emissions|HFC|C5F12", "kt C5F12/yr", 1, 3],
            _msa + ["World", "Emissions|HFC|C2F6", "kt C2F6/yr", 1, 3],
            irregular_msa + ["World", "Emissions|HFC|C2F6", "kt C2F6/yr", 0.5, 1.5],
            _msb + ["World", "Emissions|HFC|C5F12", "kt C5F12/yr", 9, 3],
            _msb + ["World", "Emissions|HFC|C2F6", "kt C2F6/yr", 1, 3],
        ],
        columns=["model", "scenario", "region", "variable", "unit", 2010, 2015],
    )
    tdownscale_df = pd.DataFrame(
        [
            [
                "model_b",
                "scen_b",
                "World",
                "Emissions|HFC|C2F6",
                "kt C2F6/yr",
                1.25,
                2,
                3,
            ],
            [
                "model_b",
                "scen_c",
                "World",
                "Emissions|HFC|C2F6",
                "kt C2F6/yr",
                1.2,
                2.3,
                2.8,
            ],
        ],
        columns=["model", "scenario", "region", "variable", "unit", 2010, 2015, 2050],
    )

    def test__construct_consistent_values(self, test_db):
        test_db_co2 = convert_units_to_MtCO2_equiv(test_db)
        tcruncher = self.tclass(test_db_co2)
        aggregate_name = "agg"
        assert aggregate_name not in tcruncher._db.variables().values
        component_ratio = ["Emissions|HFC|C2F6", "Emissions|HFC|C5F12"]
        consistent_vals = tcruncher._construct_consistent_values(
            aggregate_name, component_ratio
        )
        assert aggregate_name in consistent_vals["variable"].values
        consistent_vals = pyam.IamDataFrame(consistent_vals).timeseries()
        timeseries_data = tcruncher._db.timeseries()
        assert all(
            [
                np.allclose(
                    consistent_vals.iloc[0].iloc[ind],
                    timeseries_data.iloc[0].iloc[ind]
                    + timeseries_data.iloc[1].iloc[ind],
                )
                for ind in range(len(timeseries_data.iloc[0]))
            ]
        )

    def test_derive_relationship(self, test_db):
        tcruncher = self.tclass(test_db)
        res = tcruncher.derive_relationship(
            "Emissions|HFC|C5F12", ["Emissions|HFC|C2F6"]
        )
        assert callable(res)

    def test_derive_relationship_error_multiple_lead_vars(self, test_db):
        tcruncher = self.tclass(test_db)
        error_msg = re.escape(
            "``variable_leaders`` contains more than one variable. "
        )
        with pytest.raises(ValueError, match=error_msg):
            tcruncher.derive_relationship("Emissions|HFC|C5F12", ["a", "b"])

    def test_derive_relationship_error_no_info_leader(self, test_db):
        # test that crunching fails if there's no data about the lead gas in the
        # database
        variable_leaders = ["Emissions|HFC|C2F6"]
        tcruncher = self.tclass(test_db.filter(variable=variable_leaders, keep=False))

        error_msg = re.escape(
            "No data for `variable_leaders` ({}) in database".format(variable_leaders)
        )
        with pytest.raises(ValueError, match=error_msg):
            tcruncher.derive_relationship("Emissions|HFC|C5F12", variable_leaders)

    def test_derive_relationship_error_no_info_follower(self, test_db):
        # test that crunching fails if there's no data about the follower gas in the
        # database
        variable_follower = "Emissions|HFC|C5F12"
        tcruncher = self.tclass(test_db.filter(variable=variable_follower, keep=False))

        error_msg = re.escape(
            "No data for `variable_follower` ({}) in database".format(variable_follower)
        )
        with pytest.raises(ValueError, match=error_msg):
            tcruncher.derive_relationship(variable_follower, ["Emissions|HFC|C2F6"])

    def test_relationship_usage_not_enough_time(self, test_db, test_downscale_df):
        tcruncher = self.tclass(test_db)

        filler = tcruncher.derive_relationship(
            "Emissions|HFC|C5F12", ["Emissions|HFC|C2F6"]
        )

        test_downscale_df = self._adjust_time_style_to_match(test_downscale_df, test_db)
        error_msg = re.escape(
            "Not all required timepoints are in the data for the lead"
            " gas (Emissions|HFC|C2F6)"
        )
        with pytest.raises(ValueError, match=error_msg):
            res = filler(test_downscale_df)

    def test_relationship_usage_multiple_bad_data(self, unequal_df, test_downscale_df):
        tcruncher = self.tclass(unequal_df)
        error_msg = "The follower and leader data have different sizes"
        with pytest.raises(ValueError, match=error_msg):
            filler = tcruncher.derive_relationship(
                "Emissions|HFC|C5F12", ["Emissions|HFC|C2F6"]
            )

    def test_relationship_usage_multiple_data(self, unequal_df, test_downscale_df):
        equal_df = unequal_df.filter(model="model_a")
        tcruncher = self.tclass(equal_df)
        test_downscale_df = self._adjust_time_style_to_match(
            test_downscale_df, equal_df
        ).filter(year=[2010, 2015])
        filler = tcruncher.derive_relationship(
            "Emissions|HFC|C5F12", ["Emissions|HFC|C2F6"]
        )
        res = filler(test_downscale_df)

        lead_iamdf = test_downscale_df.filter(variable="Emissions|HFC|C2F6")

        exp = lead_iamdf.timeseries()
        # The follower values are 1 and 9 (average 5), the leader values are all 1
        # hence we expect the input * 5 as output.
        exp[exp.columns[0]] = exp[exp.columns[0]] * 5
        exp = exp.reset_index()
        exp["variable"] = "Emissions|HFC|C5F12"
        exp["unit"] = "kt C5F12/yr"
        exp = IamDataFrame(exp)

        pd.testing.assert_frame_equal(
            res.timeseries(), exp.timeseries(), check_like=True
        )

        # comes back on input timepoints
        np.testing.assert_array_equal(
            res.timeseries().columns.values.squeeze(),
            test_downscale_df.timeseries().columns.values.squeeze(),
        )

    def test_relationship_usage_nans(self, unequal_df, test_downscale_df):
        equal_df = unequal_df.filter(model="model_a")
        equal_df.data["value"].iloc[0] = np.nan
        tcruncher = self.tclass(equal_df)
        test_downscale_df = self._adjust_time_style_to_match(
            test_downscale_df, equal_df
        ).filter(year=[2010, 2015])
        filler = tcruncher.derive_relationship(
            "Emissions|HFC|C5F12", ["Emissions|HFC|C2F6"]
        )
        res = filler(test_downscale_df)
        assert all(res.data["year"] == 2015)

    def test_relationship_usage(self, test_db, test_downscale_df):
        tcruncher = self.tclass(test_db)

        filler = tcruncher.derive_relationship(
            "Emissions|HFC|C5F12", ["Emissions|HFC|C2F6"]
        )

        test_downscale_df = self._adjust_time_style_to_match(
            test_downscale_df, test_db
        ).filter(year=[2010, 2015])
        res = filler(test_downscale_df)

        lead_iamdf = test_downscale_df.filter(variable="Emissions|HFC|C2F6")

        # We have a ratio of (2/0.5) = 4 for 2010 and (3/1.5) = 2 for 2015
        exp = lead_iamdf.timeseries()
        exp[exp.columns[0]] = exp[exp.columns[0]] * 4
        exp[exp.columns[1]] = exp[exp.columns[1]] * 2
        exp = exp.reset_index()
        exp["variable"] = "Emissions|HFC|C5F12"
        exp["unit"] = "kt C5F12/yr"
        exp = IamDataFrame(exp)

        pd.testing.assert_frame_equal(
            res.timeseries(), exp.timeseries(), check_like=True
        )

        # comes back on input timepoints
        np.testing.assert_array_equal(
            res.timeseries().columns.values.squeeze(),
            test_downscale_df.timeseries().columns.values.squeeze(),
        )

    def test_multiple_units_breaks_infillee(self, test_db, test_downscale_df):
        tcruncher = self.tclass(test_db)

        filler = tcruncher.derive_relationship(
            "Emissions|HFC|C5F12", ["Emissions|HFC|C2F6"]
        )

        test_downscale_df = self._adjust_time_style_to_match(
            test_downscale_df, test_db
        ).filter(year=[2010, 2015])
        test_downscale_df["unit"].iloc[0] = "bad units"
        with pytest.raises(
            AssertionError, match="There are multiple units for the lead variable."
        ):
            res = filler(test_downscale_df)

    def test_multiple_units_breaks_infiller_follower(self, test_db, test_downscale_df):
        test_db["unit"].iloc[2] = "bad units/yr"
        with pytest.raises(
            AssertionError,
            match=re.escape("Not all units are found in the conversion table. We lack {}".format(["units"]))
        ):
            tcruncher = self.tclass(test_db)
            filler = tcruncher.derive_relationship(
                "Emissions|HFC|C5F12", ["Emissions|HFC|C2F6"]
            )

    def test_multiple_units_breaks_infiller_leader(self, test_db, test_downscale_df):
        bad_units = "bad units/yr"
        test_db["unit"].iloc[0] = bad_units
        to_convert_var = test_db.variables(True)
        to_convert_units = to_convert_var["unit"]
        not_found = [
            y
            for y in to_convert_units.map(
                lambda x: x.split(" ")[-1][:-3].replace("-equiv", "")
            ).values
            if y not in ["C2F6", "C5F12"]
        ]
        er_msg = re.escape("Not all units are found in the conversion table. We lack {}".format(not_found))
        with pytest.raises(
            AssertionError, match=er_msg
        ):
            tcruncher = self.tclass(test_db)
            filler = tcruncher.derive_relationship(
                "Emissions|HFC|C5F12", ["Emissions|HFC|C2F6"]
            )