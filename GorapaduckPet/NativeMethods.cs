using System.Runtime.InteropServices;
using Forms = System.Windows.Forms;

namespace GorapaduckPet;

internal static class NativeMethods
{
    [StructLayout(LayoutKind.Sequential)]
    private struct Rect { public int Left, Top, Right, Bottom; }

    [DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll")]
    private static extern bool GetWindowRect(IntPtr hWnd, out Rect rect);

    public static bool IsForegroundFullscreen()
    {
        var handle = GetForegroundWindow();
        if (handle == IntPtr.Zero || !GetWindowRect(handle, out var rect)) return false;
        var screen = Forms.Screen.FromHandle(handle);
        var bounds = screen.Bounds;
        const int tolerance = 2;
        return rect.Left <= bounds.Left + tolerance && rect.Top <= bounds.Top + tolerance &&
               rect.Right >= bounds.Right - tolerance && rect.Bottom >= bounds.Bottom - tolerance;
    }
}
