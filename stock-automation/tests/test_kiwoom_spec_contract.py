import ast
import json
import unittest
from pathlib import Path


SPEC_PATH = (
    Path(__file__).resolve().parents[2]
    / "Kiwoom-REST-API"
    / "kiwoom"
    / "_data"
    / "kiwoom_api_spec.json"
)


# These are the exact Kiwoom REST contracts consumed by the automation engine.
# Keeping the request and response fields here makes an upstream specification
# change fail loudly before an image is deployed to AWS.
USED_CONTRACTS = {
    "ka10099": {
        "path": "/api/dostk/stkinfo",
        "request": {"mrkt_tp"},
        "response": {"list", "code", "name", "nxtEnable"},
    },
    "ka10032": {
        "path": "/api/dostk/rkinfo",
        "request": {"mrkt_tp", "mang_stk_incls", "stex_tp"},
        "response": {
            "trde_prica_upper", "stk_cd", "stk_nm", "cur_prc", "flu_rt",
            "sel_bid", "buy_bid", "now_trde_qty", "pred_trde_qty", "trde_prica",
        },
    },
    "ka10007": {
        "path": "/api/dostk/mrkcond",
        "request": {"stk_cd"},
        "response": {
            "stk_nm", "stk_cd", "date", "tm", "cur_prc", "flu_rt",
            "open_pric", "high_pric", "low_pric", "trde_qty", "trde_prica",
            "pred_trde_qty", "sel_1bid", "buy_1bid",
            *(f"sel_{number}bid_req" for number in range(1, 11)),
            *(f"buy_{number}bid_req" for number in range(1, 11)),
        },
    },
    "ka10081": {
        "path": "/api/dostk/chart",
        "request": {"stk_cd", "base_dt", "upd_stkpc_tp"},
        "response": {
            "stk_dt_pole_chart_qry", "cur_prc", "trde_qty", "trde_prica", "dt",
            "open_pric", "high_pric", "low_pric",
        },
    },
    "ka10080": {
        "path": "/api/dostk/chart",
        "request": {"stk_cd", "tic_scope", "upd_stkpc_tp", "base_dt"},
        "response": {
            "stk_min_pole_chart_qry", "cur_prc", "trde_qty", "cntr_tm",
            "open_pric", "high_pric", "low_pric",
        },
    },
    "ka10001": {
        "path": "/api/dostk/stkinfo",
        "request": {"stk_cd"},
        "response": {
            "stk_cd", "stk_nm", "mac", "per", "pbr", "roe", "sale_amt",
            "bus_pro", "cup_nga", "cur_prc",
        },
    },
    "ka20001": {
        "path": "/api/dostk/sect",
        "request": {"mrkt_tp", "inds_cd"},
        "response": {"cur_prc", "flu_rt"},
    },
    "ka90001": {
        "path": "/api/dostk/thme",
        "request": {"qry_tp", "stk_cd", "date_tp", "thema_nm", "flu_pl_amt_tp", "stex_tp"},
        "response": {
            "thema_grp", "thema_grp_cd", "thema_nm", "flu_rt",
            "rising_stk_num", "fall_stk_num",
        },
    },
    "ka90002": {
        "path": "/api/dostk/thme",
        "request": {"date_tp", "thema_grp_cd", "stex_tp"},
        "response": {"thema_comp_stk", "stk_cd", "stk_nm"},
    },
    "ka90009": {
        "path": "/api/dostk/rkinfo",
        "request": {"mrkt_tp", "amt_qty_tp", "qry_dt_tp", "date", "stex_tp"},
        "response": {
            "frgnr_orgn_trde_upper", "orgn_netslmt_stk_cd",
            "orgn_netslmt_amt", "orgn_netprps_stk_cd", "orgn_netprps_amt",
        },
    },
    "ka90004": {
        "path": "/api/dostk/stkinfo",
        "request": {"dt", "mrkt_tp", "stex_tp"},
        "response": {"stk_prm_trde_prst", "stk_cd", "netprps_prica"},
    },
    "kt10000": {
        "path": "/api/dostk/ordr",
        "request": {"dmst_stex_tp", "stk_cd", "ord_qty", "ord_uv", "trde_tp", "cond_uv"},
        "response": {"ord_no", "dmst_stex_tp"},
    },
    "kt10001": {
        "path": "/api/dostk/ordr",
        "request": {"dmst_stex_tp", "stk_cd", "ord_qty", "ord_uv", "trde_tp", "cond_uv"},
        "response": {"ord_no", "dmst_stex_tp"},
    },
    "kt00007": {
        "path": "/api/dostk/acnt",
        "request": {"ord_dt", "qry_tp", "stk_bond_tp", "sell_tp", "stk_cd", "fr_ord_no", "dmst_stex_tp"},
        "response": {
            "acnt_ord_cntr_prps_dtl", "ord_no", "ord_qty", "cntr_qty", "cntr_uv",
            "ord_remnq", "acpt_tp",
        },
    },
    "kt00001": {
        "path": "/api/dostk/acnt",
        "request": {"qry_tp"},
        "response": {"ord_alow_amt"},
    },
    "kt00018": {
        "path": "/api/dostk/acnt",
        "request": {"qry_tp", "dmst_stex_tp"},
        "response": {
            "acnt_evlt_remn_indv_tot", "stk_cd", "rmnd_qty", "trde_able_qty", "evlt_amt",
        },
    },
    "ka10074": {
        "path": "/api/dostk/acnt",
        "request": {"strt_dt", "end_dt"},
        "response": {"rlzt_pl"},
    },
}


class KiwoomSpecContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SPEC_PATH.exists():
            raise RuntimeError(f"bundled Kiwoom specification is missing: {SPEC_PATH}")
        raw = json.loads(SPEC_PATH.read_text(encoding="utf-8"))["apis"]
        cls.specs = {}
        for name, spec in raw.items():
            api_id = str(spec.get("meta", {}).get("API ID", ""))
            if api_id:
                cls.specs[api_id] = (name, spec)

    def test_all_runtime_contracts_match_bundled_official_spec(self):
        for api_id, expected in USED_CONTRACTS.items():
            with self.subTest(api_id=api_id):
                self.assertIn(api_id, self.specs)
                _name, spec = self.specs[api_id]
                self.assertEqual("POST", spec["meta"]["Method"])
                self.assertEqual(expected["path"], spec["meta"]["URL"])

                request_rows = spec["request"]["body"]
                request_fields = {row["element"] for row in request_rows}
                required_fields = {
                    row["element"] for row in request_rows if row.get("required") == "Y"
                }
                self.assertTrue(expected["request"] <= request_fields)
                self.assertTrue(required_fields <= expected["request"])

                response_fields = {
                    row["element"] for row in spec["response"]["body"]
                }
                self.assertTrue(expected["response"] <= response_fields)

    def test_source_api_id_and_path_pairs_use_the_verified_contracts(self):
        source_root = Path(__file__).resolve().parents[1] / "src" / "stock_automation"
        files = [source_root / "providers" / "kiwoom.py", source_root / "aws_runtime.py"]
        observed = set()
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                api_id = request_path = None
                for keyword in node.keywords:
                    if keyword.arg == "api_id" and isinstance(keyword.value, ast.Constant):
                        api_id = keyword.value.value
                    if keyword.arg == "path" and isinstance(keyword.value, ast.Constant):
                        request_path = keyword.value.value
                if (
                    api_id is None
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in {"_single", "_list"}
                    and len(node.args) >= 2
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[1], ast.Constant)
                ):
                    api_id = node.args[0].value
                    request_path = node.args[1].value
                if isinstance(api_id, str) and api_id.startswith("ka"):
                    observed.add((api_id, request_path))

        expected = {(api_id, contract["path"]) for api_id, contract in USED_CONTRACTS.items()}
        self.assertTrue(observed <= expected, observed - expected)


if __name__ == "__main__":
    unittest.main()
