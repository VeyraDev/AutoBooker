"""共享书架服务：分类、上传、列表、加入书稿。"""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.library_shelf import LibraryCategory, LibraryItem, LibraryItemStatus
from app.models.reference import (
    FileLifecycleStatus,
    FilePurpose,
    OutlineUsage,
    ParseStatus,
    ReferenceFile,
    ReferenceFilePurpose,
)
from app.models.user import User

DEFAULT_CATEGORIES: list[tuple[str, str, str, int]] = [
    ("humanities", "人文社科", "历史、社会、文化与思想类读物", 10),
    ("philosophy", "哲学思想", "哲学、伦理学与思想史", 15),
    ("history", "历史地理", "中外历史、考古与地理", 18),
    ("politics", "政治法律", "政治学、法学与公共政策", 22),
    ("education", "教育心理", "教育学、心理学与学习科学", 25),
    ("science", "自然科学", "数理化生与科普", 30),
    ("math", "数学统计", "数学、统计学与运筹", 32),
    ("medicine", "医学健康", "医学、公共卫生与健康管理", 35),
    ("tech", "计算机与技术", "软件、AI、工程与产品", 40),
    ("ai", "人工智能", "机器学习、大模型与智能系统", 42),
    ("engineering", "工程技术", "机械、电子、土木与工业工程", 45),
    ("business", "经济管理", "商业、金融与管理", 50),
    ("finance", "金融投资", "银行、证券、保险与投资", 52),
    ("marketing", "市场运营", "营销、品牌与增长", 55),
    ("textbook", "教材讲义", "课程教材、讲义与教辅", 60),
    ("exam", "考试考证", "升学考试、职业资格与培训", 62),
    ("literature", "文学艺术", "小说、散文、艺术与批评", 70),
    ("language", "语言写作", "语言学习、写作与翻译", 72),
    ("design", "设计创意", "设计、广告与创意产业", 75),
    ("reference", "工具参考", "手册、标准、辞典与资料汇编", 80),
    ("report", "报告白皮书", "行业报告、白皮书与调研", 85),
    ("biography", "人物传记", "人物传记与口述史", 88),
    ("other", "其他", "未归类资料", 99),
]

ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt"}
MAX_UPLOAD_BYTES = 80 * 1024 * 1024  # 80MB


def seed_library_categories(db: Session) -> int:
    existing = {c.slug for c in db.query(LibraryCategory).all()}
    added = 0
    for slug, name, desc, order in DEFAULT_CATEGORIES:
        if slug in existing:
            continue
        db.add(
            LibraryCategory(
                id=uuid.uuid4(),
                slug=slug,
                name=name,
                description=desc,
                sort_order=order,
            )
        )
        added += 1
    if added:
        db.commit()
    return added


def list_categories(db: Session) -> list[LibraryCategory]:
    seed_library_categories(db)
    return db.query(LibraryCategory).order_by(LibraryCategory.sort_order.asc(), LibraryCategory.name.asc()).all()


def list_shelf_items(
    db: Session,
    *,
    category_slug: str | None = None,
    q: str | None = None,
    mine: bool = False,
    uploader_id: UUID | None = None,
    limit: int = 48,
    offset: int = 0,
) -> tuple[list[LibraryItem], int]:
    seed_library_categories(db)
    qry = db.query(LibraryItem).filter(LibraryItem.status == LibraryItemStatus.published)
    if mine and uploader_id:
        qry = qry.filter(LibraryItem.uploader_id == uploader_id)
    if category_slug:
        cat = db.query(LibraryCategory).filter(LibraryCategory.slug == category_slug).first()
        if cat:
            qry = qry.filter(LibraryItem.category_id == cat.id)
        else:
            return [], 0
    if q and q.strip():
        like = f"%{q.strip()}%"
        qry = qry.filter(LibraryItem.title.ilike(like))
    total = qry.count()
    rows = (
        qry.order_by(LibraryItem.use_count.desc(), LibraryItem.created_at.desc())
        .offset(max(0, offset))
        .limit(min(100, max(1, limit)))
        .all()
    )
    return rows, total


def get_published_item(db: Session, item_id: UUID) -> LibraryItem:
    row = db.get(LibraryItem, item_id)
    if not row or row.status != LibraryItemStatus.published:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "书架条目不存在或未上架")
    return row


def create_shelf_item(
    db: Session,
    *,
    user: User,
    title: str,
    authors: list[str],
    description: str,
    category_slug: str,
    tags: list[str],
    filename: str,
    content: bytes,
) -> LibraryItem:
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文件为空")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文件过大（上限 80MB）")

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"仅支持 {', '.join(sorted(ALLOWED_SUFFIXES))}",
        )
    if suffix == ".pdf":
        file_type = "pdf"
    elif suffix == ".docx":
        file_type = "docx"
    else:
        file_type = "txt"

    seed_library_categories(db)
    cat = db.query(LibraryCategory).filter(LibraryCategory.slug == category_slug).first()
    if not cat:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "分类不存在")

    clean_title = (title or "").strip() or Path(filename).stem
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    uploader_name = (user.email or "").split("@")[0] or "用户"

    item = LibraryItem(
        id=uuid.uuid4(),
        title=clean_title[:500],
        authors=[a.strip() for a in authors if a and str(a).strip()][:20],
        description=(description or "").strip()[:4000] or None,
        category_id=cat.id,
        tags=[t.strip() for t in tags if t and str(t).strip()][:20],
        language="zh",
        file_type=file_type,
        filename=filename[:500],
        mime_type=mime,
        content=content,
        size_bytes=len(content),
        uploader_id=user.id,
        uploader_name=uploader_name[:120],
        status=LibraryItemStatus.published,
        use_count=0,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def add_shelf_item_to_book(
    db: Session,
    *,
    book: Book,
    user: User,
    item: LibraryItem,
    background_tasks: BackgroundTasks | None = None,
) -> ReferenceFile:
    """把共享书架文件拷贝为本书参考文献并触发解析。"""
    from app.routers.references import _run_parse_task
    from app.services.assets.reference_asset_service import ReferenceAssetService
    from app.services.citation_service import create_citation_from_paper

    ref = ReferenceFile(
        book_id=book.id,
        filename=item.filename,
        storage_path=None,
        file_type=item.file_type,
        parse_status=ParseStatus.pending,
        share_to_library="private",
        file_purposes=["reference_material"],
        outline_usage=OutlineUsage.reference,
        user_note=f"来自共享书架：{item.title}",
        lifecycle_status=FileLifecycleStatus.processing,
    )
    db.add(ref)
    db.flush()
    ReferenceAssetService(db).attach_upload(
        ref=ref,
        content=bytes(item.content),
        owner_user_id=user.id,
    )
    db.add(
        ReferenceFilePurpose(
            file_id=ref.id,
            purpose=FilePurpose.reference_material,
            confidence=100,
            user_confirmed=True,
            is_primary=False,
        )
    )

    # 同步一条书目元数据，便于引用
    from app.models.citation import CitationSource

    create_citation_from_paper(
        db,
        book,
        {
            "title": item.title,
            "authors": item.authors or [],
            "source": "uploaded_file",
            "external_source": f"library_shelf:{item.id}",
            "quotable_snippet": (item.description or "")[:600],
        },
        source=CitationSource.uploaded_file,
        source_file_id=ref.id,
    )

    item.use_count = (item.use_count or 0) + 1
    db.commit()
    db.refresh(ref)

    if background_tasks is not None:
        background_tasks.add_task(
            _run_parse_task,
            book.id,
            ref.id,
            ref.storage_path or "",
            item.file_type,
            "reference",
        )
    return ref
