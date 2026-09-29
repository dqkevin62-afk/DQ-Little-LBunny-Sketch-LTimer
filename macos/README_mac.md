# DQ小兔速写计时姬 · Mac 版说明

Mac 版提供两种打包方式，按你是否要「小兔桌宠」来选：

| 版本 | 脚本 | 桌宠 | 依赖 |
|------|------|------|------|
| **完整版（推荐）** | `bash build_app.sh` | ✅ 原生小兔桌宠 | 需装 `py2app` + `PyObjC` |
| **简单版** | `bash build_app_simple.sh` | ❌ 只开页面 | 零依赖，仅用系统浏览器 |

> 两种都**必须在你的 Mac 上打包**——macOS 应用需要正确的执行权限，无法在 Windows 上交叉生成。

---

## 完整版（页面 + 小兔桌宠）· 推荐
行为对齐 Windows 版：双击 `.app` 会**先打开速写页面**，再在**右下角弹出小兔原生桌宠**。

### 桌宠操作（和 Windows 版一致）
- **左键拖动** = 移动桌宠
- **左键单击**（不拖动）= 打开速写页面
- **右键** = 菜单：打开页面 / 小兔大小（小 130 · 中 178 · 大 240）/ 退出桌宠
- 桌宠常驻置顶、可穿透「空格全屏」显示

### 打包步骤（在 Mac 上）
1. 把整个 `sketch-trainer` 文件夹拷贝到 Mac。
2. 打开「终端」，进入 `macos` 目录：
   ```bash
   cd /存放位置/sketch-trainer/macos
   ```
3. 一次性安装依赖（需 Mac 上有 Python 3，建议 python.org 或 Homebrew 版）：
   ```bash
   pip install py2app pyobjc-framework-Cocoa
   ```
4. 打包：
   ```bash
   bash build_app.sh
   ```
   脚本会拷贝网页资源，并用 `py2app` 生成 **`DQ小兔速写计时姬.app`**（内含 `app.py` + `pet.py` + `web`）。
5. 双击打开即可；或拖进「应用程序」文件夹。

> 实现说明：`pet.py` 用 **PyObjC** 创建 Cocoa 透明无边框 `NSWindow`，加载 `assets/pet/xiaotu-pet.png`，逐像素透明。这段代码在 Windows 上无法运行（无 Cocoa），仅做了语法校验，**首次在 Mac 上跑请留意终端有无报错**，必要时我再微调。

---

## 简单版（仅打开页面，零依赖）
不想装 Python 依赖、也不需要桌宠时，用这个：

1. 终端进入 `macos` 目录，运行：
   ```bash
   bash build_app_simple.sh
   ```
2. 生成 `DQ小兔速写计时姬.app`，双击用浏览器（优先 Chrome/Edge 应用窗口）打开速写页面。

---

## 首次打开被系统拦截怎么办
macOS 对未签名应用会提示「无法验证开发者 / 已损坏」。两种办法：
- **右键** `.app` → 「打开」→ 再点「打开」（允许一次即可）；
- 或终端执行（把路径换成你的实际路径）：
  ```bash
  xattr -dr com.apple.quarantine "/Applications/DQ小兔速写计时姬.app"
  ```

## 推荐浏览器
装了 **Google Chrome** 或 **Microsoft Edge** 时，会弹出干净的「无地址栏应用窗口」，体验最接近 Windows 版；
没装则用系统默认浏览器（Safari 等）打开页面，功能一样，只是多一个浏览器边框。

## 更新网页内容
以后改了 `index.html` 或 `assets/` 里的素材，只要在 Mac 上**重新跑一次对应的打包脚本**，就会把最新网页重新拷进 `.app`。

## 自定义图标（可选）
当前用的是 macOS 默认图标。想换成小兔图标，可准备一个 `app.icns`，放进
`DQ小兔速写计时姬.app/Contents/Resources/app.icns`，
并在 `Info.plist` 里加一行 `<key>CFBundleIconFile</key><string>app.icns</string>`。
（完整版可在 `setup.py` 的 `plist` 里加 `CFBundleIconFile`，重打包即可。）
