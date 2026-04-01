from pathlib import Path
from typing import Any, Optional


class SupabaseRemote:
    BUCKET = "objects"

    def __init__(self, client: Any):
        self.client = client

    @classmethod
    def from_config(cls, url: str, key: str) -> "SupabaseRemote":
        from supabase import create_client
        return cls(client=create_client(url, key))

    def upload_blob(self, project_id: str, commit_hash: str, flp_path: Path) -> None:
        blob_path = f"{project_id}/{commit_hash}.flp"
        with open(flp_path, "rb") as f:
            data = f.read()
        self.client.storage.from_(self.BUCKET).upload(
            path=blob_path,
            file=data,
            file_options={"content-type": "application/octet-stream", "upsert": "true"},
        )

    def download_blob(self, project_id: str, commit_hash: str, dest: Path) -> None:
        blob_path = f"{project_id}/{commit_hash}.flp"
        data = self.client.storage.from_(self.BUCKET).download(blob_path)
        dest.write_bytes(data)

    def insert_commit(self, project_id: str, commit: dict) -> None:
        row = {
            "hash": commit["hash"],
            "message": commit["message"],
            "branch": commit["branch"],
            "timestamp": commit["timestamp"],
            "project_id": project_id,
            "parent_hash": commit.get("parent_hash"),
            "diff": commit.get("changes", {}),
        }
        self.client.table("commits").insert(row).execute()

    def fetch_commits(self, project_id: str, branch: str) -> list:
        result = (
            self.client.table("commits")
            .select("*")
            .eq("project_id", project_id)
            .eq("branch", branch)
            .execute()
        )
        return result.data

    def ensure_project(self, name: str, owner: str) -> str:
        """Get or create a project row, return its UUID."""
        result = self.client.table("projects").select("id").eq("name", name).eq("owner", owner).execute()
        if result.data:
            return result.data[0]["id"]
        insert_result = self.client.table("projects").insert({"name": name, "owner": owner}).execute()
        return insert_result.data[0]["id"]
