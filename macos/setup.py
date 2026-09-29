# -*- coding: utf-8 -*-
"""py2app 打包配置：把 app.py + pet.py + web 资源打包成 DQ小兔速写计时姬.app

在 Mac 上：
  pip install py2app pyobjc-framework-Cocoa
  cd sketch-trainer/macos
  bash build_app.sh        # 会自动拷贝 web 资源并执行本脚本
或直接：
  python3 setup.py py2app
"""
from setuptools import setup

APP = ["app.py"]
OPTIONS = {
    "argv_emulation": False,
    "packages": ["AppKit", "Foundation"],
    "resources": ["web"],          # 打包时由 build_app.sh 拷贝到 macos/web
    "plist": {
        "CFBundleName": "DQ小兔速写计时姬",
        "CFBundleDisplayName": "DQ小兔速写计时姬",
        "CFBundleIdentifier": "com.dq.speedsketch",
        "CFBundleVersion": "0.1",
        "CFBundleShortVersionString": "0.1",
        "CFBundlePackageType": "APPL",
        "CFBundleExecutable": "app",
        "LSMinimumSystemVersion": "10.13",
        "NSHighResolutionCapable": True,
        "CFBundleGetInfoString": "DQ小兔速写计时姬 · 二次元美少女速写计时工具",
    },
}

setup(
    app=APP,
    data_files=[],
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
