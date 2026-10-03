"""Small native-Windows helpers the app window cannot do for itself: choose a folder.

A web page cannot show the real Windows folder dialog, and asking people to type
``D:\\Some Folder\\data`` is the single most common first-run stumble. So the local server shows the
standard dialog (the same one Explorer and every Microsoft app use) in a short-lived helper process
and returns the folder that was chosen.
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys

_CSHARP = r"""
using System;
using System.Runtime.InteropServices;

public static class QuantOSFolderPicker
{
    [ComImport, Guid("DC1C5A9C-E88A-4dde-A5A1-60F82A20AEF7")]
    private class FileOpenDialogCom { }

    [ComImport, Guid("42f85136-db7e-439c-85f1-e4075d135fc8"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IFileDialog
    {
        [PreserveSig] int Show(IntPtr parent);
        void SetFileTypes(uint cFileTypes, IntPtr rgFilterSpec);
        void SetFileTypeIndex(uint iFileType);
        void GetFileTypeIndex(out uint piFileType);
        void Advise(IntPtr pfde, out uint pdwCookie);
        void Unadvise(uint dwCookie);
        void SetOptions(uint fos);
        void GetOptions(out uint pfos);
        void SetDefaultFolder(IShellItem psi);
        void SetFolder(IShellItem psi);
        void GetFolder(out IShellItem ppsi);
        void GetCurrentSelection(out IShellItem ppsi);
        void SetFileName([MarshalAs(UnmanagedType.LPWStr)] string pszName);
        void GetFileName([MarshalAs(UnmanagedType.LPWStr)] out string pszName);
        void SetTitle([MarshalAs(UnmanagedType.LPWStr)] string pszTitle);
        void SetOkButtonLabel([MarshalAs(UnmanagedType.LPWStr)] string pszText);
        void SetFileNameLabel([MarshalAs(UnmanagedType.LPWStr)] string pszLabel);
        void GetResult(out IShellItem ppsi);
    }

    [ComImport, Guid("43826d1e-e718-42ee-bc55-a1e261c37bfe"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IShellItem
    {
        void BindToHandler(IntPtr pbc, ref Guid bhid, ref Guid riid, out IntPtr ppv);
        void GetParent(out IShellItem ppsi);
        void GetDisplayName(uint sigdnName, [MarshalAs(UnmanagedType.LPWStr)] out string ppszName);
        void GetAttributes(uint sfgaoMask, out uint psfgaoAttribs);
        void Compare(IShellItem psi, uint hint, out int piOrder);
    }

    [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
    private static extern void SHCreateItemFromParsingName(
        string path, IntPtr pbc, ref Guid riid, out IShellItem item);

    // Returns the chosen folder, or an empty string when the person cancels.
    public static string Pick(IntPtr owner, string title, string initial)
    {
        IFileDialog dialog = (IFileDialog)new FileOpenDialogCom();
        uint options;
        dialog.GetOptions(out options);
        // FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST
        dialog.SetOptions(options | 0x20 | 0x40 | 0x800);
        dialog.SetTitle(title);
        if (!string.IsNullOrEmpty(initial) && System.IO.Directory.Exists(initial))
        {
            Guid iid = new Guid("43826d1e-e718-42ee-bc55-a1e261c37bfe");
            IShellItem start;
            SHCreateItemFromParsingName(initial, IntPtr.Zero, ref iid, out start);
            dialog.SetFolder(start);
        }
        int hr = dialog.Show(owner);
        if (hr == unchecked((int)0x800704C7)) { return ""; }   // ERROR_CANCELLED
        if (hr != 0) { Marshal.ThrowExceptionForHR(hr); }
        IShellItem item;
        dialog.GetResult(out item);
        string path;
        item.GetDisplayName(0x80058000, out path);              // SIGDN_FILESYSPATH
        return path;
    }
}
"""

# The dialog is owned by an invisible, always-on-top window of the helper process. With no owner
# Windows may open it behind the app; borrowing another process's foreground window as the owner
# opens nothing at all (measured). An owner of our own that is topmost puts the dialog in front.
_POWERSHELL = (
    "$ErrorActionPreference='Stop';"
    "Add-Type -AssemblyName System.Windows.Forms;"
    "Add-Type -TypeDefinition @'\n" + _CSHARP + "\n'@;"
    "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
    "$owner=New-Object System.Windows.Forms.Form;"
    "$owner.TopMost=$true;$owner.ShowInTaskbar=$false;$owner.Opacity=0;"
    "$owner.FormBorderStyle='None';$owner.StartPosition='CenterScreen';"
    "$owner.Show();$owner.Activate();"
    "try{[Console]::Out.Write([QuantOSFolderPicker]::Pick("
    "$owner.Handle,$env:QUANTOS_PICK_TITLE,$env:QUANTOS_PICK_INITIAL))}"
    "finally{$owner.Close()}"
)


class FolderPickerError(RuntimeError):
    """The folder dialog could not be shown."""


def pick_folder(title: str, initial: str | None = None, timeout: float = 900.0) -> str | None:
    """Show the Windows folder dialog. Returns the chosen path, or ``None`` if cancelled."""
    if sys.platform != "win32":
        raise FolderPickerError("The folder dialog is only available on Windows. Type the path.")
    encoded = base64.b64encode(_POWERSHELL.encode("utf-16-le")).decode("ascii")
    env = {**os.environ, "QUANTOS_PICK_TITLE": title, "QUANTOS_PICK_INITIAL": initial or ""}
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-STA",
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-EncodedCommand",
                encoded,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise FolderPickerError(f"Could not open the folder dialog: {error}") from error
    if completed.returncode != 0:
        raise FolderPickerError("Windows could not show the folder dialog. Type the path instead.")
    chosen = completed.stdout.strip()
    return chosen or None
