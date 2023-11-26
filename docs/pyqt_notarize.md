
# Notarize a MacOS Python Qt App

## Introduction

In this guide, we'll demonstrate how to notarize a Python Qt application to Apple using PyInstaller. We'll cover the steps from packaging and signing the app, archiving and ultimately Notarization.

## Prerequisites
- Apple Developer Account

## Step 1: Prepare Your Python Environment
To packet a python app that support MacOS's Universal 2, you need make sure both python and python QT support Universal 2. I use:
- Python from https://www.python.org/ It supports Universal 2
- PySide6 (PYQT6 will return error when packeting app)

## Step 2: PyInstaller's spec file  
You need to have a spec file to tell PyInstaller how to pack the app. Here is an example:

```
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=['Any_Data'],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=True,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [('v', None, 'OPTION')],
    exclude_binaries=True,
    name='Output_Bin_Name',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="universal2",
    codesign_identity=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Output_Bin_Name',
)
app = BUNDLE(
    coll,
    name='You_APP_Name.app',
    icon='Your_APP_Logo.icns',
    bundle_identifier='com.xxxx.xxxx',
    info_plist={Convert_info.plist_to_JSON})

```



## Step 3: Pack the python files using PyInstaller
```
/usr/local/bin/python3 -m PyInstaller ./app.spec
```

## Step 4: Sign the app 
You need use the "Developer ID Application" to sign the app. Here is the command:

```
codesign --force --timestamp --options=runtime --sign "Developer ID Application: XXXXXX LLC (123456789)" "./App.app"

```

## Step 5: Archive the App
```
ditto -c -k --keepParent "App.app" ./app.zip
```

## Step 6: Submit to Apple using Apple ID and app-specific password:
   `xcrun altool --notarize-app --primary-bundle-id "com.xxxx.xxxx" --username "username@gmail.com" --password "aaaa-bbbb-cccc-dddd" --file ./app.zip`


## Step 7: Wait Apple for review

## Step 8: After Apple approve the App, attach the staple to the App:

```
xcrun stapler staple "App.app"
```
