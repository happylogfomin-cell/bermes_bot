from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import User

class UserRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get_by_tg(self, tg_id: int) -> User | None:
        return (await self.s.execute(
            select(User).where(User.tg_id == tg_id)
        )).scalar_one_or_none()

    async def create(self, tg_id: int, username: str | None) -> User:
        u = User(tg_id=tg_id, username=username, balance=10000)
        self.s.add(u)
        await self.s.flush()
        return u