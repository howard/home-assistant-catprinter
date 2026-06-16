"""Parity / characterization tests for the vendored printer protocol.

These import ``commands.py`` directly (it has no Home Assistant or third-party
dependencies) so they run without a Home Assistant install. They lock the
byte-level output so future edits can't silently change the wire protocol.
"""
import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "custom_components", "catprinter"),
)

import commands  # noqa: E402


def test_checksum_known_vector():
    # chk_sum walks CHECKSUM_TABLE; verify against an independently computed value.
    payload = bytearray([0x00, 0x30])
    b2 = 0
    for byte in payload:
        b2 = commands.CHECKSUM_TABLE[(b2 ^ byte) & 0xFF]
    assert commands.chk_sum(payload, 0, len(payload)) == b2


def test_cmd_set_energy_framing():
    cmd = commands.cmd_set_energy(0xFFFF)
    # 0x51 0x78 0xaf <len-lo=2> <len-hi=0> ... high, low bytes of energy
    assert cmd[0] == 0x51
    assert cmd[1] == 0x78
    assert cmd[2] == 0xAF  # -81 unsigned
    assert cmd[4] == 0x02  # payload length
    assert cmd[6] == 0xFF  # energy high byte
    assert cmd[7] == 0xFF  # energy low byte
    assert cmd[-1] == 0xFF  # trailer
    # checksum byte is over the 2 payload bytes
    assert cmd[8] == commands.chk_sum(cmd, 6, 2)


def test_print_row_all_white_uses_run_length():
    # A full white row (no black pixels) compresses well -> run-length command 0xbf.
    row = [False] * commands.PRINT_WIDTH
    out = commands.cmd_print_row(row)
    assert out[0] == 0x51 and out[1] == 0x78
    assert out[2] == 0xBF  # -65 unsigned == run-length print command
    assert out[-1] == 0xFF


def test_print_row_falls_back_to_fixed_length_when_incompressible():
    # Alternating pixels defeat run-length encoding -> fixed-length command 0xa2.
    row = [i % 2 == 0 for i in range(commands.PRINT_WIDTH)]
    out = commands.cmd_print_row(row)
    assert out[2] == 0xA2  # -94 unsigned == fixed-length print command
    # Fixed-length payload is PRINT_WIDTH / 8 bytes.
    assert out[4] == commands.PRINT_WIDTH // 8


def test_byte_encode_bit_order():
    # First pixel maps to the least-significant bit of the first byte.
    row = [True] + [False] * 7
    assert commands.byte_encode(row) == [0b00000001]
    row = [False] * 7 + [True]
    assert commands.byte_encode(row) == [0b10000000]


def test_cmds_print_img_prologue_and_epilogue():
    rows = [[False] * commands.PRINT_WIDTH for _ in range(3)]
    data = commands.cmds_print_img(rows, energy=0xFFFF)
    # Begins with device-state query.
    assert data[: len(commands.CMD_GET_DEV_STATE)] == commands.CMD_GET_DEV_STATE
    # Ends with a device-state query (epilogue).
    assert data[-len(commands.CMD_GET_DEV_STATE):] == commands.CMD_GET_DEV_STATE
    # Contains the lattice start/end markers.
    assert bytes(commands.CMD_LATTICE_START) in bytes(data)
    assert bytes(commands.CMD_LATTICE_END) in bytes(data)
