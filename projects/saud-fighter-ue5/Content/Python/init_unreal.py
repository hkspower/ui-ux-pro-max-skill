"""Runs when the editor starts (UE's init_unreal.py, Content/Python).

Adds the SAUD menu (Tools/unreal/saud_menu/saud_menu.py) to the top bar and
does nothing else. Every item in it is started by hand.
"""

import os
import sys

import unreal

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_MENU_DIR = os.path.join(_PROJECT, "Tools", "unreal", "saud_menu")

if os.path.isdir(_MENU_DIR) and _MENU_DIR not in sys.path:
    sys.path.insert(0, _MENU_DIR)

try:
    import saud_menu
    saud_menu.register()
except Exception as exc:
    unreal.log_warning("[SAUD] the SAUD menu was not added: %s" % exc)
