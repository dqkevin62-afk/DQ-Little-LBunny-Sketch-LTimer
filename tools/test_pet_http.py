# -*- coding: utf-8 -*-
"""打包前最后一次真实链路自检：起源码桌宠（--no-page），逐个打 HTTP 接口。

重点覆盖「打卡」相关链路（提醒气泡 / 置顶 / 陪画状态），并确认已删接口确实没了。
跑完自动关掉桌宠进程。
"""
import subprocess
import sys
import time
import urllib.error
import urllib.request

PY = r"C:\Users\admin\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
BASE = "http://127.0.0.1:18765"

fails = []
total = 0


def check(name, cond, extra=""):
    global total
    total += 1
    if cond:
        print("  [OK] " + name)
    else:
        print("  [X] " + name + ("  -> " + extra if extra else ""))
        fails.append(name)


def make_test_image(w=1400, h=1000):
    """造一张大参考图（data:uri），用来量「预推 / 直接进入」的耗时差。"""
    import base64
    import io
    import os
    from PIL import Image
    im = Image.frombytes("RGB", (w, h), os.urandom(w * h * 3))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def code(path, method="GET", body=None):
    req = urllib.request.Request(BASE + path, method=method)
    data = None
    if body is not None:
        data = body.encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        r = urllib.request.urlopen(req, data=data, timeout=4)
        return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return -1, str(e)


proc = subprocess.Popen([PY, "desktop/xiaotu_pet.py", "--no-page"])
try:
    up = False
    for _ in range(80):
        s, _ = code("/ping")
        if s == 200:
            up = True
            break
        time.sleep(0.5)
    check("桌宠本地服务起来了（/ping 200）", up)

    s, body = code("/pet_state")
    check("/pet_state 返回 200", s == 200, str(s))
    j = {}
    try:
        import json
        j = json.loads(body)
    except Exception:
        pass
    check("pet_state 带 ok / on / companion / phase（待机提醒靠它判断）",
          all(k in j for k in ("ok", "on", "companion", "phase")), body[:120])
    check("桌宠在线（on=true）", j.get("on") is True, str(j))

    s, _ = code("/pet?cmd=say&secs=8&text=" + urllib.parse.quote("恭喜主人今日速写打卡成功！"))
    check("打卡气泡通道 cmd=say 可用", s == 200, str(s))
    s, _ = code("/pet?cmd=expr&kind=happy")
    check("cmd=expr 可用", s == 200, str(s))
    s, _ = code("/pet?cmd=topmost&on=1")
    check("cmd=topmost 可用", s == 200, str(s))
    s, _ = code("/pet?cmd=pure_end")
    check("cmd=pure_end 可用（纯净模式收尾）", s == 200, str(s))
    s, _ = code("/huaban_search?q=test")
    check("搜索代理仍在（桌宠能力）", s in (200, 400, 500), str(s))

    s, _ = code("/pet?cmd=image_off")
    check("已删的 cmd=image_off 确实没了（400）", s == 400, str(s))
    s, _ = code("/pet?cmd=follow&on=1")
    check("已删的 cmd=follow 确实没了（400）", s == 400, str(s))
    s, _ = code("/pet_image", "POST", '{"d":"x"}')
    check("已删的 POST /pet_image 确实没了（404）", s == 404, str(s))
    s, _ = code("/pet_pure", "POST", '{"d":"","on":false}')
    check("纯净模式入口 /pet_pure 仍在（不能误删）", s in (200, 400, 500), str(s))

    # ---- 参考图预推：点开始就该立刻出图，不该让人等 ----
    import json as _json
    big = make_test_image()
    t0 = time.time()
    s, _ = code("/pet_preload", "POST", _json.dumps({"d": big}))
    t_pre = time.time() - t0
    check("/pet_preload 预推成功", s == 200, str(s))

    t0 = time.time()
    s, _ = code("/pet_pure", "POST", '{"d":"","on":true}')   # 不带图：用缓存进入
    t_in = time.time() - t0
    check("用缓存进入纯净模式（不带图也能起来）", s == 200, str(s))
    code("/pet_pure", "POST", '{"on":false}')                # 退出，准备对比

    t0 = time.time()
    s, _ = code("/pet_pure", "POST", _json.dumps({"d": big, "on": True}))  # 带图进入（老路径）
    t_full = time.time() - t0
    check("带图直接进入也能成功", s == 200, str(s))
    code("/pet_pure", "POST", '{"on":false}')

    print("  [i] 耗时：预推 %.2fs → 用缓存进入 %.2fs（带图直接进入 %.2fs）"
          % (t_pre, t_in, t_full))
    check("预推过的进入明显更快（不用再编码/传输/解码）",
          t_in < t_full * 0.6 or t_in < 0.35, "缓存 %.2fs / 带图 %.2fs" % (t_in, t_full))
finally:
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except Exception:
        proc.kill()

print("\n结果：" + str(total - len(fails)) + " 通过 / " + str(len(fails)) + " 失败")
sys.exit(1 if fails else 0)
