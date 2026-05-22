"""window_control.py - Force focus/maximize de cualquier ventana Windows.

Técnicas en cascada (de más conservadora a más agresiva):
  1. ShowWindow + SetForegroundWindow simple
  2. AttachThreadInput hack: pega input queue del proceso target al nuestro,
     después SetForegroundWindow ya no se bloquea
  3. SendKeys('%') Alt virtual + ShowWindow_RESTORE (truco Gemini)
  4. AllowSetForegroundWindow + post WM_SYSCOMMAND SC_MAXIMIZE

Si Jarvis se ejecuta con privilegios de Administrator, todas las técnicas
funcionan sin restriction. Sin admin: las primeras 2 pueden fallar
silenciosamente en Win11.

Uso:
    from jarvis_v2.skills.window_control import force_maximize_window
    force_maximize_window("Telegram")
"""
from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes


SW_RESTORE = 9
SW_MAXIMIZE = 3
WM_SYSCOMMAND = 0x0112
SC_MAXIMIZE = 0xF030


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def find_window_by_title(keyword: str) -> int | None:
    """EnumWindows + match parcial titulo (case-insensitive). Devuelve hwnd."""
    user32 = ctypes.windll.user32
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                          ctypes.c_void_p)
    found = {"hwnd": None}
    kw = keyword.lower()

    def _cb(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if kw in title.lower():
            found["hwnd"] = hwnd
            return False  # stop enum
        return True

    user32.EnumWindows(EnumWindowsProc(_cb), 0)
    return found["hwnd"]


def force_foreground(hwnd: int) -> bool:
    """AttachThreadInput hack para bypass foreground lock de Windows."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    fg_hwnd = user32.GetForegroundWindow()
    if fg_hwnd == hwnd:
        return True

    # Get thread IDs
    fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None)
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)
    cur_thread = kernel32.GetCurrentThreadId()

    attached_fg = False
    attached_target = False
    try:
        # Attach our input queue to foreground + target
        if fg_thread != cur_thread:
            attached_fg = bool(user32.AttachThreadInput(cur_thread, fg_thread,
                                                          True))
        if target_thread != cur_thread:
            attached_target = bool(user32.AttachThreadInput(cur_thread,
                                                              target_thread,
                                                              True))

        # Ahora SetForegroundWindow NO se bloquea
        user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetActiveWindow(hwnd)

        time.sleep(0.3)
        return user32.GetForegroundWindow() == hwnd
    finally:
        if attached_fg:
            user32.AttachThreadInput(cur_thread, fg_thread, False)
        if attached_target:
            user32.AttachThreadInput(cur_thread, target_thread, False)


def _send_alt_unlock():
    """Truco Gemini: SendKeys('%') envia Alt virtual que destraba foreground lock."""
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.SendKeys("%")
        time.sleep(0.1)
    except Exception as e:
        print(f"[window] SendKeys alt fail: {e}", file=sys.stderr)


def force_maximize_window(keyword: str, retries: int = 3) -> dict:
    """Cascada de técnicas para maximizar + foreground una ventana.

    Returns: {ok, hwnd, technique, admin}
    """
    user32 = ctypes.windll.user32
    admin = _is_admin()
    hwnd = find_window_by_title(keyword)
    if not hwnd:
        return {"ok": False, "error": "window_not_found",
                "keyword": keyword, "admin": admin}

    for attempt in range(retries):
        # Tecnica 1: simple ShowWindow + SetForeground
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
        time.sleep(0.4)
        if user32.GetForegroundWindow() == hwnd:
            return {"ok": True, "hwnd": hwnd, "technique": "simple",
                    "attempt": attempt + 1, "admin": admin}

        # Tecnica 2: AttachThreadInput
        if force_foreground(hwnd):
            user32.ShowWindow(hwnd, SW_MAXIMIZE)
            time.sleep(0.3)
            if user32.GetForegroundWindow() == hwnd:
                return {"ok": True, "hwnd": hwnd, "technique": "attach_thread",
                        "attempt": attempt + 1, "admin": admin}

        # Tecnica 3: Alt unlock + retry
        _send_alt_unlock()
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
        time.sleep(0.4)
        if user32.GetForegroundWindow() == hwnd:
            return {"ok": True, "hwnd": hwnd, "technique": "alt_unlock",
                    "attempt": attempt + 1, "admin": admin}

        # Tecnica 4: PostMessage SC_MAXIMIZE (incluso si foreground falla, maxime)
        user32.PostMessageW(hwnd, WM_SYSCOMMAND, SC_MAXIMIZE, 0)
        time.sleep(0.4)

    fg = user32.GetForegroundWindow()
    return {"ok": False, "error": "foreground_lock_persistent",
            "hwnd": hwnd, "current_fg": fg, "admin": admin,
            "hint": ("Correr daemons como Administrator (Run as Admin) "
                      "para alcanzar high integrity level y bypass total")}


def minimize_window(keyword: str) -> dict:
    """Minimiza ventana (libera foreground para que otra app tome el foco)."""
    user32 = ctypes.windll.user32
    SW_MINIMIZE = 6
    hwnd = find_window_by_title(keyword)
    if not hwnd:
        return {"ok": False, "error": "window_not_found"}
    user32.ShowWindow(hwnd, SW_MINIMIZE)
    return {"ok": True, "hwnd": hwnd}


def list_visible_windows() -> list[dict]:
    """Lista ventanas visibles con titulo (para debug)."""
    user32 = ctypes.windll.user32
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                          ctypes.c_void_p)
    wins = []

    def _cb(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        wins.append({"hwnd": hwnd, "title": buf.value})
        return True

    user32.EnumWindows(EnumWindowsProc(_cb), 0)
    return wins


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: window_control.py <keyword> [list|min|max]")
        sys.exit(1)
    op = sys.argv[1]
    if op == "list":
        for w in list_visible_windows():
            print(f"  {w['hwnd']}: {w['title'][:80]}")
    elif op == "min":
        kw = sys.argv[2]
        print(minimize_window(kw))
    else:
        # default: max
        kw = " ".join(sys.argv[1:])
        import json
        r = force_maximize_window(kw)
        print(json.dumps(r, ensure_ascii=False, indent=2))
