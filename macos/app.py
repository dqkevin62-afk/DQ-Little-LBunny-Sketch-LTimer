# -*- coding: utf-8 -*-
"""DQ小兔速写计时姬 · macOS 主入口（py2app 打包用）

启动后：先打开速写页面（与 Windows 版一致），再弹出小兔原生桌宠。
桌宠逻辑在 pet.py（PyObjC 透明窗口）。
"""
import pet

if __name__ == "__main__":
    pet.open_page()
    pet.run_pet()
