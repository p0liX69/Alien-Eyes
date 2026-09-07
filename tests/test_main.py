# tests/test_main.py
from alien_eyes.main import parse_args, pick_backend


def test_pick_backend_sim_flag_forces_sim():
    assert pick_backend(True, is_pi_fn=lambda: True) == "sim"


def test_pick_backend_pi_flag_forces_pi():
    assert pick_backend(False, is_pi_fn=lambda: False) == "pi"


def test_pick_backend_auto_detects_pi():
    assert pick_backend(None, is_pi_fn=lambda: True) == "pi"


def test_pick_backend_auto_detects_mac():
    assert pick_backend(None, is_pi_fn=lambda: False) == "sim"


def test_parse_args_sim_flag():
    args = parse_args(["--sim"])
    assert args.sim is True
    assert args.pi is False


def test_parse_args_pi_flag():
    args = parse_args(["--pi"])
    assert args.sim is False
    assert args.pi is True
