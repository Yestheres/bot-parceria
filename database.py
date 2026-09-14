from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg

from config import DATABASE_URL

logger = logging.getLogger(__name__)

_MIGRATION_LOCK_KEY = 891_234_567


class Database:
    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        async def _init_connection(conn: asyncpg.Connection) -> None:
            # Faz asyncpg converter JSONB <-> dict Python automaticamente.
            await conn.set_type_codec(
                "jsonb",
                encoder=json.dumps,
                decoder=json.loads,
                schema="pg_catalog",
            )
            await conn.set_type_codec(
                "json",
                encoder=json.dumps,
                decoder=json.loads,
                schema="pg_catalog",
            )

        self._pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            command_timeout=30,
            init=_init_connection,
        )
        logger.info("Pool de conexões criado.")
        await self._run_migrations()

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("Pool de conexões fechado.")

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database não inicializada. Chame connect() primeiro.")
        return self._pool

    async def _run_migrations(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("SELECT pg_advisory_lock($1)", _MIGRATION_LOCK_KEY)
            try:
                await self._create_tables(conn)
                logger.info("Migrations aplicadas com sucesso.")
            finally:
                await conn.execute("SELECT pg_advisory_unlock($1)", _MIGRATION_LOCK_KEY)

    @staticmethod
    async def _create_tables(conn: asyncpg.Connection) -> None:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id              BIGINT PRIMARY KEY,
                approval_channel_id   BIGINT,
                publication_channel_id BIGINT,
                ticket_category_id    BIGINT,
                closed_category_id    BIGINT,
                staff_role_id         BIGINT,
                ai_api_key            TEXT,
                ai_model              TEXT,
                ai_base_url           TEXT,
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id            BIGSERIAL PRIMARY KEY,
                guild_id      BIGINT NOT NULL,
                channel_id    BIGINT NOT NULL UNIQUE,
                user_id       BIGINT NOT NULL,
                step          TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT 'open',
                data          JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_one_open_ticket_per_user
            ON tickets (guild_id, user_id)
            WHERE status = 'open'
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tickets_step_updated
            ON tickets (step, updated_at)
        """)

    # ---------- guild_config ----------
    async def set_approval_channel(self, guild_id: int, channel_id: int) -> None:
        await self.pool.execute(
            """
            INSERT INTO guild_config (guild_id, approval_channel_id)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE
                SET approval_channel_id = EXCLUDED.approval_channel_id,
                    updated_at = NOW()
            """,
            guild_id, channel_id,
        )

    async def get_approval_channel(self, guild_id: int) -> int | None:
        row = await self.pool.fetchrow(
            "SELECT approval_channel_id FROM guild_config WHERE guild_id = $1",
            guild_id,
        )
        return row["approval_channel_id"] if row else None

    async def set_publication_channel(self, guild_id: int, channel_id: int) -> None:
        await self.pool.execute(
            """
            INSERT INTO guild_config (guild_id, publication_channel_id)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE
                SET publication_channel_id = EXCLUDED.publication_channel_id,
                    updated_at = NOW()
            """,
            guild_id, channel_id,
        )

    async def get_publication_channel(self, guild_id: int) -> int | None:
        row = await self.pool.fetchrow(
            "SELECT publication_channel_id FROM guild_config WHERE guild_id = $1",
            guild_id,
        )
        return row["publication_channel_id"] if row else None

    async def set_ticket_category(self, guild_id: int, category_id: int) -> None:
        await self.pool.execute(
            """
            INSERT INTO guild_config (guild_id, ticket_category_id)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE
                SET ticket_category_id = EXCLUDED.ticket_category_id,
                    updated_at = NOW()
            """,
            guild_id, category_id,
        )

    async def get_ticket_category(self, guild_id: int) -> int | None:
        row = await self.pool.fetchrow(
            "SELECT ticket_category_id FROM guild_config WHERE guild_id = $1",
            guild_id,
        )
        return row["ticket_category_id"] if row else None

    async def set_closed_category(self, guild_id: int, category_id: int) -> None:
        await self.pool.execute(
            """
            INSERT INTO guild_config (guild_id, closed_category_id)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE
                SET closed_category_id = EXCLUDED.closed_category_id,
                    updated_at = NOW()
            """,
            guild_id, category_id,
        )

    async def get_closed_category(self, guild_id: int) -> int | None:
        row = await self.pool.fetchrow(
            "SELECT closed_category_id FROM guild_config WHERE guild_id = $1",
            guild_id,
        )
        return row["closed_category_id"] if row else None

    async def set_staff_role(self, guild_id: int, role_id: int) -> None:
        await self.pool.execute(
            """
            INSERT INTO guild_config (guild_id, staff_role_id)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE
                SET staff_role_id = EXCLUDED.staff_role_id,
                    updated_at = NOW()
            """,
            guild_id, role_id,
        )

    async def get_staff_role(self, guild_id: int) -> int | None:
        row = await self.pool.fetchrow(
            "SELECT staff_role_id FROM guild_config WHERE guild_id = $1",
            guild_id,
        )
        return row["staff_role_id"] if row else None

    async def set_ai_config(
        self,
        guild_id: int,
        api_key: str | None,
        model: str | None,
        base_url: str | None,
    ) -> None:
        await self.pool.execute(
            """
            INSERT INTO guild_config (guild_id, ai_api_key, ai_model, ai_base_url)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (guild_id) DO UPDATE
                SET ai_api_key  = EXCLUDED.ai_api_key,
                    ai_model    = EXCLUDED.ai_model,
                    ai_base_url = EXCLUDED.ai_base_url,
                    updated_at  = NOW()
            """,
            guild_id, api_key, model, base_url,
        )

    async def get_ai_config(self, guild_id: int) -> dict[str, str | None] | None:
        row = await self.pool.fetchrow(
            "SELECT ai_api_key, ai_model, ai_base_url FROM guild_config WHERE guild_id = $1",
            guild_id,
        )
        if not row or not row["ai_api_key"]:
            return None
        return {
            "api_key": row["ai_api_key"],
            "model": row["ai_model"] or "glm-4.5-flash",
            "base_url": row["ai_base_url"] or "https://openrouter.ai/api/v1",
        }

    async def clear_ai_config(self, guild_id: int) -> None:
        await self.pool.execute(
            """
            UPDATE guild_config
            SET ai_api_key = NULL, ai_model = NULL, ai_base_url = NULL, updated_at = NOW()
            WHERE guild_id = $1
            """,
            guild_id,
        )

    # ---------- tickets ----------
    async def get_open_ticket(self, guild_id: int, user_id: int) -> dict[str, Any] | None:
        row = await self.pool.fetchrow(
            """
            SELECT * FROM tickets
            WHERE guild_id = $1 AND user_id = $2 AND status = 'open'
            """,
            guild_id, user_id,
        )
        return dict(row) if row else None

    async def get_ticket_by_channel(self, channel_id: int) -> dict[str, Any] | None:
        row = await self.pool.fetchrow(
            "SELECT * FROM tickets WHERE channel_id = $1",
            channel_id,
        )
        return dict(row) if row else None

    async def create_ticket(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        step: str,
    ) -> int | None:
        try:
            row = await self.pool.fetchrow(
                """
                INSERT INTO tickets (guild_id, channel_id, user_id, step)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                guild_id, channel_id, user_id, step,
            )
            return row["id"] if row else None
        except asyncpg.UniqueViolationError:
            return None

    async def update_ticket_step(
        self,
        ticket_id: int,
        step: str,
        data: dict[str, Any],
    ) -> None:
        # Como o codec JSONB tá configurado no pool, dá pra passar o dict direto.
        await self.pool.execute(
            """
            UPDATE tickets
            SET step = $1, data = $2, updated_at = NOW()
            WHERE id = $3
            """,
            step, data, ticket_id,
        )

    async def close_ticket(self, ticket_id: int, status: str) -> None:
        await self.pool.execute(
            """
            UPDATE tickets
            SET status = $1, updated_at = NOW()
            WHERE id = $2
            """,
            status, ticket_id,
        )

    async def list_stale_tickets(self, max_age_seconds: int) -> list[dict[str, Any]]:
        rows = await self.pool.fetch(
            """
            SELECT * FROM tickets
            WHERE status = 'open'
              AND updated_at < NOW() - ($1 || ' seconds')::interval
            """,
            str(max_age_seconds),
        )
        return [dict(r) for r in rows]
