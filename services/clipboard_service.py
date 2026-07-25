from PIL import ImageGrab


class ClipboardService:
    """
    Reads image data from the system clipboard.
    """

    def get_image(self):
        """
        Returns:
            (True, image)  -> Clipboard contains an image.
            (False, None)  -> No image available.
        """

        try:
            clip = ImageGrab.grabclipboard()

        except Exception:
            return False, None

        if clip is None:
            return False, None

        if hasattr(clip, "save"):
            return True, clip

        return False, None