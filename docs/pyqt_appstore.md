
# Publish Python Qt App to Appstore

## Introduction

In this guide, we'll demonstrate how to publish a Python Qt application to App Store using PyInstaller for packaging. We'll cover the steps from packaging and signing the app, to archiving and ultimately publishing it on the App Store.

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
    entitlements_file='./entitlements.plist',
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


## Step 3: Entitlements file
To publish the App to AppStore You must enable sandbox mode. Also include the necessary permissions(just for my App).

```
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>com.apple.security.app-sandbox</key>
	<true/>
	<key>com.apple.security.files.user-selected.read-write</key>
	<true/>
	<key>com.apple.security.files.bookmarks.app-scope</key>
	<true/>
</dict>
</plist>

```

## Step 4: Pack the python files using PyInstaller
```
/usr/local/bin/python3 -m PyInstaller ./app.spec
```

## Step 5: Sign the app 
You need use the "3rd Party Mac Developer Application" to sign the app. Here is the command:

```
codesign --force --timestamp --options=runtime --deep --sign "3rd Party Mac Developer Application: XXXXXXX LLC (123456789)" --entitlements "./app.entitlements" "./dist/You_APP_Name.app"

```

## Step 6: Archive the signed pkg installer
To publish the app to App Store, you need to archive the pkg installer file with "3rd Party Mac Developer Installer" cart. 

```
productbuild --component "./dist/You_APP_Name.app" /Applications "package.pkg" --sign "3rd Party Mac Developer Installer: XXXXXXX LLC (123456789)"

```



## Step 7: Submit the pkg app using Transporter for Review
