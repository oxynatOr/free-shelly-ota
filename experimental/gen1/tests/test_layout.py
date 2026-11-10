"""Tests for components/gen1_ota/layout.py: the CSV parser, the derived values and the manifest -> CSV generator."""
import importlib.util
import json
import os
import sys

import pytest

HERE = os.path.dirname(__file__)
spec = importlib.util.spec_from_file_location("gen1_ota_layout", os.path.join(HERE, "..", "components", "gen1_ota", "layout.py"))
L = importlib.util.module_from_spec(spec)
sys.modules["gen1_ota_layout"] = L
spec.loader.exec_module(L)
PRESETS = os.path.join(HERE, "..", "components", "gen1_ota", "partitions")


def preset(name):
    with open(os.path.join(PRESETS, name + "-stock.csv"), encoding="utf-8") as f:
        return L.parse_csv(f.read())


def test_shelly1_matches_the_old_constants():
    lay = preset("SHSW-1")
    assert (lay.cfg, lay.slot0, lay.slot1, lay.stage, lay.stage_end) == (0x1000, 0x8000, 0x108000, 0x70000, 0xFA000)
    assert lay.max_image == 0x68000 and lay.irom_org == 0x40208010 and lay.irom_len == 0xB2FF0
    assert (lay.eeprom, lay.rfcal_sector, lay.cache_bank) == (0xFB000, 0xFC, 0)


def test_plug2_layout():
    lay = preset("SHPLG2-1")
    assert (lay.cfg, lay.slot0, lay.slot1) == (0x7000, 0x100000, 0x200000)
    assert lay.irom_org == 0x40200010 and lay.cache_bank == 1
    assert lay.stage_end <= lay.slot0 and lay.max_image <= lay.stage_size


def test_ld_and_defines():
    lay = preset("SHSW-1")
    ld = L.render_ld(lay)
    assert "org = 0x40208010, len = 0xB2FF0" in ld
    assert "_SPIFFS_end = 0x402FA000" in ld and "_EEPROM_start = 0x402FB000" in ld
    d = L.defines(lay)
    assert d["GEN1_SLOT0"] == "0x8000u" and d["GEN1_RFCAL_SECTOR"] == "0xFCu"


def manifest(path):
    with open(os.path.join(HERE, "..", "out", "stock", path, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.skipif(not os.path.isdir(os.path.join(HERE, "..", "out", "stock", "SHSW-1")), reason="stock packages not extracted")
def test_presets_equal_the_generated_layout_of_the_packages():
    for pkg in ("SHSW-1", "SHPLG-S", "SHPLG2-1", "SHBDUO-1", "SHEM"):
        assert L.parse_csv(L.partitions_from_manifest(manifest(pkg))) == preset(pkg)


def test_bad_tables_are_refused():
    ok = """rboot_cfg, data, rboot, 0x1000, 0x1000,
app_0, app, ota_0, 0x8000, 0xB3000,
fs_0, data, spiffs, 0xBB000, 0x40000,
app_1, app, ota_1, 0x108000, 0xB3000,
"""
    assert L.parse_csv(ok).stage == 0x70000
    with pytest.raises(L.LayoutError):
        L.parse_csv(ok.replace("app_1, app, ota_1, 0x108000", "app_1, app, ota_1, 0x40000"))  # overlaps slot 0
    with pytest.raises(L.LayoutError):
        L.parse_csv(ok.replace("rboot_cfg, data, rboot, 0x1000, 0x1000,\n", ""))  # row missing
    with pytest.raises(L.LayoutError):
        L.parse_csv(ok.replace("0x8000", "0x8100"))  # not sector aligned
    with pytest.raises(L.LayoutError):
        L.parse_csv(ok.replace("0xB3000", "0xB2000", 1))  # the slots differ in size
    with pytest.raises(L.LayoutError):
        L.parse_csv("app_0, app, ota_0, 0x8000\n")  # too few columns


def test_k_and_m_suffixes_and_a_stage_row():
    t = """rboot_cfg, data, rboot, 4K, 4K,
app_0, app, ota_0, 32K, 716K,
app_1, app, ota_1, 1056K, 716K,
stage, data, scratch, 0x70000, 0x8A000,
"""
    lay = L.parse_csv(t)
    assert (lay.cfg, lay.slot0, lay.slot1, lay.stage) == (0x1000, 0x8000, 0x108000, 0x70000)


def test_not_a_gen1_package_is_refused():
    with pytest.raises(L.LayoutError):
        L.partitions_from_manifest({"platform": "cc3200", "parts": {}})
