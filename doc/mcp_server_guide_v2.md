# MCPサーバー作成ガイド v2

## 1. 環境セットアップ
### 1.1 作業ディレクトリの作成と仮想環境のセットアップ
```bash
# 作業ディレクトリを作成して移動
mkdir mcp-project
cd mcp-project

# 仮想環境の作成
python -m venv dotenv

# 仮想環境の有効化（Windows）
dotenv\Scripts\activate
```

### 1.2 必要なパッケージのインストール
```bash
# requirements.txtの作成
cat > requirements.txt << EOF
mcp
mcp[cli]
aiohttp  # 外部APIを使用する場合
python-dotenv  # 環境変数を使用する場合
EOF

# パッケージのインストール
pip install -r requirements.txt
```

## 2. MCPサーバーの実装
### 2.1 基本的なサーバーコード（計算機能の例）
```python:calculator.py
from mcp.server.fastmcp import FastMCP
import math

# MCPサーバーのインスタンス作成
mcp = FastMCP("Calculator Server")

@mcp.tool()
def add(a: int, b: int) -> int:
    """2つの数値を足し算します"""
    return a + b

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### 2.2 外部APIを使用するサーバーコード（ChatWork APIの例）
```python:chatwork_mcp_server.py
from mcp.server.fastmcp import FastMCP
import aiohttp
import os
from typing import List, Dict
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

# MCPサーバーのインスタンス作成
mcp = FastMCP("ChatWork MCP Server")

# 環境変数からAPIトークンを取得
CHATWORK_API_TOKEN = os.getenv("CHATWORK_API_TOKEN")

@mcp.tool()
async def get_rooms() -> List[Dict]:
    """ChatWorkのルーム一覧を取得"""
    if not CHATWORK_API_TOKEN:
        raise ValueError("ChatWork APIトークンが設定されていません")

    async with aiohttp.ClientSession() as session:
        headers = {
            "X-ChatWorkToken": CHATWORK_API_TOKEN
        }
        try:
            async with session.get(
                "https://api.chatwork.com/v2/rooms",
                headers=headers
            ) as response:
                if response.status == 401:
                    raise ValueError("APIトークンが無効です")
                if response.status == 429:
                    raise ValueError("APIリクエスト制限を超過しました")
                if not response.ok:
                    raise ValueError(f"APIエラー: {response.status}")
                
                return await response.json()
        except aiohttp.ClientError as e:
            raise ValueError(f"ネットワークエラー: {str(e)}")
```

### 2.3 環境変数の設定（外部APIを使用する場合）
```env:.env
CHATWORK_API_TOKEN=your_api_token_here
```

## 3. Cursorとの連携設定を行う（重要な更新）
### 3.1 mcp.jsonの正しい設定方法
```json:mcp.json
{
  "servers": {
    "calculator": {
      "command": "C:\\Users\\username\\path\\to\\dotenv\\Scripts\\python.exe",
      (仮想環境未設定の場合、こちらのパスを利用。C:\\Users\\masak\\AppData\\Local\\Programs\\Python\\Python313\\python.exe)
      "args": [
        "C:\\Users\\username\\path\\to\\calculator.py"
      ]
    }
  }
}
```

### 3.2 設定時の重要なポイント
1. **commandの指定**
   - ✅ 仮想環境のPython.exeへの**絶対パス**を使用
   - ❌ `"python"` や相対パスは使用しない
   - 例: `"C:\\Users\\username\\project\\dotenv\\Scripts\\python.exe"`

2. **argsの指定**
   - ✅ 実行するPythonファイルへの**絶対パス**を使用
   - ❌ 相対パスは使用しない
   - 例: `"C:\\Users\\username\\project\\calculator.py"`

3. **パスの区切り文字**
   - Windowsパスの場合、`\\`  を使用（JSONでは自動エスケープ）

4. **環境変数の設定（必要な場合）**
```json
{
  "servers": {
    "chatwork": {
      "command": "C:\\Users\\username\\path\\to\\dotenv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\username\\path\\to\\chatwork_mcp_server.py"
      ],
      "env": {
        "CHATWORK_API_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

## 4. 動作確認とトラブルシューティング
### 4.1 基本的な確認手順
1. Cursorを再起動
2. コマンドパレットを開き、MCPサーバーが認識されているか確認
3. Agentモードで簡単なコマンドを実行してテスト

### 4.2 よくある問題と解決方法
1. **サーバーが認識されない**
   - commandのPython.exeパスが絶対パスになっているか確認
   - argsのPythonファイルパスが絶対パスになっているか確認
   - パスに日本語が含まれていないか確認

2. **実行時エラー**
   - 仮想環境が有効化されているか確認
   - 必要なパッケージが全てインストールされているか確認
   - 環境変数が正しく設定されているか確認

3. **外部API関連のエラー**
   - APIトークンが正しいか確認
   - .envファイルが正しい場所にあるか確認
   - ネットワーク接続を確認

## 5. ベストプラクティス
1. **プロジェクト構成**
```
mcp-project/
├── dotenv/                # 仮想環境
├── .env                   # 環境変数（必要な場合）
├── requirements.txt       # 依存パッケージ
├── calculator.py         # MCPサーバーコード
└── README.md             # プロジェクトの説明
```

2. **コード品質**
   - 型ヒントを積極的に使用
   - エラーハンドリングを適切に実装
   - ドキュメンテーション文字列を各ツールに追加

3. **セキュリティ**
   - APIキーは必ず環境変数で管理
   - 機密情報をコードにハードコーディングしない
   - 適切なエラーメッセージで情報漏洩を防ぐ 