from __future__ import annotations
from typing import Optional, Dict, Any, BinaryIO, Tuple, Union, List
from flask import current_app, flash
import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
from werkzeug.datastructures import FileStorage

class CloudinaryService:
    @staticmethod
    def is_available() -> bool:
        """Check if Cloudinary is properly configured and available."""
        try:
            return all([
                cloudinary.config().cloud_name is not None,
                cloudinary.config().api_key is not None,
                cloudinary.config().api_secret is not None
            ])
        except Exception as e:
            current_app.logger.error(f"Cloudinary configuration error: {e}")
            return False

    @staticmethod
    def upload_file(
        file: Union[FileStorage, BinaryIO], 
        folder: str = "", 
        resource_type: str = "auto",
        public_id: Optional[str] = None
    ) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """
        Upload a file to Cloudinary.
        
        Args:
            file: File to upload (FileStorage or file-like object)
            folder: Cloudinary folder path
            resource_type: Type of resource ('image', 'video', 'raw', 'auto')
            public_id: Optional public ID for the file
            
        Returns:
            Tuple of (success, result) where result is either the upload data or an error message
        """
        if not CloudinaryService.is_available():
            return False, "Cloudinary is not properly configured"

        try:
            upload_result = cloudinary.uploader.upload(
                file,
                folder=folder,
                resource_type=resource_type,
                public_id=public_id,
                use_filename=True,
                unique_filename=True,
                overwrite=True
            )
            return True, {
                'url': upload_result.get('secure_url'),
                'public_id': upload_result.get('public_id'),
                'format': upload_result.get('format'),
                'resource_type': upload_result.get('resource_type'),
                'bytes': upload_result.get('bytes'),
                'width': upload_result.get('width'),
                'height': upload_result.get('height')
            }
        except Exception as e:
            error_msg = f"Error uploading to Cloudinary: {str(e)}"
            current_app.logger.error(error_msg)
            return False, error_msg

    @staticmethod
    def delete_file(public_id: str, resource_type: str = "image") -> Tuple[bool, str]:
        """
        Delete a file from Cloudinary.
        
        Args:
            public_id: The public ID of the file to delete
            resource_type: Type of resource ('image', 'video', 'raw')
            
        Returns:
            Tuple of (success, message)
        """
        if not CloudinaryService.is_available():
            return False, "Cloudinary is not properly configured"

        try:
            result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
            if result.get('result') == 'ok':
                return True, "File deleted successfully"
            return False, result.get('result', 'Unknown error')
        except Exception as e:
            error_msg = f"Error deleting from Cloudinary: {str(e)}"
            current_app.logger.error(error_msg)
            return False, error_msg

    @staticmethod
    def get_cloudinary_url(public_id: str, **transformations) -> Optional[str]:
        """Generate a Cloudinary URL with optional transformations."""
        try:
            return cloudinary.CloudinaryImage(public_id).build_url(**transformations)
        except Exception as e:
            current_app.logger.error(f"Error generating Cloudinary URL: {e}")
            return None

# Create a singleton instance
cloudinary_service = CloudinaryService()

def validate_cloudinary_config() -> None:
    """Log Cloudinary readiness at startup."""
    if not cloudinary_service.is_available():
        current_app.logger.warning(
            "Cloudinary not properly configured. "
            "Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET environment variables."
        )
            pass
