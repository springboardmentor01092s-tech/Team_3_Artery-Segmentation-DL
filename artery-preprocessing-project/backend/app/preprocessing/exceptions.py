class ImageValidationError(ValueError):
    pass


class UnsupportedImageError(ImageValidationError):
    pass


class PreprocessingParameterError(ValueError):
    pass
