!include LogicLib.nsh
!include nsDialogs.nsh

Var MinionsCliPathCheckbox
Var MinionsCliPathState

Page custom MINIONS_CLI_PATH_PAGE MINIONS_CLI_PATH_PAGE_LEAVE

!macro MINIONS_UPDATE_CLI_PATH ACTION
  InitPluginsDir
  File /oname=$PLUGINSDIR\minions-update-path.ps1 "..\..\..\..\nsis\update-minions-path.ps1"
  nsExec::ExecToStack `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PLUGINSDIR\minions-update-path.ps1" -Action "${ACTION}" -Path "$INSTDIR\binaries\minions-backend"`
  Pop $0
  Pop $1
!macroend

!macro MINIONS_ADD_CLI_PATH_IF_SELECTED
  ${If} $MinionsCliPathState == 0
    DetailPrint "$(minionsCliPathSkipped)"
  ${Else}
    IfFileExists "$INSTDIR\binaries\minions-backend\minions.exe" 0 minions_cli_path_missing
    !insertmacro MINIONS_UPDATE_CLI_PATH "Add"
    ${If} $0 == 0
      DetailPrint "$(minionsCliPathAdded)"
    ${Else}
      DetailPrint "$(minionsCliPathUpdateFailed)"
      DetailPrint "$1"
    ${EndIf}
    Goto minions_cli_path_done
    minions_cli_path_missing:
      DetailPrint "$(minionsCliPathMissing)"
    minions_cli_path_done:
  ${EndIf}
!macroend

!macro MINIONS_REMOVE_CLI_PATH
  !insertmacro MINIONS_UPDATE_CLI_PATH "Remove"
  ${If} $0 != 0
    DetailPrint "$(minionsCliPathUpdateFailed)"
    DetailPrint "$1"
  ${EndIf}
!macroend

!macro MINIONS_INSTALL_DEBUG_LAUNCHER
  SetOutPath "$INSTDIR"
  File /oname=minions-desktop-debug.cmd "..\..\..\..\nsis\minions-desktop-debug.cmd"
  File /oname=minions-desktop-debug.ps1 "..\..\..\..\nsis\minions-desktop-debug.ps1"
  CreateShortcut "$SMPROGRAMS\Minions Desktop (Debug).lnk" "$INSTDIR\minions-desktop-debug.cmd" "" "$INSTDIR\minions-desktop.exe" 0
!macroend

!macro MINIONS_REMOVE_DEBUG_LAUNCHER
  Delete "$SMPROGRAMS\Minions Desktop (Debug).lnk"
  Delete "$INSTDIR\minions-desktop-debug.cmd"
  Delete "$INSTDIR\minions-desktop-debug.ps1"
!macroend

Function MINIONS_CLI_PATH_PAGE
  ${GetOptions} $CMDLINE "/NO_MINIONS_PATH" $0
  ${IfNot} ${Errors}
    StrCpy $MinionsCliPathState 0
    Abort
  ${EndIf}

  ${GetOptions} $CMDLINE "/P" $0
  ${IfNot} ${Errors}
    StrCpy $MinionsCliPathState 1
    Abort
  ${EndIf}

  ${If} ${Silent}
    StrCpy $MinionsCliPathState 1
    Abort
  ${EndIf}

  nsDialogs::Create 1018
  Pop $0
  ${If} $0 == error
    Abort
  ${EndIf}

  !insertmacro MUI_HEADER_TEXT "$(minionsCliPathPageTitle)" "$(minionsCliPathPageSubtitle)"
  ${NSD_CreateLabel} 0 0 100% 28u "$(minionsCliPathPageDescription)"
  Pop $0
  ${NSD_CreateCheckbox} 0 44u 100% 12u "$(minionsCliPathCheckbox)"
  Pop $MinionsCliPathCheckbox

  ${If} $MinionsCliPathState == 0
    SendMessage $MinionsCliPathCheckbox ${BM_SETCHECK} 0 0
  ${Else}
    SendMessage $MinionsCliPathCheckbox ${BM_SETCHECK} 1 0
  ${EndIf}

  nsDialogs::Show
FunctionEnd

Function MINIONS_CLI_PATH_PAGE_LEAVE
  ${NSD_GetState} $MinionsCliPathCheckbox $MinionsCliPathState
FunctionEnd

!macro MINIONS_STOP_BACKEND_SIDECAR
  ; The Python backend is a Tauri sidecar, not a user-facing window. A leftover
  ; (possibly orphaned, see #5550) backend keeps its PyInstaller ``.pyd`` modules
  ; memory-mapped, which locks them on Windows. The installer then fails to
  ; overwrite those files and shows the cryptic native "can't write file"
  ; abort/retry/ignore dialog.
  ;
  ; The helper stops only backend processes whose executable lives under
  ; $INSTDIR, so a coexisting Minions install is left untouched. It is
  ; ConstrainedLanguage-safe (WDAC/AppLocker): no ``[System.*]`` static calls,
  ; which throw in that mode and made the previous helper give up silently. It
  ; exits non-zero while a scoped backend is still running; if that persists we
  ; surface a friendly retry prompt rather than the raw OS dialog.
  Push $0
  InitPluginsDir
  File /oname=$PLUGINSDIR\minions-stop-backend-sidecar.ps1 "..\..\..\..\nsis\stop-backend-sidecar.ps1"
  ${Do}
    nsExec::Exec `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PLUGINSDIR\minions-stop-backend-sidecar.ps1" -InstallDir "$INSTDIR"`
    Pop $0
    ${If} $0 == 0
      ${ExitDo}
    ${EndIf}
    ; Still running (or could not be stopped). Ask the user; default to Cancel
    ; for silent installs.
    MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "$(minionsStopBackendPrompt)" /SD IDCANCEL IDRETRY +2
    Quit
  ${Loop}
  Pop $0
!macroend

!macro NSIS_HOOK_PREINSTALL
  !insertmacro MINIONS_STOP_BACKEND_SIDECAR
!macroend

!macro NSIS_HOOK_POSTINSTALL
  !insertmacro MINIONS_ADD_CLI_PATH_IF_SELECTED
  !insertmacro MINIONS_INSTALL_DEBUG_LAUNCHER
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  !insertmacro MINIONS_STOP_BACKEND_SIDECAR
  !insertmacro MINIONS_REMOVE_DEBUG_LAUNCHER
  !insertmacro MINIONS_REMOVE_CLI_PATH
!macroend
