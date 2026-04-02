"""認証ロジック（bcryptハッシュ）"""

import bcrypt
import db


def _hash_password(password: str) -> str:
    """パスワードをbcryptでハッシュ化"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, password_hash: str) -> bool:
    """パスワードを検証"""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_user(
    user_id: str, password: str, display_name: str, is_admin: bool = False
) -> bool:
    """ユーザーを作成。既に存在する場合はFalseを返す"""
    client = db.get_client()
    existing = (
        client.table("users").select("id").eq("user_id", user_id).execute().data
    )
    if existing:
        return False

    client.table("users").insert(
        {
            "user_id": user_id,
            "password_hash": _hash_password(password),
            "display_name": display_name,
            "is_admin": is_admin,
        }
    ).execute()
    return True


def authenticate(user_id: str, password: str) -> dict | None:
    """認証成功時にユーザー情報を返す。失敗時はNone"""
    client = db.get_client()
    rows = (
        client.table("users")
        .select("id, user_id, display_name, is_admin, password_hash")
        .eq("user_id", user_id)
        .execute()
        .data
    )
    if not rows:
        return None

    user = rows[0]
    if not _verify_password(password, user["password_hash"]):
        return None

    return {
        "id": user["id"],
        "user_id": user["user_id"],
        "display_name": user["display_name"],
        "is_admin": user["is_admin"],
    }


def fetch_all_users() -> list[dict]:
    """全ユーザー一覧を取得（パスワード除外）"""
    return (
        db.get_client()
        .table("users")
        .select("id, user_id, display_name, is_admin, created_at")
        .order("created_at", desc=True)
        .execute()
        .data
    )


def delete_user(user_id: str) -> None:
    """ユーザーを削除"""
    db.get_client().table("users").delete().eq("user_id", user_id).execute()
