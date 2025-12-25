"""Type stubs for pyvips.Image."""

class Image:
    """Vips image object."""

    width: int
    height: int

    @staticmethod
    def new_from_buffer(buffer: bytes, option_string: str) -> Image:
        """Create image from buffer."""
        ...

    def resize(self, scale: float, kernel: str = "lanczos3") -> Image:
        """Resize image."""
        ...

    def write_to_buffer(self, format_string: str) -> bytes:
        """Write image to buffer."""
        ...
