"""
Export and Save Service for AetherPDF.

This module encapsulates low-level saving behaviors like Incremental Saving
(in-place updates) and optimized full saving (garbage collection and stream deflation)
utilizing PyMuPDF's C backend configurations.
"""

import os
import fitz  # PyMuPDF


class ExportService:
    """
    Service class responsible for saving, optimization, and compression of PDF documents.
    """

    @staticmethod
    def save_incremental(doc: fitz.Document) -> bool:
        """
        Save modifications in-place back to the original PDF file using incremental saving.

        Incremental saving is extremely fast and robust, preserving the original file structure
        and append-only signatures.

        Args:
            doc (fitz.Document): The active fitz Document to save.

        Returns:
            bool: True if saving succeeded, False otherwise.

        Raises:
            ValueError: If the document is null or not tied to a file path.
            RuntimeError: On PyMuPDF saving failures.
        """
        if not doc:
            raise ValueError("Document instance is null.")

        filepath = doc.name
        if not filepath or filepath == "":
            raise ValueError("Document is not associated with an existing local file.")

        try:
            # save(incremental=True) modifies the file in place safely.
            # We explicitly pass encryption=fitz.PDF_ENCRYPT_KEEP to prevent
            # PyMuPDF SWIG wrapper from raising encryption mismatch errors.
            doc.save(filepath, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
            return True
        except Exception as e:
            # If incremental save fails, raise with clear details
            raise RuntimeError(f"Incremental save failed: {str(e)}")

    @staticmethod
    def save_as(doc: fitz.Document, filepath: str, optimize: bool = True) -> bool:
        """
        Save the PDF document to a new file location, optionally applying aggressive optimizations.

        Optimization includes:
        - garbage=4: Remove duplicate/unused objects and reconstruct the object table.
        - deflate=True: Apply lossless compression to uncompressed text and image streams.

        Args:
            doc (fitz.Document): The active fitz Document to save.
            filepath (str): The target absolute path for the saved file.
            optimize (bool): If True, applies full garbage collection and deflation.

        Returns:
            bool: True if saving succeeded.

        Raises:
            ValueError: If target path is invalid.
            RuntimeError: On saving failures.
        """
        if not doc:
            raise ValueError("Document instance is null.")

        if not filepath:
            raise ValueError("Save path cannot be empty.")

        try:
            if optimize:
                # Clean unused assets and compress streams for light portable footprint
                doc.save(filepath, garbage=4, deflate=True)
            else:
                doc.save(filepath)
            return True
        except Exception as e:
            raise RuntimeError(f"Save as operation failed: {str(e)}")
