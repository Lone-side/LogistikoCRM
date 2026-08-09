@echo off
rem ============================================================
rem  LogistikoCRM - Elegxos yparxousas topikis egkatastasis
rem  Wrapper: kalei to PowerShell script (swsta ellinika/Unicode).
rem  DEN svinei tipota - mono anafora + odigies katharismou.
rem ============================================================
chcp 65001 >nul
title LogistikoCRM - Elegxos egkatastasis
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0check_local_install.ps1"
