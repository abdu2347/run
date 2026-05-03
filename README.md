# 部署说明

## 简介

这是一个纯前端的跑步数据生成器，无需安装任何后端服务或插件。只需要一个Web服务器或静态托管服务即可在域名上运行。

## 部署方式（任选其一）

### 方式1：静态托管服务（推荐，最简单）

#### Vercel（免费）
1. 注册 [vercel.com](https://vercel.com)
2. 安装 Vercel CLI：`npm i -g vercel`
3. 在 `run` 文件夹执行：`vercel`
4. 按提示操作，自动获得免费域名
5. 也可以连接 GitHub 仓库实现自动部署

#### Netlify（免费）
1. 注册 [netlify.com](https://netlify.com)
2. 直接拖拽 `run` 文件夹到网页上
3. 自动生成免费域名

#### GitHub Pages（免费）
1. 将 `run` 文件夹内容推送到 GitHub 仓库
2. 进入仓库 Settings → Pages
3. 选择 branch 和文件夹
4. 访问 `你的用户名.github.io/仓库名`

### 方式2：宝塔面板

1. 安装宝塔面板
2. 添加网站，绑定你的域名
3. 上传 `run` 文件夹中的所有文件到网站根目录
4. 确保 `index.html` 在网站根目录下

### 方式3：nginx 直接部署

1. 将文件上传到服务器
2. 编辑 nginx 配置：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    root /var/www/run;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

3. 重载 nginx：`nginx -s reload`

## 重要：添加微信二维码

请将你的微信二维码图片命名为 `wx.jpg`，放置在与 `index.html` 同一目录下。

文件结构应该是：
```
run/
├── index.html
├── wx.jpg     <-- 你的微信二维码
└── README.md
```

## 功能说明

- 输入跑步时间，点击"生成TCX文件"即可下载
- 支持添加多个时间批量生成
- 生成的 TCX 文件可直接导入跑步APP（如悦跑圈、咕咚等）
- 底部包含代取快递服务联系信息

## 注意事项

1. 微信二维码建议尺寸：200x200 像素以上
2. 图片格式支持：jpg、png
3. 确保 `wx.jpg` 文件名完全正确

## 技术支持

如有问题，请联系微信号：19816278865
