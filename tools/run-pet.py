# -*- coding: utf-8 -*-
"""开发调试用：只启动小兔桌宠 + 本地代理，不开浏览器窗口（方便边改边测）。

用法：
    python tools/run-pet.py           只开桌宠（你自己打开页面）
    python tools/run-pet.py --page    顺带用默认浏览器打开项目页面
    tools/run-pet.bat                 双击运行（等同第一条）

桌宠默认就是「窗口置顶 + 屏幕右下角」（xiaotu_pet.py 里 topmost=True、贴工作区右下角），
页面通过 127.0.0.1:18765 与桌宠联动：陪画模式 / 人格点评 / 置顶开关 / 变参考图 / 跟随光标 /
一键生成 等都能在没打包 exe 的情况下直接测。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PET = os.path.join(ROOT, "desktop", "xiaotu_pet.py")

# 桌宠依赖 Pillow；当前解释器没有就切到装了 Pillow 的那个（本机 venv）
VENV = r"C:\Users\admin\.workbuddy\binaries\python\envs\default\Scripts\python.exe"


def _has_pil():
    try:
        import PIL  # noqa: F401
        return True
    except Exception:
        return False


def main():
    if not _has_pil() and os.path.exists(VENV) and \
            os.path.abspath(sys.executable) != os.path.abspath(VENV):
        # 换个带 Pillow 的解释器重跑自己
        os.execv(VENV, [VENV, os.path.abspath(__file__)] + sys.argv[1:])

    if "--page" in sys.argv:
        import threading
        import webbrowser

        def _open_page():
            import time
            time.sleep(0.8)
            webbrowser.open("file:///" + os.path.join(ROOT, "index.html").replace("\\", "/"))

        threading.Thread(target=_open_page, daemon=True).start()

    args = [a for a in sys.argv[1:] if a != "--page"]
    sys.argv = [PET, "--no-page"] + args
    sys.path.insert(0, os.path.join(ROOT, "desktop"))

    import runpy
    runpy.run_path(PET, run_name="__main__")


if __name__ == "__main__":
    main()
