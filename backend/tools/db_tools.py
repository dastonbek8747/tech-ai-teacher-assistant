
import os
import re
import json
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import make_url
from langchain_core.tools import tool

# ============================================================
# 1. SOZLAMALAR
# ============================================================

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
POSTGRES_ADMIN_URL = os.getenv("POSTGRES_ADMIN_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL .env faylida ko'rsatilmagan.")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

EXPORT_DIR = (
    Path(__file__).resolve().parents[2]
    / "generated"
    / "database_exports"
)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")

ALLOWED_COLUMN_TYPES = {
    "SMALLINT", "INTEGER", "BIGINT",
    "BOOLEAN", "TEXT", "DATE",
    "TIMESTAMP", "TIMESTAMPTZ",
    "NUMERIC", "REAL", "DOUBLE PRECISION",
    "VARCHAR(50)", "VARCHAR(100)", "VARCHAR(255)",
}


# ============================================================
# 2. YORDAMCHI FUNKSIYALAR
# ============================================================

def valid_identifier(name: str) -> str:
    """Jadval, ustun va schema nomini tekshiradi."""
    if not isinstance(name, str) or not IDENTIFIER.fullmatch(name):
        raise ValueError(f"Noto'g'ri SQL nomi: {name!r}")
    return f'"{name}"'


def qualified_table(
    table_name: str,
    schema_name: str = "public",
) -> str:
    """Schema va jadval nomini birlashtiradi."""
    return (
        f"{valid_identifier(schema_name)}."
        f"{valid_identifier(table_name)}"
    )


def parse_json(value, expected_type):
    """JSON ma'lumotni tekshiradi."""
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON formati noto'g'ri: {exc}") from exc

    if not isinstance(parsed, expected_type):
        raise ValueError(
            f"JSON qiymati {expected_type.__name__} bo'lishi kerak."
        )

    return parsed


def get_table_columns(
    table_name: str,
    schema_name: str = "public",
) -> set:
    """Jadval ustunlarini qaytaradi."""
    valid_identifier(table_name)
    valid_identifier(schema_name)

    inspector = inspect(engine)

    if not inspector.has_table(table_name, schema=schema_name):
        raise ValueError(
            f"{schema_name}.{table_name} jadvali topilmadi."
        )

    return {
        column["name"]
        for column in inspector.get_columns(
            table_name,
            schema=schema_name,
        )
    }


def check_table_exists(
    table_name: str,
    schema_name: str = "public",
):
    """Jadval mavjudligini tekshiradi."""
    get_table_columns(table_name, schema_name)


def json_error(exc):
    """Xatoni JSON shaklida qaytaradi."""
    return json.dumps(
        {"success": False, "error": str(exc)},
        ensure_ascii=False,
    )


# ============================================================
# 3. DATABASE CONNECTION
# ============================================================

# 1
@tool
def check_database_connection() -> str:
    """PostgreSQL bazasiga ulanishni tekshiradi."""
    try:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT current_database(), current_user, version()
            """)).fetchone()

        return json.dumps({
            "success": True,
            "database": row[0],
            "user": row[1],
            "version": row[2],
        }, ensure_ascii=False)

    except Exception as exc:
        return json_error(exc)


# 2
@tool
def get_database_info() -> str:
    """Joriy baza, foydalanuvchi, schema va PostgreSQL versiyasini beradi."""
    try:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT current_database(),
                       current_user,
                       current_schema(),
                       current_setting('server_version')
            """)).fetchone()

        return json.dumps({
            "database": row[0],
            "user": row[1],
            "schema": row[2],
            "postgres_version": row[3],
        }, ensure_ascii=False)

    except Exception as exc:
        return json_error(exc)


# 3
@tool
def list_database_tables(schema_name: str = "public") -> str:
    """Berilgan schema ichidagi jadvallarni ro'yxatlaydi."""
    try:
        valid_identifier(schema_name)

        tables = inspect(engine).get_table_names(
            schema=schema_name
        )

        return json.dumps({
            "schema": schema_name,
            "tables": tables,
        }, ensure_ascii=False)

    except Exception as exc:
        return json_error(exc)


# 4
@tool
def get_table_schema(
    table_name: str,
    schema_name: str = "public",
) -> str:
    """Jadval ustunlari, turlari, primary key va unique cheklovlarini beradi."""
    try:
        valid_identifier(table_name)
        valid_identifier(schema_name)

        inspector = inspect(engine)

        if not inspector.has_table(table_name, schema=schema_name):
            return f"{schema_name}.{table_name} jadvali topilmadi."

        columns = inspector.get_columns(
            table_name, schema=schema_name
        )
        primary = inspector.get_pk_constraint(
            table_name, schema=schema_name
        )
        unique = inspector.get_unique_constraints(
            table_name, schema=schema_name
        )

        return json.dumps({
            "table": table_name,
            "schema": schema_name,
            "columns": [
                {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col["nullable"],
                    "default": str(col.get("default")),
                }
                for col in columns
            ],
            "primary_key": primary.get("constrained_columns", []),
            "unique_constraints": [
                item.get("column_names", [])
                for item in unique
            ],
        }, ensure_ascii=False)

    except Exception as exc:
        return json_error(exc)


# 5
@tool
def get_table_sample(
    table_name: str,
    limit: int = 10,
    schema_name: str = "public",
) -> str:
    """Jadvaldan 1–100 oralig'ida namunaviy yozuvlarni oladi."""
    try:
        table = qualified_table(table_name, schema_name)
        limit = max(1, min(int(limit), 100))

        with engine.connect() as conn:
            rows = conn.execute(
                text(f"SELECT * FROM {table} LIMIT :lim"),
                {"lim": limit},
            ).mappings().all()

        return json.dumps(
            [dict(row) for row in rows],
            ensure_ascii=False,
            default=str,
        )

    except Exception as exc:
        return json_error(exc)


# 6
@tool
def count_table_rows(
    table_name: str,
    schema_name: str = "public",
) -> str:
    """Jadvaldagi yozuvlar sonini hisoblaydi."""
    try:
        table = qualified_table(table_name, schema_name)

        with engine.connect() as conn:
            count = conn.execute(
                text(f"SELECT COUNT(*) FROM {table}")
            ).scalar_one()

        return json.dumps({
            "table": table_name,
            "count": count,
        }, ensure_ascii=False)

    except Exception as exc:
        return json_error(exc)


# ============================================================
# 4. TABLE CREATION AND MODIFICATION
# ============================================================

# 7
@tool
def create_database_table(
    table_name: str,
    columns_json: str,
    schema_name: str = "public",
) -> str:
    """Jadval yaratadi. columns_json ichida name, type, primary_key, nullable, unique bo'ladi."""
    try:
        table = qualified_table(table_name, schema_name)
        columns = parse_json(columns_json, list)

        if not columns:
            return "Kamida bitta ustun kerak."

        definitions = []
        seen = set()
        primary_count = 0

        for col in columns:
            if not isinstance(col, dict):
                return "Har bir ustun JSON obyekt bo'lishi kerak."

            name = col.get("name")
            col_type = " ".join(
                str(col.get("type", "")).upper().split()
            )

            qname = valid_identifier(name)

            if name in seen:
                return f"Takroriy ustun: {name}"

            seen.add(name)

            if col_type not in ALLOWED_COLUMN_TYPES:
                return f"Ruxsat berilmagan tur: {col_type}"

            parts = [qname, col_type]

            if col.get("primary_key"):
                primary_count += 1

                if col_type not in {"SMALLINT", "INTEGER", "BIGINT"}:
                    return "Primary key uchun INTEGER yoki BIGINT ishlating."

                parts.append(
                    "GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY"
                )
            elif col.get("nullable") is False:
                parts.append("NOT NULL")

            if col.get("unique"):
                parts.append("UNIQUE")

            definitions.append(" ".join(parts))

        if primary_count > 1:
            return "Faqat bitta primary key ustuni qo'llab-quvvatlanadi."

        with engine.begin() as conn:
            conn.execute(text(
                f"CREATE TABLE {table} ({', '.join(definitions)})"
            ))

        return json.dumps({
            "success": True,
            "message": f"{schema_name}.{table_name} yaratildi.",
        }, ensure_ascii=False)

    except Exception as exc:
        return json_error(exc)


# 8
@tool
def add_table_column(
    table_name: str,
    column_name: str,
    column_type: str,
    nullable: bool = True,
    schema_name: str = "public",
) -> str:
    """Mavjud jadvalga yangi ustun qo'shadi."""
    try:
        table = qualified_table(table_name, schema_name)
        col = valid_identifier(column_name)
        column_type = " ".join(column_type.upper().split())

        if column_type not in ALLOWED_COLUMN_TYPES:
            return "Ruxsat berilmagan ustun turi."

        columns = get_table_columns(table_name, schema_name)

        if column_name in columns:
            return "Ustun allaqachon mavjud."

        null_sql = "" if nullable else " NOT NULL"

        with engine.begin() as conn:
            conn.execute(text(
                f"ALTER TABLE {table} ADD COLUMN "
                f"{col} {column_type}{null_sql}"
            ))

        return f"{column_name} ustuni qo'shildi."

    except Exception as exc:
        return json_error(exc)


# ============================================================
# 5. INSERT AND SEARCH
# ============================================================

# 9
@tool
def insert_database_record(
    table_name: str,
    record_json: str,
    schema_name: str = "public",
) -> str:
    """Bitta yozuv kiritadi. record_json — JSON obyekt."""
    try:
        table = qualified_table(table_name, schema_name)
        record = parse_json(record_json, dict)

        if not record:
            return "Kiritiladigan ma'lumot bo'sh."

        columns = get_table_columns(table_name, schema_name)
        unknown = set(record) - columns

        if unknown:
            return f"Noma'lum ustunlar: {sorted(unknown)}"

        names = list(record)
        col_sql = ", ".join(valid_identifier(n) for n in names)
        placeholders = ", ".join(
            f":v{i}" for i in range(len(names))
        )
        params = {
            f"v{i}": record[name]
            for i, name in enumerate(names)
        }

        with engine.begin() as conn:
            result = conn.execute(
                text(
                    f"INSERT INTO {table} ({col_sql}) "
                    f"VALUES ({placeholders})"
                ),
                params,
            )

        return json.dumps({
            "success": True,
            "inserted_rows": result.rowcount,
        })

    except Exception as exc:
        return json_error(exc)


# 10
@tool
def bulk_insert_records(
    table_name: str,
    records_json: str,
    schema_name: str = "public",
) -> str:
    """1000 tagacha yozuvni ommaviy kiritadi."""
    try:
        table = qualified_table(table_name, schema_name)
        records = parse_json(records_json, list)

        if not records:
            return "Yozuvlar ro'yxati bo'sh."

        if len(records) > 1000:
            return "Bir chaqiruvda ko'pi bilan 1000 yozuv kiritiladi."

        if not all(isinstance(row, dict) for row in records):
            return "Har bir yozuv JSON obyekt bo'lishi kerak."

        names = list(records[0])

        if not names or any(list(row) != names for row in records):
            return "Barcha yozuvlarda bir xil ustunlar tartibi kerak."

        columns = get_table_columns(table_name, schema_name)
        unknown = set(names) - columns

        if unknown:
            return f"Noma'lum ustunlar: {sorted(unknown)}"

        col_sql = ", ".join(valid_identifier(n) for n in names)
        values_sql = ", ".join(
            f":v{i}" for i in range(len(names))
        )

        params = [
            {
                f"v{i}": row[name]
                for i, name in enumerate(names)
            }
            for row in records
        ]

        with engine.begin() as conn:
            conn.execute(
                text(
                    f"INSERT INTO {table} ({col_sql}) "
                    f"VALUES ({values_sql})"
                ),
                params,
            )

        return json.dumps({
            "success": True,
            "inserted_rows": len(records),
        })

    except Exception as exc:
        return json_error(exc)


# 11
@tool
def search_database_records(
    table_name: str,
    filters_json: str = "{}",
    limit: int = 50,
    schema_name: str = "public",
) -> str:
    """Ustun qiymati bo'yicha qidiradi. Masalan: {\"name\":\"Ali\"}."""
    try:
        table = qualified_table(table_name, schema_name)
        filters = parse_json(filters_json, dict)
        columns = get_table_columns(table_name, schema_name)

        unknown = set(filters) - columns
        if unknown:
            return f"Noma'lum ustunlar: {sorted(unknown)}"

        limit = max(1, min(int(limit), 500))
        where = []
        params = {"lim": limit}

        for i, (name, value) in enumerate(filters.items()):
            where.append(
                f"{valid_identifier(name)} IS NOT DISTINCT FROM :p{i}"
            )
            params[f"p{i}"] = value

        where_sql = (
            " WHERE " + " AND ".join(where)
            if where else ""
        )

        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT * FROM {table}{where_sql} LIMIT :lim"
                ),
                params,
            ).mappings().all()

        return json.dumps(
            [dict(row) for row in rows],
            ensure_ascii=False,
            default=str,
        )

    except Exception as exc:
        return json_error(exc)


# ============================================================
# 6. UPDATE AND DELETE
# ============================================================

# 12
@tool
def update_database_record(
    table_name: str,
    values_json: str,
    filters_json: str,
    schema_name: str = "public",
) -> str:
    """Filtrga mos yozuvlarni yangilaydi. Bo'sh filtrga ruxsat yo'q."""
    try:
        table = qualified_table(table_name, schema_name)
        values = parse_json(values_json, dict)
        filters = parse_json(filters_json, dict)

        if not values or not filters:
            return "Yangilash uchun values va filters bo'sh bo'lmasligi kerak."

        columns = get_table_columns(table_name, schema_name)
        unknown = (set(values) | set(filters)) - columns

        if unknown:
            return f"Noma'lum ustunlar: {sorted(unknown)}"

        params = {}
        set_parts = []
        where_parts = []

        for i, (name, value) in enumerate(values.items()):
            set_parts.append(
                f"{valid_identifier(name)} = :s{i}"
            )
            params[f"s{i}"] = value

        for i, (name, value) in enumerate(filters.items()):
            where_parts.append(
                f"{valid_identifier(name)} IS NOT DISTINCT FROM :w{i}"
            )
            params[f"w{i}"] = value

        sql = (
            f"UPDATE {table} SET {', '.join(set_parts)} "
            f"WHERE {' AND '.join(where_parts)}"
        )

        with engine.begin() as conn:
            result = conn.execute(text(sql), params)

        return json.dumps({
            "success": True,
            "updated_rows": result.rowcount,
        })

    except Exception as exc:
        return json_error(exc)


# 13
@tool
def delete_database_record(
    table_name: str,
    filters_json: str,
    schema_name: str = "public",
) -> str:
    """Filtrga mos yozuvlarni o'chiradi. Bo'sh filtr taqiqlanadi."""
    try:
        table = qualified_table(table_name, schema_name)
        filters = parse_json(filters_json, dict)

        if not filters:
            return "O'chirish uchun kamida bitta filtr kerak."

        columns = get_table_columns(table_name, schema_name)
        unknown = set(filters) - columns

        if unknown:
            return f"Noma'lum ustunlar: {sorted(unknown)}"

        parts = []
        params = {}

        for i, (name, value) in enumerate(filters.items()):
            parts.append(
                f"{valid_identifier(name)} IS NOT DISTINCT FROM :p{i}"
            )
            params[f"p{i}"] = value

        with engine.begin() as conn:
            result = conn.execute(
                text(
                    f"DELETE FROM {table} "
                    f"WHERE {' AND '.join(parts)}"
                ),
                params,
            )

        return json.dumps({
            "success": True,
            "deleted_rows": result.rowcount,
        })

    except Exception as exc:
        return json_error(exc)


# ============================================================
# 7. READ-ONLY SQL AND ANALYTICS
# ============================================================

# 14
@tool
def run_readonly_sql(sql_query: str) -> str:
    """Bitta SELECT yoki WITH so'rovini read-only tranzaksiyada bajaradi."""
    try:
        sql = sql_query.strip().rstrip(";").strip()

        if not re.match(r"^(SELECT|WITH)\b", sql, re.IGNORECASE):
            return "Faqat SELECT yoki WITH so'roviga ruxsat beriladi."

        if ";" in sql:
            return "Faqat bitta SQL so'rovi yuboring."

        if re.search(
            r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|"
            r"GRANT|REVOKE|COPY|CALL|DO|EXECUTE|VACUUM|"
            r"REFRESH|SET|RESET|INTO)\b",
            sql,
            re.IGNORECASE,
        ):
            return "So'rovda ruxsat etilmagan SQL buyrug'i mavjud."

        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            result = conn.execute(text(sql))
            rows = result.mappings().fetchmany(200)

        return json.dumps(
            [dict(row) for row in rows],
            ensure_ascii=False,
            default=str,
        )

    except Exception as exc:
        return json_error(exc)


# 15
@tool
def analyze_numeric_column(
    table_name: str,
    column_name: str,
    schema_name: str = "public",
) -> str:
    """Sonli ustun uchun count, min, max, average va sum hisoblaydi."""
    try:
        table = qualified_table(table_name, schema_name)
        col = valid_identifier(column_name)

        columns = get_table_columns(table_name, schema_name)
        if column_name not in columns:
            return f"{column_name} ustuni topilmadi."

        column_info = next(
            c for c in inspect(engine).get_columns(
                table_name, schema=schema_name
            )
            if c["name"] == column_name
        )

        numeric_types = (
            "INT", "NUMERIC", "DECIMAL", "REAL",
            "DOUBLE", "FLOAT", "SMALLINT", "BIGINT",
        )

        if not any(
            t in str(column_info["type"]).upper()
            for t in numeric_types
        ):
            return "Tanlangan ustun sonli turda emas."

        with engine.connect() as conn:
            row = conn.execute(text(f"""
                SELECT COUNT({col}),
                       MIN({col}),
                       MAX({col}),
                       AVG({col}::numeric),
                       SUM({col}::numeric)
                FROM {table}
            """)).fetchone()

        return json.dumps({
            "count_non_null": row[0],
            "min": row[1],
            "max": row[2],
            "average": row[3],
            "sum": row[4],
        }, ensure_ascii=False, default=str)

    except Exception as exc:
        return json_error(exc)


# 16
@tool
def export_query_to_file(
    sql_query: str,
    file_format: str = "csv",
) -> str:
    """SELECT natijasini CSV yoki XLSX faylga eksport qiladi."""
    try:
        sql = sql_query.strip().rstrip(";").strip()

        if not re.match(r"^SELECT\b", sql, re.IGNORECASE):
            return "Eksport uchun SELECT so'rovi kerak."

        if ";" in sql:
            return "Faqat bitta SELECT so'roviga ruxsat beriladi."

        if re.search(
            r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|"
            r"GRANT|REVOKE|COPY|INTO)\b",
            sql,
            re.IGNORECASE,
        ):
            return "Eksport so'rovida o'zgartiruvchi buyruq bo'lmasligi kerak."

        fmt = file_format.lower().strip()

        if fmt not in {"csv", "xlsx"}:
            return "Format csv yoki xlsx bo'lishi kerak."

        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            df = pd.read_sql_query(text(sql), conn)

        path = EXPORT_DIR / f"query_export.{fmt}"

        if fmt == "csv":
            df.to_csv(path, index=False, encoding="utf-8-sig")
        else:
            df.to_excel(path, index=False, engine="openpyxl")

        return json.dumps({
            "success": True,
            "rows": len(df),
            "format": fmt,
            "file_path": str(path.resolve()),
        }, ensure_ascii=False)

    except Exception as exc:
        return json_error(exc)


# ============================================================
# 8. DATABASE ADMINISTRATION
# ============================================================

# 17
@tool
def create_database(database_name: str) -> str:
    """PostgreSQL serverida yangi baza yaratadi. POSTGRES_ADMIN_URL kerak."""
    try:
        valid_identifier(database_name)

        if not POSTGRES_ADMIN_URL:
            return "POSTGRES_ADMIN_URL sozlanmagan."

        admin_engine = create_engine(
            POSTGRES_ADMIN_URL,
            isolation_level="AUTOCOMMIT",
        )

        try:
            with admin_engine.connect() as conn:
                exists = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :name"),
                    {"name": database_name},
                ).scalar()

                if exists:
                    return f"{database_name} bazasi allaqachon mavjud."

                conn.execute(text(
                    f"CREATE DATABASE {valid_identifier(database_name)}"
                ))

            return f"{database_name} bazasi yaratildi."

        finally:
            admin_engine.dispose()

    except Exception as exc:
        return json_error(exc)


# 18
@tool
def drop_database_table(
    table_name: str,
    confirm_table_name: str,
    schema_name: str = "public",
) -> str:
    """Jadvalni o'chiradi; jadval nomini aynan tasdiqlash kerak."""
    try:
        if confirm_table_name != table_name:
            return "Rad etildi: jadval nomini aynan tasdiqlang."

        table = qualified_table(table_name, schema_name)
        check_table_exists(table_name, schema_name)

        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE {table} RESTRICT"))

        return f"{schema_name}.{table_name} jadvali o'chirildi."

    except Exception as exc:
        return json_error(exc)


# 19
@tool
def drop_database(
    database_name: str,
    confirm_database_name: str,
) -> str:
    """PostgreSQL bazasini o'chiradi; admin ulanishi va tasdiq kerak."""
    try:
        valid_identifier(database_name)

        if confirm_database_name != database_name:
            return "Rad etildi: baza nomini aynan tasdiqlang."

        if not POSTGRES_ADMIN_URL:
            return "POSTGRES_ADMIN_URL sozlanmagan."

        admin_url = make_url(POSTGRES_ADMIN_URL)

        if admin_url.database == database_name:
            return "Admin ulanishi ishlatayotgan bazani o'chirish taqiqlangan."

        admin_engine = create_engine(
            POSTGRES_ADMIN_URL,
            isolation_level="AUTOCOMMIT",
        )

        try:
            with admin_engine.connect() as conn:
                exists = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :name"),
                    {"name": database_name},
                ).scalar()

                if not exists:
                    return f"{database_name} bazasi topilmadi."

                conn.execute(text(
                    f"DROP DATABASE {valid_identifier(database_name)}"
                ))

            return f"{database_name} bazasi o'chirildi."

        finally:
            admin_engine.dispose()

    except Exception as exc:
        return json_error(exc)


# ============================================================
# 9. TABLE MANAGEMENT
# ============================================================

# 20
@tool
def rename_database_table(
    old_table_name: str,
    new_table_name: str,
    schema_name: str = "public",
) -> str:
    """Jadval nomini o'zgartiradi."""
    try:
        old_table = qualified_table(old_table_name, schema_name)
        new_name = valid_identifier(new_table_name)

        check_table_exists(old_table_name, schema_name)

        if inspect(engine).has_table(
            new_table_name, schema=schema_name
        ):
            return f"{new_table_name} jadvali allaqachon mavjud."

        with engine.begin() as conn:
            conn.execute(text(
                f"ALTER TABLE {old_table} RENAME TO {new_name}"
            ))

        return json.dumps({
            "success": True,
            "old_name": old_table_name,
            "new_name": new_table_name,
        }, ensure_ascii=False)

    except Exception as exc:
        return json_error(exc)


# 21
@tool
def rename_table_column(
    table_name: str,
    old_column_name: str,
    new_column_name: str,
    schema_name: str = "public",
) -> str:
    """Jadval ustunining nomini o'zgartiradi."""
    try:
        table = qualified_table(table_name, schema_name)
        old_col = valid_identifier(old_column_name)
        new_col = valid_identifier(new_column_name)

        columns = get_table_columns(table_name, schema_name)

        if old_column_name not in columns:
            return f"{old_column_name} ustuni topilmadi."

        if new_column_name in columns:
            return f"{new_column_name} ustuni allaqachon mavjud."

        with engine.begin() as conn:
            conn.execute(text(
                f"ALTER TABLE {table} "
                f"RENAME COLUMN {old_col} TO {new_col}"
            ))

        return f"{old_column_name} ustuni {new_column_name} deb o'zgartirildi."

    except Exception as exc:
        return json_error(exc)


# 22
@tool
def alter_table_column_type(
    table_name: str,
    column_name: str,
    new_column_type: str,
    schema_name: str = "public",
) -> str:
    """Ustun turini ruxsat etilgan PostgreSQL turiga o'zgartiradi."""
    try:
        table = qualified_table(table_name, schema_name)
        col = valid_identifier(column_name)
        col_type = " ".join(new_column_type.upper().split())

        if col_type not in ALLOWED_COLUMN_TYPES:
            return f"Ruxsat etilmagan ustun turi: {col_type}"

        if column_name not in get_table_columns(table_name, schema_name):
            return f"{column_name} ustuni topilmadi."

        with engine.begin() as conn:
            conn.execute(text(
                f"ALTER TABLE {table} "
                f"ALTER COLUMN {col} TYPE {col_type} "
                f"USING {col}::{col_type}"
            ))

        return json.dumps({
            "success": True,
            "table": table_name,
            "column": column_name,
            "new_type": col_type,
        }, ensure_ascii=False)

    except Exception as exc:
        return json_error(exc)


# 23
@tool
def drop_table_column(
    table_name: str,
    column_name: str,
    confirm_column_name: str,
    schema_name: str = "public",
) -> str:
    """Ustunni o'chiradi; ustun nomini aynan tasdiqlash kerak."""
    try:
        if confirm_column_name != column_name:
            return "Rad etildi: ustun nomini aynan tasdiqlang."

        table = qualified_table(table_name, schema_name)
        col = valid_identifier(column_name)
        columns = get_table_columns(table_name, schema_name)

        if column_name not in columns:
            return f"{column_name} ustuni topilmadi."

        if len(columns) <= 1:
            return "Oxirgi ustunni o'chirish mumkin emas."

        with engine.begin() as conn:
            conn.execute(text(
                f"ALTER TABLE {table} DROP COLUMN {col} RESTRICT"
            ))

        return f"{column_name} ustuni o'chirildi."

    except Exception as exc:
        return json_error(exc)


# 24
@tool
def truncate_database_table(
    table_name: str,
    confirm_table_name: str,
    schema_name: str = "public",
) -> str:
    """Jadvaldagi barcha yozuvlarni o'chiradi, jadvalni saqlaydi."""
    try:
        if confirm_table_name != table_name:
            return "Rad etildi: jadval nomini aynan tasdiqlang."

        table = qualified_table(table_name, schema_name)
        check_table_exists(table_name, schema_name)

        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {table} RESTRICT"))

        return json.dumps({
            "success": True,
            "message": f"{schema_name}.{table_name} jadvali bo'shatildi.",
        }, ensure_ascii=False)

    except Exception as exc:
        return json_error(exc)


# 25
@tool
def get_table_indexes(
    table_name: str,
    schema_name: str = "public",
) -> str:
    """Jadval indekslarini ko'rsatadi."""
    try:
        check_table_exists(table_name, schema_name)

        indexes = inspect(engine).get_indexes(
            table_name, schema=schema_name
        )

        return json.dumps({
            "table": table_name,
            "schema": schema_name,
            "indexes": indexes,
        }, ensure_ascii=False, default=str)

    except Exception as exc:
        return json_error(exc)


# 26
@tool
def get_table_foreign_keys(
    table_name: str,
    schema_name: str = "public",
) -> str:
    """Jadval foreign key bog'lanishlarini ko'rsatadi."""
    try:
        check_table_exists(table_name, schema_name)

        foreign_keys = inspect(engine).get_foreign_keys(
            table_name, schema=schema_name
        )

        return json.dumps({
            "table": table_name,
            "schema": schema_name,
            "foreign_keys": foreign_keys,
        }, ensure_ascii=False, default=str)

    except Exception as exc:
        return json_error(exc)


# 27
@tool
def get_table_statistics(
    table_name: str,
    schema_name: str = "public",
) -> str:
    """Jadval qatorlari, ustunlari va turlarini qaytaradi."""
    try:
        table = qualified_table(table_name, schema_name)
        check_table_exists(table_name, schema_name)

        columns = inspect(engine).get_columns(
            table_name, schema=schema_name
        )

        with engine.connect() as conn:
            row_count = conn.execute(
                text(f"SELECT COUNT(*) FROM {table}")
            ).scalar_one()

        return json.dumps({
            "table": table_name,
            "schema": schema_name,
            "row_count": row_count,
            "column_count": len(columns),
            "columns": [
                {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col["nullable"],
                }
                for col in columns
            ],
        }, ensure_ascii=False, default=str)

    except Exception as exc:
        return json_error(exc)


# ============================================================
# 10. BARCHA 27 TA TOOL
# ============================================================

DATABASE_TOOLS = [
    check_database_connection,  # 1
    get_database_info,         # 2
    list_database_tables,      # 3
    get_table_schema,          # 4
    get_table_sample,          # 5
    count_table_rows,          # 6
    create_database_table,     # 7
    add_table_column,          # 8
    insert_database_record,    # 9
    bulk_insert_records,       # 10
    search_database_records,   # 11
    update_database_record,    # 12
    delete_database_record,    # 13
    run_readonly_sql,          # 14
    analyze_numeric_column,    # 15
    export_query_to_file,      # 16
    create_database,           # 17
    drop_database_table,       # 18
    drop_database,             # 19
    rename_database_table,     # 20
    rename_table_column,       # 21
    alter_table_column_type,   # 22
    drop_table_column,         # 23
    truncate_database_table,  # 24
    get_table_indexes,         # 25
    get_table_foreign_keys,    # 26
    get_table_statistics,      # 27
]
