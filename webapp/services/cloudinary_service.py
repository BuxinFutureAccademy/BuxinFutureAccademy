from __future__ import annotations
from typing import Optional, Dict, Any, BinaryIO


def is_available() -> bool:
    try:
        import cloudinary  # type: ignore
        return True
    except Exception:
        return False


def upload_file(file_obj: BinaryIO, public_id: str, folder: str, resource_type: str = 'raw') -> Optional[Dict[str, Any]]:
    try:
        import cloudinary.uploader as uploader  # type: ignore
    except Exception:
        return None

    try:
        result = uploader.upload(
            file_obj,
            resource_type=resource_type,
            public_id=public_id,
            folder=folder,
            overwrite=True,
        )
        return {
            'secure_url': result.get('secure_url'),
            'public_id': result.get('public_id'),
            'resource_type': result.get('resource_type'),
            'bytes': result.get('bytes'),
        }
    except Exception:
        return None
