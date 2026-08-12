# 重启后端服务

如果你遇到 bcrypt 密码长度错误，请按以下步骤操作：

## 1. 停止当前运行的后端服务

在运行后端的终端按 `Ctrl+C` 停止服务。

## 2. 重新启动后端

```bash
cd novelcraft
uvicorn backend.main:app --reload
```

## 3. 验证修复

修复后的代码会：
- 自动将超过 72 字节的密码截断到 72 字节
- 在注册和登录时都会处理
- 不会再抛出 `ValueError` 错误

## 4. 如果仍然有问题

检查是否是旧的密码哈希导致的问题：

```bash
# 删除数据库重新迁移
rm novelcraft/data/novelcraft.db
PYTHONPATH=. python backend/migrations/migrate_add_users.py

# 重启后端
uvicorn backend.main:app --reload
```

## 5. 测试

访问前端注册页面，使用正常长度的密码（8-72 字符）进行注册和登录。

**注意**: 
- 前端已经限制了密码输入最多 72 字符（通过 `maxLength={72}`）
- 后端会自动处理任何超长密码
- 建议用户使用英文字母、数字和常见符号作为密码字符
