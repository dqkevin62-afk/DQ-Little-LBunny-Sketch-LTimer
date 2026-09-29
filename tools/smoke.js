// jsdom 冒烟测试：验证配色改造 + 核心功能未被破坏
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

const ROOT = path.dirname(__dirname);
let html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");
const guides = fs.readFileSync(path.join(ROOT, "assets", "guides.js"), "utf8");
// file:// 下 jsdom 不加载外链脚本，改为内联注入
html = html.replace(
  '<script src="assets/guides.js"></script>',
  "<script>" + guides + "</script>"
);

const errs = [];
const dom = new JSDOM(html, {
  runScripts: "dangerously",
  url: "http://localhost/",
  pretendToBeVisual: true,
  virtualConsole: new (require("jsdom").VirtualConsole)().on("jsdomError", e => {
    // jsdom 不支持真实媒体播放 / 字体加载，这类非业务错误忽略
    if (!/misans\.css|Not implemented|HTMLMediaElement/.test(String(e.message || ""))) errs.push(String(e.message));
  }).on("error", (...a) => errs.push("console.error: " + a.join(" "))),
});
const w = dom.window;
const d = w.document;
const $ = s => d.querySelector(s);

let pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log("  ✓ " + name); }
  else { fail++; console.log("  ✗ " + name + (extra ? "  → " + extra : "")); }
}

const css = html.slice(html.indexOf("<style>"), html.indexOf("</style>"));

console.log("【配色变量】");
["--pink", "--pink-soft", "--purple", "--purple-soft", "--caramel", "--cream",
 "--ink", "--muted", "--bg", "--bg-2", "--card", "--line", "--shadow"]
  .forEach(v => ok(":root 定义 " + v, css.includes(v + ":")));
ok("主色为紫罗兰 #7f5fc0", /--pink:\s*#7f5fc0/.test(css));
ok("底色为淡紫罗兰 #efe8f9", /--bg:\s*#efe8f9/.test(css));
ok("卡片为纯白 #ffffff", /--card:\s*#ffffff/.test(css));
ok("文字为深紫灰 #3b3350（非纯黑）", /--ink:\s*#3b3350/.test(css));
ok("有淡丁香装饰色 --lilac", /--lilac:\s*#b39ae0/.test(css));
const dark = css.slice(css.indexOf('[data-theme="dark"]'));
["--caramel", "--cream", "--bg-2", "--shadow", "--lilac"].forEach(v =>
  ok("深色主题已同步 " + v, dark.includes(v)));
ok("深色主题底色为深紫夜色（降饱和 30% 后 #17141d）", /--bg:\s*#17141d/.test(dark));
ok("深色底色统一降饱和（卡片 / 分区块 / 浅底块都换过色）",
  /--card:\s*#231f2d/.test(dark) && /--bg-2:\s*#201c2d/.test(dark) &&
  /--cream:\s*#2c273c/.test(dark) && /--pink-soft:\s*#39324c/.test(dark) &&
  /--purple-soft:\s*#352f49/.test(dark));
ok("主色 / 文字 / 装饰色不跟着降饱和",
  /--pink:\s*#9f80e0/.test(dark) && /--purple:\s*#9b86dd/.test(dark) &&
  /--ink:\s*#eae4f5/.test(dark) && /--lilac:\s*#b9a5ec/.test(dark));
ok("上传区底色跟随主题（不再写死白色）",
  /\.upload-zone\s*\{[^}]*background:\s*var\(--card\)/s.test(css) && !/\.upload-zone\s*\{[^}]*background:\s*#fff/s.test(css));
ok("缩略图删除按钮底色也跟随主题", /\.thumb-del\s*\{[^}]*background:\s*var\(--card\)/s.test(css));
ok("深色主题提亮主色 #9f80e0", /--pink:\s*#9f80e0/.test(dark));

console.log("\n【旧配色已清除】");
["#d4537e", "#7f77dd", "#f0dce5", "rgba(212, 83, 126", "rgba(127, 119, 221",
 "#c8836a", "#f6eddd", "#3f3730", "#1d1917", "#b98a63"]
  .forEach(c => ok("不再出现 " + c, !html.includes(c)));

console.log("\n【参考图质感：紫底白卡 + 设备框 + 胶囊按钮】");
ok("body 有白色柔光斑（仅浅色）", css.includes("html:not([data-theme=\"dark\"]) body"));
ok(".card 使用 --shadow", /\.card\s*\{[^}]*box-shadow:\s*var\(--shadow\)/s.test(css));
ok("画布卡片是白色厚内框（设备框质感）", /\.stage\.card\s*\{[^}]*border:\s*7px solid var\(--card\)/s.test(css));
ok("设备框外圈淡紫描边", /\.stage\.card\s*\{[^}]*0 0 0 1\.5px var\(--line\)/s.test(css));
ok("按钮为胶囊形 999px", /\.btn\s*\{[^}]*border-radius:\s*999px/s.test(css));
ok("题词框为柔渐变底", /\.prompt-box\s*\{[^}]*linear-gradient/s.test(css));
ok("进度条为胶囊标签", /\.progress-line\s*\{[^}]*border-radius:\s*999px/s.test(css));
ok("计时环底色跟随主题 .ring-track", css.includes(".ring-track { stroke: var(--pink-soft)"));
ok("计时环主色跟随主题 #ring", /#ring\s*\{[^}]*stroke:\s*var\(--pink\)/s.test(css));
ok("休息态用淡丁香 #ring.rest", /#ring\.rest\s*\{[^}]*var\(--lilac\)/s.test(css));

console.log("\n【计时环元素】");
ok("环轨道存在", !!$(".ring-track"));
ok("进度环存在", !!$("#ring"));
ok("起始无 rest 类", !$("#ring").classList.contains("rest"));

console.log("\n【核心 UI 仍在】");
ok("上传本地参考图卡片", !!$("#mode-image-card"));
ok("只剩这一个模式卡片（小兔出题 / 关键词开画已删）",
  d.querySelectorAll(".mode-card[data-mode]").length === 1
  && !$("#mode-topic-card") && !$("#mode-keyword-card"));
ok("页面里不再出现「小兔出题」「关键词开画」字样",
  !/小兔出题|关键词开画/.test(html));
ok("题库分类 chips 已随模式删掉", !$("#cat-row") && d.querySelectorAll(".cat-block").length === 0);
ok("不再有 VIP / SVIP 字样", !/VIP|SVIP/.test(html));
ok("会员订阅区块已删掉", !$(".vip-list") && !html.includes("data-vip")
  && !/会员订阅/.test(html));
ok("会员/账号徽章样式已删（.acct-badge / .vip-list 都没了）",
  !/\.acct-badge/.test(css) && !/\.vip-list\s*\{/.test(css));
ok("建议输入框 2000 字上限", $("#suggest-text") && $("#suggest-text").maxLength === 2000);

console.log("\n【给 DQ 提建议：联系方式直接显示，只留 复制内容 / 清空】");
ok("两个发送按钮已删（发送到 DQ QQ / 发送到 DQ邮箱）",
  !$("#btn-suggest-qq") && !$("#btn-suggest-mail")
  && !/发送到 DQ QQ|发送到 DQ邮箱/.test($("#tab-suggest").textContent));
ok("发送通道相关代码一并删干净（tencent:// / mailto / 断网队列 / 网络探测）",
  !/tencent:\/\/message/.test(html) && !/mailto:/.test(html)
  && !/SUGGEST_ENDPOINT|sketchSuggestV1|sendViaQQ|sendViaMail|netProbe|suggestQueue/.test(html));
ok("标题下面依次是 QQ 号 / 邮箱 / QQ 群（每行只有文字）", (() => {
  const kids = [...$("#tab-suggest").children].slice(0, 4).map(e => e.textContent.trim());
  return kids.join("|") === "给 DQ 提建议|DQ QQ：3700810|DQ Email：3700810@qq.com|DQ小兔速写姬QQ群：1124504859";
})());
ok("复制按钮已删（DOM 与样式里都没有了）",
  !$("#tab-suggest .copy-btn") && !/\.copy-btn|data-copy=/.test(html));
ok("联系方式三行都走主色变量（不写死颜色）",
  /\.set-qq\s*\{[^}]*color:\s*var\(--pink\)/.test(css)
  && $("#tab-suggest").querySelectorAll(".set-qq").length === 3);
ok("离线待发队列的界面与样式都撤了",
  !$("#suggest-queue") && !/\.suggest-queue/.test(css));
ok("「复制内容 / 清空」两个按钮保留",
  !!$("#btn-suggest-copy") && !!$("#btn-suggest-clear"));

console.log("\n【账号功能已删（注册 / 登录 / 退出）】");
ok("账号标签页已删", !d.querySelector('[data-tab="account"]') && !$("#tab-account"));
ok("设置只剩 3 个标签（显示 / 语言 / 给DQ提建议）",
  d.querySelectorAll("#set-tabs .tab").length === 3,
  "实际 " + d.querySelectorAll("#set-tabs .tab").length);
ok("账号输入框与按钮全删",
  !$("#acct-user") && !$("#acct-pass") && !$("#acct-note")
  && !$("#btn-acct-login") && !$("#btn-acct-reg") && !$("#btn-acct-logout"));
ok("账号相关 JS 全删（USER_KEY / doLogin / renderAccount / isAdmin / hashPwd）",
  !/USER_KEY|CUR_KEY|sketchUsersV1|sketchUserV1|doLogin|doRegister|doLogout|afterLogin|renderAccount|renderAdminBtn|isAdmin|hashPwd|allUsers|saveUsers|setCurUser/.test(html));
ok("账号相关 CSS 全删（.acct-row / .acct-badge）",
  !/\.acct-row\s*\{/.test(css) && !/\.acct-badge\s*\{/.test(css));
// 注意：「登录」两个字在 QQ 通道的提示语里会正常出现，所以这里只查账号功能专属词
ok("设置页不再出现「注册 / 退出登录」字样", !/注册|退出登录/.test(html));
ok("管理员面板改用 adminMode 口令（不再依赖账号）",
  /if \(!adminMode\) return;/.test(html) && !/ad-users/.test(html));
ok("管理员页不再显示「已注册用户」", !/已注册用户/.test(html));
ok("不再有音色标签", !d.querySelector('[data-tab="voice"]'));
ok("不再有字体标签", !d.querySelector('[data-tab="font"]'));
ok("默认停在「显示」页", d.querySelector("#set-tabs .tab.on").dataset.tab === "display");
ok("「显示」页默认可见", !!$("#tab-display") && $("#tab-display").hidden === false);
ok("字体栈仍写死在 CSS 变量里",
  /--font-r:[^;]*MiSans Regular/.test(css) && /--font-b:[^;]*MiSans Regular/.test(css));
ok("字体仍由 misans.css 引入", /href="assets\/fonts\/misans\.css"/.test(html));

// 改版本只改 index.html 里的 APP_VER（侧栏 + 桌面 exe 都从那儿读），并给 CHANGELOG 加一节
const VER = "V1.2";
console.log("\n【标题改为 DQ小兔速写计时姬 + 小小的 " + VER + "】");
const sbH1 = d.querySelector("#sidebar h1");
ok("侧栏标题已改名", sbH1.textContent.replace(/\s+/g, "") === "DQ小兔速写计时姬" + VER);
ok("标题文字是 DQ小兔速写计时姬", /^DQ小兔速写计时姬/.test(sbH1.textContent.trim()));
ok("版本号是 " + VER, sbH1.querySelector(".ver") && sbH1.querySelector(".ver").textContent === VER);
ok("版本号在标题内（显示在旁边）", sbH1.querySelector(".ver") !== null);
// 版本号只有一个来源：index.html 的 APP_VER（侧栏 + 桌面 exe 都跟着它）
ok("版本号只写在一处（index.html 的 APP_VER）",
  new RegExp('const APP_VER = "' + VER + '";').test(html) && !/V1\.0\.0/.test(html));
ok("侧栏版本号由 APP_VER 自动填上（不用手改 HTML）",
  /id="app-ver"/.test(html) && /\$\("app-ver"\)\.textContent = APP_VER/.test(html));
ok("桌面端卡片版本号跟着 APP_VER 走（不再写死在 py 里）",
  /"%s · 一起练速写吧" % app_version\(\)/.test(
    fs.readFileSync(path.join(ROOT, "desktop", "xiaotu_pet.py"), "utf8")));
ok("版本号样式很小", /#sidebar h1 \.ver\s*\{[^}]*font-size:\s*10px/s.test(css));
ok("版本号不抢主标题字重", /#sidebar h1 \.ver\s*\{[^}]*font-weight:\s*400/s.test(css));
ok("浏览器标签页标题同步", /<title>DQ小兔速写计时姬 · 二次元美少女篇<\/title>/.test(html));
ok("欢迎页署名同步", /DQ小兔速写计时姬/.test($("#screen-welcome").innerHTML));
ok("分享文案同步", /DQ小兔速写计时姬/.test(html.match(/每天十分钟练动态感/) ? html : ""));
ok("页面里已无旧名 DQ速写计时姬（含 i18n 词条）", !/DQ速写计时姬/.test(html),
  "残留 " + ((html.match(/DQ速写计时姬/g) || []).length) + " 处");
ok("标题不会被挤出侧栏（字号已收窄到 16px）",
  /#sidebar h1 \{[^}]*font-size:\s*16px/s.test(css) && /#sidebar h1 \{[^}]*white-space:\s*nowrap/s.test(css));

console.log("\n【上传参考图后：右侧画布只显示参考图，隐藏小兔形象，保留下方文字】");
const himeImg = d.querySelector("#screen-welcome .hime-img");
const himeName = d.querySelector("#screen-welcome .hime-name");
const welcomeTxt = d.querySelector("#screen-welcome .welcome");
ok("默认（未上传）显示小兔形象", !!himeImg && himeImg.hidden === false && himeName.hidden === false);
ok("默认不显示参考图区", $("#welcome-img").hidden === true);
ok("有隐藏小兔形象的 CSS 规则",
  /#screen-welcome\s+\.hime-img\[hidden\]/.test(css) && /#screen-welcome\s+\.hime-name\[hidden\]/.test(css));
ok("setWelcomeHero 存在", w.eval("typeof setWelcomeHero") === "function");
// 模拟上传：往「上传本地参考图」的库里塞两张假图并调用 showRefThumb
w.eval("setMode('image'); S.imgStore.image=['blob:fake-a','blob:fake-b']; syncImages(); showRefThumb(1);");
ok("上传后参考图区显示", $("#welcome-img").hidden === false);
ok("参考图 src 已更新", $("#welcome-img-el").getAttribute("src") === "blob:fake-b");
ok("此时隐藏小兔那张图", himeImg.hidden === true);
ok("同时隐藏小兔署名", himeName.hidden === true);
ok("下方文字块保留", !!welcomeTxt && welcomeTxt.hidden !== true
  && /小兔陪你练速写/.test(welcomeTxt.textContent));
ok("下方开始练习按钮保留", !!$("#btn-welcome-start"));
// 删掉参考图后：小兔形象恢复
w.eval("S.imgStore.image=[]; syncImages(); renderThumbs(); setWelcomeHero(false);");
ok("删掉参考图后小兔形象恢复", himeImg.hidden === false && himeName.hidden === false);
ok("删掉参考图后参考图区隐藏", $("#welcome-img").hidden === true);
// 再上传：参考图重新显示（记住上次预览的那张）
w.eval("S.imgStore.image=['blob:fake-a','blob:fake-b']; syncImages(); showRefThumb(1);");
ok("重新上传后参考图区显示", $("#welcome-img").hidden === false
  && $("#welcome-img-el").getAttribute("src") === "blob:fake-b");
ok("此时小兔形象再次隐藏", himeImg.hidden === true);
w.eval("S.imgStore.image=[]; syncImages(); renderThumbs();");

console.log("\n【单张时长 + 练习张数 合并为一个模块】");
const durCard = $("#dur-row").closest(".card");
const cntCard = $("#cnt-row").closest(".card");
ok("时长与张数在同一个卡片内", durCard && durCard === cntCard);
ok("卡片内是三个小分段(时长/张数/计时方式)", durCard.querySelectorAll(".set-group").length === 3);
ok("分段标题保留原文案", /单张时长/.test(durCard.innerHTML) && /练习张数/.test(durCard.innerHTML));
ok("分段之间有虚线分隔",
  /\.set-group \+ \.set-group[^{]*\{[^}]*border-top:\s*1px dashed/s.test(css));
ok("主题卡下面接分段也有间距（不能贴在一起）",
  /\.opt-list \+ \.set-group[^{]*\{[^}]*margin-top:\s*16px/s.test(css));
ok("设置页「开 / 关」是等宽胶囊", /#pet-top-row \.chip\s*\{[^}]*min-width:\s*64px/.test(css));
ok("深色预览卡的文字显式取变量（否则深底压深字看不清）",
  /\.opt-item \.n\s*\{[^}]*color:\s*var\(--ink\)/.test(css) &&
  /\.opt-item \.dsc\s*\{[^}]*color:\s*var\(--muted\)/.test(css));
ok("时长自定义按钮仍在", !!$("#btn-custom-dur"));
ok("张数自定义按钮仍在", !!$("#btn-custom-cnt"));
ok("默认 1 分钟 / 10 张选中",
  !!$("#dur-row").querySelector('.chip.on[data-dur="60"]') &&
  !!$("#cnt-row").querySelector('.chip.on[data-cnt="10"]'));
$("#dur-row").querySelector('[data-dur="300"]').dispatchEvent(new w.Event("click", { bubbles: true }));
ok("合并后时长切换仍生效", !!$("#dur-row").querySelector('.chip.on[data-dur="300"]'));
$("#cnt-row").querySelector('[data-cnt="20"]').dispatchEvent(new w.Event("click", { bubbles: true }));
ok("合并后张数切换仍生效", !!$("#cnt-row").querySelector('.chip.on[data-cnt="20"]'));

console.log("\n【主题切换】");
const themeBtns = d.querySelectorAll('[data-theme="dark"]');
ok("存在深色选项", themeBtns.length >= 1);
const btnDark = [...d.querySelectorAll(".opt-item")].find(e => e.dataset.theme === "dark");
if (btnDark) { btnDark.dispatchEvent(new w.Event("click", { bubbles: true })); }
ok("切到深色后 data-theme=dark", d.documentElement.getAttribute("data-theme") === "dark");
const btnLight = [...d.querySelectorAll(".opt-item")].find(e => e.dataset.theme === "light");
if (btnLight) { btnLight.dispatchEvent(new w.Event("click", { bubbles: true })); }
ok("切回浅色 data-theme=light", d.documentElement.getAttribute("data-theme") === "light");

console.log("\n【设置里已删除「音色」「字体」整个功能】");
ok("音色面板已删除", !$("#tab-voice") && !$("#voice-list") && !$("#voice-note"));
ok("音色按钮已删除", !$("#btn-voice-default") && !$("#btn-clip-sample") && !$("#v-def-name"));
ok("字体面板已删除", !$("#tab-font") && !$("#font-list") && !$("#font-note"));
ok("音色相关 CSS 已删除", !/\.voice-item|\.voice-list|\.v-def\b|\.v-def-btns/.test(css));
ok("字体相关 CSS 已删除", !/\.font-item|\.font-list/.test(css));
ok("音色/字体的 JS 逻辑已删除",
  !/renderVoices|renderFonts|selectVoice|voiceNoteText|fontNoteText|applyFont|loadFontCss|FONT_KEY|playRef|stopRef/.test(html));
ok("切到语言页仍正常", (() => {
  const t = d.querySelector('[data-tab="lang"]');
  if (!t) return false;
  t.dispatchEvent(new w.Event("click", { bubbles: true }));
  return $("#tab-lang").hidden === false && $("#tab-display").hidden === true;
})());
d.querySelector('[data-tab="display"]').dispatchEvent(new w.Event("click", { bubbles: true }));
ok("切回显示页正常", $("#tab-display").hidden === false);

console.log("\n【语言：只剩 中文 / 英文（日语已删）】");
ok("语言选项只剩 2 个（中文 / English）",
  $("#lang-list").querySelectorAll(".opt-item").length === 2);
ok("日语选项已删（含说明文字）",
  !$('[data-lang="ja"]') && !/日本語/.test(html) && !/日文界面与语音/.test(html));
ok("日语词典整段删除（DICT.ja 没了，DICT.en 还在）",
  w.eval("DICT.ja") === undefined && w.eval("DICT.en") !== undefined
  && !/^\s*ja:\s*\{/m.test(html));
ok("LANG_TTS 只剩中文 / 英文",
  /LANG_TTS = \{ zh: "zh-CN", en: "en-US" \}/.test(html) && !/ja-JP/.test(html));
ok("日语的界面文案分支已删（durLabel / progLine / 自定义…）",
  !/l === "ja"/.test(html) && !/追随/.test(html));
ok("以前存过 ja 的老记录会回落到中文", (() => {
  w.eval("localStorage.setItem('sketchLangV1','ja')");
  const r = w.eval("currentLang()") === "zh" && w.eval("durLabel(60)").indexOf("分钟") >= 0;
  w.eval("localStorage.removeItem('sketchLangV1')");
  return r;
})());
ok("切到 English 仍正常（英文文案生效）", (() => {
  w.eval("localStorage.setItem('sketchLangV1','en')");
  const r = w.eval("currentLang()") === "en" && w.eval("durLabel(60)").indexOf("minute") >= 0
    && w.eval("progLine()").indexOf("No.") === 0;
  w.eval("localStorage.setItem('sketchLangV1','zh')");
  return r;
})());

console.log("\n【默认中文：打开小兔桌宠就是简体中文】");
ok("detectLang 恒为中文（不再跟随系统语言自动变英文）",
  /function detectLang\(\)[\s\S]{0,400}return "zh";/.test(html) && !/navigator\.languages/.test(
    (html.match(/function detectLang\(\)[\s\S]*?\n\}/) || [""])[0]));
const migSrc = (html.match(/\/\/ 打开就是简体中文[\s\S]*?\n\}\)\(\);/) || [""])[0];
ok("有一次性的「归位到中文」初始化代码",
  /sketchLangZhV1/.test(migSrc) && /setItem\(LANG_KEY, "zh"\)/.test(migSrc));
ok("老记录存着英文也会被拉回中文（一次性归位）", (() => {
  w.eval("localStorage.setItem('sketchLangV1','en'); localStorage.removeItem('sketchLangZhV1');");
  w.eval(migSrc);
  const r = w.eval("localStorage.getItem('sketchLangV1')") === "zh"
    && w.eval("currentLang()") === "zh" && w.eval("durLabel(60)").indexOf("分钟") >= 0;
  return r;
})());
ok("归位过一次后，手动切英文不会被强行改回中文", (() => {
  w.eval("localStorage.setItem('sketchLangZhV1','1'); localStorage.setItem('sketchLangV1','en');");
  w.eval(migSrc);
  const r = w.eval("localStorage.getItem('sketchLangV1')") === "en";
  w.eval("localStorage.setItem('sketchLangV1','zh');");
  return r;
})());
ok("没存过语言时打开就是中文", (() => {
  w.eval("localStorage.removeItem('sketchLangV1')");
  const r = w.eval("currentLang()") === "zh";
  w.eval("localStorage.setItem('sketchLangV1','zh')");
  return r;
})());
ok("设置项说明改成「默认中文」，不再写其他地区默认英文",
  /打开就是它/.test(html) && !/中日以外地区默认英文/.test(html) && !/其他地区默认/.test(html));
ok("「界面语言：zh-CN → 简体中文」那行已删（含 sysLangLabel）",
  !$("#sys-lang-note") && !/sysLangLabel/.test(html) && !/界面语言：/.test(html));
ok("设置页标题居中（.card h2 的 flex 会把它挤到左边，已单独修正）",
  /#screen-settings > h2\s*\{[^}]*justify-content:\s*center/s.test(css));

console.log("\n【播报音色仍固定为甜妹（引擎保留）】");
ok("DEFAULT_VOICE 为 p3", w.eval("DEFAULT_VOICE") === "p3");
ok("默认音色名是甜妹", w.eval("defaultPreset().name") === "甜妹");
ok("默认参考音频为 03_甜妹_01.mp3", w.eval("defaultPreset().refs[0]") === "03_甜妹_01.mp3");
ok("未手动选择时回落到甜妹", w.eval("getVoiceChoice().id") === "p3");
ok("10 款音色预设保留（引擎用）",
  w.eval("VOICE_PRESETS.every(p=>p.refs.length===3) && VOICE_PRESETS.length===10"));
ok("播报仍走 speakWith", /function speakWith\(/.test(html));
const refFiles = fs.readdirSync(path.join(ROOT, "assets", "voice")).filter(f => f.endsWith(".mp3"));
ok("内置音频 30 条", refFiles.length === 30, "实际 " + refFiles.length);
ok("03_甜妹_01.mp3 已内置", fs.existsSync(path.join(ROOT, "assets", "voice", "03_甜妹_01.mp3")));

console.log("\n【星级成就 + 分享】");
ok("打卡标题已改名", /我的DQ小兔速写打卡/.test(html));
ok("星级分 5 档", w.eval("STAR_TIERS.length") === 5);
ok("最高为 5 星", w.eval("STAR_TIERS[4].star") === 5 && w.eval("STAR_TIERS[4].name") === "速写大师");
const tlog = {};
for (let i = 0; i < 10; i++) {
  const dd = new Date(); dd.setDate(dd.getDate() - i);
  tlog[`${dd.getFullYear()}-${dd.getMonth() + 1}-${dd.getDate()}`] = { count: 10, sec: 3600 };
}
w.localStorage.setItem("sketchLogV1", JSON.stringify(tlog));
w.eval("renderStats()");
const si = w.eval("starInfo(getLog())");
ok("速写值 = 张数+天数×2+连续×5+分钟×0.5", si.val === 470, "实际 " + si.val);
ok("10天×10张×1小时 → 4 星", si.star === 4);
ok("4 星名为速写达人", si.name === "速写达人");
ok("距离 5 星还差 330", si.next && si.next.star === 5 && si.need === 330);
ok("星串固定 5 位", w.eval("starsOf(starInfo(getLog()))").length === 5);
ok("连续 10 天满 1 小时 → 连续天数 10", w.eval("calcStreak(getLog())") === 10);
ok("结算页星级块已渲染", /star-name/.test($("#sum-star").innerHTML));
ok("渲染出 4 颗实心星", ($("#sum-star").innerHTML.match(/★/g) || []).length === 4);
ok("进度条有宽度", /star-bar"><i style="width:\d+%/.test($("#sum-star").innerHTML));
["btn-share-wx", "btn-share-qq", "btn-share-x", "btn-share-copy"]
  .forEach(id => ok("分享按钮 " + id, !!$("#" + id)));
const stxt = w.eval("shareText()");
ok("分享文案含打卡标题", stxt.includes("我的DQ小兔速写打卡"));
ok("分享文案含星星与星级名", /★.*速写达人/.test(stxt));
ok("分享文案含连续天数", stxt.includes("连续 10 天"));
ok("分享文案含累计张数", stxt.includes("累计 100 张"));

console.log("\n【排行榜已删除】");
ok("排行榜卡片删掉了（标题 / rank-top / rank-list 全没）",
  !/DQ小兔速写排行榜/.test(html) && !$("#rank-top") && !$("#rank-list"));
ok("排行榜渲染逻辑删掉了（renderRank / rankOf / rankPct）",
  !/function renderRank|function rankOf|function rankPct|renderRank\(/.test(html));
ok("排行榜 CSS 删掉了",
  !/\.rank-top\s*\{/.test(css) && !/\.rank-list\s*\{/.test(css)
  && !/\.rank-row\s*\{/.test(css) && !/\.rank-stars\s*\{/.test(css));
ok("分享文案不再含排行榜名次", !/排行榜/.test(stxt));
ok("打卡规则里也不提排行榜名次了", !/名次 = 6/.test(html));

console.log("\n【得星规则 ❗️ 按钮】");
const rbtn = $("#btn-star-rule"), rbox = $("#star-rule");
ok("规则按钮存在", !!rbtn);
ok("按钮文案是打卡规则 ❗️", rbtn.textContent.includes("打卡规则"));
ok("按钮在打卡标题同一行内",
  rbtn.closest("h2") && /我的DQ小兔速写打卡/.test(rbtn.closest("h2").textContent));
ok("规则面板默认收起", rbox.hidden === true);
rbtn.dispatchEvent(new w.Event("click", { bubbles: true }));
ok("点击后展开", rbox.hidden === false);
ok("按钮切到选中态", rbtn.classList.contains("ok"));
ok("面板标题是打卡规则", /打卡规则/.test(rbox.innerHTML));
ok("规则先讲「满 60 分钟 = 今日打卡」",
  /当天累计专注满 60 分钟 = 今日打卡成功/.test(rbox.innerHTML));
ok("列出速写值公式", /累计张数 \+ 打卡天数×2 \+ 连续天数×5 \+ 累计专注分钟×0\.5/.test(rbox.innerHTML));
ok("列出 5 档门槛", rbox.querySelectorAll(".rule-row").length === 5);
ok("门槛从高到低", /速写大师[\s\S]*起笔萌新/.test(rbox.innerHTML));
ok("说明 4 项打卡规则", rbox.querySelectorAll(".rule-ul div").length === 4);
ok("显示今日进度", /今日打卡已完成|今日已画 \d+ \/ 60 分钟/.test(rbox.innerHTML));
rbtn.dispatchEvent(new w.Event("click", { bubbles: true }));
ok("再点收起", rbox.hidden === true && !rbtn.classList.contains("ok"));
ok("字体已补 ★ 字符", fs.readFileSync(path.join(ROOT, "index.html"), "utf8").includes("★"));

console.log("\n【打卡重设计：每天 1 小时 = 1 颗 ★ + 当月星历】");
ok("每天目标是 3600 秒（1 小时）", w.eval("DAILY_GOAL_SEC") === 3600);
ok("差 1 秒不算，满 3600 才算打卡",
  w.eval("isDayDone('2026-1-1', { '2026-1-1': { count: 9, sec: 3599 } })") === false &&
  w.eval("isDayDone('2026-1-1', { '2026-1-1': { count: 9, sec: 3600 } })") === true);
ok("顶部改成「本月打卡天数」", /本月打卡天数/.test(html) && !!$("#dk-days"));
ok("侧栏不再渲染旧的星级块（sb-star 已删）", !$("#sb-star") && !/id="sb-star"/.test(html));
ok("有当月星历容器", !!$("#cal"));
ok("日历是 7 列网格", /\.cal\s*\{[^}]*repeat\(7/.test(css));
ok("实星格高亮 / 无这天淡出", /\.cal-cell\.on\s*\{/.test(css) && /\.cal-cell\.void\s*\{/.test(css));

const nowD = new Date(), nY = nowD.getFullYear(), nM = nowD.getMonth() + 1, nD = nowD.getDate();
const dim = new Date(nY, nM, 0).getDate();
const clog = {};
for (let i = 1; i <= 5; i++) clog[`${nY}-${nM}-${i}`] = { count: 6, sec: 3600 };
w.localStorage.setItem("sketchLogV1", JSON.stringify(clog));
w.eval("S.phase='idle'; S.liveSec=0; renderStats()");
ok("日历固定 31 格（1~31 日）", $("#cal").querySelectorAll(".cal-cell").length === 31);
ok("已打卡 5 天 → 5 颗实星", $("#cal").querySelectorAll(".cal-cell.on").length === 5);
ok("本月其余日子是空星", ($("#cal").innerHTML.match(/☆/g) || []).length === dim - 5);
ok("本月没有的那几天淡出（31 - 当月天数）", $("#cal").querySelectorAll(".cal-cell.void").length === 31 - dim);
ok("今天那一格有高亮", $("#cal").querySelectorAll(".cal-cell.today").length === 1);
ok("顶部显示本月打卡天数", $("#dk-days").textContent === "5");
ok("顶部显示当前年月", $("#dk-month").textContent === `${nY}年${nM}月`);
const todayDoneNow = nD <= 5;
ok("今日进度文案", todayDoneNow
  ? /今日打卡已完成/.test($("#dk-prog").textContent)
  : /今日已画 0 \/ 60 分钟 · 还差 60 分钟打卡/.test($("#dk-prog").textContent));
ok("进度条宽度跟着走", $("#dk-bar").style.width === (todayDoneNow ? "100%" : "0%"));
w.eval("S.phase='draw'; S.liveSec=90;");
ok("今日秒数 = 已记录 + 当前这张正在画的",
  w.eval("Math.round(todaySecNow())") === (todayDoneNow ? 3690 : 90));
w.eval("S.phase='idle'; S.liveSec=0;");

const gl = {}; gl[`${nY}-${nM}-${nD}`] = { count: 9, sec: 3595 };
w.localStorage.setItem("sketchLogV1", JSON.stringify(gl));
w.eval("window.__cele=0; window.__celeBak=celebrateDaily; celebrateDaily=function(){ window.__cele++; };");
w.eval("S.phase='draw'; S.liveSec=4; checkDailyGoal();");
ok("还差一点不祝贺", w.eval("window.__cele") === 0 && w.eval("!!(getLog()[todayStr()]||{}).done") === false);
w.eval("S.liveSec=10; checkDailyGoal();");
ok("跨过 1 小时祝贺一次", w.eval("window.__cele") === 1 && w.eval("!!(getLog()[todayStr()]||{}).done") === true);
w.eval("S.liveSec=600; checkDailyGoal();");
ok("之后不再重复祝贺", w.eval("window.__cele") === 1);
w.eval("celebrateDaily=window.__celeBak; S.phase='idle'; S.liveSec=0;");
ok("恭喜音效是上行琶音（5 个音）",
  ((html.match(/function cheerSound\(\)\s*\{[\s\S]*?\n\}/) || [""])[0].match(/beep\(/g) || []).length === 5);
ok("满 1 小时小兔气泡：恭喜主人今日速写打卡成功！",
  /petSay\("恭喜主人今日速写打卡成功！", 9\)/.test(html));
ok("满 1 小时还有甜妹人声",
  /speakWith\(defaultPreset\(\), "恭喜主人今日速写打卡成功！"\)/.test(html));

console.log("\n【小兔待机提醒 / 连续打卡里程碑】");
ok("待机提醒文案（原文照抄）", w.eval("REMIND_TEXT") === "主人，今的速写还没有打卡哦~");
ok("只在小兔开着时才说话", /if \(!j \|\| !j\.ok \|\| !j\.on\) return;/.test(html));
ok("陪画 / 练习中不打扰", /if \(j\.companion\) return;/.test(html));
ok("提醒间隔 30 分钟", /30 \* 60 \* 1000/.test(html));
ok("打开小兔先来一次，之后每 30 分钟",
  /setInterval\(dkIdleTick, 30000\)/.test(html) && /setTimeout\(dkIdleTick, 20000\)/.test(html));
ok("页面加载就挂上提醒", /renderStats\(\);\s*\n\s*startDkReminder\(\);/.test(html));
ok("今天打卡了就停止催促", /if \(todayDone\(\)\) \{ stopDkReminder\(\); return; \}/.test(html));
ok("打卡成功那一下也停掉催促", /celebrateDaily\(\);[\s\S]{0,120}stopDkReminder\(\);/.test(html));
ok("一周里程碑文案", w.eval("MS_TEXT[7]") === "主人，你已经连续打卡一周啦！主人真棒！今天还继续吗？");
ok("一个月里程碑文案", w.eval("MS_TEXT[30]") === "主人，你已经连续打卡一个月啦！主人真棒！今天还继续吗？");
const l7 = {};
for (let i = 0; i < 7; i++) {
  const x = new Date(); x.setDate(x.getDate() - i);
  l7[`${x.getFullYear()}-${x.getMonth() + 1}-${x.getDate()}`] = { count: 3, sec: 3600 };
}
w.localStorage.setItem("sketchLogV1", JSON.stringify(l7));
w.localStorage.setItem("sketchDkMsV1", "{}");
ok("连续 7 天满 1 小时 → 连续天数 7", w.eval("calcStreak(getLog())") === 7);
w.eval("window.__say=''; window.__sayBak=petSay; petSay=function(t){ window.__say=t; };");
ok("满一周弹出祝贺气泡", w.eval("checkMilestone()") === true && w.eval("window.__say") === w.eval("MS_TEXT[7]"));
w.eval("window.__say='';");
ok("同一个里程碑只祝贺一次", w.eval("checkMilestone()") === false && w.eval("window.__say") === "");
const l30 = {};
for (let i = 0; i < 30; i++) {
  const x = new Date(); x.setDate(x.getDate() - i);
  l30[`${x.getFullYear()}-${x.getMonth() + 1}-${x.getDate()}`] = { count: 3, sec: 3600 };
}
w.localStorage.setItem("sketchLogV1", JSON.stringify(l30));
ok("满一个月走「一个月」那条祝贺",
  w.eval("checkMilestone()") === true && w.eval("window.__say") === w.eval("MS_TEXT[30]"));
w.eval("petSay=window.__sayBak;");

console.log("\n【速写引导语音 01-08】");
const GD = path.join(ROOT, "assets", "voice", "guide");
[["01", "开场"], ["02", "准备起笔"], ["03", "开画"], ["04", "倒计时3分钟"],
 ["05", "倒计时1分钟"], ["06", "倒计时30秒"], ["07", "倒计时10秒"], ["08", "休息"]]
  .forEach(([n, tag]) => ok(`${n}_${tag} 已内置`, fs.existsSync(path.join(GD, `速写引导_${n}_${tag}.mp3`))));
ok("VOICE_CLIP_DIR 指向 guide 目录", w.eval("VOICE_CLIP_DIR") === "assets/voice/guide/");
ok("01 → 开场（试听）", w.eval("VOICE_CLIPS.sample") === "速写引导_01_开场.mp3");
ok("02 → 准备起笔（点开始练习）", w.eval("VOICE_CLIPS.ready") === "速写引导_02_准备起笔.mp3");
ok("03 → 开画", w.eval("VOICE_CLIPS.start") === "速写引导_03_开画.mp3");
ok("08 → 休息", w.eval("VOICE_CLIPS.rest") === "速写引导_08_休息.mp3");
ok("180 秒 → 04 倒计时3分钟", w.eval("clipForCountdown(180)") === "速写引导_04_倒计时3分钟.mp3");
ok("60 秒 → 05 倒计时1分钟", w.eval("clipForCountdown(60)") === "速写引导_05_倒计时1分钟.mp3");
ok("30 秒 → 06 倒计时30秒", w.eval("clipForCountdown(30)") === "速写引导_06_倒计时30秒.mp3");
ok("10 秒 → 07 倒计时10秒", w.eval("clipForCountdown(10)") === "速写引导_07_倒计时10秒.mp3");
ok("无对应音频的时长回退合成语音", w.eval("clipForCountdown(300)") === null);
ok("试听按钮随音色面板一并删除", !$("#btn-clip-sample"));
ok("09_GOGOGO 已内置", fs.existsSync(path.join(GD, "速写引导_09_GOGOGO_元气版.mp3")));
ok("VOICE_CLIPS.go 指向 09", w.eval("VOICE_CLIPS.go") === "速写引导_09_GOGOGO_元气版.mp3");
ok("GO 有合成语音兜底文案", typeof w.eval("SPEAK_LINES.go") === "string" && w.eval("SPEAK_LINES.go").length > 0);
ok("开场只播倒计时（不含开画/GOGOGO）",
  /speakSeq\(\[\s*\{ file: clipForCountdown\(S\.dur\)/.test(html) &&
  !/\{ file: VOICE_CLIPS\.start/.test(html) && !/\{ file: VOICE_CLIPS\.go/.test(html));
ok("倒计时播完才开始走进度条",
  /clipForCountdown\(S\.dur\)[\s\S]*startPhase\("draw", S\.dur\)/.test(html));
ok("开始练习不再播准备起笔语音", !/\{ file: VOICE_CLIPS\.ready/.test(html));
ok("休息不再播语音", !/\{ file: VOICE_CLIPS\.rest/.test(html));
ok("里程碑仍走倒计时音频队列", /file: clipForCountdown\(c0\)/.test(html));
ok("旧的直接 speak 调用已全部替换",
  !/speak\(SPEAK_LINES\.(ready|start|rest)\)/.test(html) &&
  !/speak\(SPEAK_LINES\.countdown\(durLabel\(c0\)\)\)/.test(html));
ok("播失败会回退合成语音", /clipAudio\.onerror = finish\(giveUp\)/.test(html) && /p\.catch\(finish\(giveUp\)\)/.test(html));
ok("有 15 秒兜底防队列卡死", /setTimeout\(finish\(next\), 15000\)/.test(html));
let rtErr = null;
try {
  w.eval("clipBusy=false;clipQueue.length=0;speakSeq([{file:VOICE_CLIPS.ready,text:SPEAK_LINES.ready}])");
} catch (e) { rtErr = e.message; }
ok("运行时真实调用引导语音不报错", !rtErr, rtErr || "");
let rtErr2 = null;
try {
  w.eval("clipBusy=false;clipQueue.length=0;speakSeq([{file:null,text:'只有文字的兜底'}])");
} catch (e) { rtErr2 = e.message; }
ok("无音频时走合成语音兜底不报错", !rtErr2, rtErr2 || "");

console.log("\n【倒计时滴答音（默认常开·无开关）】");
ok("滴答音频已内置", fs.existsSync(path.join(ROOT, "assets", "voice", "sfx", "时钟滴答_适中.mp3")));
ok("音效目录常量正确", w.eval("TICK_DIR") === "assets/voice/sfx/");
ok("音效文件名正确", w.eval("TICK_FILE") === "时钟滴答_适中.mp3");
ok("TICK_FROM 是收尾切换阈值", w.eval("TICK_FROM") === 10);
ok("音量已调大 50%（.55 → .825）", Math.abs(w.eval("TICK_VOL") - 0.825) < 1e-6
  && Math.abs(w.eval("TICK_VOL") / 0.55 - 1.5) < 0.01,
  "实际 " + w.eval("TICK_VOL"));
ok("有音频预解锁 primeTick", /function primeTick\(\)/.test(html));
ok("点开始练习时先解锁音频", /primeTick\(\);\s*\/\//.test(html));
ok("进度条开始转就起声（默认开，不计时模式除外）",
  /if \(S\.timing !== "none"\) startTick\(\);/.test(html));
// 开关按钮与整套开关逻辑都必须彻底删干净
ok("开关按钮已删除（HTML）", !$("#btn-tick-toggle") && !/btn-tick-toggle/.test(html));
ok("开关样式已删除（CSS）", !/\.tick-toggle/.test(html));
ok("开关逻辑已删除（JS）",
  !/tickMuted|tickEnabled|renderTickBtn|TICK_RUSH|tickRushOn/.test(html));
ok("圆圈里只剩数字和阶段文字",
  ($(".ring-time") || {}).children && $(".ring-time").querySelectorAll("button").length === 0);
ok("不再有本地存储持久化", !/sketchTickV1|TICK_KEY/.test(html));
// 最后 10 秒：停掉滴答，切回原来的逐秒升调提示音
ok("最后10秒切回默认提示音",
  /tickFinalOn\(\);\s*\n\s*beep\(650 \+ \(10 - c0\) \* 60, 120\);/.test(html));
ok("收尾切换只执行一次", /function tickFinalOn\(\) \{\s*\n\s*if \(tickFinal\) return;/.test(html));
ok("收尾时会停掉滴答", /tickFinal = true;\s*\n\s*stopTick\(\);/.test(html));
ok("起播时重置播放速率", /tickAudio\.playbackRate = 1/.test(html));
ok("startTick 幂等（不再提前 return）", !/if \(!tickEnabled\(\) \|\| tickAudio\) return/.test(html));
ok("5 处静音点齐全", (html.match(/stopTick\(\);/g) || []).length >= 5,
  "命中 " + (html.match(/stopTick\(\);/g) || []).length + " 处");
ok("本段结束就停（phaseDone 内）", /clearInterval\(S\.timer\);\s*\n\s*stopTick\(\);/.test(html));
ok("滴答为循环播放", /loop = true/.test(html));
let tkErr = null;
try {
  w.eval("primeTick();startTick();startTick();tickFinalOn();tickFinalOn();stopTick();stopTick();");
} catch (e) { tkErr = e.message; }
ok("解锁 + 重复起播 + 收尾切换 + 重复停止都不报错", !tkErr, tkErr || "");
let tkErr2 = null;
try {
  w.eval("startTick(); tickFinalOn(); startTick();");
  w.eval("tickFinal === false");   // 重新起播应重置收尾标记
} catch (e) { tkErr2 = e.message; }
ok("重新起播会重置收尾标记", !tkErr2 && w.eval("tickFinal") === false);

console.log("\n【结算页按钮文案】");
ok("再来一组 → 加油！我要再画一组！", $("#btn-again").textContent === "加油！我要再画一组！");
ok("返回设置 → 返回", $("#btn-back").textContent === "返回");
ok("不再出现旧文案", !/>再来一组</.test(html) && !/>返回设置</.test(html));

console.log("\n【教程数据】");
ok("GUIDE_DATA 已加载", !!w.GUIDE_DATA && Object.keys(w.GUIDE_DATA).length >= 11);
ok("教程 SVG 未写死颜色", !/#d4537e|#7f77dd/.test(guides));

console.log("\n运行时错误：" + (errs.length ? errs.join(" | ") : "无"));
ok("无运行时报错", errs.length === 0);

// 桌面端源码（后面很多段要用）
const pet = fs.readFileSync(path.join(ROOT, "desktop", "xiaotu_pet.py"), "utf8");

console.log("\n【模式精简：只剩「上传本地参考图」】");
ok("关键词开画模式已删（卡片 / 输入框 / 常用词 / 结果区全没了）",
  !$("#mode-keyword-card") && !$("#kw-input") && !$("#kw-freq") && !$("#kw-results")
  && !$("#btn-kw-search") && !$("#kw-wrap"));
ok("关键词相关 JS 已删（renderKwFreq / kwPickImage / SEARCH_BASE）",
  !/function renderKwFreq|function kwPickImage|SEARCH_BASE/.test(html));
ok("关键词相关 CSS 已删", !/\.kw-results\s*\{/.test(css) && !/\.kw-row\s*\{/.test(css)
  && !/\.kw-freq\s*\{/.test(css));
ok("出题只看上传的参考图：无图失败、有图成功", (function () {
  w.eval("S.images=[];");
  const noImg = w.eval("buildQueue()") === false;
  w.eval("S.images=['https://x/a.jpg'];");
  const hasImg = w.eval("buildQueue()") === true && w.eval("S.queue[0].img") === "https://x/a.jpg";
  w.eval("S.images=[];");
  return noImg && hasImg;
})());
ok("没图时点开始提示先上传（不再有分类/关键词分支）",
  /alert\("请先上传至少一张参考图"\)/.test(html));
ok("两个花瓣画板参考链接入口已删掉",
  !$(".ref-links") && !/三次元美少女参考|二次元美少女参考/.test(html)
  && !$("#upload-wrap").querySelector("a"));
ok("「DQ速写参考」按钮入口已删掉",
  !/id="btn-ref"/.test(html) && !/\$\("btn-ref"\)\.addEventListener/.test(html));
ok("花瓣链接的 CSS 一起清掉（.ref-links 规则没了）",
  !/\.ref-links\s*\{/.test(css));
// 出题/分类相关的界面文案跟着一起改掉（不再出现「题目会出现在这里」）
ok("欢迎页文案改成上传参考图说法",
  /在左侧上传参考图，再选好时长和张数/.test(html) && !/在左侧选好时长、张数和速写基础/.test(html));
ok("练习提示区不再用分类/题目字段（无图只提示上传）",
  !/item\.cat|item\.txt/.test(html) && /还没有参考图，请先上传/.test(html));
// 桌面端自带的搜索代理是桌宠能力，不随网页模式一起删
ok("桌面端仍含本地搜索代理 /huaban_search", pet.includes("/huaban_search") && pet.includes("start_search_server"));
ok("桌面端搜索代理端口为 18765", pet.includes("SEARCH_PORT = 18765"));

console.log("\n【计时方式：倒计时 / 正向计时 / 不计时】");
ok("计时方式分组存在", !!$("#timing-row"));
ok("含 3 个选项(倒计时/正向计时/不计时)", $("#timing-row").querySelectorAll(".chip").length === 3);
ok("默认选中倒计时", $('[data-timing="down"]').classList.contains("on"));
$('[data-timing="up"]').click();
ok("点正向计时 chip 设置 S.timing=up", w.eval("S.timing") === "up");
ok("正向计时 note 文案更新", $("#timing-note").textContent.indexOf("正向") >= 0);
$('[data-timing="none"]').click();
ok("点不计时 chip 设置 S.timing=none", w.eval("S.timing") === "none");
ok("不计时 note 文案更新", $("#timing-note").textContent.indexOf("不计时") >= 0);
// 不计时：startPhase 进入绘制时隐藏计时环、显示「自由练习」、不播滴答、按钮改「下一张」
w.eval("S.timing='none'; startPhase('draw', 60);");
ok("不计时 隐藏计时环(timer-off)", $(".ring-wrap").classList.contains("timer-off"));
ok("不计时 中央显示「自由练习」", $("#time-text").textContent === "自由练习");
ok("不计时 按钮文案改为「下一张」", $("#btn-skip").textContent === "下一张");
// 正向计时：隐藏计时环被清除、起点 0、记录 phaseStart、按钮「下一张」
w.eval("S.timing='up'; startPhase('draw', 60);");
ok("正向计时 清除 timer-off", !$(".ring-wrap").classList.contains("timer-off"));
ok("正向计时 起始显示 0", $("#time-text").textContent === "0");
ok("正向计时 记录 phaseStart", typeof w.eval("S.phaseStart") === "number" && w.eval("S.phaseStart") > 0);
ok("正向计时 按钮文案「下一张」", $("#btn-skip").textContent === "下一张");
// 倒计时：恢复默认显示与「跳过」按钮
w.eval("S.timing='down'; startPhase('draw', 60);");
ok("倒计时 清除 timer-off", !$(".ring-wrap").classList.contains("timer-off"));
ok("倒计时 按钮文案「跳过」", $("#btn-skip").textContent === "跳过");
// 手动切换(下一张)在 正向/不计时 下记录实际已画时长
w.eval("S.timing='up'; S.phaseStart=Date.now()-5000; S.idx=0; S.queue=[{txt:'x'}]; nextPrompt();");
ok("正向计时 手动切换记录已画时长(focusSec>0)", w.eval("S.focusSec") > 0);

console.log("\n【桌宠陪画模式】");
ok("陪画：代理基址 127.0.0.1:18765", w.eval("PET_BASE") === "http://127.0.0.1:18765");
ok("陪画：COMP_PHRASE 含 tired/doze 文案",
  w.eval("Array.isArray(COMP_PHRASE.tired)") === true && w.eval("COMP_PHRASE.doze.length") > 0);
ok("陪画：已定义 compStart/compStop/compPoll",
  w.eval("typeof compStart") === "function" && w.eval("typeof compStop") === "function" &&
  w.eval("typeof compPoll") === "function");
ok("陪画：已定义 compSessionBegin/compSessionEnd",
  w.eval("typeof compSessionBegin") === "function" && w.eval("typeof compSessionEnd") === "function");
ok("陪画：慵懒困困音色(p10)可解析",
  (w.eval("JSON.stringify(presetOf('p10'))") || "").indexOf("慵懒困困") >= 0);
// 不计时没有明确总时长 → 不陪画；计时模式 → 启动轮询（jsdom 无 fetch，验证逻辑不抛错）
w.eval("S.timing='none'; compSessionBegin();");
ok("陪画：不计时进入时不启动轮询", w.eval("compTimer") === null);
w.eval("S.dur=60; S.count=10; S.timing='down'; compSessionBegin();");
ok("陪画：计时模式启动状态轮询", w.eval("compTimer") !== null);
w.eval("compSessionEnd();");
ok("陪画：结束后停止轮询", w.eval("compTimer") === null);
// 开始/结束已接线到练习流程
ok("陪画：开始练习调用 compSessionBegin", /compSessionBegin\(\);/.test(html));
ok("陪画：finish() 调用 compSessionEnd", /compSessionEnd\(\);/.test(html));
// 桌面端（xiaotu_pet.py，变量 pet 已在上面读取）
ok("桌面端含陪画接口 /pet 与 /pet_state",
  pet.includes('"/pet_state"') && pet.includes('"/pet"'));
ok("桌面端含 companion_start / companion_stop",
  pet.includes("companion_start") && pet.includes("companion_stop"));
ok("pet_state 的 on = 桌宠在线（不是 companion，否则待机提醒永远进不去）",
  /"on": bool\(p\.hwnd\)/.test(pet) && !/"on": bool\(p\.companion_on\)/.test(pet));
ok("pet_state 的 companion 仍是陪画开关", /"companion": bool\(p\.companion_on\)/.test(pet));
ok("桌面端两种气泡：文字实线圆角矩形 + 表情虚线圆",
  pet.includes("_draw_text_bubble") && pet.includes("_draw_expr_bubble") &&
  pet.includes("_dashed_circle"));
ok("桌面端陪画相位含 tired / doze / done",
  pet.includes('"tired"') && pet.includes('"doze"') && pet.includes('"done"'));
ok("桌面端 main() 赋值全局 PET 供 HTTP 调用", /PET = pet/.test(pet));

console.log("\n【两张卡片都固定展开：无折叠 / 无箭头 / 无选中高亮】");
ok("侧栏共 2 张卡片（练习设置 + 打开本地参考图）",
  d.querySelectorAll(".mode-card .mode-body").length === 2);
ok("默认就是参考图模式", w.eval("S.mode") === "image");
ok("卡片内容默认就是可见的（.mode-body 直接 display:block）",
  /\.mode-card \.mode-body\s*\{[^}]*display:\s*block/s.test(css));
ok("卡片标题里不再有箭头（.mode-flag 已从页面移除）",
  d.querySelectorAll(".mode-card .mode-flag").length === 0);
ok("页面不再出现「点此启用」", !/点此启用/.test(html));
ok("卡片不做成可点光标（cursor: default）",
  /\.mode-card\s*\{[^}]*cursor:\s*default/s.test(css));
ok("选中高亮样式已删（不再有 .mode-card.on）",
  !/\.mode-card\.on\b/.test(css) && !/classList[\s\S]{0,40}"on"[\s\S]{0,40}mode-card/.test(html));
ok("折叠逻辑已删（toggleModeCard / isFixedCard / renderModeCards 全没了）",
  !/toggleModeCard|isFixedCard|renderModeCards/.test(html));
ok("标题文字：练习设置 / 打开本地参考图",
  $("#practice-settings-card h2").textContent.trim() === "练习设置" &&
  $("#mode-image-card h2").textContent.trim() === "打开本地参考图");
ok("不再出现「上传本地参考图模式」字样", !/上传本地参考图模式/.test(html));
// 点标题：既不折叠、也不切模式、也不加高亮
const modeBefore = w.eval("S.mode");
$("#practice-settings-card h2").dispatchEvent(new w.Event("click", { bubbles: true }));
$("#mode-image-card h2").dispatchEvent(new w.Event("click", { bubbles: true }));
ok("点标题仍保持可见（CSS 里恒 display:block）",
  /\.mode-card \.mode-body\s*\{[^}]*display:\s*block/s.test(css));
ok("点标题不会切换模式", w.eval("S.mode") === modeBefore);
ok("点标题不会加高亮 class",
  !$("#mode-image-card").classList.contains("on") &&
  !$("#practice-settings-card").classList.contains("on"));

console.log("\n【参考图：拖入 / Ctrl+V 粘贴】");
ok("已定义 addImageSources", w.eval("typeof addImageSources") === "function");
ok("已定义 imageSourcesFromData", w.eval("typeof imageSourcesFromData") === "function");
w.eval("setMode('image'); S.imgStore.image=[]; syncImages(); addImageSources(['blob:x1','blob:x2'], false);");
ok("追加图片写入 S.images", w.eval("S.images.length") === 2);
ok("缩略图渲染 2 张", $("#thumb-grid").querySelectorAll("img").length === 2);
w.eval("addImageSources(['blob:y1'], true);");
ok("replace=true 覆盖原图", w.eval("S.images.length") === 1 && w.eval("S.images[0]") === "blob:y1");
ok("上传区文案含拖入/粘贴提示", /拖进来|Ctrl\+V|粘贴/.test($(".upload-zone").textContent));
ok("上传区是圆角正方形（aspect-ratio 1:1 + 圆角）",
  /\.upload-zone\s*\{[^}]*aspect-ratio:\s*1\s*\/\s*1/.test(css) &&
  /\.upload-zone\s*\{[^}]*border-radius:\s*\d+px/.test(css));
ok("上传区实线加粗紫边（边缘更明显）",
  /\.upload-zone\s*\{[^}]*border:\s*2\.5px\s+solid\s+var\(--purple\)/.test(css));
ok("上传区文案分主副两行", !!$(".upload-zone .up-main") && !!$(".upload-zone .up-sub"));

console.log("\n【参考图：选完立刻在方框里预览 + 最多 9 张】");
ok("方框里预留了预览图元素", !!$("#up-preview") && !!$("#upload-zone .up-preview"));
ok("方框里预留了空态文案块", !!$("#up-empty") && !!$("#up-empty .up-main"));
ok("点方框仍能继续加图（文件选择框还在 label 里）", !!$("#upload-zone #file-input"));
ok("预览图铺满方框（绝对定位 + 完整显示不裁切）",
  /\.upload-zone \.up-preview\s*\{[^}]*position:\s*absolute/s.test(css) &&
  /\.upload-zone \.up-preview\s*\{[^}]*object-fit:\s*contain/s.test(css));
ok("空态文案整块让位给预览", /\.upload-zone \.up-empty\s*\{[^}]*display:\s*flex/s.test(css));
ok("有 MAX_REFS = 9 上限常量", /const MAX_REFS = 9;/.test(html));
ok("有 updateUploadPreview 刷新方框预览", /function updateUploadPreview\(\)/.test(html));
w.eval("setMode('image'); S.imgStore.image=[]; syncImages(); renderThumbs();");
ok("没图时方框是空态文案（预览图隐藏）",
  $("#up-preview").hidden === true && $("#up-empty").hidden === false && $("#up-hint").hidden === true);
w.eval("addImageSources(['blob:p1','blob:p2','blob:p3'], true);");
ok("选完图方框立刻显示预览", $("#up-preview").hidden === false);
ok("方框预览的就是新加的第一张", $("#up-preview").getAttribute("src") === "blob:p1");
ok("方框里的小条写明第几张", /第 1 \/ 3 张/.test($("#up-hint").textContent));
ok("有图时隐藏空态文案", $("#up-empty").hidden === true && $("#up-hint").hidden === false);
ok("预览小图仍排在下面的缩略图里", $("#thumb-grid").querySelectorAll("img").length === 3);
w.eval("showRefThumb(2);");
ok("点小图换预览时方框也跟着换", $("#up-preview").getAttribute("src") === "blob:p3");
ok("换预览后小条序号跟着变", /第 3 \/ 3 张/.test($("#up-hint").textContent));
w.eval("setMode('image'); S.imgStore.image=[]; syncImages(); renderThumbs();");
ok("一次加 12 张只收前 9 张",
  w.eval("addImageSources(['blob:a1','blob:a2','blob:a3','blob:a4','blob:a5','blob:a6','blob:a7','blob:a8','blob:a9','blob:a10','blob:a11','blob:a12'], false)") === 9);
ok("库里确实只有 9 张", w.eval("S.images.length") === 9);
ok("缩略图也只渲染 9 张", $("#thumb-grid").querySelectorAll("img").length === 9);
ok("已经 9 张时再加会收不进来", w.eval("addImageSources(['blob:b1'], false)") === 0);
ok("收不进来时小兔会提醒", /petSay\(refOverText\(MAX_REFS\)/.test(html));
ok("超出的本地图会释放 blob 内存", /over\.forEach\([\s\S]{0,200}revokeObjectURL/.test(html));
ok("上传区文案带上 9 张上限", /已加载 9 \/ 9 张参考图/.test($("#upload-info").textContent));
ok("空态副文案写明最多 9 张", /一次最多 9 张/.test($(".up-sub").textContent));
ok("英文条目已同步（最多 9 张那句）",
  /一次最多 9 张，练习时随机轮播/.test(html) && /Up to 9 images/.test(html));
w.eval("S.imgStore.image=[]; syncImages();");
ok("replace 模式也最多 9 张",
  w.eval("addImageSources(['blob:c1','blob:c2','blob:c3','blob:c4','blob:c5','blob:c6','blob:c7','blob:c8','blob:c9','blob:c10'], true)") === 9);
ok("删光后方框回到空态", (function () {
  w.eval("for (var i=0;i<9;i++) delRefThumb(0);");
  return $("#up-preview").hidden === true && $("#up-empty").hidden === false;
})());
const applyLangFn = (html.match(/function applyLang\(l\)[\s\S]*?(?=\nfunction )/) || [""])[0];
ok("切语言时上传区说明会跟着重渲染", /renderThumbs\(\)/.test(applyLangFn));
ok("方框里的预览图右上角有 ✕ 删除按钮", !!$("#up-del") && !!$("#upload-wrap > #up-del"));
// 回归：✕ 曾经是 <button> 放在 <label> 里 —— button 也属于「可关联控件」，会把
// 「点方框」的点击目标抢走，导致点方框再也不弹文件选择框（2026-09-29 修）
ok("✕ 不在 <label> 里（否则会抢走点方框的点击目标）", !$("#upload-zone #up-del")
  && !$("#upload-zone button") && !$("#upload-zone input:not(#file-input)"));
ok("方框用 for= 显式绑到文件选择框", $("#upload-zone").getAttribute("for") === "file-input");
ok("点方框真的会触发文件选择框（label.control 就是它）",
  (function () { const c = $("#upload-zone").control; return !!c && c === $("#file-input"); })());
ok("点方框会把点击转发给文件选择框", (function () {
  let n = 0;
  const f = $("#file-input"), h = () => { n++; };
  f.addEventListener("click", h);
  $("#upload-zone").dispatchEvent(new w.MouseEvent("click", { bubbles: true, cancelable: true }));
  f.removeEventListener("click", h);
  return n === 1;
})());
ok("点 ✕ 不会误触发文件选择框", (function () {
  let n = 0;
  const f = $("#file-input"), h = () => { n++; };
  f.addEventListener("click", h);
  $("#up-del").dispatchEvent(new w.MouseEvent("click", { bubbles: true, cancelable: true }));
  f.removeEventListener("click", h);
  return n === 0;
})());
ok("✕ 有说明与无障碍标签",
  /id="up-del"[\s\S]{0,120}title="删掉这张参考图，重新选"[\s\S]{0,80}aria-label="删掉这张参考图"/.test(html));
ok("✕ 贴右上角（绝对定位 + 圆形）",
  /#upload-wrap \.up-del\s*\{[^}]*position:\s*absolute/s.test(css) &&
  /#upload-wrap \.up-del\s*\{[^}]*top:\s*10px/s.test(css) &&
  /#upload-wrap \.up-del\s*\{[^}]*right:\s*10px/s.test(css) &&
  /#upload-wrap \.up-del\s*\{[^}]*border-radius:\s*50%/s.test(css));
ok("没图时 ✕ 藏起来", (function () {
  w.eval("S.imgStore.image=[]; syncImages(); renderThumbs();");
  return $("#up-del").hidden === true;
})());
w.eval("S.imgStore.image=['blob:z1','blob:z2']; syncImages(); renderThumbs(); showRefThumb(0);");
ok("有图时 ✕ 显示出来", $("#up-del").hidden === false);
ok("✕ 在方框里也阻止了「开文件对话框」的默认行为",
  /\$\("up-del"\)\.addEventListener\("click",\s*e\s*=>\s*\{\s*\n\s*e\.preventDefault\(\);\s*\n\s*e\.stopPropagation\(\)/.test(html));
$("#up-del").dispatchEvent(new w.Event("click", { bubbles: true, cancelable: true }));
ok("点 ✕ 删掉当前预览的那张", w.eval("S.images.join(',')") === "blob:z2");
ok("删完自动预览剩下那张", $("#up-del").hidden === false
  && $("#up-preview").getAttribute("src") === "blob:z2");
$("#up-del").dispatchEvent(new w.Event("click", { bubbles: true, cancelable: true }));
ok("删光后方框回到空态、✕ 也跟着消失",
  $("#up-del").hidden === true && $("#up-preview").hidden === true && w.eval("S.images.length") === 0);

console.log("\n【选图不卡顿：重活挪出主线程 + 延后到空闲】");
ok("不再用同步 PNG 编码 toDataURL（只留不支持 toBlob 时的兜底）",
  /cv\.toBlob\(b => \{/.test(html) &&
  (html.match(/toDataURL\(/g) || []).length === 1 &&
  /\} else \{\s*\n\s*resolve\(cv\.toDataURL\("image\/png"\)\);/.test(html));
ok("编码完用 FileReader 异步读成 data:uri", /fr\.readAsDataURL\(b\)/.test(html));
ok("有 whenIdle 把预推推到画面之后", /function whenIdle\(fn\)/.test(html) &&
  /requestIdleCallback\(fn, \{ timeout: 900 \}\)/.test(html) && /setTimeout\(fn, 120\)/.test(html));
ok("预推不在选图那一刻同步跑（走 whenIdle）",
  /function petPurePreload\(src\)[\s\S]{0,320}whenIdle\(runPreload\)/.test(html));
ok("同一时刻只推一张，避免重复编码",
  /if \(_preBusy\) return;/.test(html) && /_preBusy = src;/.test(html));
ok("中途换图会收敛到最新那张（不排队推废图）",
  /_preWant = src;/.test(html) &&
  /if \(_preWant && _preWant !== _purePreSrc\) whenIdle\(runPreload\)/.test(html));
ok("方框预览图异步解码（不阻塞首帧）",
  /id="up-preview"[\s\S]{0,80}decoding="async"/.test(html));
ok("缩略图也异步解码", /data-i="\$\{i\}"[\s\S]{0,80}decoding="async"/.test(html));

console.log("\n【参考图：图只存在一份（upload 库），不会串模式】");
ok("参考图只存一份 imgStore.image",
  /imgStore:\s*\{\s*image:\s*\[\]\s*\}/.test(html) && !/keyword:\s*\[\]/.test(html));
ok("有 syncImages 把图同步进 S.images", w.eval("typeof syncImages") === "function");
ok("有 refKey 判断当前是不是参考图模式", /function refKey\(\)/.test(html));
w.eval("S.imgStore={image:[]}; refIdxMem.image=0;" +
       "setMode('image'); addImageSources(['blob:up1','blob:up2'], true);");
ok("上传后拿到这 2 张", w.eval("S.images.length") === 2 && w.eval("S.images[0]") === "blob:up1");
ok("出题拿的就是上传的这 2 张",
  w.eval("buildQueue()") === true && w.eval("S.queue[0].img") === "blob:up1");
w.eval("S.imgStore={image:[]}; syncImages();");
ok("清掉图后 buildQueue 失败（不会拿旧图开画）", w.eval("buildQueue()") === false);
ok("清掉图后没有参考图可给", w.eval("currentRefSrc()") === null);
ok("点开始先同步一次当前模式的图（双保险）",
  /\$\("btn-start"\)\.addEventListener\("click",[\s\S]{0,200}?syncImages\(\)/.test(html));

console.log("\n【参考图缩略图：右上角 ✕ 删掉单张】");
w.eval("setMode('image'); S.imgStore.image=['blob:d1','blob:d2','blob:d3']; syncImages(); renderThumbs();");
ok("每张缩略图都带一个 ✕ 删除按钮", $("#thumb-grid").querySelectorAll(".thumb-del").length === 3);
ok("删除按钮带序号与无障碍标签",
  /class="thumb-del" data-del="\$\{i\}"[\s\S]{0,120}aria-label="删除参考图\$\{i \+ 1\}"/.test(html));
$("#thumb-grid").querySelector('[data-del="1"]').dispatchEvent(new w.Event("click", { bubbles: true }));
ok("点 ✕ 后只剩 2 张", w.eval("S.images.length") === 2);
ok("删掉的正是中间那张", w.eval("S.images.join(',')") === "blob:d1,blob:d3");
ok("缩略图立刻刷新", $("#thumb-grid").querySelectorAll("img").length === 2);
ok("点 ✕ 不会顺带把这张图设成预览（删的是第 2 张）",
  $("#welcome-img-el").getAttribute("src") === "blob:d3");
ok("本地图删掉后释放 blob 内存", /revokeObjectURL/.test(html));
w.eval("delRefThumb(0); delRefThumb(0);");
ok("删光后清空参考图区", $("#welcome-img").hidden === true && w.eval("S.images.length") === 0);
ok("删光后恢复小兔形象", d.querySelector("#screen-welcome .hime-img").hidden === false);
ok("删光后点开始会提示先上传（不会静默进参考图模式）",
  w.eval("(function(){syncImages();return buildQueue();})()") === false);
ok("删除按钮贴在缩略图右上角",
  /\.thumb-del\s*\{[^}]*position:\s*absolute/s.test(css) &&
  /\.thumb-del\s*\{[^}]*top:\s*3px/s.test(css) && /\.thumb-del\s*\{[^}]*right:\s*3px/s.test(css));
ok("删除按钮常驻可见（不用悬停才冒出来）", !/\.thumb-del\s*\{[^}]*opacity:\s*0/s.test(css));
ok("缩略图外层有定位容器", /\.thumb-cell\s*\{[^}]*position:\s*relative/s.test(css));
w.eval("S.imgStore={image:[]}; setMode('image'); syncImages(); renderThumbs();");

console.log("\n【桌宠设置：只剩 窗口置顶】");
ok("置顶设置行存在", !!$("#pet-top-row"));
ok("默认置顶=开", w.eval("petPrefTop()") === true);
$('#pet-top-row [data-pet-top="0"]').click();
ok("点「关」后 petPrefTop=false", w.eval("petPrefTop()") === false);
ok("练习页的「桌宠置顶」快捷按钮已删（练习中不再显示开关）",
  !$("#btn-pet-pin") && !/btn-pet-pin/.test(html) && !/renderPinBtn/.test(html));
ok("练习页控制区只剩 暂停 / 跳过 / 结束",
  $("#screen-practice .ctrls").querySelectorAll("button").length === 3);
ok("说明文案不再提练习页快捷开关",
  !$("#pet-top-note").textContent.includes("练习页")
  && $("#pet-top-note").textContent.includes("默认置顶显示"));
w.eval("localStorage.removeItem('sketchPetTopV1');");
ok("跟随光标整块已删（行 / 说明 / 网页逻辑全没了）",
  !$("#pet-follow-row") && !$("#pet-follow-note") && !/跟随光标/.test(html)
  && !/PET_FOLLOW_KEY|petPrefFollow|petFollow\(/.test(html));
ok("桌面端跟随光标能力已删（set_follow / _follow_cursor / cmd=follow）",
  !pet.includes("set_follow") && !pet.includes("_follow_cursor")
  && !pet.includes('"follow"') && !pet.includes("self.follow"));
ok("「速写时变成参考图」整块已删（行 / 说明 / 网页逻辑全没了）",
  !$("#pet-ref-row") && !$("#pet-ref-note") && !/速写时变成参考图/.test(html)
  && !/PET_REF_KEY|petPrefRef|petShowImage|petImageOff|petSessionEnd/.test(html));
ok("桌面端「桌宠变成参考图」接口已删（/pet_image 与 cmd=image_off）",
  !pet.includes('"/pet_image"') && !pet.includes('"image_off"'));
ok("纯净模式仍靠 set_image_global → set_display_image 送图（不能误删）",
  pet.includes("def set_image_global") && pet.includes("def set_display_image")
  && pet.includes("set_image_global(obj.get(\"d\"))"));

console.log("\n【已删除：小兔点评十种人格 + 图片卡片内生成按钮（勿回加）】");
ok("点评区块不再存在", !$("#persona-row") && !$("#critique-line"));
ok("图片卡片内三个生成按钮不再存在",
  !$("#btn-pet-on") && !$("#btn-pet-sticker") && !$("#btn-pet-social"));
ok("点评文案与人格逻辑已移除",
  w.eval("typeof CRITIQUE") === "undefined" && w.eval("typeof critique") === "undefined");
ok("页面不再出现「小兔点评这张图」", !html.includes("小兔点评这张图"));

console.log("\n【设置页一键生成已删（桌面端右键菜单仍保留）】");
ok("设置页两个生成按钮已删",
  !$("#btn-make-sticker") && !$("#btn-make-card")
  && !/btn-make-sticker|btn-make-card/.test(html));
ok("设置页不再出现「一键生成 / 生成表情包 / 生成社媒卡片」字样",
  !/一键生成|生成表情包|生成社媒卡片/.test(html));
ok("桌面端仍保留一键生成能力（右键菜单 + /pet_card）",
  pet.includes("def make_card") && pet.includes('"sticker"') && pet.includes('"social"')
  && pet.includes('"/pet_card"') && pet.includes('"表情包（透明 PNG）"')
  && pet.includes('"社媒卡片（1080×1350）"'));
ok("桌面端仍含 显示参考图 能力（set_display_image）",
  pet.includes("set_display_image"));

console.log("\n【纯净参考图模式：大图置顶 / 滚轮缩放 / 另存 / 唤回主界面】");
ok("有参考图时欢迎屏显示开始按钮（CSS）",
  /#welcome-img:not\(\[hidden\]\)\s*~\s*\.welcome\s+#btn-welcome-start/.test(css));
ok("已定义 petPureStart / petPureEnd",
  w.eval("typeof petPureStart") === "function" && w.eval("typeof petPureEnd") === "function");
ok("欢迎屏开始按钮流程含纯净模式", html.includes("petPureStart(src)"));
ok("btn-start 里集中触发纯净模式（任何入口都生效）",
  /btn-start"\)\.addEventListener[\s\S]{0,900}petPureStart\(src\)/.test(html));
ok("参考图模式开练就进纯净模式", /if \(refKey\(\) && S\.images\.length\)/.test(html));
ok("纯净模式：参考图走独立大窗，小兔留右下角（不再让桌宠变成图）",
  pet.includes("def ensure_pure_window") && pet.includes('PetWindow(kind="pure")') &&
  /def enter_pure[\s\S]{0,1400}self\.set_display_image\(None\)/.test(pet));
ok("进入纯净模式先收起主界面，再建大图（点下去界面立刻没）",
  /def enter_pure[\s\S]{0,1200}hide_page_window\(\)[\s\S]{0,400}ensure_pure_window\(\)/.test(pet));
ok("大图没起来会把主界面还回去（不至于把人晾在空白桌面）",
  /show_image\(self\._display_src\)[\s\S]{0,300}restore_page_window\(\)/.test(pet));
ok("大图窗口与桌宠用不同窗口类", pet.includes('PET_CLASS + ("Pure" if kind == "pure" else "")'));
ok("纯净模式不冒气泡/不呼吸的旧限制已撤销（小兔照常陪画）",
  !/if self\.pure:\s*\n\s*return\s+# 纯净参考图模式/.test(pet));
ok("倒计时推给小兔（cmd=timer + set_timer + 头顶计时圆盘）",
  pet.includes('cmd == "timer"') && pet.includes("def set_timer") &&
  pet.includes("def _draw_timer_dial"));
ok("计时圆盘 = 白底圆 + 中间大字秒数 + 下面小字状态",
  /def _draw_timer_dial[\s\S]{0,900}fill=\(255, 255, 255, 255\)/.test(pet) &&
  /def _draw_timer_dial[\s\S]{0,1500}self\.timer_label/.test(pet));
ok("圆里默认什么都不放（没有倒计时就只是空白白圆）",
  /def _draw_timer_dial[\s\S]{0,1500}if self\.timer_left < 0:\s*\n\s*return canvas/.test(pet));
ok("秒数会自动缩字号，1~4 位都不会顶出圆外",
  /def _text_fit\(self, draw, text, maxw, size_hint\)/.test(pet) &&
  /_text_fit\(draw, num, c \* 0\.80/.test(pet));
ok("左侧那块小牌已撤掉（窗口不再向左加宽）",
  !pet.includes("_draw_timer_chip") && !pet.includes("_timer_pad"));
ok("计时圆盘与陪画气泡共用头顶那条带子（有倒计时优先画圆盘）",
  /if self\.timer_left >= 0 and self\.kind == "pet":\s*\n\s*canvas = self\._draw_timer_dial/.test(pet) &&
  /elif self\.bubble_kind:/.test(pet));
ok("要显示倒计时就把头顶带子留出来，不用时收回",
  /def set_timer[\s\S]{0,700}if left >= 0:\s*\n\s*self\._ensure_band\(\)/.test(pet));
ok("倒计时状态随计时方式区分（准备起笔/绘制中/最后冲刺/已画）",
  /ready[\s\S]{0,200}准备起笔/.test(html) && html.includes("最后冲刺") && html.includes("已画"));
ok("纯净模式每秒同步倒计时，退出即清空",
  w.eval("typeof petTimerPush") === "function" && w.eval("typeof petClockStart") === "function" &&
  w.eval("typeof petClockStop") === "function" && /petClockStop\(\); petFetch\("\/pet\?cmd=pure_end"\)/.test(html));
ok("打开的浏览器窗口也固定中文（独立 profile，不动平时那个 Chrome）",
  pet.includes('"--lang=zh-CN"') && pet.includes('"--accept-lang=zh-CN"')
  && pet.includes("--user-data-dir="));
ok("Chrome 关掉后台节流（页面最小化后计时不卡）",
  pet.includes("--disable-background-timer-throttling") &&
  pet.includes("--disable-backgrounding-occluded-windows") &&
  pet.includes("--disable-intensive-wake-up-throttling"));
const hideFn = (pet.match(/def hide_page_window\(\):[\s\S]*?(?=\ndef )/) || [""])[0];
ok("主界面一步隐藏（不再最小化，没有缩小动画、不用等 IsIconic）",
  pet.includes("def hide_page_window") && pet.includes("def restore_page_window") &&
  /ShowWindow\(hwnd, SW_HIDE\)/.test(hideFn) &&
  !/SW_MINIMIZE|IsIconic|time\.sleep/.test(hideFn));   // 没有最小化、没有轮询等待
ok("记住页面窗口句柄（收起后也唤得回来）",
  pet.includes("PAGE_HWND") && pet.includes("def remember_page_window"));
ok("open_page 后会记住页面窗口句柄",
  pet.includes("remember_page_window()      # 后台轮询记住窗口句柄"));
ok("enter_pure 每步单独容错，主界面收起必定执行",
  /def enter_pure[\s\S]{0,1700}hide_page_window\(\)/.test(pet) &&
  /except Exception:\s*\n\s*log\("enter_pure：收起主界面失败/.test(pet));
ok("exit_pure 用 restore_page_window 统一唤回", pet.includes("exit_pure：唤回主界面失败"));
ok("petPureStart 失败会重试一次（收起主界面不容许丢包）",
  /const failed = \(\) => \{[\s\S]{0,160}setTimeout\(\(\) => petPureStart\(src, true\), 700\)/.test(html));
ok("重试也失败会把主界面还回来（不把人晾在空白桌面）",
  /const failed = \(\) => \{[\s\S]{0,400}petFetch\("\/pet\?cmd=pure_end"\)/.test(html));
ok("点开始立刻弹图，不再等 300ms",
  /if \(src\) petPureStart\(src\);/.test(html) && !/setTimeout\(\(\) => petPureStart\(src\), 300\)/.test(html));
ok("有预推通道 /pet_preload（只解码缓存、不建窗）",
  pet.includes('"/pet_preload"') && html.includes('"/pet_preload"') &&
  /def preload_pure[\s\S]{0,600}PURE_PRE_IMG/.test(pet));
ok("已预推过的图：进入时不带图，桌面端用缓存直接弹",
  /if \(src === _purePreSrc\) \{ post\(""\)/.test(html));
ok("show_image 优先用预解码的图（省掉现场解码）",
  /PURE_PRE_IMG if PURE_PRE_IMG is not None else self\._decode_display_image\(\)/.test(pet));
ok("上传 / 切预览时就把图预推过去",
  /function renderThumbs[\s\S]{0,600}petPurePreload\(currentRefSrc\(\)\)/.test(html) &&
  /function showRefThumb\(i\)[\s\S]{0,300}petPurePreload\(src\)/.test(html));
ok("练习中换题会同步桌面端大图，休息时提前预推下一张",
  html.includes("function pureSyncImage()") &&
  /function renderPrompt[\s\S]{0,800}pureSyncImage\(\)/.test(html));
ok("大图窗口右键菜单：另存为 / 翻转 / 显示主界面 / 退出速写",
  /kind == "pure"[\s\S]{0,300}图片另存为…[\s\S]{0,400}24, FLIP_MENU_TEXT[\s\S]{0,300}显示主界面/.test(pet) &&
  /显示主界面[\s\S]{0,400}退出速写（回到主界面）/.test(pet));
ok("finish 收尾含 petPureEnd", /function finish\(\)[\s\S]{0,400}petPureEnd\(\)/.test(html));
ok("已声明 memmove 的 argtypes（64 位指针溢出会让画面全画不出来）",
  /ctypes\.memmove\.argtypes\s*=\s*\[ctypes\.c_void_p,\s*ctypes\.c_char_p,\s*ctypes\.c_size_t\]/.test(pet));
// ⚠️ 64 位句柄溢出：不声明 argtypes，句柄 >2^31 就抛 OverflowError，
//    之前 gdi32.DeleteObject 就炸在 enter_pure 内部，导致主界面永远收不起来。
for (const fn of ["DeleteObject", "GetDeviceCaps", "SelectObject", "CreateDIBSection",
                  "CreateCompatibleDC", "IsWindow", "ShowWindow", "SetWindowPos",
                  "GetWindowRect", "UpdateLayeredWindow", "DestroyWindow",
                  "CreateWindowExW", "DestroyMenu", "TrackPopupMenu", "GetDC", "ReleaseDC"]) {
  ok("已声明 " + fn + " 的 argtypes / restype（防 64 位句柄溢出）",
    new RegExp("(?:^|\\n)\\s*(?:user32|gdi32)\\." + fn + "\\.(?:argtypes|restype)\\s*=", "m").test(pet));
}
// 多显示器那几个调用同样要声明，否则句柄照样被截断
for (const fn of ["MonitorFromWindow", "MonitorFromRect", "MonitorFromPoint",
                  "GetMonitorInfoW", "EnumDisplayMonitors", "GetCursorPos"]) {
  ok("已声明 " + fn + " 的 argtypes / restype（多屏相关）",
    new RegExp("(?:^|\\n)\\s*user32\\." + fn + "\\.(?:argtypes|restype)\\s*=", "m").test(pet));
}
ok("桌面端含 enter_pure / exit_pure / pure_zoom_step",
  pet.includes("def enter_pure") && pet.includes("def exit_pure") && pet.includes("def pure_zoom_step"));
ok("桌面端缩放范围 0.5 ~ 2.0（最多 200%、最小 50%）",
  pet.includes("PURE_ZOOM_MIN = 0.5") && pet.includes("PURE_ZOOM_MAX = 2.0")
  && !/PURE_ZOOM_MAX\s*=\s*2\.5/.test(pet));
ok("步进 15%：0.5→2.0 正好 10 格",
  pet.includes("PURE_ZOOM_STEP = 0.15"));

console.log("\n【参考图缩放：放大到最大不出屏幕四边、不变形】");
ok("有等比夹取 _fit_pure_size（宽高各自截断会把图拉扁）",
  /def _fit_pure_size\(self, w, h, wa, margin\)/.test(pet));
ok("等比：只算一个比例再同时缩宽高",
  /r = min\(r, max_w \/ float\(w\)\)/.test(pet) && /r = min\(r, max_h \/ float\(h\)\)/.test(pet)
  && /w = max\(1, int\(round\(w \* r\)\)\)/.test(pet) && /h = max\(1, int\(round\(h \* r\)\)\)/.test(pet));
ok("有 _clamp_into_area 把窗口夹进四条边",
  /def _clamp_into_area\(self, cx, cy, wa, margin\)/.test(pet));
ok("比工作区还大时居中（不会顶出去）",
  /self\._w >= \(wa\.right - wa\.left - margin \* 2\)/.test(pet));
ok("缩放后按所在屏夹取，不会只用主屏工作区",
  /wa = self\._monitor_work_area\(\) if keep_center == "cur" else self\._pointer_work_area\(\)/.test(pet));

console.log("\n【多屏：参考图大窗可搬到任意一块显示器（仍置顶）】");
ok("有 MONITORINFO 结构", /class MONITORINFO\(ctypes\.Structure\)/.test(pet));
ok("按 ctypes.sizeof 设 cbSize",
  /mi\.cbSize = ctypes\.sizeof\(MONITORINFO\)/.test(pet));
ok("有 list_monitor_work_areas 枚举所有屏",
  /def list_monitor_work_areas\(\)/.test(pet) && /EnumDisplayMonitors\(None, None, MONITORENUMPROC\(_cb\), 0\)/.test(pet));
ok("枚举结果按左→右排序（搬屏顺序稳定）",
  /uniq\.sort\(key=lambda a: \(a\.left, a\.top\)\)/.test(pet));
ok("有 _monitor_work_area 取窗口所在那块屏",
  /def _monitor_work_area\(self, rect=None\)/.test(pet)
  && /MonitorFromWindow\(self\.hwnd, MONITOR_DEFAULTTONEAREST\)/.test(pet));
ok("有 _pointer_work_area（首次弹图开在鼠标那块屏）",
  /def _pointer_work_area\(self\)/.test(pet));
ok("有 pure_to_next_monitor 搬到下一块屏", /def pure_to_next_monitor\(self\)/.test(pet));
ok("只有一块屏时不搬（返回 False）",
  /if len\(areas\) < 2 or not self\.hwnd:\s*\n\s*return False/.test(pet));
ok("循环搬屏（最后一块再搬回第一块）",
  /nxt = areas\[\(idx \+ 1\) % len\(areas\)\]/.test(pet));
ok("多屏才显示「移到下一个屏幕」菜单项",
  /if len\(list_monitor_work_areas\(\)\) > 1:/.test(pet)
  && /AppendMenuW\(hmenu, MF_STRING, 23, "移到下一个屏幕"\)/.test(pet));
ok("菜单命令 23 接到 pure_to_next_monitor",
  /elif cmd == 23:/.test(pet) && /self\.pure_to_next_monitor\(\)/.test(pet));
ok("搬屏后仍保持置顶（只挪位置不改 Z 序）",
  /SWP_NOSIZE \| SWP_NOZORDER \| SWP_NOACTIVATE/.test(pet));
ok("桌面端最小化/恢复页面窗口", pet.includes("SW_MINIMIZE") && pet.includes("SW_RESTORE"));
ok("桌面端含 图片另存为 与 显示主界面 菜单",
  pet.includes("save_display_image") && pet.includes("显示主界面"));
ok("桌面端注册双击 + 滚轮消息",
  pet.includes("CS_DBLCLKS") && pet.includes("WM_LBUTTONDBLCLK") && pet.includes("WM_MOUSEWHEEL"));

console.log("\n【参考图翻转：只走右键菜单，没有快捷键】");
ok("桌面端用 PIL 左右镜像", /FLIP_LEFT_RIGHT/.test(pet) && /def _flip_source\(self\)/.test(pet));
ok("镜像结果缓存一份（缩放重采样不每次重转）",
  /self\._pure_img_flip = self\._pure_img\.transpose/.test(pet) &&
  /if self\._pure_img_flip is None:/.test(pet));
ok("缩放时按翻转状态取图", /src = self\._flip_source\(\)[\s\S]{0,80}\.resize\(\(w, h\), Image\.LANCZOS\)/.test(pet));
ok("有 toggle_flip 来回切换",
  /def toggle_flip\(self\)/.test(pet) && /self\.flip_h = not self\.flip_h/.test(pet));
ok("翻转后原地重绘（窗口中心不动、倍率不变）",
  /def toggle_flip[\s\S]{0,600}self\._apply_pure_zoom\(keep_center="cur"\)/.test(pet));
ok("菜单项「水平翻转参考图」在纯净模式右键里",
  pet.includes('FLIP_MENU_TEXT = "水平翻转参考图"') &&
  /MF_STRING \| \(MF_CHECKED if self\.flip_h else 0\),\s*\n\s*24, FLIP_MENU_TEXT/.test(pet));
ok("已在翻转时菜单打勾", /MF_CHECKED if self\.flip_h else 0/.test(pet));
ok("菜单命令 24 接到 toggle_flip",
  /elif cmd == 24:/.test(pet) && /self\.toggle_flip\(\)\s*#/.test(pet));
// ⚠️ 2026-09-29：全局热键 H 会让主人速写时打字打不出 H，整条链路删干净，只留右键菜单。
ok("没有全局热键：热键常量 / 注册调用 / WM_HOTKEY 分支全没了",
  !/WM_HOTKEY\s*=/.test(pet) && !/VK_H\s*=/.test(pet) &&
  !/HOTKEY_FLIP_ID/.test(pet) && !/MOD_NOREPEAT\s*=/.test(pet) &&
  !/user32\.RegisterHotKey/.test(pet) && !/msg == WM_HOTKEY/.test(pet));
ok("没有 _register_flip_hotkey / _unregister_flip_hotkey / _hk_registered 残留",
  !/_register_flip_hotkey|_unregister_flip_hotkey|_hk_registered/.test(pet));
ok("菜单文案里不再带（H）提示", !/（H）/.test(pet));
ok("退出纯净模式时会把翻转状态复位",
  /def exit_pure[\s\S]{0,700}self\.flip_h = False/.test(pet));

console.log("\n【桌面大图：以鼠标为中心缩放，绝不横向拉伸】");
ok("滚轮缩放以鼠标为中心（pure_zoom_step 收下鼠标坐标）",
  /def pure_zoom_step\(self, sign, mx=None, my=None\)/.test(pet) &&
  /self\.pure_zoom_step\(1 if delta > 0 else -1, mx, my\)/.test(pet));
ok("_apply_pure_zoom 支持 anchor 锚点（并把左上角换算回中心）",
  /def _apply_pure_zoom\(self, keep_center="cur", anchor=None\)/.test(pet) &&
  /if anchor and self\._w and self\._h:/.test(pet) &&
  /cx = int\(round\(mx - rx \* w \+ w \/ 2\.0\)\)/.test(pet));
ok("鼠标坐标从 WM_MOUSEWHEEL 的 lparam 取（c_short：副屏负坐标也对）",
  /mx = ctypes\.c_short\(lparam & 0xFFFF\)\.value/.test(pet) &&
  /my = ctypes\.c_short\(\(lparam >> 16\) & 0xFFFF\)\.value/.test(pet));
ok("顶到边缘只等比收住，绝不横向拉伸（_fit_pure_size 宽高同比例）",
  /r = min\(r, max_w \/ float\(w\)\)/.test(pet) &&
  /r = min\(r, max_h \/ float\(h\)\)/.test(pet) &&
  /w = max\(1, int\(round\(w \* r\)\)\)/.test(pet) &&
  /h = max\(1, int\(round\(h \* r\)\)\)/.test(pet));
ok("在小兔身上滚：鼠标不在图上 → 按大图中心缩放（不传锚点）",
  /PURE_WIN\.pure_zoom_step\(1 if delta > 0 else -1\)/.test(pet));

console.log("\n【右键小兔：「返回当前参考图模式」】");
ok("桌宠右键菜单新增「返回当前参考图模式」（命令 25）",
  pet.includes('"返回当前参考图模式"') && /25, "返回当前参考图模式"/.test(pet) &&
  /elif cmd == 25:/.test(pet) && /self\.back_to_pure\(\)/.test(pet));
ok("只在网页模式下显示（纯净模式里已经有「显示主界面」，不重复）",
  /if not self\.pure and self\.has_pure_src\(\):/.test(pet));
ok("有 back_to_pure：把刚才那张图的大窗唤回来",
  /def back_to_pure\(self\)/.test(pet) && /self\._display_src = src/.test(pet) &&
  /ok = self\.enter_pure\(\)/.test(pet));
ok("进模式时记住那张图（_last_pure_src）",
  /self\._last_pure_src = self\._display_src/.test(pet) &&
  /self\._last_pure_src = None/.test(pet));
ok("没有图时不会硬进（小兔会提示先上传）",
  /还没.*参考图|还没有参考图/.test(pet) && /返回参考图模式：手上没有可参考的图/.test(pet));
ok("已经在参考图模式里就直接返回，不重复进入",
  /if self\.pure:\s*\n\s*return True/.test(pet));
ok("桌面端含 POST /pet_pure 原子入口", pet.includes('"/pet_pure"'));
// ⚠️ HTTP 请求线程上建窗口：ThreadingHTTPServer 每请求一个线程，
//    请求结束线程退出 → 它建的窗口立刻被销毁（参考图大窗一闪就没）。
ok("pet_call 会把任务切回窗口线程执行（不能在 HTTP 线程上建窗口）",
  pet.includes("WM_PET_CALL") && pet.includes("def drain_pet_tasks") &&
  pet.includes("PET_THREAD_ID") && /GetCurrentThreadId\(\)/.test(pet));
ok("已在窗口线程时不重复投递（避免自锁）",
  /if PET_THREAD_ID and PET_THREAD_ID == kernel32\.GetCurrentThreadId\(\)/.test(pet));
ok("窗口过程处理 WM_PET_CALL", /msg == WM_PET_CALL[\s\S]{0,80}drain_pet_tasks\(\)/.test(pet));
ok("已声明 PostMessageW / GetCurrentThreadId 签名",
  /user32\.PostMessageW\.(argtypes|restype)\s*=/.test(pet) &&
  /kernel32\.GetCurrentThreadId\.(argtypes|restype)\s*=/.test(pet));

console.log("\n【纯净模式右键菜单：退出速写（结束这一组 + 回到主界面）】");
ok("大图窗口菜单新增「退出速写」", /kind == "pure"[\s\S]{0,400}退出速写/.test(pet));
ok("小兔菜单在纯净模式下也有「退出速写」",
  /if self\.pure:[\s\S]{0,200}退出速写/.test(pet));
ok("菜单项 22 → request_pure_quit", /cmd == 22:\s*\n\s*request_pure_quit\(\)/.test(pet));
ok("request_pure_quit 先关大图并唤回主界面",
  /def request_pure_quit[\s\S]{0,400}exit_pure\(True\)/.test(pet));
ok("倒计时心跳响应带回 quit 信号",
  /cmd == "timer"[\s\S]{0,700}"quit": pure_quit_active\(\)/.test(pet));
ok("网页收到 quit 就执行 finish（等同点结束）",
  /if \(j && j\.quit\) pureRemoteQuit\(\)/.test(html) &&
  /function pureRemoteQuit\(\)[\s\S]{0,200}finish\(\);/.test(html));
ok("新一组开始时清掉上一次的退出信号",
  /clear_pure_quit\(\)\s*# 新的一组/.test(pet) && html.includes("_pureQuitDone = false"));
ok("退出信号有兜底有效期（避免下次误触发）", pet.includes("PURE_QUIT_TTL"));
ok("pure_end 会复位退出信号", /cmd == "pure_end"[\s\S]{0,160}clear_pure_quit\(\)/.test(pet));

console.log("\n【退出桌宠：关掉全部 UI + 清缓存（保留用户数据）】");
ok("退出桌宠走 quit_app（不再只销毁桌宠窗口）",
  /cmd == 4:\s*\n\s*quit_app\(\)/.test(pet) && !/cmd == 4:\s*\n\s*user32\.DestroyWindow\(self\.hwnd\)/.test(pet));
ok("退出时会关闭页面窗口（先 WM_CLOSE，必要时只杀自己拉起的实例）",
  pet.includes("def close_page_window") && pet.includes("WM_CLOSE = 0x0010") &&
  /taskkill", "\/PID", str\(PAGE_PID\)/.test(pet));
ok("记录自己拉起的浏览器进程号 PAGE_PID", pet.includes("PAGE_PID = pr.pid"));
ok("退出时会收掉参考图大窗", pet.includes("def destroy_pure_window"));
ok("退出时会清缓存（浏览器缓存 / 落地网页 / 临时图）",
  pet.includes("def clear_app_cache") && pet.includes("dq_pet_*.png"));
const _cacheList = (pet.match(/CHROME_CACHE_DIRS = \{([\s\S]*?)\}/) || ["", ""])[1];
ok("! 绝不删用户数据：Local Storage / IndexedDB 不在删除名单",
  _cacheList.length > 0 && !/Local Storage/.test(_cacheList) && !/IndexedDB/.test(_cacheList));
ok("缓存删除按白名单走（不是整个删掉浏览器档案）",
  pet.includes("CHROME_CACHE_DIRS") && pet.includes("CHROME_KEEP_FILES"));
ok("清完缓存后仍保留卡片成品目录（cards 不动）",
  !/shutil\.rmtree\(\s*self\._card_dir\(\)/.test(pet));
ok("退出收尾走后台线程，关窗口不卡界面",
  /def quit_app\(\)[\s\S]{0,1200}threading\.Thread\(target=worker/.test(pet));
ok("等浏览器进程真正退出再清缓存（否则文件被占用删不掉）",
  pet.includes("def _wait_pid_exit") && /_wait_pid_exit\(PAGE_PID/.test(pet));
ok("删目录有重试（浏览器刚退出时可能短暂占用）",
  pet.includes("def _rmtree_retry") && pet.includes("_rmtree_retry(web"));
ok("退出时把本次生成的临时图片按名单删掉", pet.includes("def sweep_temp_images") &&
  /for p in list\(TMP_FILES\):/.test(pet) && pet.includes("TMP_FILES.add(p)"));
ok("退出时把预解码缓存也放掉（纯内存）",
  /def clear_app_cache\(\)[\s\S]*?PURE_PRE_IMG = None/.test(pet));

console.log("\n【exe 单实例：重复双击只提示，不再起第二只小兔】");
ok("用命名互斥体判定单实例",
  /def single_instance\(\)[\s\S]{0,200}CreateMutexW[\s\S]{0,200}ERROR_ALREADY_EXISTS/.test(pet));
ok("互斥体签名已声明（64 位下不被截断）",
  /kernel32\.CreateMutexW\.argtypes[\s\S]{0,200}CreateMutexW\.restype = HANDLE/.test(pet));
ok("第二个实例不再重复起桌宠（通知完直接 return）",
  /if not single_instance\(\):[\s\S]{0,400}notify_running_instance\(\)[\s\S]{0,300}return/.test(pet));
ok("第二个实例会把已打开的页面唤到前台", /notify_running_instance\(\)[\s\S]{0,200}open_page\(\)/.test(pet));
ok("已定义 notify_running_instance", pet.includes("def notify_running_instance"));
ok("通知主通道走本地 HTTP", pet.includes("/pet?cmd=already"));
ok("HTTP 不通时退化成广播注册消息",
  /PostMessageW\(HWND_BROADCAST, WM_ALREADY/.test(pet) &&
  /user32\.RegisterWindowMessageW\.restype = ctypes\.c_uint/.test(pet));
ok("广播消息名两个进程能对上（同一个字符串）",
  pet.includes('WM_ALREADY_MSG = "DQXiaotuPet_AlreadyRunning"'));
ok("窗口过程收得到这条注册消息",
  /if WM_ALREADY and msg == WM_ALREADY:[\s\S]{0,120}self\.notify_running\(\)/.test(pet));
ok("/pet 命令表里有 already（走 pet_call 排队到窗口线程）",
  /elif cmd == "already":[\s\S]{0,200}pet_call\("notify_running"\)/.test(pet));
ok("提示文案就是「小兔已经在运行了哦」",
  pet.includes('ALREADY_TEXT = "小兔已经在运行了哦"') &&
  /ALREADY_TEXT\)/.test(pet));
ok("小兔会跳一下（起跳—落回的半个正弦周期）",
  /self\.hop_until = self\.hop_t0 \+ self\.hop_dur/.test(pet) &&
  /hop_amp \* math\.sin\(math\.pi/.test(pet));
ok("跳动幅度明显大于呼吸（看得出在跳）", pet.includes("self.hop_amp = 26.0 * self.scale"));
ok("跳完自动复位（不会卡在半空）",
  /if now >= self\.hop_until:[\s\S]{0,90}self\.hop_amp = 0\.0/.test(pet));
ok("被「关闭桌宠」收起时会先放回来再提示",
  /def notify_running[\s\S]{0,280}if not self\.visible:[\s\S]{0,80}self\.show_pet\(\)/.test(pet));
ok("拖动中不跳动（免得和拖拽抢位置）",
  /if self\.hop_until and not self\.dragging:/.test(pet));
ok("启动时先扫一遍上次留下的临时图片",
  /n = sweep_temp_images\(\)[\s\S]{0,220}启动时清掉残留临时图片/.test(pet));

console.log("\n【系统托盘小图标：右键可 打开/设置/关闭/退出】");
ok("桌面端用 Shell_NotifyIconW 加托盘图标",
  pet.includes("Shell_NotifyIconW") && pet.includes("NIM_ADD") && pet.includes("NIM_DELETE"));
ok("已声明 Shell_NotifyIconW / LoadImageW 签名",
  /shell32\.Shell_NotifyIconW\.(argtypes|restype)\s*=/.test(pet) &&
  /user32\.LoadImageW\.(argtypes|restype)\s*=/.test(pet));
ok("有 NOTIFYICONDATAW 结构且按 ctypes.sizeof 设 cbSize",
  pet.includes("class NOTIFYICONDATAW") && /data\.cbSize = ctypes\.sizeof\(NOTIFYICONDATAW\)/.test(pet));
ok("托盘消息 WM_TRAY 在窗口过程里处理（左键开页面 / 右键弹菜单）",
  pet.includes("WM_TRAY") && /msg == WM_TRAY[\s\S]{0,260}open_page\(\)[\s\S]{0,200}_tray_menu\(\)/.test(pet));
ok("托盘菜单：打开速写页面 / 设置桌宠 / 关闭桌宠 / 退出桌宠",
  /def _tray_menu[\s\S]{0,400}打开速写页面[\s\S]{0,1500}设置桌宠[\s\S]{0,900}关闭桌宠[\s\S]{0,400}退出桌宠/.test(pet));
ok("设置桌宠含 小兔大小 / 窗口置顶 / 呼吸动画 / 陪画模式",
  ["小兔大小", "窗口置顶", "呼吸动画", "陪画模式"].every(t =>
    new RegExp("def _tray_menu[\\s\\S]{0,1200}" + t).test(pet)));
ok("关闭桌宠 = 收起小兔但程序还在（托盘可再放回）",
  pet.includes("def hide_pet") && pet.includes("def show_pet") &&
  /cmd == 30:\s*\n\s*self\.hide_pet\(\)/.test(pet) && /cmd == 31:\s*\n\s*self\.show_pet\(\)/.test(pet));
ok("小兔收起时菜单改成「显示小兔」",
  /if self\.visible:[\s\S]{0,120}关闭桌宠[\s\S]{0,120}显示小兔/.test(pet));
ok("退出时收掉托盘图标（不留残影）",
  /msg == WM_DESTROY[\s\S]{0,200}self\.remove_tray_icon\(\)/.test(pet));
ok("启动时挂上托盘图标", /pet\.add_tray_icon\(\)/.test(pet));
ok("桌宠本体仍不占任务栏按钮（保留 WS_EX_TOOLWINDOW）",
  /ex_style = WS_EX_LAYERED \| WS_EX_TOOLWINDOW \| WS_EX_NOACTIVATE/.test(pet));
ok("菜单派发抽成 menu_cmd / run_menu（桌宠右键与托盘共用）",
  pet.includes("def menu_cmd") && pet.includes("def run_menu") &&
  /def show_menu\(self\):\s*\n\s*self\.run_menu\(self\._menu\(\)\)/.test(pet));

console.log("\n【网页里缩放参考图：以鼠标为中心 / 不撑坏 UI / 全屏 500%】");
ok("网页端绑上了滚轮缩放（练习页 + 开始前的大图 + 全屏层）",
  /bindWebZoom\("prompt-box"\)/.test(html) && /bindWebZoom\("welcome-img"\)/.test(html) &&
  /bindWebZoom\("img-fs"\)/.test(html));
ok("滚轮监听用 passive:false（否则 preventDefault 无效、页面跟着一起滚）",
  /addEventListener\("wheel"[\s\S]{0,300}\{\s*passive:\s*false\s*\}/.test(html));
ok("缩放时阻止页面滚动",
  /addEventListener\("wheel"[\s\S]{0,200}e\.preventDefault\(\)/.test(html));
ok("普通画面 50%~200%，全屏看图最大 500%",
  /WEB_ZOOM_MIN = 0\.5, WEB_ZOOM_MAX = 2\.0/.test(html) &&
  /FS_ZOOM_MIN = 0\.5, FS_ZOOM_MAX = 5\.0/.test(html));
// 🔴 缩放走 transform：只改视觉不动布局 —— 框永远那么大，图超出就被裁，
//    不会把下面的计时环/按钮挤下去（以前改图片宽度会把框撑大 → 遮挡 UI）
ok("缩放走 transform（不再改图片宽度撑大框）",
  /transform = "translate\("/.test(html) && /scale\("/.test(html) &&
  !/el\.style\.width = Math\.round/.test(html));
ok("transform-origin 固定在左上角（位移换算最简单）",
  /el\.style\.transformOrigin = "0 0"/.test(html));
ok("框保持原尺寸、超出部分裁掉（不遮挡本页 UI）",
  /\.prompt-box \{[\s\S]{0,400}position: relative; overflow: hidden/.test(html));
ok("以鼠标为中心放大（滚轮事件把鼠标坐标传进去）",
  /zAt\(el, zState\(el\)\.z \+ \(e\.deltaY < 0 \? WEB_ZOOM_STEP : -WEB_ZOOM_STEP\), e\.clientX, e\.clientY\)/.test(html));
ok("放大超出后可以按住拖动看（不会把图拖离框）",
  /addEventListener\("mousedown"/.test(html) && /zClamp\(m, m\.z,/.test(html));
ok("双击图复位到 100%",
  /addEventListener\("dblclick"[\s\S]{0,240}webZoomReset\(el\)/.test(html));
ok("换图时缩放复位到 100%", /webZoomReset\(\$\("welcome-img-el"\)\)/.test(html));
ok("有全屏看图按钮 + 全屏层（Esc / ✕ / 点空白处退出）",
  /id="fs-btn"/.test(html) && /id="img-fs"/.test(html) &&
  /id="img-fs-close"/.test(html) && /e\.key === "Escape"/.test(html));
// 按钮要一直看得见：主色实心圆 + 白图标，尺寸 45px（原 30px 的 150%）
ok("全屏按钮默认就清楚显示（没有 opacity:0 / 悬停才出现）",
  /#fs-btn \{[\s\S]{0,420}?\}/.test(html) &&
  !/#fs-btn \{[\s\S]{0,420}?opacity: 0/.test(html) &&
  !/\.prompt-box:hover #fs-btn/.test(html));
ok("全屏按钮用主色填充 + 白图标",
  /#fs-btn \{[\s\S]{0,420}?background: var\(--pink\); color: #fff/.test(html));
ok("全屏按钮比原来放大 150%（45px，字号 22px）",
  /#fs-btn \{[\s\S]{0,420}?width: 45px; height: 45px/.test(html) &&
  /#fs-btn \{[\s\S]{0,420}?font-size: 22px/.test(html));
ok("全屏按钮挂到有图的那个框上（换图重画后会重新挂）",
  /function mountFsBtn/.test(html) && /mountFsBtn\(\$\("prompt-box"\)\)/.test(html) &&
  /mountFsBtn\(\$\("welcome-img"\)\)/.test(html));
(function () {
  const box = $("#prompt-box");
  box.innerHTML = '<img src="x.png" alt="参考图">';
  const img = box.querySelector("img");
  Object.defineProperty(img, "naturalWidth", { value: 1000, configurable: true });
  Object.defineProperty(img, "naturalHeight", { value: 500, configurable: true });
  const wheel = (dy, x, y) => {
    let ev;
    try {
      ev = new w.WheelEvent("wheel", { deltaY: dy, clientX: x || 0, clientY: y || 0,
                                       bubbles: true, cancelable: true });
    } catch (e) {
      ev = new w.Event("wheel", { bubbles: true, cancelable: true });
      Object.defineProperty(ev, "deltaY", { value: dy });
    }
    box.dispatchEvent(ev);
  };
  wheel(-100, 100, 100);
  ok("往上滚 → 115%（transform 里带着 scale(1.15)）",
    img.dataset.zoom === "1.15" && /scale\(1\.15\)/.test(img.style.transform),
    img.dataset.zoom + " / " + img.style.transform);
  wheel(100, 100, 100);
  ok("往下滚 → 缩回 100%（transform 清空）",
    img.dataset.zoom === "1" && img.style.transform === "",
    img.dataset.zoom + " / " + img.style.transform);
  for (let i = 0; i < 12; i++) wheel(-100, 100, 100);
  ok("普通画面最多 200%", img.dataset.zoom === "2", img.dataset.zoom);
  for (let i = 0; i < 24; i++) wheel(100, 100, 100);
  ok("最小 50%", img.dataset.zoom === "0.5", img.dataset.zoom);
  box.dispatchEvent(new w.MouseEvent("dblclick", { bubbles: true, cancelable: true }));
  ok("双击图回到 100%", img.dataset.zoom === "1" && img.style.transform === "", img.dataset.zoom);

  // 全屏看图：点右上角 ⛶ → 打开 → 滚轮最多到 500%
  mountFsBtnTest(box);
})();
function mountFsBtnTest(box) {
  // 上面刚重画过 innerHTML，按钮会一起被冲掉 —— 正式代码里 renderPrompt 会重新挂
  w.mountFsBtn(box);
  const btn = $("#fs-btn");
  ok("换图重画后全屏按钮会重新挂回图上", btn && btn.parentElement === box,
    btn ? String(btn.parentElement.id) : "null");
  btn.dispatchEvent(new w.MouseEvent("click", { bubbles: true, cancelable: true }));
  const fs = $("#img-fs");
  ok("点 ⛶ 打开全屏看图", fs.hidden === false, String(fs.hidden));
  const fsImg = $("#img-fs-el");
  Object.defineProperty(fsImg, "naturalWidth", { value: 1000, configurable: true });
  Object.defineProperty(fsImg, "naturalHeight", { value: 500, configurable: true });
  const fsw = dy => {
    let ev;
    try {
      ev = new w.WheelEvent("wheel", { deltaY: dy, clientX: 200, clientY: 200,
                                       bubbles: true, cancelable: true });
    } catch (e) {
      ev = new w.Event("wheel", { bubbles: true, cancelable: true });
      Object.defineProperty(ev, "deltaY", { value: dy });
    }
    fs.dispatchEvent(ev);
  };
  for (let i = 0; i < 40; i++) fsw(-100);
  ok("全屏里最多放大到 500%", fsImg.dataset.zoom === "5", fsImg.dataset.zoom);
  for (let i = 0; i < 60; i++) fsw(100);
  ok("全屏里最小 50%", fsImg.dataset.zoom === "0.5", fsImg.dataset.zoom);
  $("#img-fs-close").dispatchEvent(new w.MouseEvent("click", { bubbles: true, cancelable: true }));
  ok("点 ✕ 退出全屏", fs.hidden === true, String(fs.hidden));
}

console.log("\n【版本号：一处改动，网页 + exe 一起跟上】");
ok("桌面端不再写死版本号，改成读 index.html 的 APP_VER",
  /def app_version\(\)/.test(pet) && /APP_VER\\s\*=\\s\*"/.test(pet) &&
  !/"V1\.0\.0 · 一起练速写吧"/.test(pet) && !/"V1\.0\.0 ·/.test(pet));
ok("读不到时还有兜底版本（不会变成空白）",
  new RegExp('APP_VER_FALLBACK = "' + VER + '"').test(pet));
ok("分享卡片上的版本号是拼出来的（跟着 APP_VER 走）",
  /"%s · 一起练速写吧" % app_version\(\)/.test(pet));
ok("启动日志会打印版本号（方便核对 exe 是哪一版）",
  /log\("%s %s 启动" % \(APP_NAME, app_version\(\)\)\)/.test(pet));
// ⚠️ 指纹只看「文件数 + 总大小」是不够的：V1.1→V1.2 字节数一样，exe 就不会同步新网页
ok("网页同步指纹带内容 md5（同尺寸的改动也能被发现）",
  /def _fingerprint\(root\)/.test(pet) && /hashlib\.md5\(\)/.test(pet) &&
  /return "%d_%d_%s" % \(n, size, h\.hexdigest\(\)\)/.test(pet));

console.log("\n【更新记录 CHANGELOG.md】");
const clPath = path.join(ROOT, "CHANGELOG.md");
ok("存在 CHANGELOG.md 更新记录文件", fs.existsSync(clPath));
const cl = fs.existsSync(clPath) ? fs.readFileSync(clPath, "utf8") : "";
ok("更新记录含当前版本 " + VER + " 条目", cl.includes("## [" + VER + "]"));
ok("当前版本条目含日期", /## \[V0\.2\][^\n]*—\s*\d{4}-\d{2}-\d{2}/.test(cl));
ok("更新记录分 新增功能 / 体验优化 / 问题修复",
  cl.includes("新增功能") && cl.includes("体验优化") && cl.includes("问题修复"));
ok("更新记录含上一个版本 V0.2", cl.includes("## [V0.2]"));
ok("更新记录含更早的 V0.1", cl.includes("## [V0.1]"));
ok("版本倒序：当前版本排在最前",
  cl.indexOf("## [" + VER + "]") < cl.indexOf("## [V0.2]") &&
  cl.indexOf("## [V0.2]") < cl.indexOf("## [V0.1]"));
ok("打包脚本会在完成后打开更新记录",
  fs.readFileSync(path.join(ROOT, "tools", "build-exe.py"), "utf8").includes("CHANGELOG.md"));

console.log("\n结果：" + pass + " 通过 / " + fail + " 失败");
process.exit(fail ? 1 : 0);

