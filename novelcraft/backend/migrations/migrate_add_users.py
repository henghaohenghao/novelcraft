"""
数据库迁移脚本 - 添加用户表和 user_id 外键

运行方式：
1. cd novelcraft
2. PYTHONPATH=. python backend/migrations/migrate_add_users.py
"""
import os
import sys
from pathlib import Path

# 添加 novelcraft 目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text, inspect
from backend.config import get_settings

settings = get_settings()


def migrate():
    """执行数据库迁移"""
    print("开始数据库迁移...")
    print(f"数据库类型: {settings.db_driver}")

    # 创建同步引擎
    engine = create_engine(settings.database_url_sync)

    with engine.connect() as conn:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        # 1. 创建 users 表
        if "users" not in existing_tables:
            print("创建 users 表...")
            conn.execute(text("""
                CREATE TABLE users (
                    id VARCHAR(36) PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    hashed_password VARCHAR(255) NOT NULL,
                    full_name VARCHAR(100),
                    avatar_url VARCHAR(500),
                    is_active BOOLEAN DEFAULT TRUE,
                    is_superuser BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("CREATE INDEX idx_users_email ON users(email)"))
            conn.execute(text("CREATE INDEX idx_users_username ON users(username)"))
            print("[OK] users 表创建成功")
        else:
            print("[OK] users 表已存在，跳过创建")

        # 2. 检查 projects 表是否有 user_id 列
        if "projects" in existing_tables:
            columns = [col["name"] for col in inspector.get_columns("projects")]

            if "user_id" not in columns:
                print("为 projects 表添加 user_id 列...")

                # 创建默认用户（用于现有项目）
                conn.execute(text("""
                    INSERT INTO users (id, username, email, hashed_password, full_name, is_active)
                    SELECT 'default-user-00000000000000000000', 'default_user', 'default@novelcraft.local',
                           '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5kosgTRqyHGvW', '默认用户', TRUE
                    WHERE NOT EXISTS (SELECT 1 FROM users WHERE id = 'default-user-00000000000000000000')
                """))

                # 添加 user_id 列（允许 NULL）
                conn.execute(text("ALTER TABLE projects ADD COLUMN user_id VARCHAR(36)"))

                # 将现有项目关联到默认用户
                conn.execute(text("""
                    UPDATE projects
                    SET user_id = 'default-user-00000000000000000000'
                    WHERE user_id IS NULL
                """))

                # 设置 NOT NULL 约束
                if settings.db_driver == "postgresql":
                    conn.execute(text("ALTER TABLE projects ALTER COLUMN user_id SET NOT NULL"))
                    conn.execute(text("""
                        ALTER TABLE projects
                        ADD CONSTRAINT fk_projects_user_id
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    """))
                else:
                    # SQLite 不支持 ALTER COLUMN，需要重建表
                    print("  SQLite 检测到，将重建 projects 表以添加约束...")
                    conn.execute(text("ALTER TABLE projects RENAME TO projects_old"))

                    conn.execute(text("""
                        CREATE TABLE projects (
                            id VARCHAR(36) PRIMARY KEY,
                            user_id VARCHAR(36) NOT NULL,
                            title VARCHAR(255) NOT NULL,
                            synopsis TEXT DEFAULT '',
                            genre VARCHAR(100) DEFAULT '',
                            style VARCHAR(100) DEFAULT '',
                            status VARCHAR(20) DEFAULT 'draft',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES users(id)
                        )
                    """))

                    conn.execute(text("""
                        INSERT INTO projects (id, user_id, title, synopsis, genre, style, status, created_at, updated_at)
                        SELECT id, user_id, title, synopsis, genre, style, status, created_at, updated_at
                        FROM projects_old
                    """))

                    conn.execute(text("DROP TABLE projects_old"))

                print("[OK] user_id 列添加成功")
            else:
                print("[OK] projects 表已有 user_id 列，跳过添加")

        conn.commit()

    print("\n数据库迁移完成！")
    print("\n默认用户信息：")
    print("  用户名: default_user")
    print("  邮箱: default@novelcraft.local")
    print("  密码: password123")
    print("\n请创建新用户或使用默认用户登录。")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"\n[ERROR] 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
