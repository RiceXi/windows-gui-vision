# Make a window the real foreground window, not just the top one.
#
# SetForegroundWindow alone is refused when the calling process is not the one the user is
# interacting with, and the refusal is silent: the call returns and nothing moves. The old
# workaround still works - attach this thread's input queue to the foreground window's thread,
# ask for the foreground, then detach.
#
#   powershell -File forcefocus.ps1 -TargetPid 1234
param([Parameter(Mandatory=$true)][int]$TargetPid)

$sig = @'
using System;using System.Runtime.InteropServices;
public class FF {
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
 [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
 [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
 public delegate bool EnumProc(IntPtr h, IntPtr l);
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
 public static IntPtr main = IntPtr.Zero;
 public static int mw = 0;
 public static void Find(uint want) {
   main = IntPtr.Zero; mw = 0;
   EnumWindows(delegate(IntPtr h, IntPtr l) {
     uint pid; GetWindowThreadProcessId(h, out pid);
     if (pid != want || !IsWindowVisible(h)) return true;
     RECT r; GetWindowRect(h, out r);
     int w = r.R - r.L;
     if (w > mw) { mw = w; main = h; }
     return true;
   }, IntPtr.Zero);
 }
 public static string Focus() {
   if (main == IntPtr.Zero) return "no window";
   uint fgPid; uint fg = GetWindowThreadProcessId(GetForegroundWindow(), out fgPid);
   uint me = GetCurrentThreadId();
   AttachThreadInput(me, fg, true);
   BringWindowToTop(main);
   bool ok = SetForegroundWindow(main);
   AttachThreadInput(me, fg, false);
   return "setforeground=" + ok + " fgthread=" + fg;
 }
}
'@
Add-Type -TypeDefinition $sig

[FF]::Find([uint32]$TargetPid)
Write-Output ("handle {0}: {1}" -f [FF]::main, [FF]::Focus())
