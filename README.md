# AI Image 2 Portable

简单易用的 Windows 图片生成工具。  
**双击启动，在网页里填写自己的 API 地址和 Key，就可以开始生成图片。**

---

## 核心特点

### 1）启动简单
- 直接双击：`Start_AI_Image2.bat`
- 浏览器会自动打开：`http://127.0.0.1:8012/`
- 如果目录里带 `runtime\AI_Image2_Server.exe`，**通常不用安装 Python**

### 2）接口可自定义
- 页面里直接填写：
  - `API URL Base`
  - `API Key`
- 可用于：
  - OpenAI 官方接口
  - OpenAI-compatible 第三方接口 / 网关

---

## 它能做什么

- 文生图
- 图生图（支持上传参考图）
- 遮罩局部编辑
- 保存你的接口地址和 Key
- 下载生成结果

---

## 最简单的使用方法

### 第一步：下载并解压
优先去 GitHub 的 **Releases** 页面下载 zip 包，解压到本地文件夹。

如果你拿到的是别人发给你的整个目录，也可以直接用。

### 第二步：双击启动
双击：

```bat
Start_AI_Image2.bat
```

启动后浏览器会自动打开：

```text
http://127.0.0.1:8012/
```

如果没有自动打开，就手动把这个地址复制到浏览器里。

### 第三步：填接口信息
在页面顶部找到 **API Settings**，填写：

- `API URL Base`
- `API Key`

然后点击：

```text
Save
```

### 第四步：开始生成图片
你可以直接：

- 输入提示词做文生图
- 上传参考图做图生图
- 上传遮罩图做局部修改

---

## 不想用了，怎么关闭
双击：

```bat
Stop_AI_Image2.bat
```

---

## 常见情况

### 页面打不开怎么办？
按这个顺序试：

1. 先双击 `Stop_AI_Image2.bat`
2. 再双击 `Start_AI_Image2.bat`
3. 手动打开 `http://127.0.0.1:8012/`

### 提示缺少 Python 怎么办？
说明你的目录里可能没有内置 `runtime`。

这时需要本机安装：

```text
Python 3.10+
```

然后重新双击启动。

### 为什么我填了 Key 还是不能生成？
常见原因：

- `API URL Base` 填错了
- `API Key` 填错了
- 你的上游接口不支持对应图像能力
- 你的上游只支持文生图，不支持图生图 / mask

---

## 使用前请先知道

请先明确这几点：

- **这不是官方 OpenAI 应用**
- **这不是离线模型软件**
- **这不是免 Key 工具**
- **这不附带额度，不送接口，不送账号**

这个项目只是一个：

> **本地启动的网页工具，用来调用你自己的图像接口。**

---

## 安全提醒

请注意：

- 你保存的接口地址和 Key 会写入：`local_config.json`
- 你上传的参考图、mask、prompt 可能会缓存到：`cache/`
- 运行日志会写到：
  - `ai-image2.log`
  - `ai-image2.err.log`

所以：

- 不要把 `local_config.json` 发给别人
- 如果处理的是敏感图片，记得清理 `cache/`
- 默认只在本机打开，地址是：`127.0.0.1:8012`

---

## 开发者和进阶用户

### 可选环境变量

- `OPENAI_API_KEY`
- `SUB2API_KEY`
- `OPENAI_BASE_URL`
- `AI_IMAGE_HOST`
- `AI_IMAGE_PORT`
- `AI_IMAGE_ENABLE_EXTERNAL_CONFIG`

其中：

- 默认情况下，程序只读取页面保存的 `local_config.json`
- 如果你想让它额外读取环境变量或本机 `.codex` 配置，启动前设置：

```text
AI_IMAGE_ENABLE_EXTERNAL_CONFIG=1
```

### 本地开发运行

如果你是开发者，可以这样启动：

```powershell
cd AI-image2-portable
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

然后打开：

```text
http://127.0.0.1:8012/
```

---

## 文件说明

- `Start_AI_Image2.bat`：启动程序
- `Stop_AI_Image2.bat`：停止程序
- `runtime\AI_Image2_Server.exe`：便携运行时（有它时一般不用装 Python）
- `local_config.json`：你保存的接口地址和 Key
- `cache/`：参考图、mask、prompt 等缓存

---

## License

本项目源码采用 **MIT License** 发布。  
第三方运行时和依赖组件仍分别适用其各自许可证，详见：

```text
THIRD_PARTY_NOTICES.md
```
