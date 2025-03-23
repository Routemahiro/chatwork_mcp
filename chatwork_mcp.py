from mcp.server.fastmcp import FastMCP
import aiohttp
import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv
from urllib.parse import unquote

# 環境変数の読み込み
load_dotenv()

# MCPサーバーのインスタンス作成
mcp = FastMCP("ChatWork MCP Server")

# 環境変数からAPIトークンを取得
CHATWORK_API_TOKEN = os.getenv("CHATWORK_API_TOKEN")

# レスポンスの型定義
class Room(Dict):
    room_id: int
    name: str
    type: str
    role: str
    sticky: bool
    unread_num: int
    mention_num: int
    mytask_num: int
    message_num: int
    file_num: int
    task_num: int
    icon_path: str
    last_update_time: int

class Account(Dict):
    account_id: int
    name: str
    avatar_image_url: str

class Message(Dict):
    account: Account
    body: str
    send_time: int
    update_time: int

class Task(Dict):
    task_id: int
    room: Room
    assigned_by_account: Account
    message_id: str
    body: str
    limit_time: int
    status: str  # "open" または "done"
    limit_type: str  # "date" または "time"

@mcp.tool()
async def get_rooms() -> List[Room]:
    """ChatWorkのルーム一覧を取得します
    
    Returns:
        List[Room]: ルーム情報のリスト
        
    Raises:
        ValueError: APIトークンが未設定、または無効な場合
        RuntimeError: APIリクエスト制限超過時やその他のエラー発生時
    """
    if not CHATWORK_API_TOKEN:
        raise ValueError("ChatWork APIトークンが設定されていません。環境変数 CHATWORK_API_TOKEN を設定してください。")

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
                    raise RuntimeError("APIリクエスト制限を超過しました（5分あたり300リクエスト）")
                if not response.ok:
                    raise RuntimeError(f"APIエラー: ステータスコード {response.status}")
                
                return await response.json()
        except aiohttp.ClientError as e:
            raise RuntimeError(f"ネットワークエラー: {str(e)}")

@mcp.tool()
async def get_room_messages(room_id: int, save_dir_path: str, force: int = 0) -> List[Message]:
    """チャットのメッセージ一覧を取得します
    
    Args:
        room_id (int): チャットルームのID
        save_dir_path (str): メッセージを保存するディレクトリのパス
                            必ず事前にpwdコマンドで取得したパスを指定してください
                            Windowsの場合、C:\\Users\\...のような形式で指定してください
        force (int, optional): 前回取得分からの差分を取得するか（1: 差分を取得しない, 0: 差分のみ取得）
                             通信量削減のため、ユーザーからの指示がない限り0（デフォルト値）を必ず利用
        
    Returns:
        List[Message]: メッセージ情報のリスト（force=1の場合は保存先パスを含むメッセージのリスト）
        
    Raises:
        ValueError: APIトークンが未設定、または無効な場合、またはsave_dir_pathが未指定の場合
        RuntimeError: APIリクエスト制限超過時やその他のエラー発生時
    """
    if not CHATWORK_API_TOKEN:
        raise ValueError("ChatWork APIトークンが設定されていません。環境変数 CHATWORK_API_TOKEN を設定してください。")

    # save_dir_pathのバリデーションと正規化
    if not save_dir_path or save_dir_path == "":
        raise ValueError(
            "save_dir_pathの指定が必要です。\n"
            "以下の手順で実行してください：\n"
            "1. pwdコマンドを実行してカレントディレクトリを取得\n"
            "2. 取得したパスをsave_dir_pathに指定して再実行\n"
            "\n"
            "例：\n"
            "PS> pwd\n"
            "Path: C:\\Users\\masak\\Documents\\MEGA\\mcp\n"
            "\n"
            "get_room_messages(\n"
            "    room_id=357644346,\n"
            "    save_dir_path=\"C:\\Users\\masak\\Documents\\MEGA\\mcp\",\n"
            "    force=0\n"
            ")"
        )

    # URLエンコードされたパスを適切に変換
    normalized_path = unquote(save_dir_path)
    
    # Windowsパスの形式チェック
    if os.name == 'nt' and not normalized_path.startswith(('C:\\', 'D:\\', 'E:\\')):
        if normalized_path.startswith('/c/'):
            # /c/... 形式を C:\... 形式に変換
            normalized_path = f"C:{normalized_path[2:]}".replace('/', '\\')
        else:
            raise ValueError(
                f"不正なパス形式です: {save_dir_path}\n"
                "Windowsでは C:\\Users\\...のような形式で指定してください。\n"
                "pwdコマンドで取得したパスをそのまま使用してください。"
            )

    async with aiohttp.ClientSession() as session:
        headers = {
            "X-ChatWorkToken": CHATWORK_API_TOKEN
        }
        try:
            async with session.get(
                f"https://api.chatwork.com/v2/rooms/{room_id}/messages?force={force}",
                headers=headers
            ) as response:
                if response.status == 401:
                    raise ValueError("APIトークンが無効です")
                if response.status == 403:
                    raise RuntimeError("このチャットルームにアクセスする権限がありません")
                if response.status == 404:
                    raise RuntimeError("指定されたチャットルームが見つかりません")
                if response.status == 429:
                    raise RuntimeError("APIリクエスト制限を超過しました（5分あたり300リクエスト）")
                if not response.ok:
                    raise RuntimeError(f"APIエラー: ステータスコード {response.status}")
                
                messages = await response.json()

                # メッセージを保存（force=1またはforce=0で差分がある場合）
                if force == 1 or (force == 0 and messages):
                    now = datetime.now()
                    # 保存先ディレクトリの設定（正規化されたパスを使用）
                    base_dir = Path(normalized_path)
                    save_dir = base_dir / f"room_{room_id}/{now.strftime('%Y%m%d')}"
                    save_dir.mkdir(parents=True, exist_ok=True)
                    
                    # ファイル名の設定（force=0の場合は差分ファイルであることを明記）
                    filename = f"{now.strftime('%H%M')}_{'diff' if force == 0 else 'full'}.txt"
                    save_file = save_dir / filename

                    # メッセージの整形
                    formatted_messages = []
                    for msg in messages:
                        # 送信時刻をJST（日本時間）に変換
                        send_time = datetime.fromtimestamp(msg['send_time'])
                        formatted_time = send_time.strftime('%Y-%m-%d %H:%M:%S')

                        # 本文の取得（改行コードはそのまま保持）
                        body = msg['body']

                        # 投稿元URLの抽出（[info]タグ内のURL）
                        source_url = ""
                        if '[info]' in body and '[/info]' in body:
                            info_start = body.find('[info]')
                            info_end = body.find('[/info]')
                            source_url = body[info_start+6:info_end].strip()
                            # 本文から[info]タグを削除
                            body = body[:info_start] + body[info_end+7:]

                        # メッセージの整形
                        formatted_msg = f"""===============================
本文（日時：{formatted_time}）
{body.strip()}"""
                        if source_url:
                            formatted_msg += f"\n投稿元：{source_url}"
                        formatted_msg += "\n==============================="
                        formatted_messages.append(formatted_msg)

                    # ファイルに保存
                    with open(save_file, "w", encoding="utf-8") as f:
                        f.write("\n\n".join(formatted_messages))

                    # force=1の場合のみ、システムメッセージを返す
                    if force == 1:
                        return [{
                            "message_id": "system",
                            "account": {
                                "account_id": 0,
                                "name": "System",
                                "avatar_image_url": ""
                            },
                            "body": f"メッセージ履歴を保存しました: {save_file.absolute()}",
                            "send_time": int(datetime.now().timestamp()),
                            "update_time": int(datetime.now().timestamp())
                        }]

                return messages
        except aiohttp.ClientError as e:
            raise RuntimeError(f"ネットワークエラー: {str(e)}")

@mcp.tool()
async def get_room_message(room_id: int, message_id: int) -> Message:
    """チャットの特定のメッセージを取得します
    
    Args:
        room_id (int): チャットルームのID
        message_id (int): 取得するメッセージのID
        
    Returns:
        Message: メッセージ情報
        
    Raises:
        ValueError: APIトークンが未設定、または無効な場合
        RuntimeError: APIリクエスト制限超過時やその他のエラー発生時
    """
    if not CHATWORK_API_TOKEN:
        raise ValueError("ChatWork APIトークンが設定されていません。環境変数 CHATWORK_API_TOKEN を設定してください。")

    async with aiohttp.ClientSession() as session:
        headers = {
            "X-ChatWorkToken": CHATWORK_API_TOKEN
        }
        try:
            async with session.get(
                f"https://api.chatwork.com/v2/rooms/{room_id}/messages/{message_id}",
                headers=headers
            ) as response:
                if response.status == 401:
                    raise ValueError("APIトークンが無効です")
                if response.status == 403:
                    raise RuntimeError("このメッセージにアクセスする権限がありません")
                if response.status == 404:
                    raise RuntimeError("指定されたチャットルームまたはメッセージが見つかりません")
                if response.status == 429:
                    raise RuntimeError("APIリクエスト制限を超過しました（5分あたり300リクエスト）")
                if not response.ok:
                    raise RuntimeError(f"APIエラー: ステータスコード {response.status}")
                
                return await response.json()
        except aiohttp.ClientError as e:
            raise RuntimeError(f"ネットワークエラー: {str(e)}")

@mcp.tool()
async def get_room_tasks(room_id: int) -> List[Task]:
    """チャットルームのタスク一覧を取得します
    
    Args:
        room_id (int): チャットルームのID
        
    Returns:
        List[Task]: タスク情報のリスト
        
    Raises:
        ValueError: APIトークンが未設定、または無効な場合
        RuntimeError: APIリクエスト制限超過時やその他のエラー発生時
    """
    if not CHATWORK_API_TOKEN:
        raise ValueError("ChatWork APIトークンが設定されていません。環境変数 CHATWORK_API_TOKEN を設定してください。")

    async with aiohttp.ClientSession() as session:
        headers = {
            "X-ChatWorkToken": CHATWORK_API_TOKEN
        }
        try:
            async with session.get(
                f"https://api.chatwork.com/v2/rooms/{room_id}/tasks",
                headers=headers
            ) as response:
                if response.status == 401:
                    raise ValueError("APIトークンが無効です")
                if response.status == 403:
                    raise RuntimeError("このチャットルームにアクセスする権限がありません")
                if response.status == 404:
                    raise RuntimeError("指定されたチャットルームが見つかりません")
                if response.status == 429:
                    raise RuntimeError("APIリクエスト制限を超過しました（5分あたり300リクエスト）")
                if not response.ok:
                    raise RuntimeError(f"APIエラー: ステータスコード {response.status}")
                
                return await response.json()
        except aiohttp.ClientError as e:
            raise RuntimeError(f"ネットワークエラー: {str(e)}")

@mcp.tool()
async def get_my_tasks(status: str = "open") -> List[Task]:
    """自分に割り当てられたタスク一覧を取得します
    
    Args:
        status (str, optional): タスクのステータス。"open"（未完了）または"done"（完了）。デフォルトは"open"
        
    Returns:
        List[Task]: タスク情報のリスト
        
    Raises:
        ValueError: APIトークンが未設定、または無効な場合、またはstatusの値が不正な場合
        RuntimeError: APIリクエスト制限超過時やその他のエラー発生時
    """
    if not CHATWORK_API_TOKEN:
        raise ValueError("ChatWork APIトークンが設定されていません。環境変数 CHATWORK_API_TOKEN を設定してください。")

    if status not in ["open", "done"]:
        raise ValueError('statusは"open"または"done"を指定してください')

    async with aiohttp.ClientSession() as session:
        headers = {
            "X-ChatWorkToken": CHATWORK_API_TOKEN
        }
        try:
            async with session.get(
                f"https://api.chatwork.com/v2/my/tasks?status={status}",
                headers=headers
            ) as response:
                if response.status == 401:
                    raise ValueError("APIトークンが無効です")
                if response.status == 429:
                    raise RuntimeError("APIリクエスト制限を超過しました（5分あたり300リクエスト）")
                if not response.ok:
                    raise RuntimeError(f"APIエラー: ステータスコード {response.status}")
                
                return await response.json()
        except aiohttp.ClientError as e:
            raise RuntimeError(f"ネットワークエラー: {str(e)}")

@mcp.tool()
async def post_room_tasks(
    room_id: int,
    body: str,
    to_ids: List[int],
    limit: Optional[int] = None,
    limit_type: str = "date"
) -> Task:
    """チャットルームにタスクを作成します
    
    Args:
        room_id (int): チャットルームのID
        body (str): タスクの内容
        to_ids (List[int]): タスクの担当者のアカウントIDリスト
        limit (int, optional): タスクの期限（UNIXタイムスタンプ）
        limit_type (str, optional): 期限の種類。"date"（日付）または"time"（時間）。デフォルトは"date"
        
    Returns:
        Task: 作成されたタスク情報
        
    Raises:
        ValueError: APIトークンが未設定、または無効な場合、またはlimit_typeの値が不正な場合
        RuntimeError: APIリクエスト制限超過時やその他のエラー発生時
    """
    if not CHATWORK_API_TOKEN:
        raise ValueError("ChatWork APIトークンが設定されていません。環境変数 CHATWORK_API_TOKEN を設定してください。")

    if limit_type not in ["date", "time"]:
        raise ValueError('limit_typeは"date"または"time"を指定してください')

    if not body:
        raise ValueError("タスクの内容（body）は必須です")

    if not to_ids:
        raise ValueError("タスクの担当者（to_ids）は必須です")

    # パラメータの準備
    params = {
        "body": body,
        "limit_type": limit_type,
        # to_idsをカンマ区切りの文字列に変換
        "to_ids": ",".join(str(id) for id in to_ids)
    }

    # limitの処理（文字列として追加）
    if limit is not None:
        params["limit"] = str(limit)

    async with aiohttp.ClientSession() as session:
        headers = {
            "X-ChatWorkToken": CHATWORK_API_TOKEN,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        try:
            async with session.post(
                f"https://api.chatwork.com/v2/rooms/{room_id}/tasks",
                headers=headers,
                data=params
            ) as response:
                if response.status == 400:
                    error_body = await response.text()
                    raise RuntimeError(f"リクエストが不正です: {error_body}")
                if response.status == 401:
                    raise ValueError("APIトークンが無効です")
                if response.status == 403:
                    raise RuntimeError("このチャットルームにアクセスする権限がありません")
                if response.status == 404:
                    raise RuntimeError("指定されたチャットルームが見つかりません")
                if response.status == 429:
                    raise RuntimeError("APIリクエスト制限を超過しました（5分あたり300リクエスト）")
                if not response.ok:
                    error_body = await response.text()
                    raise RuntimeError(f"APIエラー: ステータスコード {response.status}, 詳細: {error_body}")
                
                return await response.json()
        except aiohttp.ClientError as e:
            raise RuntimeError(f"ネットワークエラー: {str(e)}")

@mcp.tool()
async def get_room_task(room_id: int, task_id: int) -> Task:
    """チャットルームの特定のタスクを取得します
    
    Args:
        room_id (int): チャットルームのID
        task_id (int): タスクのID
        
    Returns:
        Task: タスク情報
        
    Raises:
        ValueError: APIトークンが未設定、または無効な場合
        RuntimeError: APIリクエスト制限超過時やその他のエラー発生時
    """
    if not CHATWORK_API_TOKEN:
        raise ValueError("ChatWork APIトークンが設定されていません。環境変数 CHATWORK_API_TOKEN を設定してください。")

    async with aiohttp.ClientSession() as session:
        headers = {
            "X-ChatWorkToken": CHATWORK_API_TOKEN
        }
        try:
            async with session.get(
                f"https://api.chatwork.com/v2/rooms/{room_id}/tasks/{task_id}",
                headers=headers
            ) as response:
                if response.status == 401:
                    raise ValueError("APIトークンが無効です")
                if response.status == 403:
                    raise RuntimeError("このタスクにアクセスする権限がありません")
                if response.status == 404:
                    raise RuntimeError("指定されたチャットルームまたはタスクが見つかりません")
                if response.status == 429:
                    raise RuntimeError("APIリクエスト制限を超過しました（5分あたり300リクエスト）")
                if not response.ok:
                    raise RuntimeError(f"APIエラー: ステータスコード {response.status}")
                
                return await response.json()
        except aiohttp.ClientError as e:
            raise RuntimeError(f"ネットワークエラー: {str(e)}")

@mcp.tool()
async def put_room_task_status(room_id: int, task_id: int, status: str = "done") -> Task:
    """チャットルームのタスクの状態を更新します
    
    Args:
        room_id (int): チャットルームのID
        task_id (int): タスクのID
        status (str, optional): タスクの新しい状態。"open"（未完了）または"done"（完了）。デフォルトは"done"
        
    Returns:
        Task: 更新されたタスク情報
        
    Raises:
        ValueError: APIトークンが未設定、または無効な場合、またはstatusの値が不正な場合
        RuntimeError: APIリクエスト制限超過時やその他のエラー発生時
    """
    if not CHATWORK_API_TOKEN:
        raise ValueError("ChatWork APIトークンが設定されていません。環境変数 CHATWORK_API_TOKEN を設定してください。")

    if status not in ["open", "done"]:
        raise ValueError('statusは"open"または"done"を指定してください')

    # パラメータの準備（bodyパラメータにステータスを設定）
    params = {
        "body": status  # APIの仕様に従い、bodyパラメータにステータスを設定
    }

    async with aiohttp.ClientSession() as session:
        headers = {
            "X-ChatWorkToken": CHATWORK_API_TOKEN,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        try:
            async with session.put(
                f"https://api.chatwork.com/v2/rooms/{room_id}/tasks/{task_id}/status",
                headers=headers,
                data=params
            ) as response:
                if response.status == 400:
                    error_body = await response.text()
                    raise RuntimeError(f"リクエストが不正です: {error_body}")
                if response.status == 401:
                    raise ValueError("APIトークンが無効です")
                if response.status == 403:
                    raise RuntimeError("このタスクにアクセスする権限がありません")
                if response.status == 404:
                    raise RuntimeError("指定されたチャットルームまたはタスクが見つかりません")
                if response.status == 429:
                    raise RuntimeError("APIリクエスト制限を超過しました（5分あたり300リクエスト）")
                if not response.ok:
                    error_body = await response.text()
                    raise RuntimeError(f"APIエラー: ステータスコード {response.status}, 詳細: {error_body}")
                
                return await response.json()
        except aiohttp.ClientError as e:
            raise RuntimeError(f"ネットワークエラー: {str(e)}")

@mcp.tool()
async def post_room_messages(room_id: int, body: str, self_unread: int = 0) -> Message:
    """チャットにメッセージを投稿します
    
    Args:
        room_id (int): チャットルームのID
        body (str): メッセージの本文
        self_unread (int, optional): 投稿したメッセージを自分の未読にするか（0: しない, 1: する）。デフォルトは0
        
    Returns:
        Message: 投稿されたメッセージ情報
        
    Raises:
        ValueError: APIトークンが未設定、または無効な場合、またはbodyが空の場合
        RuntimeError: APIリクエスト制限超過時やその他のエラー発生時
    """
    if not CHATWORK_API_TOKEN:
        raise ValueError("ChatWork APIトークンが設定されていません。環境変数 CHATWORK_API_TOKEN を設定してください。")

    if not body:
        raise ValueError("メッセージの本文（body）は必須です")

    # パラメータの準備
    params = {
        "body": body,
        "self_unread": str(self_unread)
    }

    async with aiohttp.ClientSession() as session:
        headers = {
            "X-ChatWorkToken": CHATWORK_API_TOKEN,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        try:
            async with session.post(
                f"https://api.chatwork.com/v2/rooms/{room_id}/messages",
                headers=headers,
                data=params
            ) as response:
                if response.status == 400:
                    error_body = await response.text()
                    raise RuntimeError(f"リクエストが不正です: {error_body}")
                if response.status == 401:
                    raise ValueError("APIトークンが無効です")
                if response.status == 403:
                    raise RuntimeError("このチャットルームにアクセスする権限がありません")
                if response.status == 404:
                    raise RuntimeError("指定されたチャットルームが見つかりません")
                if response.status == 429:
                    raise RuntimeError("APIリクエスト制限を超過しました（5分あたり300リクエスト）")
                if not response.ok:
                    error_body = await response.text()
                    raise RuntimeError(f"APIエラー: ステータスコード {response.status}, 詳細: {error_body}")
                
                return await response.json()
        except aiohttp.ClientError as e:
            raise RuntimeError(f"ネットワークエラー: {str(e)}")

if __name__ == "__main__":
    mcp.run(transport="stdio") 