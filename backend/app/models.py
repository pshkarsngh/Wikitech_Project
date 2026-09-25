"""SQLAlchemy models for the PostgreSQL cache.

The database stores what Wikipedia already knows, so repeated analyses of the
same article can be served without hitting the MediaWiki API again. Nothing
here is required for the API to work: with an empty ``DATABASE_URL`` the app
runs without persistence.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Article(Base):
    """An English Wikipedia article we have seen before."""

    __tablename__ = "articles"

    page_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    normalized_title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    extract: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    length: Mapped[int | None] = mapped_column(Integer)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    outgoing_links: Mapped[list["ArticleLink"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Article {self.title!r}>"


class ArticleLink(Base):
    """A directed link from one article to another, as extracted by MediaWiki."""

    __tablename__ = "article_links"
    __table_args__ = (
        UniqueConstraint("source_page_id", "target_normalized_title", name="uq_link"),
        Index("ix_article_links_target_normalized_title", "target_normalized_title"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("articles.page_id", ondelete="CASCADE"), nullable=False
    )
    target_title: Mapped[str] = mapped_column(String(512), nullable=False)
    target_normalized_title: Mapped[str] = mapped_column(String(512), nullable=False)
    target_page_id: Mapped[int | None] = mapped_column(BigInteger)
    exists: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    source: Mapped[Article] = relationship(back_populates="outgoing_links")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ArticleLink {self.source_page_id}->{self.target_title!r}>"


class AnalysisRun(Base):
    """A stored summary of one analysis, for history and simple reporting."""

    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    seed_page_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    seed_title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    total_links: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_missing: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_one_way: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
