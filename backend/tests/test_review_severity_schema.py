from app.models.chapter_review import ChapterReviewIssue
from app.models.review_stage import BookReviewFinding


def test_review_severity_columns_accept_needs_verification():
    required_length = len("needs_verification")

    assert ChapterReviewIssue.__table__.c.severity.type.length >= required_length
    assert BookReviewFinding.__table__.c.severity.type.length >= required_length
