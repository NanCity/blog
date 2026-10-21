# NanCy · 慢慢记录

博客：<https://nancity.github.io/blog/>

文章使用 Markdown 编写，推送到 `main` 后由 GitHub Actions 自动生成并发布。原来的 6 篇测试文章已移除。

## 发布一篇文章

1. 将 `templates/post.md` 复制到 `posts/`，例如 `posts/2026-10-21-my-first-post.md`。
2. 修改文件顶部的信息，在第二条 `---` 下面写 Markdown 正文。
3. 将 `draft: true` 改为 `draft: false`，提交并推送。

````markdown
---
title: "我的第一篇文章"
date: "2026-10-21"
category: "技术手记"
tags: ["Qt", "C++"]
cover: "desk"
excerpt: "记录今天解决的一个问题。"
draft: false
---

这里是正文，可以直接用 Markdown 写作。

## 遇到的问题

支持 **加粗**、列表、表格、图片和代码块。

```cpp
int main()
{
    return 0;
}
```
````

首次使用：

```powershell
git clone https://github.com/nancity/blog.git
cd blog
Copy-Item templates/post.md posts/2026-10-21-my-first-post.md
# 用编辑器修改文章，再提交：
git add posts/2026-10-21-my-first-post.md
git commit -m "发布第一篇文章"
git push origin main
```

后续在博客仓库中 `git pull --ff-only`，新增或修改 `posts/*.md` 后提交推送即可。**不需要手动编辑 `app.js` 或维护文章列表，也不需要在本地安装 Python。**

也可以直接在 GitHub 打开 `posts/`，选择 **Add file → Create new file**，创建一个 `.md` 文件并粘贴文章；提交到 `main` 后同样会自动发布。

## 写作约定

- 文件使用 UTF-8 编码，放在 `posts/` 第一层；文件名只用小写英文字母、数字和连字符，发布后尽量不要改名，以免改变文章链接。
- `title`、`date` 必填，日期格式为 `YYYY-MM-DD`。文章按日期倒序排列。
- `category` 可自定义，默认“技术手记”；分类列表会自动更新。
- `tags` 使用数组，例如 `["Qt", "视频"]`。
- `cover` 可选 `desk`、`hills`、`leaves`、`coffee`，默认 `desk`。
- `excerpt` 是列表中的摘要，省略时使用标题。阅读时长自动估算。
- `draft: true` 不发布正文，也不会出现在搜索和归档中；但提交到公开仓库的 Markdown 源文件仍然公开。
- 日期用于排序，未来日期不会自动定时发布；需要暂存时请用 `draft: true`。
- 图片放进 `assets/`，正文写 `![图片说明](assets/my-photo.jpg)`，并一起提交图片文件。
- 支持 Markdown 表格、代码块和原始 HTML；仅允许信任的仓库作者提交文章。

## 修改、撤下文章

修改对应的 `.md` 文件再推送即可更新。删除对应 `.md` 文件再提交推送即可删除文章；也可改为 `draft: true` 撤下。Git 历史保留旧版本，可以恢复。

## 自动发布与排错

GitHub **Settings → Pages → Source** 设为 **GitHub Actions**。工作流为 `.github/workflows/pages.yml`，每次推送 `main` 后，在仓库 **Actions → Publish Markdown blog** 查看进度。发布通常需要几分钟。

字段格式错误会让构建失败，日志会指出文件名和原因；失败时保留上一次成功发布的页面。修正文件并重新推送即可。

根目录的 `posts.json` 是空站点预览数据；线上数据由构建脚本生成，无须手动修改。不要将 `_site/` 提交到仓库。模板在 `templates/`，不会当作文章发布。

可选的本地预览（Python 3.12 或更高）：

```powershell
python -m pip install -r requirements.txt
python scripts/build_posts.py
python -m http.server 8000 --directory _site
```

然后打开 <http://localhost:8000>。请通过 HTTP 访问，直接双击 HTML 无法加载文章数据。
