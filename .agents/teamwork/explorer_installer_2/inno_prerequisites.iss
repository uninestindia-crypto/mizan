; ==============================================================================
; QuantOS Prerequisite Detection & Silent Download/Installation Engine
; Target: Inno Setup 6+
; Detects and silently installs:
;   1. Microsoft Visual C++ 2015-2022 Redistributable (x64)
;   2. Microsoft Edge WebView2 Evergreen Runtime
; ==============================================================================

[CustomMessages]
english.PrereqChecking=Checking required Windows system components...
english.PrereqDownloading=Downloading required Microsoft runtimes...
english.PrereqInstallingVC=Installing Microsoft Visual C++ 2015-2022 Redistributable (x64)...
english.PrereqInstallingWV=Installing Microsoft Edge WebView2 Evergreen Runtime...
english.PrereqRebootRequired=One or more system components required a restart to complete. Please restart your computer after setup finishes.
english.PrereqOfflineTitle=Missing Windows Prerequisites — Network Offline
english.PrereqOfflinePrompt=QuantOS requires the following Microsoft components which are not installed on this PC:%n%n%1%nInternet access to Microsoft download servers could not be established.%n%nTo proceed, please do one of the following:%n  1. Connect this computer to the internet and click 'Retry'.%n  2. Download the installer(s) on another computer from official Microsoft links:%n     - VC++: https://aka.ms/vs/17/release/vc_redist.x64.exe%n     - WebView2: https://go.microsoft.com/fwlink/p/?LinkId=2124703%n     Place the file(s) into a folder named 'prerequisites' next to this installer and click 'Retry'.%n%nClick 'Cancel' to exit setup safely without modifying your computer.

[Code]
var
  PrereqDownloadPage: TDownloadWizardPage;
  NeedVCRedist: Boolean;
  NeedWebView2: Boolean;
  VCRedistRebootPending: Boolean;

// -----------------------------------------------------------------------------
// 1. Detection Functions
// -----------------------------------------------------------------------------

function IsVCRedistInstalled: Boolean;
var
  InstalledVal: Cardinal;
  MajorVal: Cardinal;
begin
  Result := False;
  // Check 1: 64-bit registry hive (Native 64-bit Windows)
  if RegQueryDWordValue(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64', 'Installed', InstalledVal) then
  begin
    if InstalledVal = 1 then
    begin
      if RegQueryDWordValue(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64', 'Major', MajorVal) then
      begin
        if MajorVal >= 14 then
          Result := True;
      end
      else
        Result := True;
    end;
  end;

  // Check 2: 32-bit registry hive / WOW6432Node fallback
  if (not Result) and RegQueryDWordValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\X64', 'Installed', InstalledVal) then
  begin
    if InstalledVal = 1 then
      Result := True;
  end;
end;

function IsWebView2Installed: Boolean;
var
  VersionStr: String;
begin
  Result := False;

  // Check 1: Machine-wide (WOW6432Node - standard 64-bit Windows location)
  if RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', VersionStr) then
  begin
    Trim(VersionStr);
    if (VersionStr <> '') and (VersionStr <> '0.0.0.0') then
    begin
      Result := True;
      Exit;
    end;
  end;

  // Check 2: Machine-wide (Native 64-bit hive)
  if RegQueryStringValue(HKLM64, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', VersionStr) then
  begin
    Trim(VersionStr);
    if (VersionStr <> '') and (VersionStr <> '0.0.0.0') then
    begin
      Result := True;
      Exit;
    end;
  end;

  // Check 3: Current User (non-elevated installations)
  if RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', VersionStr) then
  begin
    Trim(VersionStr);
    if (VersionStr <> '') and (VersionStr <> '0.0.0.0') then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

// -----------------------------------------------------------------------------
// 2. Wizard Lifecycle & UI Hooks
// -----------------------------------------------------------------------------

function OnDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  Result := True;
end;

procedure InitializePrereqWizard;
begin
  PrereqDownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), CustomMessage('PrereqDownloading'), @OnDownloadProgress);
  VCRedistRebootPending := False;
end;

// Helper to find installer binary locally (offline placement)
function FindLocalInstaller(const FileName: String): String;
var
  Candidate: String;
begin
  Result := '';
  // 1. Next to setup executable in "prerequisites\"
  Candidate := ExpandConstant('{src}\prerequisites\' + FileName);
  if FileExists(Candidate) then
  begin
    Result := Candidate;
    Exit;
  end;
  // 2. Directly next to setup executable
  Candidate := ExpandConstant('{src}\' + FileName);
  if FileExists(Candidate) then
  begin
    Result := Candidate;
    Exit;
  end;
  // 3. In temporary folder if downloaded previously
  Candidate := ExpandConstant('{tmp}\' + FileName);
  if FileExists(Candidate) then
  begin
    Result := Candidate;
    Exit;
  end;
end;

// -----------------------------------------------------------------------------
// 3. Execution & Verification Flow (PrepareToInstall Hook)
// -----------------------------------------------------------------------------

function ExecutePrerequisiteInstalls(var NeedsRestart: Boolean): String;
var
  VCInstallerPath, WVInstallerPath: String;
  ResultCode: Integer;
  MissingNames: String;
  DownloadNeeded: Boolean;
  UserRetry: Boolean;
begin
  Result := '';

  while True do
  begin
    NeedVCRedist := not IsVCRedistInstalled;
    NeedWebView2 := not IsWebView2Installed;

    if (not NeedVCRedist) and (not NeedWebView2) then
      Exit; // All prerequisites present!

    MissingNames := '';
    if NeedVCRedist then
      MissingNames := MissingNames + '  • Microsoft Visual C++ 2015-2022 Redistributable (x64)' + #13#10;
    if NeedWebView2 then
      MissingNames := MissingNames + '  • Microsoft Edge WebView2 Evergreen Runtime' + #13#10;

    // Check for offline local copies
    VCInstallerPath := '';
    WVInstallerPath := '';
    DownloadNeeded := False;

    if NeedVCRedist then
    begin
      VCInstallerPath := FindLocalInstaller('vc_redist.x64.exe');
      if VCInstallerPath = '' then
        DownloadNeeded := True;
    end;

    if NeedWebView2 then
    begin
      WVInstallerPath := FindLocalInstaller('MicrosoftEdgeWebview2Setup.exe');
      if WVInstallerPath = '' then
        DownloadNeeded := True;
    end;

    // Download missing items if not found locally
    if DownloadNeeded then
    begin
      PrereqDownloadPage.Clear;
      if NeedVCRedist and (VCInstallerPath = '') then
        PrereqDownloadPage.Add('https://aka.ms/vs/17/release/vc_redist.x64.exe', 'vc_redist.x64.exe', '');
      if NeedWebView2 and (WVInstallerPath = '') then
        PrereqDownloadPage.Add('https://go.microsoft.com/fwlink/p/?LinkId=2124703', 'MicrosoftEdgeWebview2Setup.exe', '');

      PrereqDownloadPage.Show;
      try
        try
          PrereqDownloadPage.Download;
        except
          PrereqDownloadPage.Hide;
          if PrereqDownloadPage.AbortedByUser then
          begin
            Result := 'Setup was cancelled during prerequisite download.';
            Exit;
          end
          else
          begin
            // Graceful offline fallback prompt
            UserRetry := (MsgBox(FmtMessage(CustomMessage('PrereqOfflinePrompt'), [MissingNames]), mbError, MB_RETRYCANCEL) = IDRETRY);
            if UserRetry then
              Continue // Retry loop (checks local folders or re-downloads)
            else
            begin
              Result := 'Installation cannot continue without required Microsoft components.';
              Exit;
            end;
          end;
        end;
      finally
        PrereqDownloadPage.Hide;
      end;

      // Update paths from tmp download
      if NeedVCRedist and (VCInstallerPath = '') then
        VCInstallerPath := ExpandConstant('{tmp}\vc_redist.x64.exe');
      if NeedWebView2 and (WVInstallerPath = '') then
        WVInstallerPath := ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe');
    end;

    // Execute VC++ Silent Install
    if NeedVCRedist and (VCInstallerPath <> '') and FileExists(VCInstallerPath) then
    begin
      // /install /quiet /norestart
      if Exec(VCInstallerPath, '/install /quiet /norestart', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      begin
        // 0 = Success, 3010 = Success Reboot Required, 1638 = Newer version already installed
        if (ResultCode = 0) or (ResultCode = 1638) then
        begin
          // Succeeded cleanly
        end
        else if ResultCode = 3010 then
        begin
          VCRedistRebootPending := True;
          NeedsRestart := True;
        end
        else
        begin
          Result := Format('Visual C++ Redistributable installation failed with exit code %d (0x%x).', [ResultCode, ResultCode]);
          Exit;
        end;
      end
      else
      begin
        Result := 'Failed to launch Visual C++ Redistributable installer process.';
        Exit;
      end;
    end;

    // Execute WebView2 Silent Install
    if NeedWebView2 and (WVInstallerPath <> '') and FileExists(WVInstallerPath) then
    begin
      // /silent /install
      if Exec(WVInstallerPath, '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      begin
        // 0 = Success
        if ResultCode <> 0 then
        begin
          Result := Format('Microsoft Edge WebView2 installation failed with exit code %d (0x%x).', [ResultCode, ResultCode]);
          Exit;
        end;
      end
      else
      begin
        Result := 'Failed to launch WebView2 Runtime installer process.';
        Exit;
      end;
    end;

    // Post-installation verification check
    if not IsVCRedistInstalled then
    begin
      Result := 'Visual C++ 2015-2022 Redistributable installation completed, but runtime registry keys were not detected.';
      Exit;
    end;

    if not IsWebView2Installed then
    begin
      Result := 'Microsoft Edge WebView2 installation completed, but runtime registry keys were not detected.';
      Exit;
    end;

    // All done and verified
    Exit;
  end;
end;

// Hook PrepareToInstall
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := ExecutePrerequisiteInstalls(NeedsRestart);
end;
