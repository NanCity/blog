# NanCy · 慢慢记录

一个使用 HTML、CSS 和 JavaScript 编写的中文个人博客。

## 页面与功能

- 首页、文章列表、文章详情、归档及关于我
- 分类筛选、全文搜索与深浅主题切换
- 浏览器本地文章收藏
- 响应式布局，无构建依赖

当前包含 6 篇已标注的示例文章，正式使用前可替换为自己的内容。

## GitHub Pages

博客访问地址：<https://nancity.github.io/blog/>（首次部署成功后生效）。

静态文件已位于仓库根目录。在仓库 Settings → Pages 中选择 Deploy from a branch，选择 main 分支与 / (root) 目录。

不需要运行构建命令，.nojekyll 用于直接发布静态文件。资源路径使用相对路径，文章导航使用 URL hash，可在项目子目录中访问。

## 修改内容

- app.js：文章、分类、简介与页面内容
- style.css：配色、字体和布局
- index.html：页面标题、描述和导航
- assets/：插画

收藏与主题偏好保存在当前访客的浏览器中；本站没有在线文章编辑后台。
