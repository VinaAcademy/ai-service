from sqlalchemy import Column, DateTime, Integer, Boolean, func
from sqlalchemy.ext.declarative import declared_attr, declarative_base

Base = declarative_base()


# --- Mixin ---
class TimestampMixin:
    """Mixin thêm các trường created_date và updated_date."""

    created_date = Column(DateTime, default=func.now(), nullable=False)
    updated_date = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )


class SoftDeleteMixin:
    """Mixin thêm trường is_deleted cho tính năng soft delete."""

    is_deleted = Column(Boolean, default=False, nullable=False)


# --- Class Base cho tất cả các Models ---
class BaseMixin(TimestampMixin):
    """Base class kết hợp ID, Timestamp và Soft Delete."""

    id = Column(Integer, primary_key=True, index=True)

    # Tự động đặt tên bảng (ví dụ: User -> users)
    @declared_attr
    def __tablename__(cls):
        # Chuyển tên lớp từ CamelCase sang snake_case và thêm 's'
        return cls.__name__.lower() + "s"

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"
