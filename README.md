# AI Image 2 Portable

> 面向 Windows 的可双击启动 AI 图像工作台
> 支持 **BYOK（Bring Your Own Key）**、**OpenAI-compatible** 上游、**文生图 / 图生图 / 遮罩局部编辑**

**先说边界：**

- **这不是官方 OpenAI 应用**
- **这不是离线模型包，也不自带本地大模型**
- **这不是免 Key 工具**：你需要自己提供 `API URL Base` 和 `API Key`

如果你想要的是：

- 给 Windows 用户一个**双击就能打开**的图像生成网页
- 使用你自己的 OpenAI 或兼容网关
- 做文生图、参考图编辑、遮罩局部重绘
- 不要求目标电脑安装 VS Code / Codex CLI

那么这个目录就是为这个场景准备的。

---

## 为什么它适合开源分发

- **Windows 双击启动**：直接运行 `Start_AI_Image2.bat`
- **本地网页 UI**：默认打开 `http://127.0.0.1:8012/`
- **BYOK**：用户自行填写 `API URL Base` 和 `API Key`
- **OpenAI-compatible**：面向兼容 `/v1/images/*` 与部分 `/v1/responses` 图像能力的服务
- **图像编辑链路**：支持参考图、多图输入、遮罩局部编辑
- **便携优先**：若目录内带 `runtime\AI_Image2_Server.exe`，目标机可免装 Python

---

## 当前已实现能力

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| 文生图 | ✅ | 输入提示词后生成图片 |
| 图生图 | ✅ | 上传 1-16 张参考图进行编辑/重绘 |
| 遮罩编辑 | ✅ | 上传原图后，再上传同尺寸遮罩图进行局部修改 |
| OpenAI-compatible / BYOK | ✅ | 页面内保存 `API URL Base` 与 `API Key` |
| Windows 双击启动 | ✅ | `Start_AI_Image2.bat` / `Stop_AI_Image2.bat` |
| 输出参数 | ✅ | 尺寸、质量、背景、格式、压缩率 |

> 说明：**兼容**不等于**所有兼容服务都完整支持全部能力**。
> 图生图、遮罩、多图参考是否可用，取决于你的上游是否实现对应图像接口。

---

## Quick Start（Windows）

### 方式 A：普通用户

1. 获取本目录
   - **如果仓库已经发布 Release**：优先从 Release 下载并解压
   - **如果还没有 Release**：直接下载源码压缩包或拷贝整个目录
2. 双击运行：

   ```bat
   Start_AI_Image2.bat
   ```

3. 浏览器会自动打开：

   ```text
   http://127.0.0.1:8012/
   ```

4. 首次使用时，在页面里填写：
   - `API URL Base`
   - `API Key`
5. 点击 `Save`
6. 开始文生图 / 图生图 / 遮罩编辑

停止服务：

```bat
Stop_AI_Image2.bat
```

### 启动行为说明

- 如果存在 `runtime\AI_Image2_Server.exe`：
  - 直接使用内置运行时启动
  - **目标机通常不需要预装 Python**
- 如果不存在 `runtime\AI_Image2_Server.exe`：
  - 启动器会回退到本机 Python
  - 首次会自动创建 `.venv`
  - 自动安装 `requirements.txt` 依赖
  - 此时要求本机已安装 **Python 3.10+**

---

## Release 下载

如果你是给非开发者分发，建议优先使用 Release 包。

### 建议用户关注这几点

- 解压后直接在目录内双击 `Start_AI_Image2.bat`
- 如果包里带有 `runtime\AI_Image2_Server.exe`，更适合“拿来即用”
- 如果没有 `runtime`，首次启动会依赖本机 Python 3.10+
- 不要把自己的 `local_config.json` 一起打包给别人

> 当前 README 只描述**仓库里已存在的启动方式**，不假设额外打包脚本已经存在。

---

## OpenAI-compatible / BYOK 是什么意思

### BYOK

你自己提供：

- API 服务地址（`API URL Base`）
- API Key

本项目**不提供**：

- 官方账号
- 充值额度
- 上游图像服务
- 代理配额

### OpenAI-compatible

这个项目的目标不是绑定单一平台，而是对接**兼容 OpenAI 图像接口风格**的上游服务。

当前实现会优先走这类能力：

- `/v1/images/generations`
- `/v1/images/edits`
- `/v1/responses` 中的图像生成能力（部分回退路径）

因此：

- **能不能用**，取决于你的上游是否兼容
- **文生图能用**，不代表**图生图 / 遮罩也一定能用**
- **不同网关对多图输入、mask、质量参数的支持度可能不同**

---

## 安全边界

这是一个**本地启动、远程出图**的工具，不是离线推理器。

### 你需要知道的事实

- 默认监听：

  ```text
  127.0.0.1:8012
  ```

- 如果你手动把 `AI_IMAGE_HOST` 改成 `0.0.0.0`，就可能暴露给局域网
- 页面保存的 Key 会写入：

  ```text
  local_config.json
  ```

- 图生图 / 遮罩任务会在本地 `cache/` 下缓存：
  - `prompt.txt`
  - 参考图
  - mask 图
- 运行日志会写到：
  - `ai-image2.log`
  - `ai-image2.err.log`

### 安全建议

- **不要提交、分享、同步** `local_config.json`
- 如果处理敏感图片，记得定期清理 `cache/`
- 若用于个人电脑之外的环境，优先保持默认 `127.0.0.1`
- 这是第三方项目封装的本地 UI，**不是官方 OpenAI 客户端**

---

## 开发运行

适合需要改界面、调接口、看日志的开发者。

### 环境要求

- Windows
- Python 3.10+

### 本地运行

```powershell
cd AI-image2-portable
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

打开：

```text
http://127.0.0.1:8012/
```

### 可选环境变量

- `OPENAI_API_KEY`
- `SUB2API_KEY`
- `OPENAI_BASE_URL`
- `AI_IMAGE_HOST`
- `AI_IMAGE_PORT`
- `AI_IMAGE_ENABLE_EXTERNAL_CONFIG`：设为 `1` 后，才允许从环境变量或本机 `.codex` 配置导入 API 信息

### 本地配置来源

当前默认只读取页面保存下来的 `local_config.json`。如果你希望导入环境变量或本机 `.codex` 配置，请显式设置 `AI_IMAGE_ENABLE_EXTERNAL_CONFIG=1` 后再启动。这样做是为了避免开源分发时默认探测用户本机凭据。

如果只是给终端用户使用，最简单的方法仍然是：**直接在网页里填写并保存**。

---

## 适合谁 / 不适合谁

### 适合

- 想把图像能力快速交给 Windows 用户使用的人
- 已经有自己的 OpenAI 或兼容网关的人
- 需要参考图、mask、本地网页入口的人

### 不适合

- 期待“完全离线出图”的人
- 需要官方账号体系 / 官方托管体验的人
- 想要内置模型、内置算力、内置额度的人

---

## 与常见替代方案的定位差异

| 方案类型 | 定位 | 与本项目的核心差异 |
| --- | --- | --- |
| 本项目 | 本地目录 + Windows 双击启动 + BYOK 图像工作台 | 强调便携分发、本地网页入口、兼容上游 |
| 官方托管页面/官方应用 | 官方账号与官方托管体验 | 本项目不是官方应用，核心是“你自己接上游” |
| 本地离线模型 WebUI | 本机显卡/模型推理 | 本项目不附带模型，不做离线推理 |
| 通用 API 调试页 | 面向接口调试 | 本项目更偏终端用户可操作的图像工作台 |

一句话总结：

> **它不是在替代官方应用，也不是在替代本地模型 WebUI；它解决的是“Windows 上快速分发一个可用的 BYOK 图像前端”这个问题。**

---

## License

本项目源码采用 MIT License 发布。第三方运行时和依赖组件仍分别适用其各自许可证，详见 `THIRD_PARTY_NOTICES.md`。

---

## Roadmap

> 以下是方向，不代表当前版本已经实现。

- [ ] 更清晰的上游兼容性提示与错误诊断
- [ ] 更方便的缓存清理与使用后痕迹管理
- [ ] 更完整的 Release 分发说明与打包约定
- [ ] 更完善的文档、截图与常见问题

欢迎按这个方向继续补全，但请以**当前仓库实际存在的能力**为准，不要在 README 里提前承诺尚未落地的功能。
