"""Tests for scripts/record_wake_samples.py"""

import sys
import os

# Ensure the scripts directory is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_script_importable():
    """Module can be imported without side effects."""
    import record_wake_samples
    assert hasattr(record_wake_samples, "main")
    assert hasattr(record_wake_samples, "record_clip")
    assert hasattr(record_wake_samples, "save_wav")


def test_argparse_defaults():
    """Parser has correct default values."""
    from record_wake_samples import build_parser

    parser = build_parser()
    opts = parser.parse_args([])

    assert opts.count == 50
    assert opts.output_dir == "/tmp/kisti_wake_samples/real_positive/"
    assert opts.prefix == "pos"
    assert opts.device == ""


def test_generate_filename():
    """Filenames follow the pattern {prefix}_NNNN.wav."""
    from record_wake_samples import generate_filename

    assert generate_filename("/tmp/out", "pos", 1) == "/tmp/out/pos_0001.wav"
    assert generate_filename("/tmp/out", "pos", 42) == "/tmp/out/pos_0042.wav"
    assert generate_filename("/tmp/out", "neg", 999) == "/tmp/out/neg_0999.wav"
    assert generate_filename("/data", "pos", 10000) == "/data/pos_10000.wav"
