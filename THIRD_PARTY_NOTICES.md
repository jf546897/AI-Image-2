# THIRD PARTY NOTICES

本文件基于 **2026-04-26** 对 `runtime/` 目录的静态检查整理，用于说明便携发布包中可直接确认的第三方组件及许可证位置。
这是一份**最小 notices**，不是完整 SBOM；当打包产物中同时附带更具体的上游许可证文本时，以随包文本为准。

## 便携包包含的第三方运行时

- `runtime/AI_Image2_Server.exe`
- `runtime/_internal/*`

其中可以直接看到：

- Python 3.12 运行时文件（依据 `python312.dll`、`python3.dll`、`base_library.zip` 推断）
- 若干保留了 `*.dist-info/METADATA` 与 `licenses/` 目录的 Python 依赖

## 已确认组件

| 组件 | 版本 | 许可证 | 包内证据 |
| --- | --- | --- | --- |
| Python Runtime | 3.12.x（由文件名推断） | PSF License | `runtime/_internal/python312.dll`, `runtime/_internal/python3.dll`, `runtime/_internal/base_library.zip` |
| click | 8.3.1 | BSD-3-Clause | `runtime/_internal/click-8.3.1.dist-info/` |
| cryptography | 46.0.7 | Apache-2.0 OR BSD-3-Clause | `runtime/_internal/cryptography-46.0.7.dist-info/` |
| importlib_metadata | 8.7.1 | Apache-2.0 | `runtime/_internal/setuptools/_vendor/importlib_metadata-8.7.1.dist-info/` |
| MarkupSafe | 3.0.3 | BSD-3-Clause | `runtime/_internal/markupsafe-3.0.3.dist-info/` |
| numpy | 2.4.4 | 复合许可证（含 BSD-3-Clause / 0BSD / MIT / Zlib / CC0-1.0） | `runtime/_internal/numpy-2.4.4.dist-info/` |
| pydantic | 2.12.5 | MIT | `runtime/_internal/pydantic-2.12.5.dist-info/` |
| websockets | 16.0 | BSD-3-Clause | `runtime/_internal/websockets-16.0.dist-info/` |

## 随包许可证文本位置

- `runtime/_internal/click-8.3.1.dist-info/licenses/LICENSE.txt`
- `runtime/_internal/cryptography-46.0.7.dist-info/licenses/LICENSE`
- `runtime/_internal/cryptography-46.0.7.dist-info/licenses/LICENSE.APACHE`
- `runtime/_internal/cryptography-46.0.7.dist-info/licenses/LICENSE.BSD`
- `runtime/_internal/markupsafe-3.0.3.dist-info/licenses/LICENSE.txt`
- `runtime/_internal/numpy-2.4.4.dist-info/licenses/LICENSE.txt`
- `runtime/_internal/pydantic-2.12.5.dist-info/licenses/LICENSE`
- `runtime/_internal/setuptools/_vendor/importlib_metadata-8.7.1.dist-info/licenses/LICENSE`
- `runtime/_internal/websockets-16.0.dist-info/licenses/LICENSE`

`numpy` 还在其 `licenses/` 子目录中附带多个上游子组件许可证文本。

## 说明

- 上表只列出**打包运行时中能直接确认**的组件。
- `runtime/_internal` 中还包含其他二进制或库文件；如果后续需要完整第三方清单，建议在构建 runtime 时从原始 wheel / build manifest 生成正式 SBOM。
- 本文件不改变任何第三方许可证条款，也不替代上游许可证正文。
