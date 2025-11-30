from typing import TypeVar, Generic, Type, Optional, Any, Sequence

from sqlalchemy import select, update, delete, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from src.model.base import Base

# Generic type for SQLAlchemy models
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Base repository class with common CRUD operations.
    
    Usage:
        class UserRepository(BaseRepository[User]):
            def __init__(self, session: AsyncSession):
                super().__init__(User, session)
    """
    model: Type[ModelType]

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """
        Initialize repository with model class and database session.
        
        Args:
            model: SQLAlchemy model class
            session: Async database session
        """
        self.model = model
        self.session = session

    # ==================== CREATE ====================

    async def create(self, obj_in: dict | ModelType) -> ModelType:
        """
        Create a new record.
        
        Args:
            obj_in: Dictionary or model instance with data to create
            
        Returns:
            Created model instance
        """
        if isinstance(obj_in, dict):
            db_obj = self.model(**obj_in)
        else:
            db_obj = obj_in
        
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def create_many(self, objs_in: list[dict | ModelType]) -> list[ModelType]:
        """
        Create multiple records in batch.
        
        Args:
            objs_in: List of dictionaries or model instances
            
        Returns:
            List of created model instances
        """
        db_objs = []
        for obj_in in objs_in:
            if isinstance(obj_in, dict):
                db_obj = self.model(**obj_in)
            else:
                db_obj = obj_in
            db_objs.append(db_obj)
        
        self.session.add_all(db_objs)
        await self.session.commit()
        
        for db_obj in db_objs:
            await self.session.refresh(db_obj)
        
        return db_objs

    # ==================== READ ====================

    async def get_by_id(self, id: int, include_deleted: bool = False) -> Optional[ModelType]:
        """
        Get a single record by ID.
        
        Args:
            id: Primary key ID
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            Model instance or None if not found
        """
        query = select(self.model).where(self.model.id == id)
        
        if not include_deleted and hasattr(self.model, 'is_deleted'):
            query = query.where(self.model.is_deleted.is_(False))
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_field(
        self, 
        field: str, 
        value: Any, 
        include_deleted: bool = False
    ) -> Optional[ModelType]:
        """
        Get a single record by a specific field value.
        
        Args:
            field: Field name to filter by
            value: Value to match
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            Model instance or None if not found
        """
        query = select(self.model).where(getattr(self.model, field) == value)
        
        if not include_deleted and hasattr(self.model, 'is_deleted'):
            query = query.where(self.model.is_deleted.is_(False))
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
        order_by: Optional[str] = None,
        order_desc: bool = False
    ) -> Sequence[ModelType]:
        """
        Get all records with pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            include_deleted: Whether to include soft-deleted records
            order_by: Field name to order by
            order_desc: Whether to order descending
            
        Returns:
            List of model instances
        """
        query = select(self.model)
        
        if not include_deleted and hasattr(self.model, 'is_deleted'):
            query = query.where(self.model.is_deleted.is_(False))
        
        if order_by:
            order_column = getattr(self.model, order_by)
            query = query.order_by(order_column.desc() if order_desc else order_column)
        
        query = query.offset(skip).limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_multi_by_field(
        self,
        field: str,
        value: Any,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> Sequence[ModelType]:
        """
        Get multiple records by a specific field value.
        
        Args:
            field: Field name to filter by
            value: Value to match
            skip: Number of records to skip
            limit: Maximum number of records to return
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            List of model instances
        """
        query = select(self.model).where(getattr(self.model, field) == value)
        
        if not include_deleted and hasattr(self.model, 'is_deleted'):
            query = query.where(self.model.is_deleted.is_(False))
        
        query = query.offset(skip).limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_filters(
        self,
        filters: dict[str, Any],
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
        order_by: Optional[str] = None,
        order_desc: bool = False
    ) -> Sequence[ModelType]:
        """
        Get records matching multiple filter conditions.
        
        Args:
            filters: Dictionary of field-value pairs to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            include_deleted: Whether to include soft-deleted records
            order_by: Field name to order by
            order_desc: Whether to order descending
            
        Returns:
            List of model instances
        """
        conditions = [getattr(self.model, field) == value for field, value in filters.items()]
        
        if not include_deleted and hasattr(self.model, 'is_deleted'):
            conditions.append(self.model.is_deleted.is_(False))
        
        query = select(self.model).where(and_(*conditions))
        
        if order_by:
            order_column = getattr(self.model, order_by)
            query = query.order_by(order_column.desc() if order_desc else order_column)
        
        query = query.offset(skip).limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()

    # ==================== UPDATE ====================

    async def update(self, id: int, obj_in: dict) -> Optional[ModelType]:
        """
        Update a record by ID.
        
        Args:
            id: Primary key ID
            obj_in: Dictionary with fields to update
            
        Returns:
            Updated model instance or None if not found
        """
        db_obj = await self.get_by_id(id)
        if not db_obj:
            return None
        
        for field, value in obj_in.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def update_by_field(
        self, 
        field: str, 
        value: Any, 
        obj_in: dict
    ) -> Optional[ModelType]:
        """
        Update a record by a specific field value.
        
        Args:
            field: Field name to filter by
            value: Value to match
            obj_in: Dictionary with fields to update
            
        Returns:
            Updated model instance or None if not found
        """
        db_obj = await self.get_by_field(field, value)
        if not db_obj:
            return None
        
        for f, v in obj_in.items():
            if hasattr(db_obj, f):
                setattr(db_obj, f, v)
        
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def bulk_update(self, filters: dict[str, Any], obj_in: dict) -> int:
        """
        Bulk update records matching filter conditions.
        
        Args:
            filters: Dictionary of field-value pairs to filter by
            obj_in: Dictionary with fields to update
            
        Returns:
            Number of records updated
        """
        conditions = [getattr(self.model, field) == value for field, value in filters.items()]
        
        if hasattr(self.model, 'is_deleted'):
            conditions.append(self.model.is_deleted.is_(False))
        
        stmt = (
            update(self.model)
            .where(and_(*conditions))
            .values(**obj_in)
        )
        
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    # ==================== DELETE ====================

    async def delete(self, id: int, hard_delete: bool = False) -> bool:
        """
        Delete a record by ID (soft delete by default).
        
        Args:
            id: Primary key ID
            hard_delete: If True, permanently delete the record
            
        Returns:
            True if deleted, False if not found
        """
        db_obj = await self.get_by_id(id, include_deleted=hard_delete)
        if not db_obj:
            return False
        
        if hard_delete:
            await self.session.delete(db_obj)
        else:
            if hasattr(db_obj, 'is_deleted'):
                db_obj.is_deleted = True
            else:
                await self.session.delete(db_obj)
        
        await self.session.commit()
        return True

    async def delete_by_field(
        self, 
        field: str, 
        value: Any, 
        hard_delete: bool = False
    ) -> bool:
        """
        Delete a record by a specific field value.
        
        Args:
            field: Field name to filter by
            value: Value to match
            hard_delete: If True, permanently delete the record
            
        Returns:
            True if deleted, False if not found
        """
        db_obj = await self.get_by_field(field, value, include_deleted=hard_delete)
        if not db_obj:
            return False
        
        if hard_delete:
            await self.session.delete(db_obj)
        else:
            if hasattr(db_obj, 'is_deleted'):
                db_obj.is_deleted = True
            else:
                await self.session.delete(db_obj)
        
        await self.session.commit()
        return True

    async def bulk_delete(
        self, 
        filters: dict[str, Any], 
        hard_delete: bool = False
    ) -> int:
        """
        Bulk delete records matching filter conditions.
        
        Args:
            filters: Dictionary of field-value pairs to filter by
            hard_delete: If True, permanently delete records
            
        Returns:
            Number of records deleted
        """
        conditions = [getattr(self.model, field) == value for field, value in filters.items()]
        
        if hard_delete:
            stmt = delete(self.model).where(and_(*conditions))
        else:
            if hasattr(self.model, 'is_deleted'):
                stmt = (
                    update(self.model)
                    .where(and_(*conditions))
                    .values(is_deleted=True)
                )
            else:
                stmt = delete(self.model).where(and_(*conditions))
        
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def restore(self, id: int) -> Optional[ModelType]:
        """
        Restore a soft-deleted record.
        
        Args:
            id: Primary key ID
            
        Returns:
            Restored model instance or None if not found
        """
        if not hasattr(self.model, 'is_deleted'):
            return None
        
        db_obj = await self.get_by_id(id, include_deleted=True)
        if not db_obj or not db_obj.is_deleted:
            return None
        
        db_obj.is_deleted = False
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    # ==================== COUNT ====================

    async def count(self, include_deleted: bool = False) -> int:
        """
        Count total records.
        
        Args:
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            Total count
        """
        query = select(func.count(self.model.id))
        
        if not include_deleted and hasattr(self.model, 'is_deleted'):
            query = query.where(self.model.is_deleted.is_(False))
        
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def count_by_filters(
        self, 
        filters: dict[str, Any], 
        include_deleted: bool = False
    ) -> int:
        """
        Count records matching filter conditions.
        
        Args:
            filters: Dictionary of field-value pairs to filter by
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            Count of matching records
        """
        conditions = [getattr(self.model, field) == value for field, value in filters.items()]
        
        if not include_deleted and hasattr(self.model, 'is_deleted'):
            conditions.append(self.model.is_deleted.is_(False))
        
        query = select(func.count(self.model.id)).where(and_(*conditions))
        
        result = await self.session.execute(query)
        return result.scalar() or 0

    # ==================== EXISTS ====================

    async def exists(self, id: int, include_deleted: bool = False) -> bool:
        """
        Check if a record exists by ID.
        
        Args:
            id: Primary key ID
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            True if exists, False otherwise
        """
        query = select(func.count(self.model.id)).where(self.model.id == id)
        
        if not include_deleted and hasattr(self.model, 'is_deleted'):
            query = query.where(self.model.is_deleted.is_(False))
        
        result = await self.session.execute(query)
        return (result.scalar() or 0) > 0

    async def exists_by_field(
        self, 
        field: str, 
        value: Any, 
        include_deleted: bool = False
    ) -> bool:
        """
        Check if a record exists by a specific field value.
        
        Args:
            field: Field name to filter by
            value: Value to match
            include_deleted: Whether to include soft-deleted records
            
        Returns:
            True if exists, False otherwise
        """
        query = select(func.count(self.model.id)).where(getattr(self.model, field) == value)
        
        if not include_deleted and hasattr(self.model, 'is_deleted'):
            query = query.where(self.model.is_deleted.is_(False))
        
        result = await self.session.execute(query)
        return (result.scalar() or 0) > 0

    # ==================== UTILITY ====================

    async def execute_query(self, query: Select) -> Sequence[ModelType]:
        """
        Execute a custom SQLAlchemy select query.
        
        Args:
            query: SQLAlchemy Select statement
            
        Returns:
            List of model instances
        """
        result = await self.session.execute(query)
        return result.scalars().all()

    async def refresh(self, db_obj: ModelType) -> ModelType:
        """
        Refresh a model instance from database.
        
        Args:
            db_obj: Model instance to refresh
            
        Returns:
            Refreshed model instance
        """
        await self.session.refresh(db_obj)
        return db_obj

