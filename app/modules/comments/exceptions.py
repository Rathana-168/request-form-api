from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError


class CommentNotFoundError(NotFoundError):
    code = "COMMENT_NOT_FOUND"

    def __init__(self, message: str = "Comment not found"):
        super().__init__(message)


class CommentsClosedError(ConflictError):
    code = "COMMENTS_CLOSED"

    def __init__(self, message: str = "Comments are closed on a finished request"):
        super().__init__(message)


class NotCommentAuthorError(PermissionDeniedError):
    code = "NOT_COMMENT_AUTHOR"

    def __init__(self, message: str = "You can only change your own comments"):
        super().__init__(message)