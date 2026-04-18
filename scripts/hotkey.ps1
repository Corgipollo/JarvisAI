# Jarvis AI — Global Hotkey (Alt+J toggle show/hide)
# Se ejecuta en background via start-jarvis.bat

Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using System.Diagnostics;
using System.Threading;

public class JarvisHotkey {
    [DllImport("user32.dll")]
    public static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);

    [DllImport("user32.dll")]
    public static extern bool UnregisterHotKey(IntPtr hWnd, int id);

    [DllImport("user32.dll")]
    static extern IntPtr FindWindow(string lpClassName, string lpWindowName);

    [DllImport("user32.dll")]
    static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll")]
    static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

    private static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
    private const uint SWP_NOMOVE = 0x0002;
    private const uint SWP_NOSIZE = 0x0001;
    private const uint SWP_SHOWWINDOW = 0x0040;

    public static void ToggleJarvis() {
        // Buscar ventana de Chrome con Jarvis
        Process[] procs = Process.GetProcessesByName("chrome");
        foreach (Process p in procs) {
            if (p.MainWindowTitle.Contains("Jarvis") || p.MainWindowTitle.Contains("127.0.0.1:8766")) {
                IntPtr hwnd = p.MainWindowHandle;
                if (hwnd != IntPtr.Zero) {
                    if (IsWindowVisible(hwnd)) {
                        ShowWindow(hwnd, 0); // SW_HIDE
                    } else {
                        ShowWindow(hwnd, 5); // SW_SHOW
                        SetForegroundWindow(hwnd);
                        // Poner siempre arriba
                        SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW);
                    }
                    return;
                }
            }
        }

        // Si no encontro ventana, abrir Jarvis
        Process.Start(new ProcessStartInfo {
            FileName = @"C:\Program Files\Google\Chrome\Application\chrome.exe",
            Arguments = "--app=http://127.0.0.1:8766 --window-size=420,550 --window-position=8,8 --user-data-dir=\"C:\\Users\\Emmanuel\\AppData\\Local\\JarvisApp\"",
            UseShellExecute = false
        });
    }
}
"@ -ReferencedAssemblies System.Windows.Forms

# Registrar Alt+J (Alt = 0x0001, J = 0x4A)
$signature = @"
[DllImport("user32.dll")]
public static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);
[DllImport("user32.dll")]
public static extern bool UnregisterHotKey(IntPtr hWnd, int id);
"@
$WinAPI = Add-Type -MemberDefinition $signature -Name "WinAPI" -Namespace "HotKeys" -PassThru

# Alt = 0x0001, J = 0x4A
$MOD_ALT = 0x0001
$VK_J = 0x4A
$HOTKEY_ID = 1

$result = $WinAPI::RegisterHotKey([IntPtr]::Zero, $HOTKEY_ID, $MOD_ALT, $VK_J)
if ($result) {
    Write-Host "[Jarvis] Hotkey Alt+J registrado OK"
} else {
    Write-Host "[Jarvis] Error registrando hotkey (puede estar en uso)"
}

# Message loop
Add-Type -AssemblyName System.Windows.Forms
$msg = New-Object System.Windows.Forms.Message

Write-Host "[Jarvis] Hotkey listener activo. Alt+J para toggle."
Write-Host "[Jarvis] Ctrl+C para cerrar."

while ($true) {
    if ([System.Windows.Forms.Application]::DoEvents) { }

    # Check for WM_HOTKEY message
    $peek = @"
using System;
using System.Runtime.InteropServices;

public class MsgPeek {
    [StructLayout(LayoutKind.Sequential)]
    public struct MSG {
        public IntPtr hwnd;
        public uint message;
        public IntPtr wParam;
        public IntPtr lParam;
        public uint time;
        public int pt_x;
        public int pt_y;
    }

    [DllImport("user32.dll")]
    public static extern bool PeekMessage(out MSG lpMsg, IntPtr hWnd, uint wMsgFilterMin, uint wMsgFilterMax, uint wRemoveMsg);

    public const uint WM_HOTKEY = 0x0312;
    public const uint PM_REMOVE = 0x0001;
}
"@

    try { Add-Type -TypeDefinition $peek -ErrorAction SilentlyContinue } catch {}

    $m = New-Object MsgPeek+MSG
    if ([MsgPeek]::PeekMessage([ref]$m, [IntPtr]::Zero, [MsgPeek]::WM_HOTKEY, [MsgPeek]::WM_HOTKEY, [MsgPeek]::PM_REMOVE)) {
        if ($m.message -eq [MsgPeek]::WM_HOTKEY) {
            [JarvisHotkey]::ToggleJarvis()
        }
    }

    Start-Sleep -Milliseconds 50
}

# Cleanup
$WinAPI::UnregisterHotKey([IntPtr]::Zero, $HOTKEY_ID)
