from django.core.files.uploadhandler import FileUploadHandler, SkipFile

from ribcage.operations import offer


class CappedUploadHandler(FileUploadHandler):
    """First of every request's upload handlers: a file over the backup cap is dropped as it streams in, never kept (#81)."""

    def receive_data_chunk(self, raw_data, start):
        if start + len(raw_data) > offer.UPLOAD_CAP_BYTES:
            raise SkipFile
        return raw_data

    def file_complete(self, file_size):
        return None
